"""
Planner Agent — creates detailed implementation plans.

Reads the codebase, gathers requirements, asks clarifying questions,
and produces a structured plan that the Engineer will follow.
"""

from __future__ import annotations

from .base import AgentContext, AgentResult, BaseAgent


class PlannerAgent(BaseAgent):
    def _get_agent_id(self) -> str:
        return "planner"

    async def _run(self, task: str, context: AgentContext | None) -> AgentResult:
        result = await self._run_with_sdk(task)
        # Surface the plan text as a dedicated artifact for the pipeline
        if result.success and result.output:
            result.artifacts["plan"] = result.output
        return result
