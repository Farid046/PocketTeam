"""
Tests for insights_scheduler.py — cross-platform OS scheduler integration.

TDD: written before implementation. Run first to confirm FAIL, then implement.
"""

from __future__ import annotations

import platform
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FAKE_CRON = "0 22 * * *"
FAKE_CMD = 'claude --continue -p "Run /self-improve for this project"'


# ---------------------------------------------------------------------------
# Module imports
# ---------------------------------------------------------------------------

class TestModuleExists:
    def test_module_importable(self):
        """insights_scheduler module must be importable."""
        from pocketteam import insights_scheduler  # noqa: F401

    def test_public_api(self):
        """Module exposes install_scheduler, uninstall_scheduler, scheduler_status."""
        from pocketteam import insights_scheduler
        assert callable(insights_scheduler.install_scheduler)
        assert callable(insights_scheduler.uninstall_scheduler)
        assert callable(insights_scheduler.scheduler_status)


# ---------------------------------------------------------------------------
# scheduler_status
# ---------------------------------------------------------------------------

class TestSchedulerStatus:
    def test_returns_dict(self):
        """scheduler_status() returns a dict."""
        from pocketteam.insights_scheduler import scheduler_status
        result = scheduler_status()
        assert isinstance(result, dict)

    def test_has_required_keys(self):
        """scheduler_status() result has 'platform', 'registered', 'detail' keys."""
        from pocketteam.insights_scheduler import scheduler_status
        result = scheduler_status()
        assert "platform" in result
        assert "registered" in result
        assert "detail" in result

    def test_platform_is_string(self):
        """scheduler_status()['platform'] is a non-empty string."""
        from pocketteam.insights_scheduler import scheduler_status
        result = scheduler_status()
        assert isinstance(result["platform"], str)
        assert len(result["platform"]) > 0

    def test_registered_is_bool(self):
        """scheduler_status()['registered'] is a bool."""
        from pocketteam.insights_scheduler import scheduler_status
        result = scheduler_status()
        assert isinstance(result["registered"], bool)

    def test_detail_is_string(self):
        """scheduler_status()['detail'] is a string."""
        from pocketteam.insights_scheduler import scheduler_status
        result = scheduler_status()
        assert isinstance(result["detail"], str)


# ---------------------------------------------------------------------------
# macOS: launchd plist install / uninstall
# ---------------------------------------------------------------------------

class TestMacOSInstall:
    @pytest.fixture
    def fake_home(self, tmp_path):
        launch_agents = tmp_path / "Library" / "LaunchAgents"
        launch_agents.mkdir(parents=True)
        return tmp_path

    def test_install_creates_plist(self, fake_home, tmp_path, monkeypatch):
        """On macOS, install_scheduler creates a launchd plist file."""
        monkeypatch.setattr(platform, "system", lambda: "Darwin")
        monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))
        # Prevent actual launchctl calls
        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: MagicMock(returncode=0))

        from pocketteam import insights_scheduler
        # Reload to pick up monkeypatched platform
        import importlib
        importlib.reload(insights_scheduler)

        result = insights_scheduler.install_scheduler(tmp_path, FAKE_CRON)
        assert result is True

        plist_path = fake_home / "Library" / "LaunchAgents" / "com.pocketteam.insights.plist"
        assert plist_path.exists(), "Plist file not created"

    def test_install_plist_contains_cron_fields(self, fake_home, tmp_path, monkeypatch):
        """Plist includes StartCalendarInterval with correct minute/hour from cron."""
        monkeypatch.setattr(platform, "system", lambda: "Darwin")
        monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))
        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: MagicMock(returncode=0))

        from pocketteam import insights_scheduler
        import importlib
        importlib.reload(insights_scheduler)

        insights_scheduler.install_scheduler(tmp_path, "30 8 * * *")

        plist_path = fake_home / "Library" / "LaunchAgents" / "com.pocketteam.insights.plist"
        content = plist_path.read_text()
        assert "StartCalendarInterval" in content
        # Minute = 30, Hour = 8
        assert "30" in content
        assert "8" in content

    def test_install_plist_contains_claude_command(self, fake_home, tmp_path, monkeypatch):
        """Plist references claude --continue -p 'Run /self-improve...'."""
        monkeypatch.setattr(platform, "system", lambda: "Darwin")
        monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))
        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: MagicMock(returncode=0))

        from pocketteam import insights_scheduler
        import importlib
        importlib.reload(insights_scheduler)

        insights_scheduler.install_scheduler(tmp_path, FAKE_CRON)

        plist_path = fake_home / "Library" / "LaunchAgents" / "com.pocketteam.insights.plist"
        content = plist_path.read_text()
        assert "--continue" in content
        assert "self-improve" in content

    def test_uninstall_removes_plist(self, fake_home, tmp_path, monkeypatch):
        """On macOS, uninstall_scheduler removes the plist and calls launchctl unload."""
        monkeypatch.setattr(platform, "system", lambda: "Darwin")
        monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))
        launchctl_calls = []
        monkeypatch.setattr(
            subprocess, "run",
            lambda cmd, **kw: launchctl_calls.append(cmd) or MagicMock(returncode=0)
        )

        from pocketteam import insights_scheduler
        import importlib
        importlib.reload(insights_scheduler)

        # Create the plist first
        plist_path = fake_home / "Library" / "LaunchAgents" / "com.pocketteam.insights.plist"
        plist_path.write_text("<plist/>")

        result = insights_scheduler.uninstall_scheduler()
        assert result is True
        assert not plist_path.exists(), "Plist not removed"

    def test_status_registered_when_plist_exists(self, fake_home, monkeypatch):
        """scheduler_status returns registered=True when plist exists on macOS."""
        monkeypatch.setattr(platform, "system", lambda: "Darwin")
        monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))

        from pocketteam import insights_scheduler
        import importlib
        importlib.reload(insights_scheduler)

        plist_path = fake_home / "Library" / "LaunchAgents" / "com.pocketteam.insights.plist"
        plist_path.write_text("<plist/>")

        status = insights_scheduler.scheduler_status()
        assert status["registered"] is True

    def test_status_not_registered_when_plist_absent(self, fake_home, monkeypatch):
        """scheduler_status returns registered=False when plist is absent on macOS."""
        monkeypatch.setattr(platform, "system", lambda: "Darwin")
        monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))

        from pocketteam import insights_scheduler
        import importlib
        importlib.reload(insights_scheduler)

        status = insights_scheduler.scheduler_status()
        assert status["registered"] is False


# ---------------------------------------------------------------------------
# Linux: crontab install / uninstall
# ---------------------------------------------------------------------------

class TestLinuxInstall:
    def test_install_calls_crontab(self, tmp_path, monkeypatch):
        """On Linux, install_scheduler modifies crontab with a marker comment."""
        monkeypatch.setattr(platform, "system", lambda: "Linux")

        crontab_calls = []

        def fake_run(cmd, **kwargs):
            crontab_calls.append(cmd)
            # Simulate "crontab -l" returning empty on first call
            m = MagicMock()
            m.returncode = 0
            if isinstance(cmd, list) and "-l" in cmd:
                m.stdout = ""
            return m

        monkeypatch.setattr(subprocess, "run", fake_run)

        from pocketteam import insights_scheduler
        import importlib
        importlib.reload(insights_scheduler)

        result = insights_scheduler.install_scheduler(tmp_path, FAKE_CRON)
        assert result is True

        # crontab must have been called
        cmds_flat = [" ".join(c) if isinstance(c, list) else str(c) for c in crontab_calls]
        assert any("crontab" in c for c in cmds_flat)

    def test_install_includes_marker_comment(self, tmp_path, monkeypatch):
        """Linux crontab entry includes a PocketTeam marker comment for safe removal."""
        monkeypatch.setattr(platform, "system", lambda: "Linux")

        written_content = []

        def fake_run(cmd, **kwargs):
            m = MagicMock()
            m.returncode = 0
            if isinstance(cmd, list) and "-l" in cmd:
                m.stdout = ""
            if kwargs.get("input"):
                written_content.append(kwargs["input"])
            return m

        monkeypatch.setattr(subprocess, "run", fake_run)

        from pocketteam import insights_scheduler
        import importlib
        importlib.reload(insights_scheduler)

        insights_scheduler.install_scheduler(tmp_path, FAKE_CRON)

        # Marker must appear in submitted crontab content
        assert any("pocketteam" in c.lower() for c in written_content), (
            "No PocketTeam marker found in crontab content"
        )

    def test_uninstall_removes_marker_lines(self, tmp_path, monkeypatch):
        """Linux uninstall removes only PocketTeam marker lines from crontab."""
        monkeypatch.setattr(platform, "system", lambda: "Linux")

        existing_cron = (
            "# other job\n"
            "0 9 * * * /usr/bin/backup\n"
            "# pocketteam-insights\n"
            "0 22 * * * claude --continue -p \"Run /self-improve for this project\"\n"
        )
        written_content = []

        def fake_run(cmd, **kwargs):
            m = MagicMock()
            m.returncode = 0
            if isinstance(cmd, list) and "-l" in cmd:
                m.stdout = existing_cron
            if kwargs.get("input"):
                written_content.append(kwargs["input"])
            return m

        monkeypatch.setattr(subprocess, "run", fake_run)

        from pocketteam import insights_scheduler
        import importlib
        importlib.reload(insights_scheduler)

        result = insights_scheduler.uninstall_scheduler()
        assert result is True

        # The backup job must still be there, pocketteam lines must be gone
        if written_content:
            final = written_content[-1]
            assert "backup" in final
            assert "pocketteam" not in final.lower()

    def test_status_linux_registered_when_marker_in_crontab(self, tmp_path, monkeypatch):
        """Linux scheduler_status returns registered=True when marker in crontab."""
        monkeypatch.setattr(platform, "system", lambda: "Linux")

        def fake_run(cmd, **kwargs):
            m = MagicMock()
            m.returncode = 0
            m.stdout = "# pocketteam-insights\n0 22 * * * claude\n"
            return m

        monkeypatch.setattr(subprocess, "run", fake_run)

        from pocketteam import insights_scheduler
        import importlib
        importlib.reload(insights_scheduler)

        status = insights_scheduler.scheduler_status()
        assert status["registered"] is True

    def test_status_linux_not_registered_when_no_marker(self, tmp_path, monkeypatch):
        """Linux scheduler_status returns registered=False when no marker in crontab."""
        monkeypatch.setattr(platform, "system", lambda: "Linux")

        def fake_run(cmd, **kwargs):
            m = MagicMock()
            m.returncode = 0
            m.stdout = "0 9 * * * /usr/bin/backup\n"
            return m

        monkeypatch.setattr(subprocess, "run", fake_run)

        from pocketteam import insights_scheduler
        import importlib
        importlib.reload(insights_scheduler)

        status = insights_scheduler.scheduler_status()
        assert status["registered"] is False


# ---------------------------------------------------------------------------
# Windows: schtasks install / uninstall
# ---------------------------------------------------------------------------

class TestWindowsInstall:
    def test_install_calls_schtasks(self, tmp_path, monkeypatch):
        """On Windows, install_scheduler calls schtasks /Create."""
        monkeypatch.setattr(platform, "system", lambda: "Windows")

        schtasks_calls = []

        def fake_run(cmd, **kwargs):
            schtasks_calls.append(cmd)
            m = MagicMock()
            m.returncode = 0
            m.stdout = ""
            return m

        monkeypatch.setattr(subprocess, "run", fake_run)

        from pocketteam import insights_scheduler
        import importlib
        importlib.reload(insights_scheduler)

        result = insights_scheduler.install_scheduler(tmp_path, FAKE_CRON)
        assert result is True

        cmds_flat = [" ".join(c) if isinstance(c, list) else str(c) for c in schtasks_calls]
        assert any("schtasks" in c.lower() for c in cmds_flat)

    def test_uninstall_calls_schtasks_delete(self, tmp_path, monkeypatch):
        """On Windows, uninstall_scheduler calls schtasks /Delete."""
        monkeypatch.setattr(platform, "system", lambda: "Windows")

        schtasks_calls = []

        def fake_run(cmd, **kwargs):
            schtasks_calls.append(cmd)
            m = MagicMock()
            m.returncode = 0
            m.stdout = ""
            return m

        monkeypatch.setattr(subprocess, "run", fake_run)

        from pocketteam import insights_scheduler
        import importlib
        importlib.reload(insights_scheduler)

        result = insights_scheduler.uninstall_scheduler()
        assert result is True

        cmds_flat = [" ".join(c) if isinstance(c, list) else str(c) for c in schtasks_calls]
        assert any("schtasks" in c.lower() for c in cmds_flat)


# ---------------------------------------------------------------------------
# Error resilience
# ---------------------------------------------------------------------------

class TestErrorResilience:
    def test_install_returns_false_on_exception(self, tmp_path, monkeypatch):
        """install_scheduler returns False (not raises) when subprocess errors."""
        monkeypatch.setattr(platform, "system", lambda: "Darwin")
        monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: (_ for _ in ()).throw(OSError("no launchctl")))

        from pocketteam import insights_scheduler
        import importlib
        importlib.reload(insights_scheduler)

        # Should not raise
        result = insights_scheduler.install_scheduler(tmp_path, FAKE_CRON)
        assert result is False

    def test_uninstall_returns_false_when_nothing_installed(self, tmp_path, monkeypatch):
        """uninstall_scheduler returns False gracefully when nothing to remove."""
        monkeypatch.setattr(platform, "system", lambda: "Darwin")
        monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
        # Plist doesn't exist, no launchctl calls needed
        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: MagicMock(returncode=0))

        from pocketteam import insights_scheduler
        import importlib
        importlib.reload(insights_scheduler)

        result = insights_scheduler.uninstall_scheduler()
        # Nothing installed — should return False
        assert result is False

    def test_status_never_raises(self, tmp_path, monkeypatch):
        """scheduler_status never raises even when platform detection fails."""
        monkeypatch.setattr(platform, "system", lambda: "Darwin")
        monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))

        from pocketteam import insights_scheduler
        import importlib
        importlib.reload(insights_scheduler)

        # Must not raise
        result = insights_scheduler.scheduler_status()
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# CLI integration: insights on/off call scheduler
# ---------------------------------------------------------------------------

class TestCLISchedulerIntegration:
    def _make_project(self, tmp_path, enabled=False, schedule="0 22 * * *"):
        pt_dir = tmp_path / ".pocketteam"
        pt_dir.mkdir(parents=True, exist_ok=True)
        cfg_text = f"""\
project:
  name: test-project
  health_url: ''
insights:
  enabled: {str(enabled).lower()}
  schedule: '{schedule}'
  last_run: null
  telegram_notify: false
  auto_apply: false
telegram:
  chat_id: ''
  bot_token: ''
"""
        (pt_dir / "config.yaml").write_text(cfg_text)

    def test_insights_on_calls_install_scheduler(self, tmp_path, monkeypatch):
        """'insights on' calls install_scheduler after saving config."""
        self._make_project(tmp_path)
        monkeypatch.chdir(tmp_path)

        install_calls = []
        import pocketteam.insights_scheduler as sched_mod
        monkeypatch.setattr(sched_mod, "install_scheduler",
                            lambda root, cron: install_calls.append((root, cron)) or True)

        import pocketteam.cli as cli_mod
        monkeypatch.setattr(cli_mod, "insights_scheduler", sched_mod)

        from click.testing import CliRunner
        from pocketteam.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["insights", "on"])

        assert result.exit_code == 0
        assert len(install_calls) == 1

    def test_insights_off_calls_uninstall_scheduler(self, tmp_path, monkeypatch):
        """'insights off' calls uninstall_scheduler after saving config."""
        self._make_project(tmp_path, enabled=True)
        monkeypatch.chdir(tmp_path)

        uninstall_calls = []
        import pocketteam.insights_scheduler as sched_mod
        monkeypatch.setattr(sched_mod, "uninstall_scheduler",
                            lambda: uninstall_calls.append(True) or True)

        import pocketteam.cli as cli_mod
        monkeypatch.setattr(cli_mod, "insights_scheduler", sched_mod)

        from click.testing import CliRunner
        from pocketteam.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["insights", "off"])

        assert result.exit_code == 0
        assert len(uninstall_calls) == 1

    def test_insights_on_no_longer_shows_manual_schedule_instructions(self, tmp_path, monkeypatch):
        """'insights on' must NOT show manual 'claude /schedule create' instructions."""
        self._make_project(tmp_path)
        monkeypatch.chdir(tmp_path)

        import pocketteam.insights_scheduler as sched_mod
        monkeypatch.setattr(sched_mod, "install_scheduler", lambda root, cron: True)

        import pocketteam.cli as cli_mod
        monkeypatch.setattr(cli_mod, "insights_scheduler", sched_mod)

        from click.testing import CliRunner
        from pocketteam.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["insights", "on"])

        assert result.exit_code == 0
        # Must NOT suggest manual claude /schedule create command
        assert "claude /schedule create" not in result.output

    def test_insights_off_no_longer_shows_manual_remove_instructions(self, tmp_path, monkeypatch):
        """'insights off' must NOT show 'Remove Remote Agent trigger' instructions."""
        self._make_project(tmp_path, enabled=True)
        monkeypatch.chdir(tmp_path)

        import pocketteam.insights_scheduler as sched_mod
        monkeypatch.setattr(sched_mod, "uninstall_scheduler", lambda: True)

        import pocketteam.cli as cli_mod
        monkeypatch.setattr(cli_mod, "insights_scheduler", sched_mod)

        from click.testing import CliRunner
        from pocketteam.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["insights", "off"])

        assert result.exit_code == 0
        # Must NOT suggest manual removal via claude.ai
        assert "claude.ai/code/scheduled" not in result.output

    def test_insights_status_shows_scheduler_info(self, tmp_path, monkeypatch):
        """'insights status' shows OS scheduler registration status."""
        self._make_project(tmp_path, enabled=True)
        monkeypatch.chdir(tmp_path)

        import pocketteam.insights_scheduler as sched_mod
        monkeypatch.setattr(sched_mod, "scheduler_status",
                            lambda: {"platform": "macOS", "registered": True, "detail": "launchd plist active"})

        import pocketteam.cli as cli_mod
        monkeypatch.setattr(cli_mod, "insights_scheduler", sched_mod)

        from click.testing import CliRunner
        from pocketteam.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["insights", "status"])

        assert result.exit_code == 0
        # Status output must include scheduler info
        assert "macOS" in result.output or "launchd" in result.output or "registered" in result.output.lower()
