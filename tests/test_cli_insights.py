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

    def test_on_shows_schedule_command_hint(self, tmp_path, monkeypatch):
        """'insights on' always prints the Remote Agent trigger hint."""
        _make_project(tmp_path)
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        result = runner.invoke(main, ["insights", "on"])

        assert result.exit_code == 0
        assert "/schedule" in result.output or "pocketteam insights run" in result.output

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

    def test_off_shows_remove_trigger_hint(self, tmp_path, monkeypatch):
        """'insights off' reminds the user to remove the Remote Agent trigger."""
        _make_project(tmp_path, enabled=True)
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        result = runner.invoke(main, ["insights", "off"])

        assert result.exit_code == 0
        # Should mention removing the trigger or the scheduled page
        assert "scheduled" in result.output.lower() or "trigger" in result.output.lower() or "claude.ai" in result.output


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

        runner = CliRunner()
        result = runner.invoke(main, ["insights", "run"])

        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "claude" in result.output.lower()
