"""
TestRunner — programmatic test execution.

Used by QA Agent and self-healing pipeline to run tests and get
structured results without spawning a full SDK session.

Supports: pytest, npm test, composer test (auto-detected from project).
Parses output into a structured TestResult so the pipeline can make
decisions (auto-fix, rollback, escalate) based on the outcome.
"""

from __future__ import annotations

import asyncio
import re
import shutil
import time
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class TestFramework(StrEnum):
    PYTEST = "pytest"
    NPM = "npm"
    COMPOSER = "composer"
    UNKNOWN = "unknown"


@dataclass
class TestResult:
    """Structured result of a test run."""
    framework: TestFramework
    success: bool          # True if all collected tests passed
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    total: int = 0
    output: str = ""
    failed_tests: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    exit_code: int = 0

    @property
    def summary(self) -> str:
        return (
            f"{self.framework.value}: "
            f"{self.passed} passed, {self.failed} failed, "
            f"{self.errors} errors, {self.skipped} skipped "
            f"({self.duration_seconds:.1f}s)"
        )


class TestRunner:
    """
    Run tests programmatically and return structured results.
    Used by QA Agent and self-healing pipeline.
    """

    # Subprocess timeout — 5 min default, overridable per call
    DEFAULT_TIMEOUT = 300

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root

    def detect_framework(self) -> TestFramework:
        """Detect which test framework the project uses."""
        root = self.project_root
        if (root / "pyproject.toml").exists() or (root / "setup.py").exists():
            return TestFramework.PYTEST
        if (root / "package.json").exists():
            return TestFramework.NPM
        if (root / "composer.json").exists():
            return TestFramework.COMPOSER
        return TestFramework.UNKNOWN

    async def run_tests(self, timeout: int = DEFAULT_TIMEOUT) -> TestResult:
        """Auto-detect framework and run tests."""
        framework = self.detect_framework()
        if framework == TestFramework.PYTEST:
            return await self.run_pytest(timeout=timeout)
        if framework == TestFramework.NPM:
            return await self.run_npm_test(timeout=timeout)
        if framework == TestFramework.COMPOSER:
            return await self.run_composer_test(timeout=timeout)
        return TestResult(
            framework=TestFramework.UNKNOWN,
            success=False,
            output="No supported test framework detected",
            exit_code=1,
        )

    async def run_pytest(
        self,
        args: list[str] | None = None,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> TestResult:
        """Run pytest and return structured results."""
        cmd = ["python", "-m", "pytest"]
        if args:
            cmd.extend(args)
        else:
            # Default: verbose + short traceback + junit XML for parsing
            cmd.extend(["-v", "--tb=short", "-q"])

        return await self._run_command(cmd, TestFramework.PYTEST, timeout)

    async def run_npm_test(self, timeout: int = DEFAULT_TIMEOUT) -> TestResult:
        """Run npm test."""
        npm = shutil.which("npm") or "npm"
        return await self._run_command([npm, "test", "--", "--ci"], TestFramework.NPM, timeout)

    async def run_composer_test(self, timeout: int = DEFAULT_TIMEOUT) -> TestResult:
        """Run composer test (PHPUnit)."""
        composer = shutil.which("composer") or "composer"
        return await self._run_command([composer, "test"], TestFramework.COMPOSER, timeout)

    async def _run_command(
        self,
        cmd: list[str],
        framework: TestFramework,
        timeout: int,
    ) -> TestResult:
        """Execute a test command and parse the output."""
        start = time.monotonic()
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(self.project_root),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            try:
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except TimeoutError:
                proc.kill()
                await proc.communicate()
                return TestResult(
                    framework=framework,
                    success=False,
                    output=f"Test run timed out after {timeout}s",
                    exit_code=124,
                    duration_seconds=time.monotonic() - start,
                )

            output = stdout.decode("utf-8", errors="replace")
            exit_code = proc.returncode or 0
            duration = time.monotonic() - start

            parsed = _parse_output(framework, output)
            return TestResult(
                framework=framework,
                success=exit_code == 0,
                passed=parsed["passed"],
                failed=parsed["failed"],
                errors=parsed["errors"],
                skipped=parsed["skipped"],
                total=parsed["total"],
                failed_tests=parsed["failed_tests"],
                output=output,
                exit_code=exit_code,
                duration_seconds=duration,
            )

        except FileNotFoundError:
            return TestResult(
                framework=framework,
                success=False,
                output=f"Command not found: {cmd[0]}. Is it installed?",
                exit_code=127,
                duration_seconds=time.monotonic() - start,
            )


# ─────────────────────────────────────────────────────────────────────────────
# Output parsers
# ─────────────────────────────────────────────────────────────────────────────

# Individual pytest summary patterns — extracted separately for reliability
_PYTEST_PASSED_RE = re.compile(r"\b(\d+)\s+passed\b", re.IGNORECASE)
_PYTEST_FAILED_COUNT_RE = re.compile(r"\b(\d+)\s+failed\b", re.IGNORECASE)
_PYTEST_ERRORS_RE = re.compile(r"\b(\d+)\s+errors?\b", re.IGNORECASE)
_PYTEST_SKIPPED_RE = re.compile(r"\b(\d+)\s+skipped\b", re.IGNORECASE)
# pytest FAILED line: "FAILED tests/test_foo.py::TestBar::test_baz"
_PYTEST_FAILED_RE = re.compile(r"^FAILED\s+(.+)$", re.MULTILINE)

# Jest/npm summary: "Tests: 1 failed, 3 passed, 4 total"
_NPM_SUMMARY_RE = re.compile(
    r"Tests:\s*(?:(\d+) failed,\s*)?(?:(\d+) passed,\s*)?(?:(\d+) total)?",
    re.IGNORECASE,
)


def _parse_output(framework: TestFramework, output: str) -> dict:
    """Parse test output into counts."""
    result: dict = {
        "passed": 0, "failed": 0, "errors": 0, "skipped": 0,
        "total": 0, "failed_tests": [],
    }

    if framework == TestFramework.PYTEST:
        # Extract failed test names
        result["failed_tests"] = _PYTEST_FAILED_RE.findall(output)

        # Extract counts from the last occurrence of each pattern
        def _last_int(pattern: re.Pattern[str], text: str) -> int:
            matches = pattern.findall(text)
            return int(matches[-1]) if matches else 0

        result["passed"] = _last_int(_PYTEST_PASSED_RE, output)
        result["failed"] = _last_int(_PYTEST_FAILED_COUNT_RE, output)
        result["errors"] = _last_int(_PYTEST_ERRORS_RE, output)
        result["skipped"] = _last_int(_PYTEST_SKIPPED_RE, output)

        result["total"] = (
            result["passed"] + result["failed"]
            + result["errors"] + result["skipped"]
        )

    elif framework == TestFramework.NPM:
        match = _NPM_SUMMARY_RE.search(output)
        if match:
            result["failed"] = int(match.group(1) or 0)
            result["passed"] = int(match.group(2) or 0)
            result["total"] = int(match.group(3) or 0)

    return result
