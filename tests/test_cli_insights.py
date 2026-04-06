"""
Tests for `pocketteam insights` CLI group (Wave 2b — Auto-Insights Self-Healing).

TDD: these tests are written before the implementation. Run them first to confirm
they FAIL, then implement the commands to make them GREEN.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from pocketteam.cli import main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_project(tmp_path: Path, *, enabled: bool = False, schedule: str = "0 22 * * *",
                  last_run: str | None = None, chat_id: str = "") -> None:
    """Write a minimal .pocketteam/config.yaml for the given options."""
    pt_dir = tmp_path / ".pocketteam"
    pt_dir.mkdir(parents=True, exist_ok=True)
    cfg_text = f"""\
project:
  name: test-project
  health_url: ''
insights:
  enabled: {str(enabled).lower()}
  schedule: '{schedule}'
  last_run: {last_run if last_run else 'null'}
  telegram_notify: false
  auto_apply: false
telegram:
  chat_id: '{chat_id}'
  bot_token: ''
"""
    (pt_dir / "config.yaml").write_text(cfg_text)


# ---------------------------------------------------------------------------
# Group registration
# ---------------------------------------------------------------------------

class TestInsightsGroupRegistered:
    def test_insights_group_exists(self):
        """The `insights` group is registered under the main CLI."""
        runner = CliRunner()
        result = runner.invoke(main, ["insights", "--help"])
        assert result.exit_code == 0
        assert "insights" in result.output.lower() or "Auto-Insights" in result.output

    def test_insights_help_shows_subcommands(self):
        """Help output lists on, off, status, run sub-commands."""
        runner = CliRunner()
        result = runner.invoke(main, ["insights", "--help"])
        assert result.exit_code == 0
        for cmd in ("on", "off", "status", "run"):
            assert cmd in result.output


# ---------------------------------------------------------------------------
# pocketteam insights on
# ---------------------------------------------------------------------------

class TestInsightsOn:
    @pytest.fixture(autouse=True)
    def mock_scheduler(self, monkeypatch):
        """Prevent install_scheduler from writing real plists or calling launchctl."""
        import pocketteam.insights_scheduler as sched_mod
        import pocketteam.cli as cli_mod
        monkeypatch.setattr(sched_mod, "install_scheduler", lambda root, cron: True)
        monkeypatch.setattr(sched_mod, "uninstall_scheduler", lambda root: True)
        monkeypatch.setattr(cli_mod, "insights_scheduler", sched_mod)
        # Prevent interactive wizard from blocking tests that don't supply input
        monkeypatch.setattr(cli_mod, "_schedule_wizard", lambda con: "0 22 * * *")

    def test_on_enables_insights(self, tmp_path, monkeypatch):
        """'insights on' sets enabled=True in config."""
        _make_project(tmp_path, enabled=False)
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        result = runner.invoke(main, ["insights", "on"])

        assert result.exit_code == 0
        assert "enabled" in result.output.lower()

        # Verify persisted in config
        from pocketteam.config import load_config
        cfg = load_config(tmp_path)
        assert cfg.insights.enabled is True

    def test_on_custom_cron(self, tmp_path, monkeypatch):
        """'insights on --cron' persists the custom schedule."""
        _make_project(tmp_path, enabled=False)
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        result = runner.invoke(main, ["insights", "on", "--cron", "0 8 * * *"])

        assert result.exit_code == 0
        assert "0 8 * * *" in result.output

        from pocketteam.config import load_config
        cfg = load_config(tmp_path)
        assert cfg.insights.schedule == "0 8 * * *"

    def test_on_shows_scheduler_feedback(self, tmp_path, monkeypatch):
        """'insights on' shows OS scheduler registration feedback."""
        _make_project(tmp_path)
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        result = runner.invoke(main, ["insights", "on"])

        assert result.exit_code == 0
        # Should mention scheduler registration or run hint — not manual /schedule create
        assert (
            "scheduler" in result.output.lower()
            or "pocketteam insights run" in result.output
            or "registered" in result.output.lower()
        )
        # Must NOT suggest manual claude /schedule create command
        assert "claude /schedule create" not in result.output

    def test_on_sets_telegram_notify_when_chat_id_present(self, tmp_path, monkeypatch):
        """'insights on' sets telegram_notify=True when telegram.chat_id is configured."""
        _make_project(tmp_path, chat_id="12345")
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        runner.invoke(main, ["insights", "on"])

        from pocketteam.config import load_config
        cfg = load_config(tmp_path)
        assert cfg.insights.telegram_notify is True

    def test_on_leaves_telegram_notify_false_when_no_chat_id(self, tmp_path, monkeypatch):
        """'insights on' leaves telegram_notify=False when no chat_id is configured."""
        _make_project(tmp_path, chat_id="")
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        runner.invoke(main, ["insights", "on"])

        from pocketteam.config import load_config
        cfg = load_config(tmp_path)
        assert cfg.insights.telegram_notify is False


# ---------------------------------------------------------------------------
# pocketteam insights off
# ---------------------------------------------------------------------------

class TestInsightsOff:
    @pytest.fixture(autouse=True)
    def mock_scheduler(self, monkeypatch):
        """Prevent uninstall_scheduler from calling launchctl."""
        import pocketteam.insights_scheduler as sched_mod
        import pocketteam.cli as cli_mod
        monkeypatch.setattr(sched_mod, "install_scheduler", lambda root, cron: True)
        monkeypatch.setattr(sched_mod, "uninstall_scheduler", lambda root: True)
        monkeypatch.setattr(cli_mod, "insights_scheduler", sched_mod)

    def test_off_disables_insights(self, tmp_path, monkeypatch):
        """'insights off' sets enabled=False in config."""
        _make_project(tmp_path, enabled=True)
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        result = runner.invoke(main, ["insights", "off"])

        assert result.exit_code == 0
        assert "disabled" in result.output.lower()

        from pocketteam.config import load_config
        cfg = load_config(tmp_path)
        assert cfg.insights.enabled is False

    def test_off_shows_scheduler_feedback(self, tmp_path, monkeypatch):
        """'insights off' shows OS scheduler removal feedback (not manual instructions)."""
        _make_project(tmp_path, enabled=True)
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        result = runner.invoke(main, ["insights", "off"])

        assert result.exit_code == 0
        # Should mention scheduler or removal — not manual claude.ai instructions
        assert (
            "scheduler" in result.output.lower()
            or "removed" in result.output.lower()
            or "disabled" in result.output.lower()
        )
        # Must NOT show manual claude.ai/code/scheduled instructions
        assert "claude.ai/code/scheduled" not in result.output


# ---------------------------------------------------------------------------
# pocketteam insights status
# ---------------------------------------------------------------------------

class TestInsightsStatus:
    def test_status_shows_enabled_field(self, tmp_path, monkeypatch):
        """'insights status' shows whether insights are enabled."""
        _make_project(tmp_path, enabled=True)
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        result = runner.invoke(main, ["insights", "status"])

        assert result.exit_code == 0
        assert "Yes" in result.output or "enabled" in result.output.lower()

    def test_status_shows_disabled(self, tmp_path, monkeypatch):
        """'insights status' shows 'No' when disabled."""
        _make_project(tmp_path, enabled=False)
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        result = runner.invoke(main, ["insights", "status"])

        assert result.exit_code == 0
        assert "No" in result.output

    def test_status_shows_schedule(self, tmp_path, monkeypatch):
        """'insights status' shows the cron schedule."""
        _make_project(tmp_path, schedule="0 8 * * 1")
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        result = runner.invoke(main, ["insights", "status"])

        assert result.exit_code == 0
        assert "0 8 * * 1" in result.output

    def test_status_shows_never_when_no_last_run(self, tmp_path, monkeypatch):
        """'insights status' shows 'Never' when last_run is null."""
        _make_project(tmp_path, last_run=None)
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        result = runner.invoke(main, ["insights", "status"])

        assert result.exit_code == 0
        assert "Never" in result.output

    def test_status_shows_last_run_when_set(self, tmp_path, monkeypatch):
        """'insights status' shows last_run timestamp when present."""
        _make_project(tmp_path, last_run="2026-03-30T22:00:00Z")
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        result = runner.invoke(main, ["insights", "status"])

        assert result.exit_code == 0
        assert "2026-03-30" in result.output

    def test_status_shows_no_reports_when_dir_absent(self, tmp_path, monkeypatch):
        """'insights status' gracefully handles missing insights dir."""
        _make_project(tmp_path)
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        result = runner.invoke(main, ["insights", "status"])

        assert result.exit_code == 0
        assert "No reports yet" in result.output

    def test_status_lists_recent_reports(self, tmp_path, monkeypatch):
        """'insights status' lists up to 5 recent .md reports when present."""
        _make_project(tmp_path)
        insights_dir = tmp_path / ".pocketteam" / "artifacts" / "insights"
        insights_dir.mkdir(parents=True)
        for i in range(3):
            (insights_dir / f"report-2026-03-{20+i:02d}.md").write_text(f"# Report {i}")
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        result = runner.invoke(main, ["insights", "status"])

        assert result.exit_code == 0
        assert "report-2026-03" in result.output

    def test_status_shows_auto_apply_always_no(self, tmp_path, monkeypatch):
        """'insights status' always shows auto-apply as requiring CEO approval."""
        _make_project(tmp_path)
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        result = runner.invoke(main, ["insights", "status"])

        assert result.exit_code == 0
        assert "CEO" in result.output or "approval" in result.output.lower() or "No" in result.output


# ---------------------------------------------------------------------------
# pocketteam insights run
# ---------------------------------------------------------------------------

class TestInsightsRun:
    def test_run_invokes_claude_with_self_improve(self, tmp_path, monkeypatch):
        """'insights run' actually invokes claude with /self-improve."""
        import shutil
        import subprocess
        monkeypatch.chdir(tmp_path)

        # Patch shutil.which to return a fake claude path
        monkeypatch.setattr(shutil, "which", lambda name: "/usr/local/bin/claude" if name == "claude" else None)

        # Patch subprocess.run to capture the call without actually running it
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            class FakeResult:
                returncode = 0
            return FakeResult()

        monkeypatch.setattr(subprocess, "run", fake_run)

        runner = CliRunner()
        result = runner.invoke(main, ["insights", "run"])

        assert result.exit_code == 0
        assert len(calls) == 1
        cmd = calls[0]
        assert "claude" in cmd[0]
        # Must pass /self-improve as part of the prompt
        assert any("/self-improve" in arg for arg in cmd)

    def test_run_shows_running_message(self, tmp_path, monkeypatch):
        """'insights run' prints a running message and success confirmation."""
        import shutil
        import subprocess
        monkeypatch.chdir(tmp_path)

        monkeypatch.setattr(shutil, "which", lambda name: "/usr/local/bin/claude" if name == "claude" else None)

        def fake_run(cmd, **kwargs):
            class FakeResult:
                returncode = 0
            return FakeResult()

        monkeypatch.setattr(subprocess, "run", fake_run)

        runner = CliRunner()
        result = runner.invoke(main, ["insights", "run"])

        assert result.exit_code == 0
        assert "self-improve" in result.output.lower() or "analysis" in result.output.lower()
        assert "complete" in result.output.lower() or "done" in result.output.lower() or "complete" in result.output.lower()

    def test_run_fails_when_claude_not_found(self, tmp_path, monkeypatch):
        """'insights run' exits with error when claude is not in PATH."""
        import shutil
        monkeypatch.chdir(tmp_path)

        monkeypatch.setattr(shutil, "which", lambda name: None)
        # Block fallback path checks so claude is truly not found
        _orig_exists = Path.exists
        monkeypatch.setattr(Path, "exists", lambda self: False if "claude" in str(self) else _orig_exists(self))

        runner = CliRunner()
        result = runner.invoke(main, ["insights", "run"])

        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "claude" in result.output.lower()


# ---------------------------------------------------------------------------
# _send_insights_telegram helper
# ---------------------------------------------------------------------------

class TestSendInsightsTelegram:
    """Unit tests for the _send_insights_telegram helper function."""

    def test_send_telegram_reads_latest_report_and_calls_api(self, tmp_path, monkeypatch):
        """After a successful run, _send_insights_telegram sends the report content."""
        import urllib.request

        # Set up project with insights dir, report, and chat_id configured
        _make_project(tmp_path, chat_id="99999")
        insights_dir = tmp_path / ".pocketteam" / "artifacts" / "insights"
        insights_dir.mkdir(parents=True)
        report = insights_dir / "report-2026-04-01.md"
        report.write_text("# Insights\nThis is the report content.")

        # Project-specific token (preferred over global)
        (tmp_path / ".pocketteam" / "telegram.env").write_text("TELEGRAM_BOT_TOKEN=fake-token\n")

        fake_home = tmp_path / "home"
        monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))

        # Capture HTTP calls
        requests_made = []

        class FakeResponse:
            def __enter__(self): return self
            def __exit__(self, *a): pass
            def read(self): return b""

        def fake_urlopen(req, timeout=None):
            requests_made.append(req)
            return FakeResponse()

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

        from pocketteam.cli import _send_insights_telegram
        _send_insights_telegram(tmp_path, "# Insights\nThis is the report content.")

        assert len(requests_made) == 1
        req = requests_made[0]
        assert "fake-token" in req.full_url
        assert "sendMessage" in req.full_url

    def test_send_telegram_truncates_at_4000_chars(self, tmp_path, monkeypatch):
        """Report content longer than 4000 chars is truncated before sending."""
        import urllib.request

        # Project-specific setup: config with chat_id + project telegram.env
        _make_project(tmp_path, chat_id="99999")
        (tmp_path / ".pocketteam" / "telegram.env").write_text("TELEGRAM_BOT_TOKEN=fake-token\n")

        fake_home = tmp_path / "home"
        monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))

        bodies_sent = []

        class FakeResponse:
            def __enter__(self): return self
            def __exit__(self, *a): pass

        def fake_urlopen(req, timeout=None):
            bodies_sent.append(req.data)
            return FakeResponse()

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

        long_content = "x" * 5000
        from pocketteam.cli import _send_insights_telegram
        _send_insights_telegram(tmp_path, long_content)

        assert len(bodies_sent) == 1
        import urllib.parse
        body = urllib.parse.unquote(bodies_sent[0].decode())
        # The text parameter must not exceed 4000 chars
        # Find the text= part in the body
        assert "xxxxx" in body
        # Verify length of the text value is at most 4000
        params = dict(pair.split("=", 1) for pair in bodies_sent[0].decode().split("&") if "=" in pair)
        text_val = urllib.parse.unquote_plus(params.get("text", ""))
        assert len(text_val) <= 4000

    def test_send_telegram_no_error_when_not_configured(self, tmp_path, monkeypatch):
        """_send_insights_telegram is silent (no exception) when Telegram is not configured."""
        fake_home = tmp_path / "home"
        # No telegram config files
        monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))

        from pocketteam.cli import _send_insights_telegram
        # Must not raise
        _send_insights_telegram(tmp_path, "some content")

    def test_run_sends_telegram_after_success(self, tmp_path, monkeypatch):
        """'insights run' calls _send_insights_telegram when subprocess succeeds."""
        import shutil
        import subprocess

        _make_project(tmp_path)
        insights_dir = tmp_path / ".pocketteam" / "artifacts" / "insights"
        insights_dir.mkdir(parents=True)
        (insights_dir / "report-2026-04-01.md").write_text("# Report")

        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(shutil, "which", lambda name: "/usr/local/bin/claude" if name == "claude" else None)

        def fake_run(cmd, **kwargs):
            class FakeResult:
                returncode = 0
            return FakeResult()

        monkeypatch.setattr(subprocess, "run", fake_run)

        telegram_calls = []

        import pocketteam.cli as cli_module
        monkeypatch.setattr(cli_module, "_send_insights_telegram",
                            lambda root, content: telegram_calls.append((root, content)))

        runner = CliRunner()
        result = runner.invoke(main, ["insights", "run"])

        assert result.exit_code == 0
        assert len(telegram_calls) == 1

    def test_run_does_not_send_telegram_on_failure(self, tmp_path, monkeypatch):
        """'insights run' does NOT call _send_insights_telegram when subprocess fails."""
        import shutil
        import subprocess

        _make_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(shutil, "which", lambda name: "/usr/local/bin/claude" if name == "claude" else None)

        def fake_run(cmd, **kwargs):
            class FakeResult:
                returncode = 1
            return FakeResult()

        monkeypatch.setattr(subprocess, "run", fake_run)

        telegram_calls = []

        import pocketteam.cli as cli_module
        monkeypatch.setattr(cli_module, "_send_insights_telegram",
                            lambda root, content: telegram_calls.append((root, content)))

        runner = CliRunner()
        result = runner.invoke(main, ["insights", "run"])

        assert result.exit_code != 0
        assert len(telegram_calls) == 0


# ---------------------------------------------------------------------------
# _parse_schedule_input and _cron_to_time helpers
# ---------------------------------------------------------------------------

class TestParseScheduleInput:
    """Unit tests for _parse_schedule_input helper (TDD — written before impl)."""

    def test_hhmm_converts_to_cron(self):
        """'14:00' → '0 14 * * *'"""
        from pocketteam.cli import _parse_schedule_input
        assert _parse_schedule_input("14:00") == "0 14 * * *"

    def test_hhmm_single_digit_hour(self):
        """'9:30' → '30 9 * * *'"""
        from pocketteam.cli import _parse_schedule_input
        assert _parse_schedule_input("9:30") == "30 9 * * *"

    def test_hhmm_midnight(self):
        """'00:00' → '0 0 * * *'"""
        from pocketteam.cli import _parse_schedule_input
        assert _parse_schedule_input("00:00") == "0 0 * * *"

    def test_hhmm_leading_zero_hour(self):
        """'08:15' → '15 8 * * *'"""
        from pocketteam.cli import _parse_schedule_input
        assert _parse_schedule_input("08:15") == "15 8 * * *"

    def test_cron_passes_through(self):
        """'0 14 * * *' passes through unchanged."""
        from pocketteam.cli import _parse_schedule_input
        assert _parse_schedule_input("0 14 * * *") == "0 14 * * *"

    def test_complex_cron_passes_through(self):
        """'0 8 * * 1' (Monday-only) passes through unchanged."""
        from pocketteam.cli import _parse_schedule_input
        assert _parse_schedule_input("0 8 * * 1") == "0 8 * * 1"

    def test_whitespace_stripped(self):
        """Input with surrounding whitespace is handled correctly."""
        from pocketteam.cli import _parse_schedule_input
        assert _parse_schedule_input("  22:00  ") == "0 22 * * *"

    def test_invalid_input_passes_through(self):
        """Garbage input passes through unchanged (not our job to validate here)."""
        from pocketteam.cli import _parse_schedule_input
        assert _parse_schedule_input("not-a-time") == "not-a-time"


class TestCronToTime:
    """Unit tests for _cron_to_time helper (TDD — written before impl)."""

    def test_daily_cron_to_hhmm(self):
        """'0 14 * * *' → '14:00'"""
        from pocketteam.cli import _cron_to_time
        assert _cron_to_time("0 14 * * *") == "14:00"

    def test_daily_cron_with_minutes(self):
        """'30 9 * * *' → '09:30'"""
        from pocketteam.cli import _cron_to_time
        assert _cron_to_time("30 9 * * *") == "09:30"

    def test_midnight_cron(self):
        """'0 0 * * *' → '00:00'"""
        from pocketteam.cli import _cron_to_time
        assert _cron_to_time("0 0 * * *") == "00:00"

    def test_complex_cron_returns_as_is(self):
        """'0 8 * * 1' is not a simple daily cron — returned as-is."""
        from pocketteam.cli import _cron_to_time
        assert _cron_to_time("0 8 * * 1") == "0 8 * * 1"

    def test_non_cron_returns_as_is(self):
        """Random string is returned unchanged."""
        from pocketteam.cli import _cron_to_time
        assert _cron_to_time("not-a-cron") == "not-a-cron"


class TestInsightsOnHHMM:
    """Integration tests: 'insights on --cron' accepts HH:MM format."""

    def test_on_cron_hhmm_converts_and_saves(self, tmp_path, monkeypatch):
        """'insights on --cron 14:00' saves '0 14 * * *' in config."""
        _make_project(tmp_path, enabled=False)
        monkeypatch.chdir(tmp_path)

        import pocketteam.insights_scheduler as sched_mod
        import pocketteam.cli as cli_mod
        monkeypatch.setattr(sched_mod, "install_scheduler", lambda root, cron: True)
        monkeypatch.setattr(cli_mod, "insights_scheduler", sched_mod)

        runner = CliRunner()
        result = runner.invoke(main, ["insights", "on", "--cron", "14:00"])

        assert result.exit_code == 0

        from pocketteam.config import load_config
        cfg = load_config(tmp_path)
        assert cfg.insights.schedule == "0 14 * * *"

    def test_on_cron_hhmm_shown_in_output(self, tmp_path, monkeypatch):
        """Output reflects the converted cron, not raw HH:MM."""
        _make_project(tmp_path, enabled=False)
        monkeypatch.chdir(tmp_path)

        import pocketteam.insights_scheduler as sched_mod
        import pocketteam.cli as cli_mod
        monkeypatch.setattr(sched_mod, "install_scheduler", lambda root, cron: True)
        monkeypatch.setattr(cli_mod, "insights_scheduler", sched_mod)

        runner = CliRunner()
        result = runner.invoke(main, ["insights", "on", "--cron", "8:00"])

        assert result.exit_code == 0
        # The cron string should appear in output (in the schedule hint)
        assert "0 8 * * *" in result.output


# ---------------------------------------------------------------------------
# _parse_time helper
# ---------------------------------------------------------------------------

class TestParseTime:
    """Unit tests for the new _parse_time helper."""

    def test_parse_hhmm_returns_tuple(self):
        """'22:00' → (22, 0)"""
        from pocketteam.cli import _parse_time
        assert _parse_time("22:00") == (22, 0)

    def test_parse_with_minutes(self):
        """'14:30' → (14, 30)"""
        from pocketteam.cli import _parse_time
        assert _parse_time("14:30") == (14, 30)

    def test_parse_midnight(self):
        """'00:00' → (0, 0)"""
        from pocketteam.cli import _parse_time
        assert _parse_time("00:00") == (0, 0)

    def test_parse_strips_whitespace(self):
        """' 09:15 ' → (9, 15)"""
        from pocketteam.cli import _parse_time
        assert _parse_time(" 09:15 ") == (9, 15)

    def test_parse_hour_only(self):
        """'22' (no colon) → (22, 0)"""
        from pocketteam.cli import _parse_time
        assert _parse_time("22") == (22, 0)


# ---------------------------------------------------------------------------
# _schedule_wizard helper
# ---------------------------------------------------------------------------

class TestScheduleWizard:
    """Unit tests for the _schedule_wizard shared function."""

    def test_wizard_daily_returns_daily_cron(self):
        """Selecting daily + 22:00 → '0 22 * * *'"""
        from pocketteam.cli import _schedule_wizard
        from rich.console import Console
        from io import StringIO

        # Simulate: freq=1 (daily), time=22:00
        inputs = "1\n22:00\n"
        with Console(file=StringIO()) as con:
            import io
            from unittest.mock import patch
            with patch("rich.prompt.Prompt.ask", side_effect=["1", "22:00"]):
                result = _schedule_wizard(con)
        assert result == "0 22 * * *"

    def test_wizard_weekdays_returns_weekday_cron(self):
        """Selecting weekdays + 1-5 + 15:00 → '0 15 * * 1-5'"""
        from pocketteam.cli import _schedule_wizard
        from rich.console import Console
        from io import StringIO
        from unittest.mock import patch

        with Console(file=StringIO()) as con:
            with patch("rich.prompt.Prompt.ask", side_effect=["2", "1-5", "15:00"]):
                result = _schedule_wizard(con)
        assert result == "0 15 * * 1-5"

    def test_wizard_monthly_returns_monthly_cron(self):
        """Selecting monthly + day=1 + 20:00 → '0 20 1 * *'"""
        from pocketteam.cli import _schedule_wizard
        from rich.console import Console
        from io import StringIO
        from unittest.mock import patch

        with Console(file=StringIO()) as con:
            with patch("rich.prompt.Prompt.ask", side_effect=["3", "1", "20:00"]):
                result = _schedule_wizard(con)
        assert result == "0 20 1 * *"

    def test_wizard_specific_weekdays_comma_list(self):
        """Selecting weekdays + 2,3 + 18:00 → '0 18 * * 2,3'"""
        from pocketteam.cli import _schedule_wizard
        from rich.console import Console
        from io import StringIO
        from unittest.mock import patch

        with Console(file=StringIO()) as con:
            with patch("rich.prompt.Prompt.ask", side_effect=["2", "2,3", "18:00"]):
                result = _schedule_wizard(con)
        assert result == "0 18 * * 2,3"

    def test_wizard_monday_only(self):
        """Selecting weekdays + 1 (Monday only) + 18:00 → '0 18 * * 1'"""
        from pocketteam.cli import _schedule_wizard
        from rich.console import Console
        from io import StringIO
        from unittest.mock import patch

        with Console(file=StringIO()) as con:
            with patch("rich.prompt.Prompt.ask", side_effect=["2", "1", "18:00"]):
                result = _schedule_wizard(con)
        assert result == "0 18 * * 1"


# ---------------------------------------------------------------------------
# insights on — interactive wizard (no --cron)
# ---------------------------------------------------------------------------

class TestInsightsOnInteractiveWizard:
    """Integration tests: 'insights on' without --cron triggers the wizard."""

    @pytest.fixture(autouse=True)
    def mock_scheduler(self, monkeypatch):
        import pocketteam.insights_scheduler as sched_mod
        import pocketteam.cli as cli_mod
        monkeypatch.setattr(sched_mod, "install_scheduler", lambda root, cron: True)
        monkeypatch.setattr(cli_mod, "insights_scheduler", sched_mod)

    def test_on_no_cron_calls_wizard(self, tmp_path, monkeypatch):
        """'insights on' without --cron calls _schedule_wizard and saves result."""
        _make_project(tmp_path, enabled=False)
        monkeypatch.chdir(tmp_path)

        import pocketteam.cli as cli_mod
        wizard_calls = []

        def fake_wizard(con):
            wizard_calls.append(True)
            return "0 15 * * 1-5"

        monkeypatch.setattr(cli_mod, "_schedule_wizard", fake_wizard)

        runner = CliRunner()
        result = runner.invoke(main, ["insights", "on"])

        assert result.exit_code == 0
        assert len(wizard_calls) == 1

        from pocketteam.config import load_config
        cfg = load_config(tmp_path)
        assert cfg.insights.schedule == "0 15 * * 1-5"

    def test_on_with_cron_skips_wizard(self, tmp_path, monkeypatch):
        """'insights on --cron 22:00' does NOT call _schedule_wizard."""
        _make_project(tmp_path, enabled=False)
        monkeypatch.chdir(tmp_path)

        import pocketteam.cli as cli_mod
        wizard_calls = []

        def fake_wizard(con):
            wizard_calls.append(True)
            return "0 99 * * *"  # Should never be called

        monkeypatch.setattr(cli_mod, "_schedule_wizard", fake_wizard)

        runner = CliRunner()
        result = runner.invoke(main, ["insights", "on", "--cron", "22:00"])

        assert result.exit_code == 0
        assert len(wizard_calls) == 0  # Wizard not called
