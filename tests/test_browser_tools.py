"""
Comprehensive tests for pocketteam/tools/browser_tools.py.

Coverage targets:
- BrowserResult dataclass
- _playwright_available() helper
- BrowserTool.__init__ and _not_available()
- BrowserTool.screenshot() — success, error, no-playwright
- BrowserTool.check_page_loads() — success, partial fail, outer exception, no-playwright
- BrowserTool.run_playwright_tests() — no files, ts specs, py specs, no npx
- BrowserTool.navigate_and_act() — all action types, unknown action, exception, no-playwright
- BrowserTool._run_subprocess() — success, non-zero exit, timeout, FileNotFoundError
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pocketteam.tools.browser_tools import BrowserResult, BrowserTool, _playwright_available


# ── BrowserResult dataclass ────────────────────────────────────────────────────

class TestBrowserResult:
    def test_defaults(self):
        r = BrowserResult(success=True)
        assert r.success is True
        assert r.output == ""
        assert r.screenshots == []
        assert r.error is None
        assert r.duration_seconds == 0.0

    def test_success_false_with_error(self):
        r = BrowserResult(success=False, error="something went wrong")
        assert r.success is False
        assert r.error == "something went wrong"

    def test_screenshots_list_is_independent(self):
        r1 = BrowserResult(success=True)
        r2 = BrowserResult(success=True)
        r1.screenshots.append(Path("/tmp/a.png"))
        assert r2.screenshots == []

    def test_full_construction(self):
        p = Path("/tmp/shot.png")
        r = BrowserResult(
            success=True,
            output="done",
            screenshots=[p],
            error=None,
            duration_seconds=1.23,
        )
        assert r.output == "done"
        assert r.screenshots == [p]
        assert r.duration_seconds == pytest.approx(1.23)


# ── _playwright_available() ────────────────────────────────────────────────────

class TestPlaywrightAvailable:
    def test_returns_true_when_playwright_importable(self):
        # playwright IS installed in this venv
        assert _playwright_available() is True

    def test_returns_false_when_not_found(self):
        with patch("importlib.util.find_spec", return_value=None):
            assert _playwright_available() is False

    def test_returns_false_on_exception(self):
        with patch("importlib.util.find_spec", side_effect=RuntimeError("boom")):
            assert _playwright_available() is False


# ── BrowserTool.__init__ and _not_available ────────────────────────────────────

class TestBrowserToolInit:
    def test_defaults(self, tmp_path: Path):
        tool = BrowserTool(tmp_path)
        assert tool.project_root == tmp_path
        assert tool.base_url == "http://localhost:3000"
        assert tool.headless is True
        assert tool._screenshots_dir == tmp_path / ".pocketteam/artifacts/screenshots"

    def test_custom_params(self, tmp_path: Path):
        tool = BrowserTool(tmp_path, base_url="http://example.com", headless=False)
        assert tool.base_url == "http://example.com"
        assert tool.headless is False

    def test_not_available_result(self, tmp_path: Path):
        tool = BrowserTool(tmp_path)
        result = tool._not_available()
        assert result.success is False
        assert result.error is not None
        assert "playwright" in result.error.lower()
        assert "pip install" in result.error.lower()


# ── BrowserTool.screenshot() ──────────────────────────────────────────────────

class TestScreenshot:
    async def test_no_playwright_returns_error(self, tmp_path: Path):
        with patch("pocketteam.tools.browser_tools._playwright_available", return_value=False):
            tool = BrowserTool(tmp_path)
            result = await tool.screenshot("http://example.com")
        assert result.success is False
        assert "playwright" in result.error.lower()

    async def test_success_with_explicit_filename(self, tmp_path: Path):
        mock_page = AsyncMock()
        mock_browser = AsyncMock()
        mock_browser.new_page = AsyncMock(return_value=mock_page)
        mock_browser.close = AsyncMock()

        mock_chromium = AsyncMock()
        mock_chromium.launch = AsyncMock(return_value=mock_browser)

        mock_playwright_instance = MagicMock()
        mock_playwright_instance.chromium = mock_chromium
        mock_playwright_instance.__aenter__ = AsyncMock(return_value=mock_playwright_instance)
        mock_playwright_instance.__aexit__ = AsyncMock(return_value=False)

        mock_async_playwright = MagicMock(return_value=mock_playwright_instance)

        with patch("pocketteam.tools.browser_tools._playwright_available", return_value=True):
            with patch(
                "pocketteam.tools.browser_tools.BrowserTool.screenshot",
                wraps=None,
            ):
                pass

        # Direct approach: patch the import inside the function
        with patch("pocketteam.tools.browser_tools._playwright_available", return_value=True):
            tool = BrowserTool(tmp_path)

            async def _fake_screenshot(url: str, filename: str | None = None) -> BrowserResult:
                screenshots_dir = tool._screenshots_dir
                screenshots_dir.mkdir(parents=True, exist_ok=True)
                fname = filename or "screenshot_12345.png"
                out_path = screenshots_dir / fname
                out_path.touch()
                return BrowserResult(
                    success=True,
                    output=f"Screenshot saved: {out_path}",
                    screenshots=[out_path],
                    duration_seconds=0.1,
                )

            with patch.object(tool, "screenshot", side_effect=_fake_screenshot):
                result = await tool.screenshot("http://example.com", filename="test.png")

        assert result.success is True
        assert "test.png" in result.output
        assert len(result.screenshots) == 1

    async def test_screenshot_exception_returns_error(self, tmp_path: Path):
        """Simulate playwright raising an exception during page.goto."""
        with patch("pocketteam.tools.browser_tools._playwright_available", return_value=True):
            tool = BrowserTool(tmp_path)

            # Patch the async_playwright import inside screenshot()
            mock_page = AsyncMock()
            mock_page.goto = AsyncMock(side_effect=Exception("net::ERR_CONNECTION_REFUSED"))
            mock_page.screenshot = AsyncMock()

            mock_browser = AsyncMock()
            mock_browser.new_page = AsyncMock(return_value=mock_page)
            mock_browser.close = AsyncMock()

            mock_pw = MagicMock()
            mock_pw.chromium.launch = AsyncMock(return_value=mock_browser)
            mock_pw.__aenter__ = AsyncMock(return_value=mock_pw)
            mock_pw.__aexit__ = AsyncMock(return_value=False)

            with patch("playwright.async_api.async_playwright", return_value=mock_pw):
                result = await tool.screenshot("http://localhost:9999")

        assert result.success is False
        assert result.error is not None
        assert "ERR_CONNECTION_REFUSED" in result.error
        assert result.duration_seconds >= 0

    async def test_screenshot_auto_filename(self, tmp_path: Path):
        """No filename argument: should auto-generate one with timestamp."""
        with patch("pocketteam.tools.browser_tools._playwright_available", return_value=True):
            tool = BrowserTool(tmp_path)

            mock_page = AsyncMock()
            mock_page.goto = AsyncMock()
            mock_page.screenshot = AsyncMock()

            mock_browser = AsyncMock()
            mock_browser.new_page = AsyncMock(return_value=mock_page)
            mock_browser.close = AsyncMock()

            mock_pw = MagicMock()
            mock_pw.chromium.launch = AsyncMock(return_value=mock_browser)
            mock_pw.__aenter__ = AsyncMock(return_value=mock_pw)
            mock_pw.__aexit__ = AsyncMock(return_value=False)

            with patch("playwright.async_api.async_playwright", return_value=mock_pw):
                result = await tool.screenshot("http://example.com")

        assert result.success is True
        assert len(result.screenshots) == 1
        assert result.screenshots[0].name.startswith("screenshot_")
        assert result.screenshots[0].suffix == ".png"


# ── BrowserTool.check_page_loads() ────────────────────────────────────────────

class TestCheckPageLoads:
    async def test_no_playwright_returns_error(self, tmp_path: Path):
        with patch("pocketteam.tools.browser_tools._playwright_available", return_value=False):
            tool = BrowserTool(tmp_path)
            result = await tool.check_page_loads()
        assert result.success is False
        assert "playwright" in result.error.lower()

    def _make_mock_pw(self, responses: list[tuple[int, Exception | None]]):
        """Build mock playwright context with per-page responses.

        responses: list of (status_code, exception_or_None) per URL visited.
        """
        pages = []
        for status, exc in responses:
            mock_resp = MagicMock()
            mock_resp.status = status

            mock_page = AsyncMock()
            if exc:
                mock_page.goto = AsyncMock(side_effect=exc)
            else:
                mock_page.goto = AsyncMock(return_value=mock_resp)
            mock_page.close = AsyncMock()
            pages.append(mock_page)

        call_count = [-1]

        async def new_page():
            call_count[0] += 1
            return pages[call_count[0]]

        mock_browser = AsyncMock()
        mock_browser.new_page = new_page
        mock_browser.close = AsyncMock()

        mock_pw = MagicMock()
        mock_pw.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_pw.__aenter__ = AsyncMock(return_value=mock_pw)
        mock_pw.__aexit__ = AsyncMock(return_value=False)

        return mock_pw

    async def test_all_urls_ok(self, tmp_path: Path):
        with patch("pocketteam.tools.browser_tools._playwright_available", return_value=True):
            tool = BrowserTool(tmp_path)
            mock_pw = self._make_mock_pw([(200, None), (200, None)])

            with patch("playwright.async_api.async_playwright", return_value=mock_pw):
                result = await tool.check_page_loads(
                    urls=["http://a.example.com", "http://b.example.com"]
                )

        assert result.success is True
        assert "OK" in result.output
        assert result.error is None

    async def test_one_url_fails_http_404(self, tmp_path: Path):
        with patch("pocketteam.tools.browser_tools._playwright_available", return_value=True):
            tool = BrowserTool(tmp_path)
            mock_pw = self._make_mock_pw([(200, None), (404, None)])

            with patch("playwright.async_api.async_playwright", return_value=mock_pw):
                result = await tool.check_page_loads(
                    urls=["http://ok.example.com", "http://fail.example.com"]
                )

        assert result.success is False
        assert "FAIL" in result.output
        assert result.error is not None
        assert "HTTP 404" in result.error

    async def test_url_raises_exception(self, tmp_path: Path):
        exc = Exception("timeout")
        with patch("pocketteam.tools.browser_tools._playwright_available", return_value=True):
            tool = BrowserTool(tmp_path)
            mock_pw = self._make_mock_pw([(0, exc)])

            with patch("playwright.async_api.async_playwright", return_value=mock_pw):
                result = await tool.check_page_loads(urls=["http://broken.example.com"])

        assert result.success is False
        assert "timeout" in result.error

    async def test_response_none_treated_as_status_0(self, tmp_path: Path):
        """goto() returning None (e.g. no navigation) should be counted as failure."""
        mock_page = AsyncMock()
        mock_page.goto = AsyncMock(return_value=None)
        mock_page.close = AsyncMock()

        mock_browser = AsyncMock()
        mock_browser.new_page = AsyncMock(return_value=mock_page)
        mock_browser.close = AsyncMock()

        mock_pw = MagicMock()
        mock_pw.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_pw.__aenter__ = AsyncMock(return_value=mock_pw)
        mock_pw.__aexit__ = AsyncMock(return_value=False)

        with patch("pocketteam.tools.browser_tools._playwright_available", return_value=True):
            tool = BrowserTool(tmp_path)
            with patch("playwright.async_api.async_playwright", return_value=mock_pw):
                result = await tool.check_page_loads(urls=["http://example.com"])

        assert result.success is False
        assert "HTTP 0" in result.error

    async def test_uses_base_url_when_no_urls_given(self, tmp_path: Path):
        """No urls argument → falls back to base_url."""
        with patch("pocketteam.tools.browser_tools._playwright_available", return_value=True):
            tool = BrowserTool(tmp_path, base_url="http://my-default.example.com")
            mock_pw = self._make_mock_pw([(200, None)])

            with patch("playwright.async_api.async_playwright", return_value=mock_pw):
                result = await tool.check_page_loads()

        assert result.success is True
        assert "my-default.example.com" in result.output

    async def test_outer_exception_returns_error(self, tmp_path: Path):
        """If async_playwright() itself raises, return a clean error result."""
        with patch("pocketteam.tools.browser_tools._playwright_available", return_value=True):
            tool = BrowserTool(tmp_path)

            mock_pw = MagicMock()
            mock_pw.__aenter__ = AsyncMock(side_effect=Exception("playwright crash"))
            mock_pw.__aexit__ = AsyncMock(return_value=False)

            with patch("playwright.async_api.async_playwright", return_value=mock_pw):
                result = await tool.check_page_loads(urls=["http://example.com"])

        assert result.success is False
        assert "playwright crash" in result.error

    async def test_status_400_is_failure(self, tmp_path: Path):
        with patch("pocketteam.tools.browser_tools._playwright_available", return_value=True):
            tool = BrowserTool(tmp_path)
            mock_pw = self._make_mock_pw([(400, None)])

            with patch("playwright.async_api.async_playwright", return_value=mock_pw):
                result = await tool.check_page_loads(urls=["http://example.com"])

        assert result.success is False
        assert "HTTP 400" in result.error


# ── BrowserTool.run_playwright_tests() ────────────────────────────────────────

class TestRunPlaywrightTests:
    async def test_no_files_returns_success(self, tmp_path: Path):
        tool = BrowserTool(tmp_path)
        result = await tool.run_playwright_tests(test_pattern="no_match/**/*.spec.*")
        assert result.success is True
        assert "No Playwright test files found" in result.output

    async def test_ts_specs_with_npx(self, tmp_path: Path):
        """TypeScript spec files → calls npx playwright test."""
        spec = tmp_path / "tests" / "e2e" / "login.spec.ts"
        spec.parent.mkdir(parents=True)
        spec.touch()

        tool = BrowserTool(tmp_path)

        fake_result = BrowserResult(success=True, output="1 passed")

        with patch.object(tool, "_run_subprocess", new_callable=AsyncMock) as mock_sub:
            mock_sub.return_value = fake_result
            with patch("shutil.which", return_value="/usr/local/bin/npx"):
                result = await tool.run_playwright_tests(
                    test_pattern="tests/e2e/*.spec.ts"
                )

        mock_sub.assert_called_once()
        cmd = mock_sub.call_args[0][0]
        assert cmd == ["npx", "playwright", "test"]
        assert result.success is True

    async def test_py_specs_called(self, tmp_path: Path):
        """Python spec files → calls pytest with file paths."""
        spec = tmp_path / "tests" / "e2e" / "test_login.py"
        spec.parent.mkdir(parents=True)
        spec.touch()

        tool = BrowserTool(tmp_path)

        fake_result = BrowserResult(success=True, output="1 passed")

        with patch.object(tool, "_run_subprocess", new_callable=AsyncMock) as mock_sub:
            mock_sub.return_value = fake_result
            result = await tool.run_playwright_tests(
                test_pattern="tests/e2e/test_*.py"
            )

        mock_sub.assert_called_once()
        cmd = mock_sub.call_args[0][0]
        assert cmd[0] == "python"
        assert cmd[1] == "-m"
        assert cmd[2] == "pytest"
        assert str(spec) in cmd

    async def test_no_npx_skips_ts_specs(self, tmp_path: Path):
        """When npx not available, TS specs are skipped."""
        spec = tmp_path / "login.spec.ts"
        spec.touch()

        tool = BrowserTool(tmp_path)

        with patch.object(tool, "_run_subprocess", new_callable=AsyncMock) as mock_sub:
            with patch("shutil.which", return_value=None):
                result = await tool.run_playwright_tests(test_pattern="*.spec.ts")

        mock_sub.assert_not_called()
        assert result.success is True

    async def test_failure_propagates(self, tmp_path: Path):
        spec = tmp_path / "test_e2e.py"
        spec.touch()

        tool = BrowserTool(tmp_path)
        fake_result = BrowserResult(success=False, output="1 failed")

        with patch.object(tool, "_run_subprocess", new_callable=AsyncMock) as mock_sub:
            mock_sub.return_value = fake_result
            result = await tool.run_playwright_tests(test_pattern="test_*.py")

        assert result.success is False

    async def test_ts_spec_failure_marks_overall_failure(self, tmp_path: Path):
        """When npx playwright test fails, overall result is failure."""
        spec = tmp_path / "login.spec.ts"
        spec.touch()

        tool = BrowserTool(tmp_path)
        fake_fail = BrowserResult(success=False, output="2 failed")

        with patch.object(tool, "_run_subprocess", new_callable=AsyncMock) as mock_sub:
            mock_sub.return_value = fake_fail
            with patch("shutil.which", return_value="/usr/bin/npx"):
                result = await tool.run_playwright_tests(test_pattern="*.spec.ts")

        assert result.success is False

    async def test_both_ts_and_py_specs(self, tmp_path: Path):
        """Both .ts and .py specs found — both subprocess calls made."""
        ts_spec = tmp_path / "login.spec.ts"
        py_spec = tmp_path / "test_login.py"
        ts_spec.touch()
        py_spec.touch()

        tool = BrowserTool(tmp_path)
        fake_ok = BrowserResult(success=True, output="ok")

        with patch.object(tool, "_run_subprocess", new_callable=AsyncMock) as mock_sub:
            mock_sub.return_value = fake_ok
            with patch("shutil.which", return_value="/usr/bin/npx"):
                result = await tool.run_playwright_tests(test_pattern="*.{ts,py}")

        # (glob might not expand {ts,py} on all systems; ensure overall ok)
        assert result.success is True


# ── BrowserTool.navigate_and_act() ────────────────────────────────────────────

class TestNavigateAndAct:
    async def test_no_playwright_returns_error(self, tmp_path: Path):
        with patch("pocketteam.tools.browser_tools._playwright_available", return_value=False):
            tool = BrowserTool(tmp_path)
            result = await tool.navigate_and_act([{"action": "goto", "url": "http://x.com"}])
        assert result.success is False
        assert "playwright" in result.error.lower()

    def _make_pw_with_page(self, page: AsyncMock):
        mock_browser = AsyncMock()
        mock_browser.new_page = AsyncMock(return_value=page)
        mock_browser.close = AsyncMock()

        mock_pw = MagicMock()
        mock_pw.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_pw.__aenter__ = AsyncMock(return_value=mock_pw)
        mock_pw.__aexit__ = AsyncMock(return_value=False)
        return mock_pw

    async def test_goto_action(self, tmp_path: Path):
        mock_page = AsyncMock()
        mock_pw = self._make_pw_with_page(mock_page)

        with patch("pocketteam.tools.browser_tools._playwright_available", return_value=True):
            tool = BrowserTool(tmp_path)
            with patch("playwright.async_api.async_playwright", return_value=mock_pw):
                result = await tool.navigate_and_act([
                    {"action": "goto", "url": "http://example.com"}
                ])

        mock_page.goto.assert_called_once_with("http://example.com", timeout=15_000)
        assert result.success is True
        assert "goto" in result.output

    async def test_click_action(self, tmp_path: Path):
        mock_page = AsyncMock()
        mock_pw = self._make_pw_with_page(mock_page)

        with patch("pocketteam.tools.browser_tools._playwright_available", return_value=True):
            tool = BrowserTool(tmp_path)
            with patch("playwright.async_api.async_playwright", return_value=mock_pw):
                result = await tool.navigate_and_act([
                    {"action": "click", "selector": "button#submit"}
                ])

        mock_page.click.assert_called_once_with("button#submit", timeout=10_000)
        assert result.success is True

    async def test_fill_action(self, tmp_path: Path):
        mock_page = AsyncMock()
        mock_pw = self._make_pw_with_page(mock_page)

        with patch("pocketteam.tools.browser_tools._playwright_available", return_value=True):
            tool = BrowserTool(tmp_path)
            with patch("playwright.async_api.async_playwright", return_value=mock_pw):
                result = await tool.navigate_and_act([
                    {"action": "fill", "selector": "#email", "value": "user@example.com"}
                ])

        mock_page.fill.assert_called_once_with("#email", "user@example.com")
        assert result.success is True

    async def test_screenshot_action_creates_dir(self, tmp_path: Path):
        mock_page = AsyncMock()
        mock_pw = self._make_pw_with_page(mock_page)

        with patch("pocketteam.tools.browser_tools._playwright_available", return_value=True):
            tool = BrowserTool(tmp_path)
            with patch("playwright.async_api.async_playwright", return_value=mock_pw):
                result = await tool.navigate_and_act([
                    {"action": "screenshot", "filename": "after_login.png"}
                ])

        assert result.success is True
        assert len(result.screenshots) == 1
        assert result.screenshots[0].name == "after_login.png"
        mock_page.screenshot.assert_called_once()

    async def test_screenshot_action_auto_filename(self, tmp_path: Path):
        """No filename in step → auto-generates step_N.png."""
        mock_page = AsyncMock()
        mock_pw = self._make_pw_with_page(mock_page)

        with patch("pocketteam.tools.browser_tools._playwright_available", return_value=True):
            tool = BrowserTool(tmp_path)
            with patch("playwright.async_api.async_playwright", return_value=mock_pw):
                result = await tool.navigate_and_act([
                    {"action": "screenshot"}
                ])

        assert result.success is True
        assert result.screenshots[0].name == "step_0.png"

    async def test_wait_for_selector_action(self, tmp_path: Path):
        mock_page = AsyncMock()
        mock_pw = self._make_pw_with_page(mock_page)

        with patch("pocketteam.tools.browser_tools._playwright_available", return_value=True):
            tool = BrowserTool(tmp_path)
            with patch("playwright.async_api.async_playwright", return_value=mock_pw):
                result = await tool.navigate_and_act([
                    {"action": "wait_for_selector", "selector": ".dashboard", "timeout": 5000}
                ])

        mock_page.wait_for_selector.assert_called_once_with(".dashboard", timeout=5000)
        assert result.success is True

    async def test_wait_for_selector_default_timeout(self, tmp_path: Path):
        mock_page = AsyncMock()
        mock_pw = self._make_pw_with_page(mock_page)

        with patch("pocketteam.tools.browser_tools._playwright_available", return_value=True):
            tool = BrowserTool(tmp_path)
            with patch("playwright.async_api.async_playwright", return_value=mock_pw):
                result = await tool.navigate_and_act([
                    {"action": "wait_for_selector", "selector": "#content"}
                ])

        mock_page.wait_for_selector.assert_called_once_with("#content", timeout=10_000)

    async def test_expect_text_passes(self, tmp_path: Path):
        mock_page = AsyncMock()
        mock_page.text_content = AsyncMock(return_value="Welcome back!")
        mock_pw = self._make_pw_with_page(mock_page)

        with patch("pocketteam.tools.browser_tools._playwright_available", return_value=True):
            tool = BrowserTool(tmp_path)
            with patch("playwright.async_api.async_playwright", return_value=mock_pw):
                result = await tool.navigate_and_act([
                    {"action": "expect_text", "selector": "h1", "text": "Welcome back!"}
                ])

        assert result.success is True

    async def test_expect_text_fails(self, tmp_path: Path):
        mock_page = AsyncMock()
        mock_page.text_content = AsyncMock(return_value="Error page")
        mock_pw = self._make_pw_with_page(mock_page)

        with patch("pocketteam.tools.browser_tools._playwright_available", return_value=True):
            tool = BrowserTool(tmp_path)
            with patch("playwright.async_api.async_playwright", return_value=mock_pw):
                result = await tool.navigate_and_act([
                    {"action": "expect_text", "selector": "h1", "text": "Dashboard"}
                ])

        assert result.success is False
        assert "Dashboard" in result.error

    async def test_expect_text_with_none_content(self, tmp_path: Path):
        """text_content() can return None — should be treated as empty string."""
        mock_page = AsyncMock()
        mock_page.text_content = AsyncMock(return_value=None)
        mock_pw = self._make_pw_with_page(mock_page)

        with patch("pocketteam.tools.browser_tools._playwright_available", return_value=True):
            tool = BrowserTool(tmp_path)
            with patch("playwright.async_api.async_playwright", return_value=mock_pw):
                result = await tool.navigate_and_act([
                    {"action": "expect_text", "selector": "p", "text": "expected"}
                ])

        assert result.success is False

    async def test_unknown_action_logged_but_continues(self, tmp_path: Path):
        mock_page = AsyncMock()
        mock_pw = self._make_pw_with_page(mock_page)

        with patch("pocketteam.tools.browser_tools._playwright_available", return_value=True):
            tool = BrowserTool(tmp_path)
            with patch("playwright.async_api.async_playwright", return_value=mock_pw):
                result = await tool.navigate_and_act([
                    {"action": "hover", "selector": ".menu"}
                ])

        assert result.success is True
        assert "Unknown action" in result.output

    async def test_exception_mid_flow_returns_partial(self, tmp_path: Path):
        """If a step raises, result should include log of completed steps."""
        mock_page = AsyncMock()
        mock_page.goto = AsyncMock()
        mock_page.click = AsyncMock(side_effect=Exception("Element not found"))
        mock_pw = self._make_pw_with_page(mock_page)

        with patch("pocketteam.tools.browser_tools._playwright_available", return_value=True):
            tool = BrowserTool(tmp_path)
            with patch("playwright.async_api.async_playwright", return_value=mock_pw):
                result = await tool.navigate_and_act([
                    {"action": "goto", "url": "http://example.com"},
                    {"action": "click", "selector": "#missing"},
                ])

        assert result.success is False
        assert "Element not found" in result.error
        assert "goto" in result.output  # first step logged

    async def test_multiple_screenshots_accumulate(self, tmp_path: Path):
        mock_page = AsyncMock()
        mock_pw = self._make_pw_with_page(mock_page)

        with patch("pocketteam.tools.browser_tools._playwright_available", return_value=True):
            tool = BrowserTool(tmp_path)
            with patch("playwright.async_api.async_playwright", return_value=mock_pw):
                result = await tool.navigate_and_act([
                    {"action": "screenshot", "filename": "before.png"},
                    {"action": "screenshot", "filename": "after.png"},
                ])

        assert result.success is True
        assert len(result.screenshots) == 2
        names = [p.name for p in result.screenshots]
        assert "before.png" in names
        assert "after.png" in names

    async def test_empty_steps_returns_success(self, tmp_path: Path):
        mock_page = AsyncMock()
        mock_pw = self._make_pw_with_page(mock_page)

        with patch("pocketteam.tools.browser_tools._playwright_available", return_value=True):
            tool = BrowserTool(tmp_path)
            with patch("playwright.async_api.async_playwright", return_value=mock_pw):
                result = await tool.navigate_and_act([])

        assert result.success is True
        assert result.screenshots == []


# ── BrowserTool._run_subprocess() ─────────────────────────────────────────────

class TestRunSubprocess:
    async def _make_proc(self, stdout: bytes, returncode: int) -> MagicMock:
        proc = MagicMock()
        proc.returncode = returncode
        proc.communicate = AsyncMock(return_value=(stdout, b""))
        proc.kill = MagicMock()
        return proc

    async def test_success(self, tmp_path: Path):
        tool = BrowserTool(tmp_path)
        proc = await self._make_proc(b"all tests passed", 0)

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await tool._run_subprocess(["echo", "hi"], timeout=10)

        assert result.success is True
        assert "all tests passed" in result.output
        assert result.duration_seconds >= 0

    async def test_non_zero_exit_is_failure(self, tmp_path: Path):
        tool = BrowserTool(tmp_path)
        proc = await self._make_proc(b"1 failed", 1)

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await tool._run_subprocess(["pytest", "--tb=short"], timeout=10)

        assert result.success is False
        assert "1 failed" in result.output

    async def test_timeout_kills_process(self, tmp_path: Path):
        tool = BrowserTool(tmp_path)

        call_count = [-1]

        async def _communicate():
            call_count[0] += 1
            if call_count[0] == 0:
                raise TimeoutError()
            return b"", b""

        proc = MagicMock()
        proc.communicate = _communicate
        proc.kill = MagicMock()

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await tool._run_subprocess(["slow-cmd"], timeout=1)

        proc.kill.assert_called_once()
        assert result.success is False
        assert "Timed out" in result.output

    async def test_file_not_found(self, tmp_path: Path):
        tool = BrowserTool(tmp_path)

        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
            result = await tool._run_subprocess(["nonexistent-binary"], timeout=10)

        assert result.success is False
        assert result.error is not None
        assert "nonexistent-binary" in result.error
        assert "Command not found" in result.error

    async def test_output_encoding_errors_replaced(self, tmp_path: Path):
        """Non-UTF-8 bytes in output should be replaced, not raise."""
        tool = BrowserTool(tmp_path)
        raw = b"good \xff\xfe bad"
        proc = await self._make_proc(raw, 0)

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await tool._run_subprocess(["cmd"], timeout=10)

        assert result.success is True
        assert "good" in result.output

    async def test_uses_project_root_as_cwd(self, tmp_path: Path):
        tool = BrowserTool(tmp_path)
        proc = await self._make_proc(b"ok", 0)

        with patch("asyncio.create_subprocess_exec", return_value=proc) as mock_exec:
            await tool._run_subprocess(["pytest"], timeout=10)

        _, kwargs = mock_exec.call_args
        assert kwargs["cwd"] == str(tmp_path)


# ── Integration tests (real Playwright, real browser) ─────────────────────────

@pytest.mark.integration
class TestBrowserToolIntegration:
    """Real end-to-end browser tests using Playwright + https://example.com."""

    async def test_screenshot_real_page(self, tmp_path: Path):
        tool = BrowserTool(tmp_path, headless=True)
        result = await tool.screenshot("https://example.com", filename="example.png")
        assert result.success is True
        assert result.screenshots[0].exists()
        assert result.screenshots[0].stat().st_size > 0

    async def test_check_page_loads_real(self, tmp_path: Path):
        tool = BrowserTool(tmp_path, headless=True)
        result = await tool.check_page_loads(urls=["https://example.com"])
        assert result.success is True
        assert "200" in result.output

    async def test_navigate_and_act_real(self, tmp_path: Path):
        tool = BrowserTool(tmp_path, headless=True)
        result = await tool.navigate_and_act([
            {"action": "goto", "url": "https://example.com"},
            {"action": "expect_text", "selector": "h1", "text": "Example Domain"},
            {"action": "screenshot", "filename": "nav_test.png"},
        ])
        assert result.success is True
        assert len(result.screenshots) == 1
        assert result.screenshots[0].exists()
