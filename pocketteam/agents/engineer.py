"""
Engineer Agent — implements features.

Writes code, creates files, runs builds, and follows the approved plan.
Uses the "Boil the Lake" philosophy: complete coverage, not 80%.
"""

from __future__ import annotations

from typing import Optional

from .base import AgentContext, AgentResult, BaseAgent


class EngineerAgent(BaseAgent):
    def _get_agent_id(self) -> str:
        return "engineer"

    async def _run(self, task: str, context: Optional[AgentContext]) -> AgentResult:
        result = await self._run_with_sdk(task)
        if result.success and result.output:
            result.artifacts["implementation"] = result.output
        return result

    async def upgrade_to_opus(self, task: str, context: Optional[AgentContext] = None) -> AgentResult:
        """
        Upgrade to Opus for complex multi-file tasks.
        Called by the COO when the task requires deeper reasoning.
        """
        from ..constants import ENGINEER_UPGRADE_MODEL
        original_model = self._model
        self._model = ENGINEER_UPGRADE_MODEL
        try:
            return await self.execute(task, context)
        finally:
            self._model = original_model
