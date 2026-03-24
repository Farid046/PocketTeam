"""
Tests for Phase 9: TestRunner, BrowserTools, QAAgent, SecurityAgent.

No real subprocesses are spawned — all external calls are mocked.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pocketteam.agents.qa import QAAgent
from pocketteam.agents.security import DependencyScanResult, SecurityAgent
from pocketteam.tools.browser_tools import BrowserResult, BrowserTool
from pocketteam.tools.test_runner import TestFramework, TestResult, TestRunner


# ── TestRunner: framework detection ──────────────────────────────────────────

class TestFrameworkDetection:
    def test_detects_pytest_from_pyproject(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").touch()
        assert TestRunner(tmp_path).detect_framework() == TestFramework.PYTEST

    def test_detects_pytest_from_setup_py(self, tmp_path: Path):
        (tmp_path / "setup.py").touch()
        assert TestRunner(tmp_path).detect_framework() == TestFramework.PYTEST

    def test_detects_npm(self, tmp_path: Path):
        (tmp_path / "package.json").write_text("{}")
        assert TestRunner(tmp_path).detect_framework() == TestFramework.NPM

    def test_detects_composer(self, tmp_path: Path):
        (tmp_path / "composer.json").write_text("{}")
        assert TestRunner(tmp_path).detect_framework() == TestFramework.COMPOSER

    def test_unknown_when_no_manifest(self, tmp_path: Path):
        assert TestRunner(tmp_path).detect_framework() == TestFramework.UNKNOWN


# ── TestRunner: pytest output parsing ────────────────────────────────────────

class TestPytestParsing:
    """_parse_output correctly extracts counts from pytest output."""

    def _parse(self, output: str) -> dict:
        from pocketteam.tools.test_runner import _parse_output, TestFramework
        return _parse_output(TestFramework.PYTEST, output)

    def test_all_passed(self):
        output = "5 passed in 0.42s"
        result = self._parse(output)
        assert result["passed"] == 5
        assert result["failed"] == 0
        assert result["total"] == 5

    def test_mixed_results(self):
        output = "3 passed, 2 failed, 1 error in 1.20s"
        result = self._parse(output)
        assert result["passed"] == 3
        assert result["failed"] == 2
        assert result["errors"] == 1
        assert result["total"] == 6

    def test_failed_test_names_extracted(self):
        output = (
            "FAILED tests/test_auth.py::TestLogin::test_invalid_password\n"
            "FAILED tests/test_api.py::TestEndpoint::test_rate_limit\n"
            "2 failed in 0.80s"
        )
        result = self._parse(output)
        assert len(result["failed_tests"]) == 2
        assert "tests/test_auth.py::TestLogin::test_invalid_password" in result["failed_tests"]

    def test_skipped_extracted(self):
        output = "4 passed, 1 skipped in 0.30s"
        result = self._parse(output)
        assert result["skipped"] == 1
        assert result["passed"] == 4


# ── TestRunner: subprocess execution ─────────────────────────────────────────

class TestRunnerExecution:
    async def _mock_process(self, output: str, returncode: int = 0) -> MagicMock:
        """Build a fake asyncio subprocess."""
        proc = MagicMock()
        proc.returncode = returncode
        proc.communicate = AsyncMock(return_value=(output.encode(), b""))
        proc.kill = MagicMock()
        return proc

    async def test_run_pytest_success(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").touch()
        runner = TestRunner(tmp_path)
        fake_output = "3 passed in 0.42s"

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.return_value = await self._mock_process(fake_output, 0)
            result = await runner.run_pytest()

        assert result.success is True
        assert result.passed == 3
        assert result.exit_code == 0
        assert result.framework == TestFramework.PYTEST

    async def test_run_pytest_failure(self, tmp_path: Path):
        runner = TestRunner(tmp_path)
        fake_output = "FAILED tests/test_foo.py::test_bar\n1 failed in 0.15s"

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.return_value = await self._mock_process(fake_output, 1)
            result = await runner.run_pytest()

        assert result.success is False
        assert result.failed == 1
        assert result.failed_tests == ["tests/test_foo.py::test_bar"]

    async def test_command_not_found(self, tmp_path: Path):
        runner = TestRunner(tmp_path)
        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError("python")):
            result = await runner.run_pytest()

        assert result.success is False
        assert "not found" in result.output.lower()
        assert result.exit_code == 127

    async def test_timeout(self, tmp_path: Path):
        runner = TestRunner(tmp_path)

        call_count = 0

        async def _communicate():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise asyncio.TimeoutError()
            # Second call (after kill) drains the process
            return b"", b""

        proc = MagicMock()
        proc.communicate = _communicate
        proc.kill = MagicMock()

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await runner.run_pytest(timeout=1)

        assert result.success is False
        assert result.exit_code == 124
        assert "timed out" in result.output.lower()

    async def test_auto_detect_runs_pytest(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").touch()
        runner = TestRunner(tmp_path)

        with patch.object(runner, "run_pytest", new_callable=AsyncMock) as mock_pytest:
            mock_pytest.return_value = TestResult(
                framework=TestFramework.PYTEST, success=True, passed=5, total=5
            )
            result = await runner.run_tests()

        mock_pytest.assert_called_once()
        assert result.success is True

    async def test_unknown_framework_returns_error(self, tmp_path: Path):
        runner = TestRunner(tmp_path)  # tmp_path has no manifests
        result = await runner.run_tests()
        assert result.success is False
        assert result.framework == TestFramework.UNKNOWN


# ── TestResult.summary ────────────────────────────────────────────────────────

class TestResultSummary:
    def test_summary_format(self):
        r = TestResult(
            framework=TestFramework.PYTEST,
            success=True,
            passed=5, failed=1, errors=0, skipped=2, total=8,
            duration_seconds=1.5,
        )
        s = r.summary
        assert "pytest" in s
        assert "5 passed" in s
        assert "1 failed" in s


# ── BrowserTool: no Playwright ────────────────────────────────────────────────

class TestBrowserToolNoPlaywright:
    """When Playwright is not installed, methods return clear error results."""

    def _make_tool(self, tmp_path: Path) -> BrowserTool:
        return BrowserTool(tmp_path, base_url="http://localhost:3000")

    async def test_screenshot_no_playwright(self, tmp_path: Path):
        with patch("pocketteam.tools.browser_tools._playwright_available", return_value=False):
            tool = self._make_tool(tmp_path)
            result = await tool.screenshot("http://localhost:3000")
        assert result.success is False
        assert "playwright" in result.error.lower()

    async def test_check_page_loads_no_playwright(self, tmp_path: Path):
        with patch("pocketteam.tools.browser_tools._playwright_available", return_value=False):
            tool = self._make_tool(tmp_path)
            result = await tool.check_page_loads()
        assert result.success is False

    async def test_navigate_and_act_no_playwright(self, tmp_path: Path):
        with patch("pocketteam.tools.browser_tools._playwright_available", return_value=False):
            tool = self._make_tool(tmp_path)
            result = await tool.navigate_and_act([{"action": "goto", "url": "http://localhost:3000"}])
        assert result.success is False


class TestBrowserToolNoTests:
    """run_playwright_tests returns success=True when no test files found."""

    async def test_no_test_files(self, tmp_path: Path):
        with patch("pocketteam.tools.browser_tools._playwright_available", return_value=True):
            tool = BrowserTool(tmp_path)
            result = await tool.run_playwright_tests(test_pattern="tests/e2e/**/*.spec.*")
        assert result.success is True
        assert "No Playwright test files found" in result.output


# ── QAAgent.run_tests_now() ───────────────────────────────────────────────────

class TestQAAgentRunTestsNow:
    async def test_success_result(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").touch()
        agent = QAAgent(tmp_path)

        mock_result = TestResult(
            framework=TestFramework.PYTEST,
            success=True,
            passed=10, failed=0, total=10,
            output="10 passed in 1.0s",
            duration_seconds=1.0,
        )

        with patch("pocketteam.tools.test_runner.TestRunner.run_tests", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = mock_result
            result = await agent.run_tests_now()

        assert result.success is True
        assert result.artifacts["tests_passed"] is True
        assert result.artifacts["test_result"] is mock_result

    async def test_failure_result(self, tmp_path: Path):
        agent = QAAgent(tmp_path)

        mock_result = TestResult(
            framework=TestFramework.PYTEST,
            success=False,
            passed=8, failed=2, total=10,
            output="2 failed in 1.2s",
            failed_tests=["tests/test_a.py::test_x", "tests/test_b.py::test_y"],
            duration_seconds=1.2,
        )

        with patch("pocketteam.tools.test_runner.TestRunner.run_tests", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = mock_result
            result = await agent.run_tests_now()

        assert result.success is False
        assert result.artifacts["tests_passed"] is False
        assert result.error is not None
        assert "2 test(s) failed" in result.error


# ── SecurityAgent.scan_dependencies() ────────────────────────────────────────

class TestSecurityAgentScanDependencies:
    async def test_no_manifest(self, tmp_path: Path):
        agent = SecurityAgent(tmp_path)
        result = await agent.scan_dependencies()
        # Success=True (scan ran) even if no manifest found
        assert result.success is True
        assert result.artifacts["has_critical"] is False

    async def test_pip_audit_clean(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").touch()
        agent = SecurityAgent(tmp_path)

        mock_scan = DependencyScanResult(
            success=True,
            vulnerabilities=[],
            critical_count=0,
            high_count=0,
            total_count=0,
            output="No vulnerabilities found",
            scanner="pip-audit",
        )

        with patch.object(agent, "_run_dependency_scan", new_callable=AsyncMock) as mock:
            mock.return_value = mock_scan
            result = await agent.scan_dependencies()

        assert result.success is True
        assert result.artifacts["has_critical"] is False
        assert result.artifacts["vulnerability_count"] == 0

    async def test_pip_audit_critical(self, tmp_path: Path):
        agent = SecurityAgent(tmp_path)

        mock_scan = DependencyScanResult(
            success=True,
            critical_count=2,
            high_count=1,
            total_count=3,
            output="2 critical vulnerabilities found",
            scanner="pip-audit",
        )

        with patch.object(agent, "_run_dependency_scan", new_callable=AsyncMock) as mock:
            mock.return_value = mock_scan
            result = await agent.scan_dependencies()

        assert result.artifacts["has_critical"] is True
        assert result.artifacts["vulnerability_count"] == 3
        assert result.error is not None
        assert "CRITICAL" in result.error

    async def test_static_python_check_no_vulns(self, tmp_path: Path):
        req = tmp_path / "requirements.txt"
        req.write_text("click==8.1.7\nrich==13.7.0\n")
        (tmp_path / "pyproject.toml").touch()

        agent = SecurityAgent(tmp_path)
        scan_result = await agent._static_python_check()

        assert scan_result.success is True
        assert scan_result.total_count == 0
        assert "No known vulnerable" in scan_result.output

    async def test_static_python_check_detects_old_pyyaml(self, tmp_path: Path):
        req = tmp_path / "requirements.txt"
        req.write_text("pyyaml==5.4.1\nclick==8.1.7\n")

        agent = SecurityAgent(tmp_path)
        scan_result = await agent._static_python_check()

        assert scan_result.total_count > 0
        assert "pyyaml" in scan_result.output.lower()
        assert "CVE" in scan_result.output


# ── DependencyScanResult helpers ──────────────────────────────────────────────

class TestDependencyScanResult:
    def test_has_critical_true(self):
        r = DependencyScanResult(success=True, critical_count=1)
        assert r.has_critical is True

    def test_has_critical_false(self):
        r = DependencyScanResult(success=True, critical_count=0)
        assert r.has_critical is False

    def test_summary_format(self):
        r = DependencyScanResult(
            success=True,
            critical_count=2, high_count=3, total_count=5,
            scanner="pip-audit",
        )
        assert "pip-audit" in r.summary
        assert "5 vulnerabilities" in r.summary
        assert "2 critical" in r.summary
