"""
BaseAgent — wraps the Claude Agent SDK for PocketTeam agents.

Each agent is a thin wrapper around the SDK's ClaudeAgentOptions.
Safety hooks are applied automatically — agents cannot bypass them.
All agents log events to the activity stream for the dashboard.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..constants import AGENT_BUDGETS, AGENT_MAX_TURNS, AGENT_MODELS, EVENTS_FILE
from ..utils import append_jsonl


@dataclass
class AgentResult:
    """Result returned by an agent after completing its task."""
    agent_id: str
    success: bool
    output: str
    artifacts: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    turns_used: int = 0
    spend_usd: float = 0.0
    duration_seconds: float = 0.0


@dataclass
class AgentContext:
    """Shared context passed between agents in a pipeline run."""
    task_id: str
    task_description: str
    project_root: Path
    plan_id: str | None = None
    artifacts: dict[str, Any] = field(default_factory=dict)
    approved_files: list[str] = field(default_factory=list)
    phase: str = "init"
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseAgent(ABC):
    """
    Base class for all PocketTeam agents.
    Provides: SDK integration, event logging, safety hook registration, kill switch check.
    """

    def __init__(
        self,
        project_root: Path,
        context: AgentContext | None = None,
    ) -> None:
        self.project_root = project_root
        self.context = context
        self.agent_id = self._get_agent_id()
        self._model = AGENT_MODELS.get(self.agent_id, "claude-sonnet-4-6")
        self._max_turns = AGENT_MAX_TURNS.get(self.agent_id, 50)
        self._max_budget = AGENT_BUDGETS.get(self.agent_id, 5.0)
        self._start_time: float | None = None

    def _get_agent_id(self) -> str:
        """Return the agent's ID. Override in subclasses (e.g. return 'engineer')."""
        return self.__class__.__name__.lower().replace("agent", "")

    @property
    def prompt_path(self) -> Path:
        """Path to the agent's .md prompt file."""
        return (
            self.project_root / ".claude/agents/pocketteam" / f"{self.agent_id}.md"
        )

    @property
    def system_prompt(self) -> str:
        """Load the agent's system prompt from its .md file."""
        if self.prompt_path.exists():
            return self.prompt_path.read_text()
        # Fallback to bundled prompts
        bundled = Path(__file__).parent / "prompts" / f"{self.agent_id}.md"
        if bundled.exists():
            return bundled.read_text()
        return f"You are the {self.agent_id} agent. Complete your assigned task."

    def _check_kill_switch(self) -> None:
        """Raise KillSwitchError if kill switch is active."""
        from ..safety.kill_switch import KillSwitch, KillSwitchError
        ks = KillSwitch(self.project_root)
        if ks.is_active:
            raise KillSwitchError(f"Kill switch active — {self.agent_id} halted")

    async def execute(self, task: str, context: AgentContext | None = None) -> AgentResult:
        """
        Execute a task. Wraps the actual run with:
        - Kill switch check
        - Event logging (start/end)
        - Error handling
        """
        ctx = context or self.context
        self._start_time = time.time()

        try:
            self._check_kill_switch()
            await self._log_event("awake", task[:100])
            result = await self._run(task, ctx)
            await self._log_event("done", f"Task complete: {task[:50]}")
            return result
        except Exception as e:
            await self._log_event("error", str(e)[:100])
            return AgentResult(
                agent_id=self.agent_id,
                success=False,
                output="",
                error=str(e),
                duration_seconds=time.time() - (self._start_time or time.time()),
            )
        finally:
            await self._log_event("sleeping", None)

    @abstractmethod
    async def _run(self, task: str, context: AgentContext | None) -> AgentResult:
        """Implement agent-specific logic here."""
        ...

    async def spawn_subagent(
        self,
        subagent_class: type[BaseAgent],
        task: str,
        context: AgentContext | None = None,
    ) -> AgentResult:
        """Spawn a sub-agent for specialized work."""
        self._check_kill_switch()
        subagent = subagent_class(self.project_root, context or self.context)
        await self._log_event("delegating", f"→ {subagent.agent_id}: {task[:50]}")
        return await subagent.execute(task, context)

    async def _log_event(self, status: str, action: str | None) -> None:
        """Append event to stream.jsonl for dashboard/monitoring."""
        try:
            events_path = self.project_root / EVENTS_FILE
            events_path.parent.mkdir(parents=True, exist_ok=True)

            event = {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "agent": self.agent_id,
                "status": status,
                "action": action,
            }
            if self.context:
                event["task_id"] = self.context.task_id

            append_jsonl(events_path, event)
        except Exception:
            pass  # Event logging must never crash agent execution

    def _build_sdk_options(self) -> dict:
        """Build options dict for the Claude Agent SDK."""
        return {
            "model": self._model,
            "max_turns": self._max_turns,
            "max_budget_usd": self._max_budget,
            "system_prompt": self.system_prompt,
            "cwd": str(self.project_root),
        }

    async def _run_with_sdk(self, task: str) -> AgentResult:
        """
        HEADLESS/CI FALLBACK: Run a task via the Claude Agent SDK.

        ⚠️  This is NOT the normal flow. Normal usage:
            User → Claude Code → reads .claude/CLAUDE.md → COO spawns agents natively.
            That flow is FREE (runs on Claude Code subscription).

        This method is ONLY for:
        - GitHub Actions self-healing (when health check fails)
        - CI/CD headless pipeline execution
        - Requires ANTHROPIC_API_KEY (costs per token)

        Wires in: model, budget, turn limits, system prompt, per-agent tool
        allowlist (Layer 6), safety guardian via can_use_tool (Layers 1-6, 10).
        """
        from claude_agent_sdk import (  # type: ignore[import]
            AssistantMessage,
            ClaudeAgentOptions,
            PermissionResultAllow,
            PermissionResultDeny,
            ResultMessage,
            TextBlock,
            query,
        )

        from ..constants import AGENT_ALLOWED_TOOLS
        from ..safety.guardian import pre_tool_hook

        raw_allowed = AGENT_ALLOWED_TOOLS.get(self.agent_id, [])
        # Empty list = "delegates only" agent — don't restrict SDK tools list;
        # the can_use_tool callback enforces the allowlist at runtime.
        sdk_allowed_tools: list[str] | None = raw_allowed if raw_allowed else None

        agent_id = self.agent_id  # capture for closure

        async def _can_use_tool(
            tool_name: str,
            tool_input: dict[str, Any],
            ctx: Any,
        ) -> PermissionResultAllow | PermissionResultDeny:
            decision = pre_tool_hook(tool_name, tool_input, agent_id)
            if decision.get("allow"):
                return PermissionResultAllow(behavior="allow")
            return PermissionResultDeny(
                behavior="deny",
                message=decision.get("reason", "Safety policy denied"),
                interrupt=False,
            )

        options = ClaudeAgentOptions(
            model=self._model,
            max_turns=self._max_turns,
            max_budget_usd=self._max_budget,
            system_prompt=self.system_prompt,
            allowed_tools=sdk_allowed_tools if sdk_allowed_tools is not None else [],
            cwd=str(self.project_root),
            can_use_tool=_can_use_tool,
        )

        output_parts: list[str] = []

        async for event in query(prompt=task, options=options):
            if isinstance(event, AssistantMessage):
                for block in event.content:
                    if isinstance(block, TextBlock):
                        output_parts.append(block.text)
            elif isinstance(event, ResultMessage):
                duration = time.time() - (self._start_time or time.time())
                # ResultMessage.result contains the final text; fall back to
                # accumulated parts if result is absent.
                final_output = event.result or "\n\n".join(output_parts)
                if event.is_error:
                    return AgentResult(
                        agent_id=self.agent_id,
                        success=False,
                        output="",
                        error=final_output or "SDK run failed",
                        turns_used=event.num_turns,
                        spend_usd=event.total_cost_usd or 0.0,
                        duration_seconds=duration,
                    )
                return AgentResult(
                    agent_id=self.agent_id,
                    success=True,
                    output=final_output,
                    turns_used=event.num_turns,
                    spend_usd=event.total_cost_usd or 0.0,
                    duration_seconds=duration,
                )

        # No ResultMessage received (unexpected — return accumulated output)
        return AgentResult(
            agent_id=self.agent_id,
            success=bool(output_parts),
            output="\n\n".join(output_parts),
            duration_seconds=time.time() - (self._start_time or time.time()),
        )
