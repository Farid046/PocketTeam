"""
Product Agent — validates product demand and challenges assumptions.

Asks the 6 Forcing Questions, challenges premises across 3 knowledge
layers, and generates alternative approaches with effort/risk estimates.
"""

from __future__ import annotations

from .base import AgentContext, AgentResult, BaseAgent


class ProductAgent(BaseAgent):
    def _get_agent_id(self) -> str:
        return "product"

    async def _run(self, task: str, context: AgentContext | None) -> AgentResult:
        result = await self._run_with_sdk(task)
        if result.success and result.output:
            result.artifacts["product_diagnostic"] = result.output
        return result
