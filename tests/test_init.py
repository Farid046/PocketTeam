"""
Unit tests for pocketteam/init.py.

Covers testable helper functions without touching interactive _interview().
All filesystem operations use tmp_path. All subprocess and shutil.which calls
are mocked to avoid side-effects.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from pocketteam.config import PocketTeamConfig, TelegramConfig
from pocketteam.constants import (
    AGENTS_DIR,
    CLAUDE_DIR,
    POCKETTEAM_DIR,
    PLANS_DIR,
    REVIEWS_DIR,
    SKILLS_DIR,
)
from pocketteam.init import (
    POCKETTEAM_END,
    POCKETTEAM_START,
    _copy_skills,
    _create_directories,
    _create_gitignore,
    _get_pocketteam_claude_md_section,
    _setup_claude_md,
    _setup_optimal_defaults,
    _setup_settings_json,
    _setup_telegram_plugin,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_console() -> MagicMock:
    """Return a silent mock console."""
    return MagicMock()


def _minimal_config(project_root: Path) -> PocketTeamConfig:
    cfg = PocketTeamConfig(project_root=project_root)
    cfg.project_name = "TestProject"
    return cfg


# ─────────────────────────────────────────────────────────────────────────────
# _setup_telegram_plugin
# ─────────────────────────────────────────────────────────────────────────────

class TestSetupTelegramPlugin:
    """Tests for _setup_telegram_plugin(bot_token)."""

    def test_returns_false_when_claude_not_found(self, tmp_path):
        with patch("shutil.which", return_value=None):
            result = _setup_telegram_plugin("1234:TOKEN")
        assert result is False

    def test_writes_env_file_with_token(self, tmp_path):
        token = "9876543210:AABBCCDDEEFFaabbccddeeff"
        channel_dir = tmp_path / ".claude" / "channels" / "telegram"

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "installed"
        mock_result.stderr = ""

        with (
            patch("shutil.which", return_value="/usr/bin/claude"),
            patch("subprocess.run", return_value=mock_result),
            patch("pathlib.Path.home", return_value=tmp_path),
        ):
            _setup_telegram_plugin(token)

        env_path = tmp_path / ".claude" / "channels" / "telegram" / ".env"
        assert env_path.exists(), ".env file was not created"
        content = env_path.read_text()
        assert f"TELEGRAM_BOT_TOKEN={token}" in content

    def test_env_file_has_restricted_permissions(self, tmp_path):
        token = "1111111111:AAAtoken"

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "ok"
        mock_result.stderr = ""

        with (
            patch("shutil.which", return_value="/usr/bin/claude"),
            patch("subprocess.run", return_value=mock_result),
            patch("pathlib.Path.home", return_value=tmp_path),
        ):
            _setup_telegram_plugin(token)

        env_path = tmp_path / ".claude" / "channels" / "telegram" / ".env"
        file_mode = stat.S_IMODE(env_path.stat().st_mode)
        assert file_mode == 0o600, f"Expected 0o600 but got {oct(file_mode)}"

    def test_removes_old_mcp_proxy(self, tmp_path):
        token = "2222222222:BBBtoken"

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "installed"
        mock_result.stderr = ""

        with (
            patch("shutil.which", return_value="/usr/bin/claude"),
            patch("subprocess.run", return_value=mock_result) as mock_run,
            patch("pathlib.Path.home", return_value=tmp_path),
        ):
            _setup_telegram_plugin(token)

        # First subprocess call should remove old mcp proxy
        first_call_args = mock_run.call_args_list[0][0][0]
        assert "mcp" in first_call_args
        assert "remove" in first_call_args
        assert "telegram-proxy" in first_call_args

    def test_installs_official_plugin(self, tmp_path):
        token = "3333333333:CCCtoken"

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "installed"
        mock_result.stderr = ""

        with (
            patch("shutil.which", return_value="/usr/bin/claude"),
            patch("subprocess.run", return_value=mock_result) as mock_run,
            patch("pathlib.Path.home", return_value=tmp_path),
        ):
            result = _setup_telegram_plugin(token)

        assert result is True
        # Second call is the plugin install
        second_call_args = mock_run.call_args_list[1][0][0]
        assert "plugin" in second_call_args
        assert "install" in second_call_args
        assert "telegram@claude-plugins-official" in second_call_args

    def test_returns_true_when_already_installed(self, tmp_path):
        token = "4444444444:DDDtoken"

        remove_result = MagicMock()
        remove_result.returncode = 0

        install_result = MagicMock()
        install_result.returncode = 1
        install_result.stdout = ""
        install_result.stderr = "already installed"

        with (
            patch("shutil.which", return_value="/usr/bin/claude"),
            patch("subprocess.run", side_effect=[remove_result, install_result]),
            patch("pathlib.Path.home", return_value=tmp_path),
        ):
            result = _setup_telegram_plugin(token)

        assert result is True

    def test_returns_false_on_install_failure(self, tmp_path):
        token = "5555555555:EEEtoken"

        remove_result = MagicMock()
        remove_result.returncode = 0

        install_result = MagicMock()
        install_result.returncode = 1
        install_result.stdout = ""
        install_result.stderr = "some error"

        with (
            patch("shutil.which", return_value="/usr/bin/claude"),
            patch("subprocess.run", side_effect=[remove_result, install_result]),
            patch("pathlib.Path.home", return_value=tmp_path),
        ):
            result = _setup_telegram_plugin(token)

        assert result is False

    def test_returns_false_on_exception(self, tmp_path):
        token = "6666666666:FFFtoken"
        with (
            patch("shutil.which", return_value="/usr/bin/claude"),
            patch("subprocess.run", side_effect=OSError("permission denied")),
            patch("pathlib.Path.home", return_value=tmp_path),
        ):
            result = _setup_telegram_plugin(token)
        assert result is False


# ─────────────────────────────────────────────────────────────────────────────
# _copy_skills
# ─────────────────────────────────────────────────────────────────────────────

class TestCopySkills:
    """Tests for _copy_skills(skills_source, skills_target, console)."""

    def _make_manifest(self, source: Path, skill_names: list[str]) -> None:
        manifest = {"package_skills": skill_names}
        (source / "MANIFEST.json").write_text(json.dumps(manifest))

    def test_copies_listed_md_files(self, tmp_path):
        source = tmp_path / "skills_source"
        source.mkdir()
        target = tmp_path / "skills_target"

        self._make_manifest(source, ["deploy", "monitor"])
        (source / "deploy.md").write_text("# Deploy")
        (source / "monitor.md").write_text("# Monitor")
        (source / "unlisted.md").write_text("# Unlisted")

        console = _make_console()
        _copy_skills(source, target, console)

        assert (target / "deploy.md").exists()
        assert (target / "monitor.md").exists()
        # Unlisted skill must NOT be copied
        assert not (target / "unlisted.md").exists()

    def test_creates_target_directory(self, tmp_path):
        source = tmp_path / "skills_source"
        source.mkdir()
        target = tmp_path / "deep" / "nested" / "target"

        self._make_manifest(source, ["skill_a"])
        (source / "skill_a.md").write_text("# A")

        console = _make_console()
        _copy_skills(source, target, console)

        assert target.is_dir()
        assert (target / "skill_a.md").exists()

    def test_handles_missing_manifest_gracefully(self, tmp_path):
        source = tmp_path / "skills_source"
        source.mkdir()
        target = tmp_path / "skills_target"

        # No MANIFEST.json created
        console = _make_console()
        _copy_skills(source, target, console)  # must not raise

        assert not target.exists()

    def test_handles_corrupt_manifest_gracefully(self, tmp_path):
        source = tmp_path / "skills_source"
        source.mkdir()
        target = tmp_path / "skills_target"

        (source / "MANIFEST.json").write_text("not valid json {{{")
        console = _make_console()
        _copy_skills(source, target, console)  # must not raise

        assert not target.exists()

    def test_empty_package_skills_list_copies_nothing(self, tmp_path):
        source = tmp_path / "skills_source"
        source.mkdir()
        target = tmp_path / "skills_target"

        self._make_manifest(source, [])
        (source / "some.md").write_text("# Some")

        console = _make_console()
        _copy_skills(source, target, console)

        assert not (target / "some.md").exists()

    def test_skill_in_manifest_but_missing_file_is_skipped(self, tmp_path):
        """If a skill is listed but has no .md file, nothing should crash."""
        source = tmp_path / "skills_source"
        source.mkdir()
        target = tmp_path / "skills_target"

        self._make_manifest(source, ["ghost"])
        # No ghost.md file

        console = _make_console()
        _copy_skills(source, target, console)  # must not raise


# ─────────────────────────────────────────────────────────────────────────────
# _setup_settings_json
# ─────────────────────────────────────────────────────────────────────────────

class TestSetupSettingsJson:
    """Tests for _setup_settings_json(project_root, is_new)."""

    def test_creates_settings_json_when_is_new(self, tmp_path):
        claude_dir = tmp_path / CLAUDE_DIR
        claude_dir.mkdir(parents=True)

        _setup_settings_json(tmp_path, is_new=True)

        settings_path = claude_dir / "settings.json"
        assert settings_path.exists()

        data = json.loads(settings_path.read_text())
        assert "hooks" in data

    def test_hooks_use_project_root_in_commands(self, tmp_path):
        claude_dir = tmp_path / CLAUDE_DIR
        claude_dir.mkdir(parents=True)

        _setup_settings_json(tmp_path, is_new=True)

        settings_path = claude_dir / "settings.json"
        raw = settings_path.read_text()
        # Implementation uses relative paths (PYTHONPATH=. python -m pocketteam.hooks ...)
        assert "PYTHONPATH=." in raw, "Relative PYTHONPATH not found in hook commands"

    def test_generates_pretooluse_hook(self, tmp_path):
        (tmp_path / CLAUDE_DIR).mkdir(parents=True)
        _setup_settings_json(tmp_path, is_new=True)

        data = json.loads((tmp_path / CLAUDE_DIR / "settings.json").read_text())
        hooks = data["hooks"]
        assert "PreToolUse" in hooks

    def test_generates_posttooluse_hook(self, tmp_path):
        (tmp_path / CLAUDE_DIR).mkdir(parents=True)
        _setup_settings_json(tmp_path, is_new=True)

        data = json.loads((tmp_path / CLAUDE_DIR / "settings.json").read_text())
        assert "PostToolUse" in data["hooks"]

    def test_generates_userpromptsubmit_hook(self, tmp_path):
        (tmp_path / CLAUDE_DIR).mkdir(parents=True)
        _setup_settings_json(tmp_path, is_new=True)

        data = json.loads((tmp_path / CLAUDE_DIR / "settings.json").read_text())
        assert "UserPromptSubmit" in data["hooks"]

    def test_merges_into_existing_settings(self, tmp_path):
        claude_dir = tmp_path / CLAUDE_DIR
        claude_dir.mkdir(parents=True)
        existing = {"mykey": "myvalue", "hooks": {}}
        (claude_dir / "settings.json").write_text(json.dumps(existing))

        _setup_settings_json(tmp_path, is_new=False)

        data = json.loads((claude_dir / "settings.json").read_text())
        assert data.get("mykey") == "myvalue", "Existing key was removed during merge"
        assert "PreToolUse" in data["hooks"]

    def test_does_not_duplicate_hooks_on_re_run(self, tmp_path):
        """Running _setup_settings_json twice must not duplicate matchers."""
        claude_dir = tmp_path / CLAUDE_DIR
        claude_dir.mkdir(parents=True)

        _setup_settings_json(tmp_path, is_new=True)
        # Run again as merge
        _setup_settings_json(tmp_path, is_new=False)

        data = json.loads((claude_dir / "settings.json").read_text())
        pre_tool_hooks = data["hooks"]["PreToolUse"]
        matchers = [h.get("matcher") for h in pre_tool_hooks]
        # No duplicate matchers
        assert len(matchers) == len(set(matchers))

    def test_creates_backup_when_merging(self, tmp_path):
        claude_dir = tmp_path / CLAUDE_DIR
        claude_dir.mkdir(parents=True)
        (claude_dir / "settings.json").write_text('{"hooks": {}}')

        _setup_settings_json(tmp_path, is_new=False)

        backup = claude_dir / "settings.json.backup"
        assert backup.exists(), "Backup not created on merge"

    def test_handles_invalid_json_gracefully(self, tmp_path):
        claude_dir = tmp_path / CLAUDE_DIR
        claude_dir.mkdir(parents=True)
        (claude_dir / "settings.json").write_text("not json {")

        # Must not raise
        _setup_settings_json(tmp_path, is_new=False)


# ─────────────────────────────────────────────────────────────────────────────
# _setup_claude_md
# ─────────────────────────────────────────────────────────────────────────────

class TestSetupClaudeMd:
    """Tests for _setup_claude_md(project_root, cfg, is_new)."""

    def test_creates_claude_md_when_new(self, tmp_path):
        cfg = _minimal_config(tmp_path)
        (tmp_path / CLAUDE_DIR).mkdir(parents=True)

        _setup_claude_md(tmp_path, cfg, is_new=True)

        md_path = tmp_path / CLAUDE_DIR / "CLAUDE.md"
        assert md_path.exists()

    def test_claude_md_contains_project_name(self, tmp_path):
        cfg = _minimal_config(tmp_path)
        cfg.project_name = "MyUniqueProject"
        (tmp_path / CLAUDE_DIR).mkdir(parents=True)

        _setup_claude_md(tmp_path, cfg, is_new=True)

        content = (tmp_path / CLAUDE_DIR / "CLAUDE.md").read_text()
        assert "MyUniqueProject" in content

    def test_claude_md_contains_markers(self, tmp_path):
        cfg = _minimal_config(tmp_path)
        (tmp_path / CLAUDE_DIR).mkdir(parents=True)

        _setup_claude_md(tmp_path, cfg, is_new=True)

        content = (tmp_path / CLAUDE_DIR / "CLAUDE.md").read_text()
        assert POCKETTEAM_START in content
        assert POCKETTEAM_END in content

    def test_merges_into_existing_file(self, tmp_path):
        cfg = _minimal_config(tmp_path)
        claude_dir = tmp_path / CLAUDE_DIR
        claude_dir.mkdir(parents=True)

        # Pre-existing content
        existing_content = "# My Existing Docs\n\nSome content here.\n"
        (claude_dir / "CLAUDE.md").write_text(existing_content)

        _setup_claude_md(tmp_path, cfg, is_new=False)

        content = (claude_dir / "CLAUDE.md").read_text()
        assert "My Existing Docs" in content
        assert POCKETTEAM_START in content

    def test_replaces_existing_pocketteam_section(self, tmp_path):
        cfg = _minimal_config(tmp_path)
        cfg.project_name = "UpdatedProject"
        claude_dir = tmp_path / CLAUDE_DIR
        claude_dir.mkdir(parents=True)

        old_section = f"{POCKETTEAM_START}\n# OLD SECTION\n{POCKETTEAM_END}"
        (claude_dir / "CLAUDE.md").write_text(old_section)

        _setup_claude_md(tmp_path, cfg, is_new=False)

        content = (claude_dir / "CLAUDE.md").read_text()
        assert "OLD SECTION" not in content
        assert "UpdatedProject" in content

    def test_creates_backup_on_merge(self, tmp_path):
        cfg = _minimal_config(tmp_path)
        claude_dir = tmp_path / CLAUDE_DIR
        claude_dir.mkdir(parents=True)
        (claude_dir / "CLAUDE.md").write_text("# Pre-existing\n")

        _setup_claude_md(tmp_path, cfg, is_new=False)

        backup = claude_dir / "CLAUDE.md.backup"
        assert backup.exists(), "Backup not created"
        assert "Pre-existing" in backup.read_text()


# ─────────────────────────────────────────────────────────────────────────────
# _get_pocketteam_claude_md_section
# ─────────────────────────────────────────────────────────────────────────────

class TestGetPocketteamClaudeMdSection:
    """Tests for the section generator."""

    def test_contains_start_marker(self, tmp_path):
        cfg = _minimal_config(tmp_path)
        section = _get_pocketteam_claude_md_section(cfg)
        assert POCKETTEAM_START in section

    def test_contains_end_marker(self, tmp_path):
        cfg = _minimal_config(tmp_path)
        section = _get_pocketteam_claude_md_section(cfg)
        assert POCKETTEAM_END in section

    def test_contains_project_name(self, tmp_path):
        cfg = _minimal_config(tmp_path)
        cfg.project_name = "AmazingApp"
        section = _get_pocketteam_claude_md_section(cfg)
        assert "AmazingApp" in section

    def test_start_before_end(self, tmp_path):
        cfg = _minimal_config(tmp_path)
        section = _get_pocketteam_claude_md_section(cfg)
        assert section.index(POCKETTEAM_START) < section.index(POCKETTEAM_END)


# ─────────────────────────────────────────────────────────────────────────────
# _create_directories
# ─────────────────────────────────────────────────────────────────────────────

class TestCreateDirectories:
    """Tests for _create_directories(project_root)."""

    def test_creates_pocketteam_dir(self, tmp_path):
        _create_directories(tmp_path)
        assert (tmp_path / POCKETTEAM_DIR).is_dir()

    def test_creates_plans_dir(self, tmp_path):
        _create_directories(tmp_path)
        assert (tmp_path / PLANS_DIR).is_dir()

    def test_creates_reviews_dir(self, tmp_path):
        _create_directories(tmp_path)
        assert (tmp_path / REVIEWS_DIR).is_dir()

    def test_creates_agents_dir(self, tmp_path):
        _create_directories(tmp_path)
        assert (tmp_path / AGENTS_DIR).is_dir()

    def test_creates_skills_dir(self, tmp_path):
        _create_directories(tmp_path)
        assert (tmp_path / SKILLS_DIR).is_dir()

    def test_creates_events_stream_file(self, tmp_path):
        _create_directories(tmp_path)
        events = tmp_path / ".pocketteam" / "events" / "stream.jsonl"
        assert events.exists()

    def test_idempotent_on_second_call(self, tmp_path):
        _create_directories(tmp_path)
        _create_directories(tmp_path)  # Must not raise

    def test_creates_github_workflows_dir(self, tmp_path):
        _create_directories(tmp_path)
        assert (tmp_path / ".github" / "workflows").is_dir()


# ─────────────────────────────────────────────────────────────────────────────
# _setup_optimal_defaults
# ─────────────────────────────────────────────────────────────────────────────

class TestSetupOptimalDefaults:
    """Tests for _setup_optimal_defaults(project_root)."""

    def test_sets_effort_level_medium(self, tmp_path):
        claude_dir = tmp_path / CLAUDE_DIR
        claude_dir.mkdir(parents=True)
        (claude_dir / "settings.json").write_text('{"hooks": {}}')

        # Patch home to avoid touching real ~/.claude.json
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        with patch("pathlib.Path.home", return_value=fake_home):
            _setup_optimal_defaults(tmp_path)

        data = json.loads((claude_dir / "settings.json").read_text())
        assert data.get("effortLevel") == "medium"

    def test_does_not_overwrite_existing_effort_level(self, tmp_path):
        claude_dir = tmp_path / CLAUDE_DIR
        claude_dir.mkdir(parents=True)
        (claude_dir / "settings.json").write_text('{"effortLevel": "high", "hooks": {}}')

        fake_home = tmp_path / "home"
        fake_home.mkdir()
        with patch("pathlib.Path.home", return_value=fake_home):
            _setup_optimal_defaults(tmp_path)

        data = json.loads((claude_dir / "settings.json").read_text())
        assert data["effortLevel"] == "high"

    def test_sets_remote_control_in_global_config(self, tmp_path):
        claude_dir = tmp_path / CLAUDE_DIR
        claude_dir.mkdir(parents=True)
        (claude_dir / "settings.json").write_text('{"hooks": {}}')

        fake_home = tmp_path / "home"
        fake_home.mkdir()
        with patch("pathlib.Path.home", return_value=fake_home):
            _setup_optimal_defaults(tmp_path)

        global_cfg = fake_home / ".claude.json"
        assert global_cfg.exists()
        data = json.loads(global_cfg.read_text())
        assert data.get("remoteControlAtStartup") is True

    def test_does_not_crash_when_settings_json_missing(self, tmp_path):
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        # No settings.json created
        with patch("pathlib.Path.home", return_value=fake_home):
            _setup_optimal_defaults(tmp_path)  # Must not raise


# ─────────────────────────────────────────────────────────────────────────────
# run_uninstall
# ─────────────────────────────────────────────────────────────────────────────

class TestRunUninstall:
    """Tests for run_uninstall(keep_artifacts)."""

    def _prepare_project(self, tmp_path: Path) -> None:
        """Create a fully initialized project structure for uninstall tests."""
        # CLAUDE.md with PocketTeam section
        claude_dir = tmp_path / CLAUDE_DIR
        claude_dir.mkdir(parents=True)
        (claude_dir / "CLAUDE.md").write_text(
            f"# Existing\n\n{POCKETTEAM_START}\n# PT\n{POCKETTEAM_END}\n"
        )
        # settings.json with pocketteam hooks
        settings = {
            "hooks": {
                "PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "cd /x && python -m pocketteam.safety pre"}]}]
            }
        }
        (claude_dir / "settings.json").write_text(json.dumps(settings))

        # Agent and skills dirs
        agents_dir = tmp_path / AGENTS_DIR
        agents_dir.mkdir(parents=True)
        (agents_dir / "engineer.md").write_text("# engineer")

        skills_dir = tmp_path / SKILLS_DIR
        skills_dir.mkdir(parents=True)
        (skills_dir / "deploy.md").write_text("# deploy")

        # GitHub Actions workflow
        workflow_dir = tmp_path / ".github" / "workflows"
        workflow_dir.mkdir(parents=True)
        (workflow_dir / "pocketteam-monitor.yml").write_text("name: PocketTeam Monitor")

        # .pocketteam dir
        pt_dir = tmp_path / POCKETTEAM_DIR
        pt_dir.mkdir(parents=True)
        (pt_dir / "config.yaml").write_text("project_name: test")

    @pytest.mark.asyncio
    async def test_removes_pocketteam_section_from_claude_md(self, tmp_path):
        from pocketteam.init import run_uninstall

        self._prepare_project(tmp_path)

        with (
            patch("pathlib.Path.cwd", return_value=tmp_path),
            patch("pocketteam.init.Confirm.ask", return_value=False),
            patch("pocketteam.init.console"),
        ):
            await run_uninstall(keep_artifacts=True)

        content = (tmp_path / CLAUDE_DIR / "CLAUDE.md").read_text()
        assert POCKETTEAM_START not in content
        assert POCKETTEAM_END not in content

    @pytest.mark.asyncio
    async def test_preserves_existing_content_in_claude_md(self, tmp_path):
        from pocketteam.init import run_uninstall

        self._prepare_project(tmp_path)

        with (
            patch("pathlib.Path.cwd", return_value=tmp_path),
            patch("pocketteam.init.Confirm.ask", return_value=False),
            patch("pocketteam.init.console"),
        ):
            await run_uninstall(keep_artifacts=True)

        content = (tmp_path / CLAUDE_DIR / "CLAUDE.md").read_text()
        assert "# Existing" in content

    @pytest.mark.asyncio
    async def test_removes_agent_definitions_dir(self, tmp_path):
        from pocketteam.init import run_uninstall

        self._prepare_project(tmp_path)

        with (
            patch("pathlib.Path.cwd", return_value=tmp_path),
            patch("pocketteam.init.Confirm.ask", return_value=False),
            patch("pocketteam.init.console"),
        ):
            await run_uninstall(keep_artifacts=True)

        assert not (tmp_path / AGENTS_DIR).exists()

    @pytest.mark.asyncio
    async def test_removes_skills_dir(self, tmp_path):
        from pocketteam.init import run_uninstall

        self._prepare_project(tmp_path)

        with (
            patch("pathlib.Path.cwd", return_value=tmp_path),
            patch("pocketteam.init.Confirm.ask", return_value=False),
            patch("pocketteam.init.console"),
        ):
            await run_uninstall(keep_artifacts=True)

        assert not (tmp_path / SKILLS_DIR).exists()

    @pytest.mark.asyncio
    async def test_removes_github_actions_workflow(self, tmp_path):
        from pocketteam.init import run_uninstall

        self._prepare_project(tmp_path)

        with (
            patch("pathlib.Path.cwd", return_value=tmp_path),
            patch("pocketteam.init.Confirm.ask", return_value=False),
            patch("pocketteam.init.console"),
        ):
            await run_uninstall(keep_artifacts=True)

        assert not (tmp_path / ".github" / "workflows" / "pocketteam-monitor.yml").exists()

    @pytest.mark.asyncio
    async def test_keeps_pocketteam_dir_when_keep_artifacts_true(self, tmp_path):
        from pocketteam.init import run_uninstall

        self._prepare_project(tmp_path)

        with (
            patch("pathlib.Path.cwd", return_value=tmp_path),
            patch("pocketteam.init.Confirm.ask", return_value=False),
            patch("pocketteam.init.console"),
        ):
            await run_uninstall(keep_artifacts=True)

        assert (tmp_path / POCKETTEAM_DIR).exists()

    @pytest.mark.asyncio
    async def test_removes_pocketteam_dir_when_confirmed(self, tmp_path):
        from pocketteam.init import run_uninstall

        self._prepare_project(tmp_path)

        with (
            patch("pathlib.Path.cwd", return_value=tmp_path),
            # keep_artifacts=False → asks Confirm; we return True (user confirms deletion)
            patch("pocketteam.init.Confirm.ask", return_value=True),
            patch("pocketteam.init.console"),
        ):
            await run_uninstall(keep_artifacts=False)

        assert not (tmp_path / POCKETTEAM_DIR).exists()

    @pytest.mark.asyncio
    async def test_keeps_pocketteam_dir_when_user_declines(self, tmp_path):
        from pocketteam.init import run_uninstall

        self._prepare_project(tmp_path)

        with (
            patch("pathlib.Path.cwd", return_value=tmp_path),
            # keep_artifacts=False → asks Confirm; user says no
            patch("pocketteam.init.Confirm.ask", return_value=False),
            patch("pocketteam.init.console"),
        ):
            await run_uninstall(keep_artifacts=False)

        assert (tmp_path / POCKETTEAM_DIR).exists()

    @pytest.mark.asyncio
    async def test_removes_pocketteam_hooks_from_settings_json(self, tmp_path):
        from pocketteam.init import run_uninstall

        self._prepare_project(tmp_path)

        with (
            patch("pathlib.Path.cwd", return_value=tmp_path),
            patch("pocketteam.init.Confirm.ask", return_value=False),
            patch("pocketteam.init.console"),
        ):
            await run_uninstall(keep_artifacts=True)

        settings_path = tmp_path / CLAUDE_DIR / "settings.json"
        if settings_path.exists():
            data = json.loads(settings_path.read_text())
            hooks_str = json.dumps(data.get("hooks", {}))
            assert "pocketteam" not in hooks_str


# ─────────────────────────────────────────────────────────────────────────────
# _create_gitignore
# ─────────────────────────────────────────────────────────────────────────────

class TestCreateGitignore:
    """Tests for _create_gitignore(project_root)."""

    def test_creates_gitignore(self, tmp_path):
        _create_gitignore(tmp_path)
        assert (tmp_path / ".gitignore").exists()

    def test_gitignore_ignores_pocketteam_sessions(self, tmp_path):
        _create_gitignore(tmp_path)
        content = (tmp_path / ".gitignore").read_text()
        assert ".pocketteam/" in content

    def test_gitignore_ignores_dotenv(self, tmp_path):
        _create_gitignore(tmp_path)
        content = (tmp_path / ".gitignore").read_text()
        assert ".env" in content

    def test_gitignore_keeps_env_example(self, tmp_path):
        _create_gitignore(tmp_path)
        content = (tmp_path / ".gitignore").read_text()
        assert "!.env.example" in content

    def test_gitignore_ignores_pycache(self, tmp_path):
        _create_gitignore(tmp_path)
        content = (tmp_path / ".gitignore").read_text()
        assert "__pycache__/" in content
