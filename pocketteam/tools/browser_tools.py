"""
BrowserTools — Playwright-based browser testing.

Used by QA sub-agent for UI/E2E testing.
Playwright is an optional dependency — if not installed, methods return
a clear error result instead of raising ImportError.

Capabilities:
- screenshot(url)     → take screenshot of a page
- check_page_loads()  → verify a list of URLs return HTTP 200
- run_playwright_tests() → execute .spec.ts / test_*.py playwright files
- navigate_and_act()  → headless interaction flow (click, fill, submit)
"""

from __future__ import annotations

import asyncio
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class BrowserResult:
    """Result of a browser tool operation."""
    success: bool
    output: str = ""
    screenshots: list[Path] = field(default_factory=list)
    error: str | None = None
    duration_seconds: float = 0.0


def _playwright_available() -> bool:
    """Check if Playwright is installed without importing it at module level."""
    try:
        import importlib
        return importlib.util.find_spec("playwright") is not None
    except Exception:
        return False


class BrowserTool:
    """
    Headless browser tool backed by Playwright.

    If Playwright is not installed, all methods return a BrowserResult
    with success=False and a clear installation message — no crashes.
    """

    def __init__(
        self,
        project_root: Path,
        base_url: str = "http://localhost:3000",
        headless: bool = True,
    ) -> None:
        self.project_root = project_root
        self.base_url = base_url
        self.headless = headless
        self._screenshots_dir = project_root / ".pocketteam/artifacts/screenshots"

    def _not_available(self) -> BrowserResult:
        return BrowserResult(
            success=False,
            error=(
                "Playwright is not installed. "
                "Run: pip install playwright && playwright install chromium"
            ),
        )

    async def screenshot(
        self,
        url: str,
        filename: str | None = None,
    ) -> BrowserResult:
        """Take a screenshot of a URL. Returns path to the saved file."""
        if not _playwright_available():
            return self._not_available()

        start = time.monotonic()
        try:
            from playwright.async_api import async_playwright  # type: ignore[import]

            self._screenshots_dir.mkdir(parents=True, exist_ok=True)
            fname = filename or f"screenshot_{int(time.time())}.png"
            out_path = self._screenshots_dir / fname

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=self.headless)
                page = await browser.new_page()
                await page.goto(url, timeout=15_000)
                await page.screenshot(path=str(out_path))
                await browser.close()

            return BrowserResult(
                success=True,
                output=f"Screenshot saved: {out_path}",
                screenshots=[out_path],
                duration_seconds=time.monotonic() - start,
            )
        except Exception as exc:
            return BrowserResult(
                success=False,
                error=str(exc),
                duration_seconds=time.monotonic() - start,
            )

    async def check_page_loads(
        self,
        urls: list[str] | None = None,
        timeout_ms: int = 10_000,
    ) -> BrowserResult:
        """
        Verify that all given URLs load without error.
        Falls back to base_url if no URLs given.
        """
        if not _playwright_available():
            return self._not_available()

        check_urls = urls or [self.base_url]
        start = time.monotonic()
        failed: list[str] = []
        lines: list[str] = []

        try:
            from playwright.async_api import async_playwright  # type: ignore[import]

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=self.headless)
                for url in check_urls:
                    try:
                        page = await browser.new_page()
                        response = await page.goto(url, timeout=timeout_ms)
                        status = response.status if response else 0
                        if status >= 400 or status == 0:
                            failed.append(f"{url} → HTTP {status}")
                            lines.append(f"FAIL {url} (HTTP {status})")
                        else:
                            lines.append(f"OK   {url} (HTTP {status})")
                        await page.close()
                    except Exception as exc:
                        failed.append(f"{url} → {exc}")
                        lines.append(f"FAIL {url} ({exc})")
                await browser.close()

        except Exception as exc:
            return BrowserResult(
                success=False,
                error=str(exc),
                duration_seconds=time.monotonic() - start,
            )

        return BrowserResult(
            success=len(failed) == 0,
            output="\n".join(lines),
            error="\n".join(failed) if failed else None,
            duration_seconds=time.monotonic() - start,
        )

    async def run_playwright_tests(
        self,
        test_pattern: str = "tests/e2e/**/*.spec.*",
        timeout: int = 120,
    ) -> BrowserResult:
        """
        Run Playwright test files matching a glob pattern.
        Delegates to `npx playwright test` for .spec.ts files,
        or `pytest` for .py files.
        """
        start = time.monotonic()

        # Check for npx playwright
        import shutil
        spec_files = list(self.project_root.glob(test_pattern))
        if not spec_files:
            return BrowserResult(
                success=True,
                output=f"No Playwright test files found matching: {test_pattern}",
                duration_seconds=time.monotonic() - start,
            )

        # Prefer npx playwright for .spec.ts, fallback to pytest for .spec.py
        ts_specs = [f for f in spec_files if f.suffix in (".ts", ".js")]
        py_specs = [f for f in spec_files if f.suffix == ".py"]

        outputs: list[str] = []
        success = True

        if ts_specs and shutil.which("npx"):
            result = await self._run_subprocess(
                ["npx", "playwright", "test"],
                timeout=timeout,
            )
            outputs.append(result.output)
            if not result.success:
                success = False

        if py_specs:
            result = await self._run_subprocess(
                [sys.executable, "-m", "pytest"] + [str(f) for f in py_specs],
                timeout=timeout,
            )
            outputs.append(result.output)
            if not result.success:
                success = False

        return BrowserResult(
            success=success,
            output="\n\n".join(outputs),
            duration_seconds=time.monotonic() - start,
        )

    async def navigate_and_act(self, steps: list[dict[str, Any]]) -> BrowserResult:
        """
        Execute a sequence of browser actions.

        Each step is a dict: {"action": "goto|click|fill|screenshot", ...args}

        Example:
          [
            {"action": "goto", "url": "http://localhost:3000/login"},
            {"action": "fill", "selector": "#email", "value": "test@example.com"},
            {"action": "fill", "selector": "#password", "value": "secret"},
            {"action": "click", "selector": "button[type=submit]"},
            {"action": "screenshot", "filename": "after_login.png"},
          ]
        """
        if not _playwright_available():
            return self._not_available()

        start = time.monotonic()
        screenshots: list[Path] = []
        log: list[str] = []

        try:
            from playwright.async_api import async_playwright  # type: ignore[import]

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=self.headless)
                page = await browser.new_page()

                for step in steps:
                    action = step.get("action", "")
                    log.append(f"→ {action}")

                    if action == "goto":
                        await page.goto(step["url"], timeout=15_000)
                    elif action == "click":
                        await page.click(step["selector"], timeout=10_000)
                    elif action == "fill":
                        await page.fill(step["selector"], step["value"])
                    elif action == "screenshot":
                        self._screenshots_dir.mkdir(parents=True, exist_ok=True)
                        fname = step.get("filename", f"step_{len(screenshots)}.png")
                        path = self._screenshots_dir / fname
                        await page.screenshot(path=str(path))
                        screenshots.append(path)
                    elif action == "wait_for_selector":
                        await page.wait_for_selector(
                            step["selector"],
                            timeout=step.get("timeout", 10_000),
                        )
                    elif action == "expect_text":
                        content = await page.text_content(step["selector"])
                        expected = step["text"]
                        if expected not in (content or ""):
                            raise AssertionError(
                                f"Expected '{expected}' in '{content}'"
                            )
                    else:
                        log.append(f"  Unknown action: {action}")

                await browser.close()

        except Exception as exc:
            return BrowserResult(
                success=False,
                output="\n".join(log),
                screenshots=screenshots,
                error=str(exc),
                duration_seconds=time.monotonic() - start,
            )

        return BrowserResult(
            success=True,
            output="\n".join(log),
            screenshots=screenshots,
            duration_seconds=time.monotonic() - start,
        )

    async def _run_subprocess(self, cmd: list[str], timeout: int) -> BrowserResult:
        """Helper: run a subprocess and return its output."""
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
                return BrowserResult(
                    success=False,
                    output=f"Timed out after {timeout}s",
                    duration_seconds=time.monotonic() - start,
                )

            output = stdout.decode("utf-8", errors="replace")
            return BrowserResult(
                success=(proc.returncode == 0),
                output=output,
                duration_seconds=time.monotonic() - start,
            )
        except FileNotFoundError:
            return BrowserResult(
                success=False,
                error=f"Command not found: {cmd[0]}",
                duration_seconds=time.monotonic() - start,
            )
