"""
Investigator Agent — root-cause analysis.

Applies the hypothesis-test-verify loop to find root causes of bugs
and production incidents. Enforces the 3-Strike Rule: after 3 failed
fix attempts, escalates to the CEO instead of continuing.
"""

from __future__ import annotations

from .base import AgentContext, AgentResult, BaseAgent


class InvestigatorAgent(BaseAgent):
    def _get_agent_id(self) -> str:
        return "investigator"

    async def _run(self, task: str, context: AgentContext | None) -> AgentResult:
        result = await self._run_with_sdk(task)
        if result.success and result.output:
            result.artifacts["investigation"] = result.output
            # Self-healing loop uses this flag to decide whether to attempt auto-fix
            result.artifacts["requires_human"] = "ESCALATE" in result.output.upper()
        return result
