"""
Tests for pocketteam/dashboard.py — helper functions and logic.

All Docker/subprocess calls are mocked; no real containers are started.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from pocketteam.config import DashboardConfig, PocketTeamConfig
from pocketteam.constants import (
    DASHBOARD_IMAGE,
    DASHBOARD_PORT,
    DASHBOARD_PORT_RANGE_END,
    DASHBOARD_VERSION,
)
from pocketteam.dashboard import (
    ALLOWED_COMPOSE_COMMANDS,
    _build_compose_cmd,
    _load_dashboard_config,
    _write_auth_token,
    check_disk_space,
    dashboard_configure_cmd,
    dashboard_start_cmd,
    dashboard_status_cmd,
    dashboard_stop_cmd,
    detect_compose_command,
    ensure_pocketteam_gitignore,
    find_free_port,
    generate_compose,
    get_real_username,
    sanitize_container_name,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _make_cfg(
    tmp_path: Path,
    port: int = 3847,
    compose_command: str = "docker compose",
    docker_context: str = "default",
    compose_dir: str | None = None,
    project_root_str: str | None = None,
    container_name: str = "pocketteam-dashboard",
) -> tuple[PocketTeamConfig, Path]:
    """Build a minimal PocketTeamConfig with a real compose file on disk."""
    compose_dir_path = Path(compose_dir) if compose_dir else tmp_path / "compose"
    compose_dir_path.mkdir(parents=True, exist_ok=True)
    compose_file = compose_dir_path / "docker-compose.yml"
    compose_file.write_text("version: '3.8'\nservices:\n  dashboard:\n    image: x\n")

    cfg = PocketTeamConfig(project_root=tmp_path)
    cfg.dashboard = DashboardConfig(
        enabled=True,
        port=port,
        image=DASHBOARD_IMAGE,
        image_version=DASHBOARD_VERSION,
        compose_dir=str(compose_dir_path),
        docker_context=docker_context,
        compose_command=compose_command,
        project_root=project_root_str or str(tmp_path),
        claude_project_hash=str(tmp_path).replace("/", "-"),
        compose_checksum="",
        container_name=container_name,
    )
    return cfg, compose_file


# ─────────────────────────────────────────────────────────────────────────────
# get_real_username
# ─────────────────────────────────────────────────────────────────────────────


class TestGetRealUsername:
    def test_returns_sudo_user_when_present(self, monkeypatch):
        monkeypatch.setenv("SUDO_USER", "alice")
        assert get_real_username() == "alice"

    def test_falls_back_to_user_env(self, monkeypatch):
        monkeypatch.delenv("SUDO_USER", raising=False)
        monkeypatch.setenv("USER", "bob")
        assert get_real_username() == "bob"

    def test_falls_back_to_pwd_when_no_env(self, monkeypatch):
        monkeypatch.delenv("SUDO_USER", raising=False)
        monkeypatch.delenv("USER", raising=False)
        import pwd
        expected = pwd.getpwuid(os.getuid()).pw_name
        assert get_real_username() == expected


# ─────────────────────────────────────────────────────────────────────────────
# check_disk_space
# ─────────────────────────────────────────────────────────────────────────────


class TestCheckDiskSpace:
    def test_passes_when_enough_space(self):
        with patch("shutil.disk_usage") as mock_du:
            mock_du.return_value = MagicMock(free=500 * 1024 * 1024)
            # Should not raise
            check_disk_space(min_mb=200)

    def test_exits_when_insufficient_space(self):
        with patch("shutil.disk_usage") as mock_du:
            mock_du.return_value = MagicMock(free=100 * 1024 * 1024)
            with pytest.raises(SystemExit) as exc_info:
                check_disk_space(min_mb=200)
            assert exc_info.value.code == 1

    def test_exactly_at_limit_passes(self):
        with patch("shutil.disk_usage") as mock_du:
            mock_du.return_value = MagicMock(free=200 * 1024 * 1024)
            # Exactly 200 MB should not exit
            check_disk_space(min_mb=200)

    def test_one_byte_under_limit_exits(self):
        with patch("shutil.disk_usage") as mock_du:
            # 200 MB minus 1 byte → integer division → 199 MB free
            mock_du.return_value = MagicMock(free=200 * 1024 * 1024 - 1)
            with pytest.raises(SystemExit):
                check_disk_space(min_mb=200)


# ─────────────────────────────────────────────────────────────────────────────
# find_free_port
# ─────────────────────────────────────────────────────────────────────────────


class TestFindFreePort:
    def test_returns_first_free_port(self):
        # connect_ex returns non-zero (port free) on first try
        with patch("socket.socket") as mock_socket_cls:
            mock_sock = MagicMock()
            mock_sock.__enter__ = lambda s: mock_sock
            mock_sock.__exit__ = MagicMock(return_value=False)
            mock_sock.connect_ex.return_value = 1  # 1 = connection refused = port free
            mock_socket_cls.return_value = mock_sock
            port = find_free_port(start=3847, end=3857)
        assert port == 3847

    def test_skips_occupied_ports(self):
        """First two ports occupied (connect_ex=0), third is free."""
        results = [0, 0, 1]  # 0 = occupied
        call_count = {"n": 0}

        with patch("socket.socket") as mock_socket_cls:
            mock_sock = MagicMock()
            mock_sock.__enter__ = lambda s: mock_sock
            mock_sock.__exit__ = MagicMock(return_value=False)

            def connect_side_effect(addr):
                val = results[call_count["n"]]
                call_count["n"] += 1
                return val

            mock_sock.connect_ex.side_effect = connect_side_effect
            mock_socket_cls.return_value = mock_sock
            port = find_free_port(start=3847, end=3857)
        assert port == 3849

    def test_exits_when_all_ports_occupied(self):
        with patch("socket.socket") as mock_socket_cls:
            mock_sock = MagicMock()
            mock_sock.__enter__ = lambda s: mock_sock
            mock_sock.__exit__ = MagicMock(return_value=False)
            mock_sock.connect_ex.return_value = 0  # all occupied
            mock_socket_cls.return_value = mock_sock
            with pytest.raises(SystemExit) as exc_info:
                find_free_port(start=3847, end=3847)  # single port range
            assert exc_info.value.code == 1


# ─────────────────────────────────────────────────────────────────────────────
# detect_compose_command
# ─────────────────────────────────────────────────────────────────────────────


class TestDetectComposeCommand:
    def test_returns_docker_compose_v2(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = detect_compose_command()
        assert result == ["docker", "compose"]

    def test_falls_back_to_v1(self):
        call_results = [
            MagicMock(returncode=1),  # "docker compose version" fails
            MagicMock(returncode=0),  # "docker-compose version" succeeds
        ]
        with patch("subprocess.run", side_effect=call_results):
            result = detect_compose_command()
        assert result == ["docker-compose"]

    def test_exits_when_no_compose_found(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            with pytest.raises(SystemExit) as exc_info:
                detect_compose_command()
            assert exc_info.value.code == 1


# ─────────────────────────────────────────────────────────────────────────────
# generate_compose
# ─────────────────────────────────────────────────────────────────────────────


class TestGenerateCompose:
    def _minimal_dash(self, port: int = 3847) -> DashboardConfig:
        return DashboardConfig(
            enabled=True,
            port=port,
            image=DASHBOARD_IMAGE,
            image_version=DASHBOARD_VERSION,
        )

    def test_contains_port_binding(self):
        dash = self._minimal_dash(port=3900)
        content = generate_compose(
            dash=dash,
            claude_project_dir=Path("/home/user/.claude/projects/hash"),
            pocketteam_dir=Path("/home/user/project/.pocketteam"),
            env_file_path=Path("/home/user/.pocketteam/dashboard/hash/.env"),
        )
        assert "127.0.0.1:3900:3900" in content

    def test_contains_image_ref(self):
        dash = self._minimal_dash()
        content = generate_compose(
            dash=dash,
            claude_project_dir=Path("/a"),
            pocketteam_dir=Path("/b"),
            env_file_path=Path("/c/.env"),
        )
        assert f"{DASHBOARD_IMAGE}:{DASHBOARD_VERSION}" in content

    def test_contains_security_opts(self):
        dash = self._minimal_dash()
        content = generate_compose(
            dash=dash,
            claude_project_dir=Path("/a"),
            pocketteam_dir=Path("/b"),
            env_file_path=Path("/c/.env"),
        )
        assert "no-new-privileges:true" in content
        assert "cap_drop" in content

    def test_contains_localhost_only_binding(self):
        dash = self._minimal_dash()
        content = generate_compose(
            dash=dash,
            claude_project_dir=Path("/a"),
            pocketteam_dir=Path("/b"),
            env_file_path=Path("/c/.env"),
        )
        assert "127.0.0.1" in content

    def test_contains_read_only(self):
        dash = self._minimal_dash()
        content = generate_compose(
            dash=dash,
            claude_project_dir=Path("/a"),
            pocketteam_dir=Path("/b"),
            env_file_path=Path("/c/.env"),
        )
        assert "read_only: true" in content

    def test_contains_healthcheck(self):
        dash = self._minimal_dash()
        content = generate_compose(
            dash=dash,
            claude_project_dir=Path("/a"),
            pocketteam_dir=Path("/b"),
            env_file_path=Path("/c/.env"),
        )
        assert "healthcheck" in content
        assert "/api/v1/health" in content

    def test_volume_paths_in_compose(self):
        dash = self._minimal_dash()
        content = generate_compose(
            dash=dash,
            claude_project_dir=Path("/data/claude"),
            pocketteam_dir=Path("/data/pocketteam"),
            env_file_path=Path("/env/.env"),
        )
        assert "/data/claude:/data/claude/project:ro" in content
        assert "/data/pocketteam:/data/pocketteam:ro" in content

    def test_env_file_path_in_compose(self):
        dash = self._minimal_dash()
        content = generate_compose(
            dash=dash,
            claude_project_dir=Path("/a"),
            pocketteam_dir=Path("/b"),
            env_file_path=Path("/tokens/.env"),
        )
        assert "/tokens/.env" in content

    def test_memory_and_cpu_limits(self):
        dash = self._minimal_dash()
        content = generate_compose(
            dash=dash,
            claude_project_dir=Path("/a"),
            pocketteam_dir=Path("/b"),
            env_file_path=Path("/c/.env"),
        )
        assert "mem_limit: 256m" in content
        assert "cpus: 0.5" in content

    def test_restart_policy(self):
        dash = self._minimal_dash()
        content = generate_compose(
            dash=dash,
            claude_project_dir=Path("/a"),
            pocketteam_dir=Path("/b"),
            env_file_path=Path("/c/.env"),
        )
        assert "restart: on-failure:3" in content

    def test_port_env_var(self):
        dash = self._minimal_dash(port=3847)
        content = generate_compose(
            dash=dash,
            claude_project_dir=Path("/a"),
            pocketteam_dir=Path("/b"),
            env_file_path=Path("/c/.env"),
        )
        assert "PORT=3847" in content


# ─────────────────────────────────────────────────────────────────────────────
# sanitize_container_name
# ─────────────────────────────────────────────────────────────────────────────


class TestSanitizeContainerName:
    def test_simple_name_gets_dashboard_suffix(self):
        assert sanitize_container_name("myproject") == "myproject-dashboard"

    def test_spaces_replaced_with_hyphens(self):
        assert sanitize_container_name("My Cool Project") == "my-cool-project-dashboard"

    def test_uppercased_to_lowercase(self):
        assert sanitize_container_name("ACME") == "acme-dashboard"

    def test_special_chars_stripped(self):
        assert sanitize_container_name("my_project!@#") == "myproject-dashboard"

    def test_empty_string_falls_back_to_default(self):
        assert sanitize_container_name("") == "pocketteam-dashboard"

    def test_all_special_chars_falls_back_to_default(self):
        assert sanitize_container_name("!@#$%") == "pocketteam-dashboard"

    def test_leading_trailing_hyphens_stripped(self):
        assert sanitize_container_name("-myproject-") == "myproject-dashboard"

    def test_numbers_preserved(self):
        assert sanitize_container_name("project42") == "project42-dashboard"

    def test_mixed_spaces_and_special_chars(self):
        assert sanitize_container_name("My Project 2.0!") == "my-project-20-dashboard"


# ─────────────────────────────────────────────────────────────────────────────
# generate_compose — container_name
# ─────────────────────────────────────────────────────────────────────────────


class TestGenerateComposeContainerName:
    def _minimal_dash(self, container_name: str = "pocketteam-dashboard") -> DashboardConfig:
        return DashboardConfig(
            enabled=True,
            port=3847,
            image=DASHBOARD_IMAGE,
            image_version=DASHBOARD_VERSION,
            container_name=container_name,
        )

    def test_uses_dash_container_name_by_default(self):
        dash = self._minimal_dash(container_name="myproject-dashboard")
        content = generate_compose(
            dash=dash,
            claude_project_dir=Path("/a"),
            pocketteam_dir=Path("/b"),
            env_file_path=Path("/c/.env"),
        )
        assert "container_name: myproject-dashboard" in content

    def test_explicit_container_name_overrides_dash(self):
        dash = self._minimal_dash(container_name="myproject-dashboard")
        content = generate_compose(
            dash=dash,
            claude_project_dir=Path("/a"),
            pocketteam_dir=Path("/b"),
            env_file_path=Path("/c/.env"),
            container_name="override-dashboard",
        )
        assert "container_name: override-dashboard" in content
        assert "myproject-dashboard" not in content

    def test_fallback_when_container_name_empty(self):
        dash = self._minimal_dash(container_name="")
        content = generate_compose(
            dash=dash,
            claude_project_dir=Path("/a"),
            pocketteam_dir=Path("/b"),
            env_file_path=Path("/c/.env"),
        )
        assert "container_name: pocketteam-dashboard" in content

    def test_different_projects_get_different_container_names(self):
        dash_a = self._minimal_dash(container_name="project-alpha-dashboard")
        dash_b = self._minimal_dash(container_name="project-beta-dashboard")
        content_a = generate_compose(
            dash=dash_a,
            claude_project_dir=Path("/a"),
            pocketteam_dir=Path("/b"),
            env_file_path=Path("/c/.env"),
        )
        content_b = generate_compose(
            dash=dash_b,
            claude_project_dir=Path("/a"),
            pocketteam_dir=Path("/b"),
            env_file_path=Path("/c/.env"),
        )
        assert "container_name: project-alpha-dashboard" in content_a
        assert "container_name: project-beta-dashboard" in content_b
        assert "project-alpha-dashboard" not in content_b
        assert "project-beta-dashboard" not in content_a


# ─────────────────────────────────────────────────────────────────────────────
# _write_auth_token
# ─────────────────────────────────────────────────────────────────────────────


class TestWriteAuthToken:
    def test_creates_env_file(self, tmp_path):
        token = _write_auth_token(tmp_path)
        env_file = tmp_path / ".env"
        assert env_file.exists()

    def test_env_file_contains_auth_token(self, tmp_path):
        token = _write_auth_token(tmp_path)
        content = (tmp_path / ".env").read_text()
        assert content.startswith("AUTH_TOKEN=")
        assert token in content

    def test_token_is_64_hex_chars(self, tmp_path):
        token = _write_auth_token(tmp_path)
        assert len(token) == 64
        assert all(c in "0123456789abcdef" for c in token)

    def test_env_file_permissions_600(self, tmp_path):
        _write_auth_token(tmp_path)
        env_file = tmp_path / ".env"
        mode = oct(env_file.stat().st_mode)[-3:]
        assert mode == "600"

    def test_creates_parent_dirs(self, tmp_path):
        nested = tmp_path / "a" / "b" / "c"
        _write_auth_token(nested)
        assert (nested / ".env").exists()

    def test_tokens_are_unique(self, tmp_path):
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        token_a = _write_auth_token(dir_a)
        token_b = _write_auth_token(dir_b)
        assert token_a != token_b


# ─────────────────────────────────────────────────────────────────────────────
# ensure_pocketteam_gitignore
# ─────────────────────────────────────────────────────────────────────────────


class TestEnsurePocketteamGitignore:
    def test_creates_gitignore_with_deny_all(self, tmp_path):
        ensure_pocketteam_gitignore(tmp_path)
        gitignore = tmp_path / ".pocketteam" / ".gitignore"
        assert gitignore.exists()
        assert gitignore.read_text().strip() == "*"

    def test_does_not_overwrite_existing_gitignore(self, tmp_path):
        gitignore = tmp_path / ".pocketteam" / ".gitignore"
        gitignore.parent.mkdir(parents=True, exist_ok=True)
        gitignore.write_text("custom-rule\n")
        ensure_pocketteam_gitignore(tmp_path)
        assert gitignore.read_text() == "custom-rule\n"

    def test_creates_parent_dirs(self, tmp_path):
        ensure_pocketteam_gitignore(tmp_path)
        assert (tmp_path / ".pocketteam").is_dir()


# ─────────────────────────────────────────────────────────────────────────────
# _build_compose_cmd
# ─────────────────────────────────────────────────────────────────────────────


class TestBuildComposeCmd:
    def test_docker_compose_v2_includes_context(self, tmp_path):
        cfg, compose_file = _make_cfg(
            tmp_path, compose_command="docker compose", docker_context="orbstack"
        )
        cmd = _build_compose_cmd(cfg, compose_file)
        assert cmd[:4] == ["docker", "--context", "orbstack", "compose"]
        assert "-f" in cmd
        assert str(compose_file) in cmd

    def test_docker_compose_v1_no_context(self, tmp_path):
        cfg, compose_file = _make_cfg(
            tmp_path, compose_command="docker-compose", docker_context="default"
        )
        cmd = _build_compose_cmd(cfg, compose_file)
        assert cmd[0] == "docker-compose"
        assert "--context" not in cmd
        assert str(compose_file) in cmd

    def test_raises_on_invalid_compose_command(self, tmp_path):
        cfg, compose_file = _make_cfg(tmp_path, compose_command="rm -rf /")
        with pytest.raises(ValueError, match="Invalid compose_command"):
            _build_compose_cmd(cfg, compose_file)

    def test_allowed_compose_commands_set(self):
        assert "docker compose" in ALLOWED_COMPOSE_COMMANDS
        assert "docker-compose" in ALLOWED_COMPOSE_COMMANDS


# ─────────────────────────────────────────────────────────────────────────────
# _load_dashboard_config
# ─────────────────────────────────────────────────────────────────────────────


class TestLoadDashboardConfig:
    def test_exits_when_dashboard_not_enabled(self, tmp_path):
        with patch("pocketteam.dashboard.load_config") as mock_load:
            cfg = PocketTeamConfig(project_root=tmp_path)
            cfg.dashboard.enabled = False
            mock_load.return_value = cfg
            with pytest.raises(SystemExit) as exc_info:
                _load_dashboard_config(tmp_path)
            assert exc_info.value.code == 1

    def test_exits_when_compose_file_missing(self, tmp_path):
        with patch("pocketteam.dashboard.load_config") as mock_load:
            cfg = PocketTeamConfig(project_root=tmp_path)
            cfg.dashboard.enabled = True
            cfg.dashboard.compose_dir = str(tmp_path / "missing")
            mock_load.return_value = cfg
            with pytest.raises(SystemExit) as exc_info:
                _load_dashboard_config(tmp_path)
            assert exc_info.value.code == 1

    def test_returns_cfg_and_compose_file(self, tmp_path):
        cfg, compose_file = _make_cfg(tmp_path)
        with patch("pocketteam.dashboard.load_config", return_value=cfg):
            returned_cfg, returned_file = _load_dashboard_config(tmp_path)
        assert returned_cfg is cfg
        assert returned_file == compose_file

    def test_exits_when_compose_dir_empty(self, tmp_path):
        with patch("pocketteam.dashboard.load_config") as mock_load:
            cfg = PocketTeamConfig(project_root=tmp_path)
            cfg.dashboard.enabled = True
            cfg.dashboard.compose_dir = ""
            mock_load.return_value = cfg
            with pytest.raises(SystemExit) as exc_info:
                _load_dashboard_config(tmp_path)
            assert exc_info.value.code == 1


# ─────────────────────────────────────────────────────────────────────────────
# dashboard_start_cmd
# ─────────────────────────────────────────────────────────────────────────────


class TestDashboardStartCmd:
    def test_runs_up_dash_d(self, tmp_path):
        cfg, compose_file = _make_cfg(tmp_path, compose_command="docker compose")

        with (
            patch("pocketteam.dashboard.load_config", return_value=cfg),
            patch("pocketteam.dashboard.check_docker_daemon"),
            patch("pocketteam.dashboard.wait_for_healthy", return_value=True),
            patch("webbrowser.open"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(returncode=0)
            dashboard_start_cmd(tmp_path)

        calls = mock_run.call_args_list
        # Last call should be the up -d command
        up_call = calls[-1][0][0]
        assert "up" in up_call
        assert "-d" in up_call

    def test_exits_on_compose_failure(self, tmp_path):
        cfg, compose_file = _make_cfg(tmp_path, compose_command="docker compose")

        with (
            patch("pocketteam.dashboard.load_config", return_value=cfg),
            patch("pocketteam.dashboard.check_docker_daemon"),
            patch("subprocess.run") as mock_run,
        ):
            # First call: image inspect (returncode=0, image exists)
            # Second call: compose up (returncode=1, failure)
            mock_run.side_effect = [
                MagicMock(returncode=0),  # image inspect
                MagicMock(returncode=1),  # compose up
            ]
            with pytest.raises(SystemExit) as exc_info:
                dashboard_start_cmd(tmp_path)
            assert exc_info.value.code == 1

    def test_builds_image_when_not_found(self, tmp_path):
        cfg, compose_file = _make_cfg(tmp_path)
        # Create a dashboard dir so build_image doesn't exit
        (tmp_path / "dashboard").mkdir()
        (tmp_path / "dashboard" / "Dockerfile").write_text("FROM scratch\n")

        with (
            patch("pocketteam.dashboard.load_config", return_value=cfg),
            patch("pocketteam.dashboard.check_docker_daemon"),
            patch("pocketteam.dashboard.wait_for_healthy", return_value=False),
            patch("subprocess.run") as mock_run,
        ):
            # image inspect fails → build triggered; build succeeds; compose up succeeds
            mock_run.side_effect = [
                MagicMock(returncode=1),  # image inspect → not found
                MagicMock(returncode=0),  # docker build
                MagicMock(returncode=0),  # compose up
            ]
            dashboard_start_cmd(tmp_path)

        # Verify docker build was called
        build_call = mock_run.call_args_list[1][0][0]
        assert "build" in build_call

    def test_opens_browser_when_healthy(self, tmp_path):
        cfg, compose_file = _make_cfg(tmp_path, port=3847)

        with (
            patch("pocketteam.dashboard.load_config", return_value=cfg),
            patch("pocketteam.dashboard.check_docker_daemon"),
            patch("pocketteam.dashboard.wait_for_healthy", return_value=True),
            patch("webbrowser.open") as mock_browser,
            patch("subprocess.run", return_value=MagicMock(returncode=0)),
        ):
            dashboard_start_cmd(tmp_path)

        mock_browser.assert_called_once_with("http://localhost:3847")


# ─────────────────────────────────────────────────────────────────────────────
# dashboard_stop_cmd
# ─────────────────────────────────────────────────────────────────────────────


class TestDashboardStopCmd:
    def test_runs_compose_down(self, tmp_path):
        cfg, compose_file = _make_cfg(tmp_path, compose_command="docker compose")

        with (
            patch("pocketteam.dashboard.load_config", return_value=cfg),
            patch("pocketteam.dashboard.check_docker_daemon"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(returncode=0)
            dashboard_stop_cmd(tmp_path)

        last_cmd = mock_run.call_args[0][0]
        assert "down" in last_cmd

    def test_stop_uses_correct_context(self, tmp_path):
        cfg, compose_file = _make_cfg(
            tmp_path, compose_command="docker compose", docker_context="orbstack"
        )

        with (
            patch("pocketteam.dashboard.load_config", return_value=cfg),
            patch("pocketteam.dashboard.check_docker_daemon"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(returncode=0)
            dashboard_stop_cmd(tmp_path)

        last_cmd = mock_run.call_args[0][0]
        assert "--context" in last_cmd
        assert "orbstack" in last_cmd


# ─────────────────────────────────────────────────────────────────────────────
# dashboard_status_cmd
# ─────────────────────────────────────────────────────────────────────────────


class TestDashboardStatusCmd:
    def test_exits_nonzero_when_container_not_found(self, tmp_path):
        cfg, compose_file = _make_cfg(tmp_path)

        with (
            patch("pocketteam.dashboard.load_config", return_value=cfg),
            patch("pocketteam.dashboard.check_docker_daemon"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(
                returncode=1, stdout="", text=True
            )
            with pytest.raises(SystemExit) as exc_info:
                dashboard_status_cmd(tmp_path)
            assert exc_info.value.code == 1

    def test_exits_nonzero_when_not_running(self, tmp_path):
        cfg, compose_file = _make_cfg(tmp_path)

        with (
            patch("pocketteam.dashboard.load_config", return_value=cfg),
            patch("pocketteam.dashboard.check_docker_daemon"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="exited (up 2026-01-01T00:00:00Z)\n",
                text=True,
            )
            with pytest.raises(SystemExit) as exc_info:
                dashboard_status_cmd(tmp_path)
            assert exc_info.value.code == 1

    def test_no_exit_when_running(self, tmp_path):
        cfg, compose_file = _make_cfg(tmp_path)
        pocketteam_dir = tmp_path / ".pocketteam"
        pocketteam_dir.mkdir(parents=True, exist_ok=True)

        with (
            patch("pocketteam.dashboard.load_config", return_value=cfg),
            patch("pocketteam.dashboard.check_docker_daemon"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="running (up 2026-01-01T00:00:00Z)\n",
                text=True,
            )
            # Should NOT raise SystemExit
            dashboard_status_cmd(tmp_path)

    def test_uses_docker_inspect(self, tmp_path):
        cfg, compose_file = _make_cfg(
            tmp_path,
            docker_context="desktop-linux",
            container_name="myproject-dashboard",
        )
        pocketteam_dir = tmp_path / ".pocketteam"
        pocketteam_dir.mkdir(parents=True, exist_ok=True)

        with (
            patch("pocketteam.dashboard.load_config", return_value=cfg),
            patch("pocketteam.dashboard.check_docker_daemon"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="running (up 2026-01-01T00:00:00Z)\n",
                text=True,
            )
            dashboard_status_cmd(tmp_path)

        cmd = mock_run.call_args[0][0]
        assert "inspect" in cmd
        assert "myproject-dashboard" in cmd
        assert "desktop-linux" in cmd


# ─────────────────────────────────────────────────────────────────────────────
# dashboard_configure_cmd
# ─────────────────────────────────────────────────────────────────────────────


class TestDashboardConfigureCmd:
    def test_no_changes_returns_early(self, tmp_path):
        cfg, compose_file = _make_cfg(tmp_path)

        with (
            patch("pocketteam.dashboard.load_config", return_value=cfg),
            patch("pocketteam.dashboard.check_docker_daemon"),
            patch("subprocess.run") as mock_run,
        ):
            # Should not call subprocess at all
            dashboard_configure_cmd(tmp_path)
            mock_run.assert_not_called()

    def test_updates_port_in_config(self, tmp_path):
        cfg, compose_file = _make_cfg(tmp_path, port=3847)

        with (
            patch("pocketteam.dashboard.load_config", return_value=cfg),
            patch("pocketteam.dashboard.save_config") as mock_save,
            patch("pocketteam.dashboard.check_docker_daemon"),
            patch("pocketteam.dashboard.wait_for_healthy", return_value=True),
            patch("subprocess.run", return_value=MagicMock(returncode=0)),
        ):
            dashboard_configure_cmd(tmp_path, port=4000)

        mock_save.assert_called()
        assert cfg.dashboard.port == 4000

    def test_updates_domain_in_config(self, tmp_path):
        cfg, compose_file = _make_cfg(tmp_path)

        with (
            patch("pocketteam.dashboard.load_config", return_value=cfg),
            patch("pocketteam.dashboard.save_config"),
            patch("pocketteam.dashboard.check_docker_daemon"),
            patch("pocketteam.dashboard.wait_for_healthy", return_value=True),
            patch("subprocess.run", return_value=MagicMock(returncode=0)),
        ):
            dashboard_configure_cmd(tmp_path, domain="dashboard.example.com")

        assert cfg.dashboard.domain == "dashboard.example.com"

    def test_project_root_override_must_be_under_home(self, tmp_path):
        cfg, compose_file = _make_cfg(tmp_path)

        with (
            patch("pocketteam.dashboard.load_config", return_value=cfg),
        ):
            # /tmp is not under home on most systems
            # We simulate this by making the resolved path not relative to home
            with patch("pathlib.Path.is_relative_to", return_value=False):
                with pytest.raises(SystemExit) as exc_info:
                    dashboard_configure_cmd(tmp_path, project_root_override="/tmp/bad")
                assert exc_info.value.code == 1

    def test_project_root_override_must_be_existing_dir(self, tmp_path):
        cfg, compose_file = _make_cfg(tmp_path)

        with (
            patch("pocketteam.dashboard.load_config", return_value=cfg),
            patch("pathlib.Path.is_relative_to", return_value=True),
        ):
            with pytest.raises(SystemExit) as exc_info:
                dashboard_configure_cmd(
                    tmp_path,
                    project_root_override=str(tmp_path / "nonexistent"),
                )
            assert exc_info.value.code == 1

    def test_regenerates_compose_file_on_port_change(self, tmp_path):
        cfg, compose_file = _make_cfg(tmp_path, port=3847)

        with (
            patch("pocketteam.dashboard.load_config", return_value=cfg),
            patch("pocketteam.dashboard.save_config"),
            patch("pocketteam.dashboard.check_docker_daemon"),
            patch("pocketteam.dashboard.wait_for_healthy", return_value=True),
            patch("subprocess.run", return_value=MagicMock(returncode=0)),
        ):
            dashboard_configure_cmd(tmp_path, port=4000)

        # Compose file should have been rewritten with new port
        content = compose_file.read_text()
        assert "4000" in content

    def test_restarts_container_after_configure(self, tmp_path):
        cfg, compose_file = _make_cfg(tmp_path, compose_command="docker compose")

        with (
            patch("pocketteam.dashboard.load_config", return_value=cfg),
            patch("pocketteam.dashboard.save_config"),
            patch("pocketteam.dashboard.check_docker_daemon"),
            patch("pocketteam.dashboard.wait_for_healthy", return_value=True),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(returncode=0)
            dashboard_configure_cmd(tmp_path, port=4000)

        calls = [c[0][0] for c in mock_run.call_args_list]
        # Should have called down then up -d
        down_calls = [c for c in calls if "down" in c]
        up_calls = [c for c in calls if "up" in c]
        assert len(down_calls) >= 1
        assert len(up_calls) >= 1

    def test_compose_checksum_updated_after_regeneration(self, tmp_path):
        cfg, compose_file = _make_cfg(tmp_path, port=3847)

        with (
            patch("pocketteam.dashboard.load_config", return_value=cfg),
            patch("pocketteam.dashboard.save_config"),
            patch("pocketteam.dashboard.check_docker_daemon"),
            patch("pocketteam.dashboard.wait_for_healthy", return_value=True),
            patch("subprocess.run", return_value=MagicMock(returncode=0)),
        ):
            dashboard_configure_cmd(tmp_path, port=4000)

        # Checksum should now reflect new compose content
        new_content = compose_file.read_text()
        expected_checksum = hashlib.sha256(new_content.encode()).hexdigest()
        assert cfg.dashboard.compose_checksum == expected_checksum
