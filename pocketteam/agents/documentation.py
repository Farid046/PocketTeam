"""
Documentation Agent — keeps docs in sync with code.

Updates README, ARCHITECTURE.md, CHANGELOG, and API docs after every
ship. Detects stale documentation and preserves the project's voice.
Uses Haiku (cheap) because docs are a straightforward writing task.
"""

from __future__ import annotations

from typing import Optional

from .base import AgentContext, AgentResult, BaseAgent


class DocumentationAgent(BaseAgent):
    def _get_agent_id(self) -> str:
        return "documentation"

    async def _run(self, task: str, context: Optional[AgentContext]) -> AgentResult:
        return await self._run_with_sdk(task)
