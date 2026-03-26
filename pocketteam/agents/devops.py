"""
DevOps Agent — deploy, canary, and rollback.

Deploys to staging and production using canary strategy.
Sub-agent: Release Manager (CHANGELOG, version bump, PR creation).
Bash access is restricted by Layer 2 + Layer 6 safety.
"""

from __future__ import annotations

from .base import AgentContext, AgentResult, BaseAgent


class DevOpsAgent(BaseAgent):
    def _get_agent_id(self) -> str:
        return "devops"

    async def _run(self, task: str, context: AgentContext | None) -> AgentResult:
        result = await self._run_with_sdk(task)
        if result.success and result.output:
            result.artifacts["deploy_report"] = result.output
        return result
