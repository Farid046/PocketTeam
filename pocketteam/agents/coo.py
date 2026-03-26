"""
COO Agent — Chief Operating Officer.

Receives tasks from the CEO and orchestrates the pipeline.
In Claude Code, the COO *is* the main session (reads CLAUDE.md).
In Python SDK mode, the COO acts as the top-level reasoning agent that
understands the task, asks clarifying questions if needed, and then
delegates via Pipeline or direct spawn_subagent() calls.
"""

from __future__ import annotations

from .base import AgentContext, AgentResult, BaseAgent


class COOAgent(BaseAgent):
    """
    Chief Operating Officer — top-level orchestrator.

    Responsibilities:
    - Understand and clarify incoming tasks from the CEO
    - Decide whether to run the full pipeline or handle directly
    - Delegate to specialist agents
    - Report status and results back to CEO

    The COO itself does NOT implement features — it only plans and delegates.
    Tool list is empty (delegates-only): safety guardian enforces this via
    can_use_tool callback (Layer 6: COO allowlist = []).
    """

    def _get_agent_id(self) -> str:
        return "coo"

    async def _run(self, task: str, context: AgentContext | None) -> AgentResult:
        """
        Run the COO reasoning pass.

        For a task that arrives outside the Pipeline (e.g., direct invocation
        for clarification or status reporting), the COO calls the SDK to
        reason about the task and formulate a delegation plan.
        The Pipeline itself drives the full agent workflow.
        """
        return await self._run_with_sdk(task)

    async def run_pipeline(self, task: str) -> bool:
        """
        Convenience: run the full multi-phase pipeline for a task.
        Creates a SharedContext and delegates to Pipeline.
        Returns True if pipeline completed successfully.
        """
        from ..core.context import SharedContext
        from ..core.pipeline import Pipeline

        shared = SharedContext.create_new(
            task_description=task,
            project_root=self.project_root,
        )

        pipeline = Pipeline(
            context=shared,
            on_status_update=self._on_status_update,
        )
        return await pipeline.run()

    async def _on_status_update(self, message: str) -> None:
        """Log pipeline status updates as agent events."""
        await self._log_event("working", message[:200])
