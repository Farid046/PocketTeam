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
import re
import time
from collections import deque

import yaml

from ..constants import EVENTS_FILE, LEARNINGS_DIR
from .base import AgentContext, AgentResult, BaseAgent

# Completion action pattern: "Finished (N tool calls, Xs)"
_DURATION_RE = re.compile(r"Finished \(\d+ tool calls,\s*(\d+)s\)")

# Threshold: agents averaging more than this are flagged as slow
_SLOW_AGENT_THRESHOLD_SECONDS = 120

# Valid event schema: agent names and statuses we accept
_VALID_AGENT_RE = re.compile(r"^[a-z0-9_-]+$")
_VALID_STATUSES = {"started", "done", "error", "info", "warning", "denied", "allowed"}


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
            self._emit_finding_event(patterns)

        return AgentResult(
            agent_id=self.agent_id,
            success=True,
            output=f"Analyzed {len(events)} events. Found {len(patterns)} patterns.",
            artifacts={"patterns": patterns},
        )

    def _read_recent_events(self, task_id: str | None = None) -> list[dict]:
        """Read recent events from stream.jsonl.

        Uses a deque(maxlen=200) to avoid loading the entire file into memory
        (OOM prevention for large event streams).
        """
        from ..constants import OBSERVER_MAX_EVENTS_WINDOW

        events_path = self.project_root / EVENTS_FILE
        if not events_path.exists():
            return []

        lines: deque[str] = deque(maxlen=OBSERVER_MAX_EVENTS_WINDOW)
        try:
            with open(events_path, encoding="utf-8") as f:
                for line in f:
                    lines.append(line)
        except OSError:
            return []

        events = []
        for line in lines:
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if task_id and event.get("task_id") != task_id:
                continue
            events.append(event)
        return events

    def _detect_patterns(self, events: list[dict]) -> list[dict]:
        """Detect recurring patterns from events.

        Validates event schema before processing to reject malformed/injected
        entries (security fix C).

        Detects:
        - Error patterns: agents with 3+ errors
        - Retry patterns: agents with 3+ retries
        - Duration patterns: agents averaging >120s completion time
        - Cross-agent patterns: QA consistently finding errors after Engineer
        """
        # ── Schema validation ────────────────────────────────────────────────
        valid_events = [
            e for e in events
            if isinstance(e.get("agent"), str)
            and _VALID_AGENT_RE.match(e["agent"])
            and e.get("status") in _VALID_STATUSES
        ]

        patterns: list[dict] = []
        today = time.strftime("%Y-%m-%d")

        # ── Error / retry counting ────────────────────────────────────────────
        agent_errors: dict[str, int] = {}
        agent_retries: dict[str, int] = {}

        # Duration tracking: agent → list of seconds
        agent_durations: dict[str, list[float]] = {}

        # Cross-agent: track QA-error-after-engineer sequences
        qa_errors_after_engineer: int = 0
        last_complete_agent: str = ""

        for event in valid_events:
            agent = event["agent"]
            status = event.get("status", "")
            action = event.get("action", "")

            if status == "error":
                agent_errors[agent] = agent_errors.get(agent, 0) + 1

            if "retry" in action.lower():
                agent_retries[agent] = agent_retries.get(agent, 0) + 1

            # Duration: parse "Finished (N tool calls, Xs)"
            if status == "done":
                m = _DURATION_RE.search(action)
                if m:
                    seconds = float(m.group(1))
                    agent_durations.setdefault(agent, []).append(seconds)

            if agent == "qa" and status == "error" and last_complete_agent == "engineer":
                qa_errors_after_engineer += 1

            last_complete_agent = agent

        # ── Flag agents with 3+ errors ────────────────────────────────────────
        for agent, count in agent_errors.items():
            if count >= 3:
                patterns.append({
                    "agent": agent,
                    "pattern": f"Agent {agent} had {count} errors in this task",
                    "severity": "warning",
                    "count": count,
                    "timestamp": today,
                })

        # ── Flag agents with excessive retries ────────────────────────────────
        for agent, count in agent_retries.items():
            if count >= 3:
                patterns.append({
                    "agent": agent,
                    "pattern": f"Agent {agent} needed {count} retries",
                    "severity": "info",
                    "count": count,
                    "timestamp": today,
                })

        # ── Flag slow agents (avg duration > threshold) ───────────────────────
        for agent, durations in agent_durations.items():
            if durations:
                avg_s = sum(durations) / len(durations)
                if avg_s > _SLOW_AGENT_THRESHOLD_SECONDS:
                    patterns.append({
                        "agent": agent,
                        "pattern": (
                            f"Agent {agent} is slow: avg {avg_s:.0f}s "
                            f"over {len(durations)} run(s)"
                        ),
                        "severity": "info",
                        "count": len(durations),
                        "timestamp": today,
                    })

        # ── Cross-agent: QA consistently fails after Engineer ─────────────────
        if qa_errors_after_engineer >= 3:
            patterns.append({
                "agent": "qa",
                "pattern": (
                    f"QA found errors after Engineer {qa_errors_after_engineer} times — "
                    "Engineer output quality may need review"
                ),
                "severity": "warning",
                "count": qa_errors_after_engineer,
                "timestamp": today,
            })

        return patterns

    def _update_learnings(self, patterns: list[dict]) -> None:
        """Update .pocketteam/learnings/ with new patterns.

        Security fix A: sanitises agent names to prevent path traversal.
        YAML parse error: creates a backup of corrupt files before resetting.
        """
        learnings_dir = self.project_root / LEARNINGS_DIR
        learnings_dir.mkdir(parents=True, exist_ok=True)

        for pattern in patterns:
            agent = pattern["agent"]

            # ── Security: sanitise agent name ─────────────────────────────────
            safe_agent = re.sub(r"[^a-z0-9_-]", "", agent.lower())
            if not safe_agent:
                safe_agent = "unknown"
            learnings_file = learnings_dir / f"{safe_agent}.yaml"

            # Extra path-traversal check
            if not str(learnings_file.resolve()).startswith(str(learnings_dir.resolve())):
                continue

            # ── Load existing (with YAML backup on corruption) ─────────────────
            existing: dict = {"patterns": []}
            if learnings_file.exists():
                raw = ""
                try:
                    raw = learnings_file.read_text(encoding="utf-8")
                    existing = yaml.safe_load(raw) or {"patterns": []}
                    if not isinstance(existing, dict):
                        raise ValueError("Not a dict")
                    if "patterns" not in existing or not isinstance(existing["patterns"], list):
                        existing["patterns"] = []
                except Exception:
                    # Backup corrupt YAML before resetting
                    if raw:
                        backup = learnings_file.with_suffix(".yaml.bak")
                        try:
                            backup.write_text(raw, encoding="utf-8")
                        except OSError:
                            pass
                    existing = {"patterns": []}

            # ── Update or append pattern ───────────────────────────────────────
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

            # ── Save ───────────────────────────────────────────────────────────
            try:
                learnings_file.write_text(
                    yaml.dump(existing, default_flow_style=False),
                    encoding="utf-8",
                )
            except OSError:
                pass

    def _emit_finding_event(self, patterns: list[dict]) -> None:
        """Write an observer observation event to the event stream."""
        from ..utils import append_jsonl

        events_path = self.project_root / EVENTS_FILE
        summary = "; ".join(p.get("pattern", "")[:40] for p in patterns[:5])
        append_jsonl(
            events_path,
            {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "agent": "observer",
                "type": "observation",
                "tool": "",
                "status": "info",
                "action": f"Found {len(patterns)} pattern(s): {summary}"[:200],
            },
        )
