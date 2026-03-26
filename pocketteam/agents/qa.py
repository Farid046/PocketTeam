"""
QA Agent — runs tests and validates quality.

Executes unit, integration, and E2E tests. Detects regressions.

Two modes:
1. SDK mode (via execute()): full Claude session with Bash access to run
   tests, interpret results, and fix flaky tests.
2. Programmatic mode (via run_tests_now()): direct TestRunner call for
   self-healing pipeline and health checks — no LLM needed.
"""

from __future__ import annotations

from .base import AgentContext, AgentResult, BaseAgent


class QAAgent(BaseAgent):
    def _get_agent_id(self) -> str:
        return "qa"

    async def _run(self, task: str, context: AgentContext | None) -> AgentResult:
        result = await self._run_with_sdk(task)
        if result.success and result.output:
            result.artifacts["qa_report"] = result.output
            # Pipeline uses "FAIL" / "PASS" markers in QA output
            result.artifacts["tests_passed"] = "FAIL" not in result.output.upper()
        return result

    async def run_tests_now(
        self,
        args: list[str] | None = None,
        timeout: int = 300,
    ) -> AgentResult:
        """
        Programmatic test execution — no SDK session needed.

        Used by:
        - self-healing pipeline (quick verification after auto-fix)
        - staging validation before production deploy
        - GitHub Actions health check

        Returns AgentResult whose artifacts["test_result"] is a TestResult.
        """
        from ..tools.test_runner import TestRunner

        runner = TestRunner(self.project_root)
        framework = runner.detect_framework()

        if framework.value == "pytest" and args:
            test_result = await runner.run_pytest(args=args, timeout=timeout)
        else:
            test_result = await runner.run_tests(timeout=timeout)

        await self._log_event(
            "working",
            f"Tests: {test_result.passed} passed, {test_result.failed} failed",
        )

        return AgentResult(
            agent_id=self.agent_id,
            success=test_result.success,
            output=test_result.summary,
            artifacts={
                "test_result": test_result,
                "tests_passed": test_result.success,
                "qa_report": test_result.output,
            },
            error=None if test_result.success else (
                f"{test_result.failed} test(s) failed: "
                + ", ".join(test_result.failed_tests[:5])
            ),
            duration_seconds=test_result.duration_seconds,
        )

    async def run_browser_tests(
        self,
        base_url: str = "http://localhost:3000",
        test_pattern: str = "tests/e2e/**/*.spec.*",
    ) -> AgentResult:
        """
        Run Playwright E2E tests.
        Sub-agent capability: Browser Tester.
        """
        from ..tools.browser_tools import BrowserTool

        browser = BrowserTool(self.project_root, base_url=base_url)

        await self._log_event("working", f"Running browser tests against {base_url}")

        # First verify the app is reachable
        health = await browser.check_page_loads([base_url])
        if not health.success:
            return AgentResult(
                agent_id=self.agent_id,
                success=False,
                output=health.output or "",
                error=f"App not reachable at {base_url}: {health.error}",
            )

        # Run test files
        result = await browser.run_playwright_tests(test_pattern=test_pattern)

        return AgentResult(
            agent_id=self.agent_id,
            success=result.success,
            output=result.output,
            artifacts={
                "browser_test_output": result.output,
                "screenshots": [str(p) for p in result.screenshots],
            },
            error=result.error,
            duration_seconds=result.duration_seconds,
        )
