"""
Phase 4 Tests: Init GitHub integration.

Tests that `pocketteam init` correctly sets up GitHub integration.
All GitHub API calls are mocked — no real repos are created.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from pocketteam.config import GitHubConfig, PocketTeamConfig, load_config, save_config
from pocketteam.github_setup import (
    GitHubSetupError,
    check_gh_authenticated,
    check_gh_installed,
    create_repo,
    get_gh_username,
    repo_exists,
    run_github_setup,
    set_repo_secret,
    set_repo_secrets,
)


class TestGhCliChecks:
    """Test gh CLI detection and auth status."""

    def test_check_gh_installed_found(self) -> None:
        with patch("pocketteam.github_setup.shutil.which", return_value="/usr/bin/gh"):
            assert check_gh_installed() is True

    def test_check_gh_installed_not_found(self) -> None:
        with patch("pocketteam.github_setup.shutil.which", return_value=None):
            assert check_gh_installed() is False

    def test_check_gh_authenticated_success(self) -> None:
        with patch("pocketteam.github_setup.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            assert check_gh_authenticated() is True

    def test_check_gh_authenticated_failure(self) -> None:
        with patch("pocketteam.github_setup.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            assert check_gh_authenticated() is False

    def test_get_gh_username(self) -> None:
        with patch("pocketteam.github_setup.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="testuser\n")
            assert get_gh_username() == "testuser"

    def test_get_gh_username_fails(self) -> None:
        with patch("pocketteam.github_setup.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr="not logged in")
            with pytest.raises(GitHubSetupError):
                get_gh_username()


class TestRepoOperations:
    """Test repo creation and secret management."""

    def test_repo_exists_true(self) -> None:
        with patch("pocketteam.github_setup.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            assert repo_exists("owner", "repo") is True

    def test_repo_exists_false(self) -> None:
        with patch("pocketteam.github_setup.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            assert repo_exists("owner", "repo") is False

    def test_create_repo_success(self) -> None:
        with patch("pocketteam.github_setup.subprocess.run") as mock_run, \
             patch("pocketteam.github_setup.get_gh_username", return_value="testuser"):
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="https://github.com/testuser/my-app\n",
                stderr="",
            )
            result = create_repo("my-app", private=True)
            assert result == "testuser/my-app"

    def test_create_repo_failure(self) -> None:
        with patch("pocketteam.github_setup.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1, stdout="", stderr="repo already exists"
            )
            with pytest.raises(GitHubSetupError, match="repo already exists"):
                create_repo("my-app")

    def test_set_repo_secret_success(self) -> None:
        with patch("pocketteam.github_setup.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            assert set_repo_secret("owner/repo", "KEY", "value") is True

    def test_set_repo_secret_empty_value(self) -> None:
        assert set_repo_secret("owner/repo", "KEY", "") is False

    def test_set_repo_secrets_with_config(self) -> None:
        cfg = PocketTeamConfig(
            auth=MagicMock(api_key="sk-ant-test"),
            telegram=MagicMock(bot_token="bot123", chat_id="456"),
        )
        with patch("pocketteam.github_setup.subprocess.run") as mock_run, \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-ant-test"}):
            mock_run.return_value = MagicMock(returncode=0)
            secrets = set_repo_secrets("owner/repo", cfg)
            assert secrets.get("ANTHROPIC_API_KEY") is True
            assert secrets.get("TELEGRAM_BOT_TOKEN") is True
            assert secrets.get("TELEGRAM_CHAT_ID") is True


class TestRunGitHubSetup:
    """Test the full run_github_setup flow."""

    def test_no_gh_cli_skips(self, tmp_path: Path) -> None:
        cfg = PocketTeamConfig(project_root=tmp_path, project_name="test")
        with patch("pocketteam.github_setup.check_gh_installed", return_value=False):
            result = run_github_setup(tmp_path, cfg, accept_defaults=True)
            assert result.enabled is False

    def test_not_authenticated_skips_in_yes_mode(self, tmp_path: Path) -> None:
        cfg = PocketTeamConfig(project_root=tmp_path, project_name="test")
        with patch("pocketteam.github_setup.check_gh_installed", return_value=True), \
             patch("pocketteam.github_setup.check_gh_authenticated", return_value=False):
            result = run_github_setup(tmp_path, cfg, accept_defaults=True)
            assert result.enabled is False

    def test_full_flow_new_repo(self, tmp_path: Path) -> None:
        cfg = PocketTeamConfig(project_root=tmp_path, project_name="my-project")
        cfg.auth.api_key = "sk-ant-test"

        # Create workflow dir so push_workflow can find the file
        wf_dir = tmp_path / ".github" / "workflows"
        wf_dir.mkdir(parents=True)
        (wf_dir / "pocketteam-monitor.yml").write_text("name: test")

        # Init git
        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=False)
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=False)
        subprocess.run(
            ["git", "commit", "-m", "init", "--allow-empty"],
            cwd=tmp_path, capture_output=True, check=False,
        )

        with patch("pocketteam.github_setup.check_gh_installed", return_value=True), \
             patch("pocketteam.github_setup.check_gh_authenticated", return_value=True), \
             patch("pocketteam.github_setup.get_gh_username", return_value="ceo-farid"), \
             patch("pocketteam.github_setup.repo_exists", return_value=False), \
             patch("pocketteam.github_setup.create_repo", return_value="ceo-farid/my-project"), \
             patch("pocketteam.github_setup.set_repo_secrets", return_value={"ANTHROPIC_API_KEY": True}), \
             patch("pocketteam.github_setup.push_workflow", return_value=True):

            result = run_github_setup(tmp_path, cfg, accept_defaults=True)

        assert result.enabled is True
        assert result.repo_owner == "ceo-farid"
        assert result.repo_name == "my-project"

    def test_full_flow_existing_repo(self, tmp_path: Path) -> None:
        cfg = PocketTeamConfig(project_root=tmp_path, project_name="existing")
        cfg.github.repo_name = "existing"

        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=False)

        with patch("pocketteam.github_setup.check_gh_installed", return_value=True), \
             patch("pocketteam.github_setup.check_gh_authenticated", return_value=True), \
             patch("pocketteam.github_setup.get_gh_username", return_value="ceo-farid"), \
             patch("pocketteam.github_setup.repo_exists", return_value=True), \
             patch("pocketteam.github_setup.set_repo_secrets", return_value={}), \
             patch("pocketteam.github_setup.subprocess.run") as mock_run:

            mock_run.return_value = MagicMock(returncode=0)
            result = run_github_setup(tmp_path, cfg, accept_defaults=True)

        assert result.enabled is True
        assert result.repo_owner == "ceo-farid"


class TestConfigGitHubRoundtrip:
    """Test that GitHub config survives save/load."""

    def test_save_load_github_config(self, tmp_path: Path) -> None:
        pt_dir = tmp_path / ".pocketteam"
        pt_dir.mkdir()

        cfg = PocketTeamConfig(project_root=tmp_path, project_name="roundtrip-test")
        cfg.github.enabled = True
        cfg.github.repo_name = "my-repo"
        cfg.github.repo_owner = "testuser"
        cfg.github.repo_private = True
        cfg.github.actions_enabled = True
        cfg.github.schedule = "*/30 * * * *"

        save_config(cfg)

        loaded = load_config(tmp_path)
        assert loaded.github.enabled is True
        assert loaded.github.repo_name == "my-repo"
        assert loaded.github.repo_owner == "testuser"
        assert loaded.github.repo_private is True
        assert loaded.github.actions_enabled is True
        assert loaded.github.schedule == "*/30 * * * *"

    def test_backwards_compat_github_actions_property(self, tmp_path: Path) -> None:
        """cfg.github_actions should still work as alias."""
        pt_dir = tmp_path / ".pocketteam"
        pt_dir.mkdir()

        cfg = PocketTeamConfig(project_root=tmp_path, project_name="compat-test")
        cfg.github_actions.enabled = True
        cfg.github_actions.schedule = "0 */2 * * *"

        # Should be reflected in cfg.github
        assert cfg.github.enabled is True
        assert cfg.github.schedule == "0 */2 * * *"

    def test_load_legacy_github_actions_key(self, tmp_path: Path) -> None:
        """Config files with old 'github_actions' key should still load."""
        pt_dir = tmp_path / ".pocketteam"
        pt_dir.mkdir()

        legacy_config = {
            "project": {"name": "legacy", "health_url": ""},
            "github_actions": {
                "enabled": True,
                "api_key": "$ANTHROPIC_API_KEY",
                "model": "claude-haiku-4-5-20251001",
                "schedule": "0 * * * *",
            },
        }
        (pt_dir / "config.yaml").write_text(yaml.dump(legacy_config))

        loaded = load_config(tmp_path)
        assert loaded.github.enabled is True
        assert loaded.github.schedule == "0 * * * *"
