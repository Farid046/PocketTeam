"""
Reviewer Agent — reviews plans, code, and architecture.

Checks for completeness, correctness, SQL safety, race conditions,
LLM trust boundary violations, and signals APPROVED when satisfied.
"""

from __future__ import annotations

from typing import Optional

from .base import AgentContext, AgentResult, BaseAgent


class ReviewerAgent(BaseAgent):
    def _get_agent_id(self) -> str:
        return "reviewer"

    async def _run(self, task: str, context: Optional[AgentContext]) -> AgentResult:
        result = await self._run_with_sdk(task)
        if result.success and result.output:
            # Pipeline checks for "APPROVED" in reviewer output to stop the loop.
            result.artifacts["approved"] = "APPROVED" in result.output.upper()
        return result
