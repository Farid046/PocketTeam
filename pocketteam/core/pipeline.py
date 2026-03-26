"""
Pipeline — the state machine that orchestrates agent phases.

Phases: init → product? → planning → implementation → staging → production → monitoring
Human gates happen between phases (CEO approval).
Kill switch checked at every phase transition.
Phase timeouts prevent deadlocks.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from ..constants import PHASE_TIMEOUTS
from .context import SharedContext

logger = logging.getLogger(__name__)


class Phase(StrEnum):
    INIT = "init"
    PRODUCT = "product"
    PLANNING = "planning"
    IMPLEMENTATION = "implementation"
    STAGING = "staging"
    PRODUCTION = "production"
    MONITORING = "monitoring"
    DONE = "done"
    FAILED = "failed"


@dataclass
class PhaseResult:
    phase: Phase
    success: bool
    output: str
    artifacts: dict[str, Any]
    error: str | None = None
    awaiting_approval: bool = False
    approval_prompt: str | None = None


class PipelineError(Exception):
    """Raised when the pipeline encounters an unrecoverable error."""


class Pipeline:
    """
    HEADLESS/CI FALLBACK: Programmatic multi-agent pipeline.

    ⚠️  This is NOT the normal flow. Normal usage:
        User → Claude Code → reads .claude/CLAUDE.md → COO spawns agents natively.
        That flow is FREE (runs on Claude Code subscription).

    This Pipeline class is ONLY for:
    - GitHub Actions self-healing (handle_health_failure)
    - CI/CD headless pipeline execution (pocketteam run-headless)
    - Requires ANTHROPIC_API_KEY (each agent call costs tokens)

    Features: phase timeouts, human gates, kill switch, artifact passing.
    """

    def __init__(
        self,
        context: SharedContext,
        on_human_gate: Callable | None = None,
        on_status_update: Callable | None = None,
    ) -> None:
        self.context = context
        self.on_human_gate = on_human_gate      # Called when CEO input needed
        self.on_status_update = on_status_update # Called for status messages
        self._current_phase = Phase.INIT

    async def run(self, skip_product: bool = True) -> bool:
        """
        Run the full pipeline.
        Returns True if pipeline completed successfully.
        """
        phases = [
            (Phase.PLANNING, self._run_planning),
            (Phase.IMPLEMENTATION, self._run_implementation),
            (Phase.STAGING, self._run_staging),
            (Phase.PRODUCTION, self._run_production),
            (Phase.MONITORING, self._run_monitoring),
        ]

        if not skip_product:
            phases.insert(0, (Phase.PRODUCT, self._run_product))

        for phase, runner in phases:
            self._check_kill_switch()
            self._current_phase = phase
            self.context.advance_phase(phase.value)

            self._log_event("phase_start", phase.value)
            await self._notify(f"Starting phase: {phase.value}")

            try:
                result = await self._run_with_timeout(runner, phase)
            except TimeoutError:
                self._log_event("phase_timeout", phase.value)
                await self._notify(
                    f"⚠️ Phase '{phase.value}' timed out after "
                    f"{PHASE_TIMEOUTS.get(phase.value, 0)//60} minutes. Escalating."
                )
                return False
            except Exception as e:
                self._log_event("phase_error", f"{phase.value}: {e}")
                await self._notify(f"❌ Phase '{phase.value}' failed: {e}")
                return False

            if not result.success:
                self._log_event("phase_failed", f"{phase.value}: {result.error}")
                await self._notify(f"❌ Phase '{phase.value}' failed: {result.error}")
                return False

            self._log_event("phase_complete", phase.value)

            if result.awaiting_approval:
                approved = await self._request_approval(result.approval_prompt or "")
                if not approved:
                    await self._notify("Pipeline stopped by CEO.")
                    return False

        self.context.advance_phase(Phase.DONE.value)
        return True

    async def _run_with_timeout(
        self,
        runner: Callable,
        phase: Phase,
    ) -> PhaseResult:
        """Run a phase with a timeout."""
        timeout = PHASE_TIMEOUTS.get(phase.value, 60 * 60)
        return await asyncio.wait_for(runner(), timeout=timeout)

    # ── Phase implementations ─────────────────────────────────────────────

    async def _run_product(self) -> PhaseResult:
        """Optional: Product Advisor validates demand."""
        from ..agents.product import ProductAgent
        agent = ProductAgent(self.context.project_root, self.context)
        result = await agent.execute(self.context.task_description)

        return PhaseResult(
            phase=Phase.PRODUCT,
            success=result.success,
            output=result.output,
            artifacts=result.artifacts,
            awaiting_approval=True,
            approval_prompt=(
                f"📋 Product diagnostic complete:\n{result.output}\n\n"
                "Proceed with implementation? (y/n)"
            ),
        )

    async def _run_planning(self) -> PhaseResult:
        """Planner + Reviewer create and validate the plan."""
        from ..agents.planner import PlannerAgent
        from ..agents.reviewer import ReviewerAgent

        planner = PlannerAgent(self.context.project_root, self.context)
        plan_result = await planner.execute(self.context.task_description)

        if not plan_result.success:
            return PhaseResult(
                phase=Phase.PLANNING,
                success=False,
                output="",
                artifacts={},
                error=plan_result.error,
            )

        # Reviewer validates the plan
        reviewer = ReviewerAgent(self.context.project_root, self.context)
        review_result = await reviewer.execute(
            f"Review this plan:\n{plan_result.output}"
        )

        return PhaseResult(
            phase=Phase.PLANNING,
            success=True,
            output=plan_result.output,
            artifacts={
                "plan": plan_result.output,
                "plan_review": review_result.output,
            },
            awaiting_approval=True,
            approval_prompt=(
                f"📋 Plan ready for review:\n{plan_result.output[:500]}...\n\n"
                f"Review: {review_result.output[:300]}...\n\n"
                "Approve plan and start implementation? (y/n)"
            ),
        )

    async def _run_implementation(self) -> PhaseResult:
        """Engineer implements, Reviewer reviews, QA tests, Security audits."""
        from ..agents.documentation import DocumentationAgent
        from ..agents.engineer import EngineerAgent
        from ..agents.qa import QAAgent
        from ..agents.reviewer import ReviewerAgent
        from ..agents.security import SecurityAgent
        from ..constants import MAX_CODE_REVIEW_LOOPS

        plan = self.context.get_latest_plan()

        # Engineer implements
        engineer = EngineerAgent(self.context.project_root, self.context)
        eng_result = await engineer.execute(
            f"Implement this plan:\n{plan.content if plan else self.context.task_description}"
        )
        if not eng_result.success:
            return PhaseResult(
                phase=Phase.IMPLEMENTATION,
                success=False, output="", artifacts={},
                error=eng_result.error,
            )

        # Review loop (max 3 rounds)
        reviewer = ReviewerAgent(self.context.project_root, self.context)
        for round_num in range(MAX_CODE_REVIEW_LOOPS):
            review = await reviewer.execute("Review the implementation")
            if "APPROVED" in (review.output or "").upper():
                break
            if round_num < MAX_CODE_REVIEW_LOOPS - 1:
                fix_result = await engineer.execute(
                    f"Fix review issues:\n{review.output}"
                )
                if not fix_result.success:
                    break

        # Parallel: QA + Security
        qa = QAAgent(self.context.project_root, self.context)
        security = SecurityAgent(self.context.project_root, self.context)

        qa_result, security_result = await asyncio.gather(
            qa.execute("Run all tests"),
            security.execute("Security audit"),
            return_exceptions=True,
        )

        # If QA or Security agents crashed, fail the phase — silent failures are unacceptable
        if isinstance(qa_result, Exception):
            return PhaseResult(
                phase=Phase.IMPLEMENTATION,
                success=False,
                output="",
                artifacts={},
                error=f"QA agent crashed: {qa_result}",
            )
        if isinstance(security_result, Exception):
            return PhaseResult(
                phase=Phase.IMPLEMENTATION,
                success=False,
                output="",
                artifacts={},
                error=f"Security agent crashed: {security_result}",
            )

        # Documentation
        docs = DocumentationAgent(self.context.project_root, self.context)
        await docs.execute("Update documentation for the new feature")

        return PhaseResult(
            phase=Phase.IMPLEMENTATION,
            success=True,
            output=eng_result.output,
            artifacts={
                "implementation": eng_result.output,
                "review": review.output if not isinstance(review, Exception) else "",
                "qa": qa_result.output,
                "security": security_result.output,
            },
        )

    async def _run_staging(self) -> PhaseResult:
        """Deploy to staging and validate. Gates on CEO approval before production."""
        from ..agents.devops import DevOpsAgent

        devops = DevOpsAgent(self.context.project_root, self.context)
        result = await devops.execute("Deploy to staging and run smoke tests")

        if not result.success:
            return PhaseResult(
                phase=Phase.STAGING,
                success=False,
                output=result.output,
                artifacts=result.artifacts,
                error=result.error,
            )

        # Human gate BEFORE production deploy starts — CEO must approve here
        return PhaseResult(
            phase=Phase.STAGING,
            success=True,
            output=result.output,
            artifacts=result.artifacts,
            awaiting_approval=True,
            approval_prompt=(
                "Staging deploy complete. Smoke tests passed.\n"
                "Approve production deploy? (y/n)"
            ),
        )

    async def _run_production(self) -> PhaseResult:
        """Deploy to production (CEO already approved at end of staging phase)."""
        from ..agents.devops import DevOpsAgent

        devops = DevOpsAgent(self.context.project_root, self.context)
        result = await devops.execute("Deploy to production (canary strategy)")

        return PhaseResult(
            phase=Phase.PRODUCTION,
            success=result.success,
            output=result.output,
            artifacts=result.artifacts,
            error=result.error,
        )

    async def _run_monitoring(self) -> PhaseResult:
        """Monitor production for 15 minutes post-deploy."""
        from ..agents.monitor import MonitorAgent

        monitor = MonitorAgent(self.context.project_root, self.context)
        result = await monitor.execute("Monitor production for 15 minutes post-deploy")

        return PhaseResult(
            phase=Phase.MONITORING,
            success=result.success,
            output=result.output,
            artifacts=result.artifacts,
        )

    # ── Helpers ────────────────────────────────────────────────────────────

    def _check_kill_switch(self) -> None:
        from ..safety.kill_switch import KillSwitch, KillSwitchError
        ks = KillSwitch(self.context.project_root)
        if ks.is_active:
            raise KillSwitchError("Kill switch is active — pipeline halted")

    async def _request_approval(self, prompt: str) -> bool:
        """Request CEO approval. In automated mode, raises for Telegram input."""
        if self.on_human_gate:
            return await self.on_human_gate(prompt)
        # Default: non-interactive mode always requires explicit approval
        await self._notify(f"⛔ HUMAN GATE:\n{prompt}")
        return False

    def _log_event(self, event_type: str, detail: str) -> None:
        """Log pipeline event to stream.jsonl."""
        import json
        import time
        try:
            from ..constants import EVENTS_FILE
            events_path = self.context.project_root / EVENTS_FILE
            events_path.parent.mkdir(parents=True, exist_ok=True)
            event = {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "agent": "pipeline",
                "type": event_type,
                "status": "working",
                "action": detail,
            }
            with open(events_path, "a") as f:
                f.write(json.dumps(event) + "\n")
        except Exception:
            logger.debug("Pipeline event logging failed (non-critical)", exc_info=True)

    async def _notify(self, message: str) -> None:
        """Send status update to CEO."""
        if self.on_status_update:
            await self.on_status_update(message)
