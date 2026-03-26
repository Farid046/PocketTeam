"""
Observer Agent — meta-learning from team performance.

Runs after task completion to:
1. Analyze agent outputs from the event stream
2. Detect recurring error patterns
3. Update agent prompts with learnings
4. Track team-wide insights

Two modes:
1. SDK mode (via execute()): full analysis with Claude
2. Programmatic mode (via analyze_task()): pattern detection without LLM
"""

from __future__ import annotations

import json
import time

import yaml

from ..constants import EVENTS_FILE, LEARNINGS_DIR
from .base import AgentContext, AgentResult, BaseAgent


class ObserverAgent(BaseAgent):
    def _get_agent_id(self) -> str:
        return "observer"

    async def _run(self, task: str, context: AgentContext | None) -> AgentResult:
        result = await self._run_with_sdk(task)
        if result.success and result.output:
            result.artifacts["observations"] = result.output
        return result

    async def analyze_task(self, task_id: str | None = None) -> AgentResult:
        """
        Programmatic post-task analysis — no SDK needed.

        Reads event stream, detects patterns, updates learnings.
        Called by COO after every completed task.
        """
        events = self._read_recent_events(task_id)
        if not events:
            return AgentResult(
                agent_id=self.agent_id,
                success=True,
                output="No events to analyze.",
            )

        # Detect patterns
        patterns = self._detect_patterns(events)

        # Update learnings files
        if patterns:
            self._update_learnings(patterns)

        return AgentResult(
            agent_id=self.agent_id,
            success=True,
            output=f"Analyzed {len(events)} events. Found {len(patterns)} patterns.",
            artifacts={"patterns": patterns},
        )

    def _read_recent_events(self, task_id: str | None = None) -> list[dict]:
        """Read recent events from stream.jsonl."""
        events_path = self.project_root / EVENTS_FILE
        if not events_path.exists():
            return []

        events = []
        try:
            for line in events_path.read_text().splitlines()[-200:]:
                if line.strip():
                    event = json.loads(line)
                    if task_id and event.get("task_id") != task_id:
                        continue
                    events.append(event)
        except Exception:
            pass
        return events

    def _detect_patterns(self, events: list[dict]) -> list[dict]:
        """Detect recurring patterns from events."""
        patterns: list[dict] = []

        # Count errors per agent
        agent_errors: dict[str, int] = {}
        agent_retries: dict[str, int] = {}

        for event in events:
            agent = event.get("agent", "unknown")
            status = event.get("status", "")

            if status == "error":
                agent_errors[agent] = agent_errors.get(agent, 0) + 1

            if "retry" in event.get("action", "").lower():
                agent_retries[agent] = agent_retries.get(agent, 0) + 1

        # Flag agents with 3+ errors
        for agent, count in agent_errors.items():
            if count >= 3:
                patterns.append({
                    "agent": agent,
                    "pattern": f"Agent {agent} had {count} errors in this task",
                    "severity": "warning",
                    "count": count,
                    "timestamp": time.strftime("%Y-%m-%d"),
                })

        # Flag agents with excessive retries
        for agent, count in agent_retries.items():
            if count >= 3:
                patterns.append({
                    "agent": agent,
                    "pattern": f"Agent {agent} needed {count} retries",
                    "severity": "info",
                    "count": count,
                    "timestamp": time.strftime("%Y-%m-%d"),
                })

        return patterns

    def _update_learnings(self, patterns: list[dict]) -> None:
        """Update .pocketteam/learnings/ with new patterns."""
        learnings_dir = self.project_root / LEARNINGS_DIR
        learnings_dir.mkdir(parents=True, exist_ok=True)

        for pattern in patterns:
            agent = pattern["agent"]
            learnings_file = learnings_dir / f"{agent}.yaml"

            # Load existing
            existing: dict = {"patterns": []}
            if learnings_file.exists():
                try:
                    existing = yaml.safe_load(learnings_file.read_text()) or {"patterns": []}
                except Exception:
                    existing = {"patterns": []}

            # Check if pattern already exists
            found = False
            for p in existing["patterns"]:
                if p.get("pattern") == pattern["pattern"]:
                    p["count"] = p.get("count", 0) + pattern["count"]
                    p["last_seen"] = pattern["timestamp"]
                    found = True
                    break

            if not found:
                existing["patterns"].append({
                    "pattern": pattern["pattern"],
                    "count": pattern["count"],
                    "first_seen": pattern["timestamp"],
                    "last_seen": pattern["timestamp"],
                    "severity": pattern["severity"],
                    "added_to_prompt": False,
                })

            # Save
            try:
                learnings_file.write_text(yaml.dump(existing, default_flow_style=False))
            except Exception:
                pass
