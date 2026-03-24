"""Observer Agent."""
from __future__ import annotations
from typing import Optional
from .base import BaseAgent, AgentContext, AgentResult

class ObserverAgent(BaseAgent):
    def _get_agent_id(self) -> str:
        return "observer"
    async def _run(self, task: str, context: Optional[AgentContext]) -> AgentResult:
        return AgentResult(agent_id=self.agent_id, success=True, output=f"Observer result for: {task}")
