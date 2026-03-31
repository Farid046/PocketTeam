"""
Unit tests for pocketteam/telegram_daemon.py
No real HTTP calls, no real subprocesses, no real filesystem outside tmp_path.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pocketteam.telegram_daemon import (
    TelegramDaemon,
    load_allowed_users,
    load_bot_token,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def project_root(tmp_path: Path) -> Path:
    pt = tmp_path / ".pocketteam"
    pt.mkdir()
    return tmp_path


@pytest.fixture()
def daemon(project_root: Path) -> TelegramDaemon:
    return TelegramDaemon(
        project_root=project_root,
        bot_token="test-token",
        allowed_users=["111"],
    )


def _make_update(text: str, user_id: str = "111", chat_id: str = "999") -> dict:
    return {
        "update_id": 1,
        "message": {
            "text": text,
            "from": {"id": int(user_id)},
            "chat": {"id": int(chat_id)},
        },
    }


# ---------------------------------------------------------------------------
# __init__ — state initialization and state file loading
# ---------------------------------------------------------------------------


class TestInit:
    def test_default_state_fields(self, project_root: Path):
        d = TelegramDaemon(project_root, "tok", ["1"])
        assert d.offset == 0
        assert d._shutdown is False
        assert d._launch_cooldown == 0.0
        assert d.sessions_launched == 0
        assert d.allowed_users == ["1"]
        assert d.bot_token == "tok"

    def test_api_base_contains_token(self, project_root: Path):
        d = TelegramDaemon(project_root, "mytoken", [])
        assert "mytoken" in d.api_base

    def test_file_paths_under_pocketteam(self, project_root: Path):
        d = TelegramDaemon(project_root, "tok", [])
        assert d.state_file.parent == project_root / ".pocketteam"
        assert d.inbox_file.parent == project_root / ".pocketteam"
        assert d.launching_lock.parent == project_root / ".pocketteam"

    def test_restores_cooldown_from_state_file(self, project_root: Path):
        state_file = project_root / ".pocketteam" / "telegram-daemon.json"
        state_file.write_text(json.dumps({"launch_cooldown": 1234567.0}))
        d = TelegramDaemon(project_root, "tok", [])
        assert d._launch_cooldown == 1234567.0

    def test_missing_state_file_uses_zero_cooldown(self, project_root: Path):
        d = TelegramDaemon(project_root, "tok", [])
        assert d._launch_cooldown == 0.0

    def test_corrupt_state_file_uses_zero_cooldown(self, project_root: Path):
        state_file = project_root / ".pocketteam" / "telegram-daemon.json"
        state_file.write_text("not-json{{{")
        d = TelegramDaemon(project_root, "tok", [])
        assert d._launch_cooldown == 0.0


# ---------------------------------------------------------------------------
# _write_inbox
# ---------------------------------------------------------------------------


class TestWriteInbox:
    def test_creates_jsonl_entry(self, daemon: TelegramDaemon):
        daemon._write_inbox("hello world", "111", "999")
        lines = daemon.inbox_file.read_text().splitlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["text"] == "hello world"
        assert entry["from"] == "111"
        assert entry["chat_id"] == "999"
        assert entry["status"] == "received"
        assert entry["source"] == "daemon"
        assert "ts" in entry

    def test_appends_multiple_entries(self, daemon: TelegramDaemon):
        daemon._write_inbox("msg1", "111", "999")
        daemon._write_inbox("msg2", "111", "999")
        lines = daemon.inbox_file.read_text().splitlines()
        assert len(lines) == 2

    def test_creates_parent_directory(self, project_root: Path):
        # Remove .pocketteam and re-create daemon with fresh project root
        import shutil
        new_root = project_root.parent / "new_proj"
        new_root.mkdir()
        (new_root / ".pocketteam").mkdir()
        d = TelegramDaemon(new_root, "tok", ["1"])
        shutil.rmtree(new_root / ".pocketteam")
        d._write_inbox("hi", "1", "1")
        assert d.inbox_file.exists()


# ---------------------------------------------------------------------------
# _write_state
# ---------------------------------------------------------------------------


class TestWriteState:
    def test_writes_json_state_file(self, daemon: TelegramDaemon):
        daemon._write_state("polling")
        data = json.loads(daemon.state_file.read_text())
        assert data["state"] == "polling"
        assert data["pid"] == os.getpid()
        assert "last_update" in data
        assert "sessions_launched" in data
        assert "project_root" in data
        assert "launch_cooldown" in data

    def test_state_values_are_persisted(self, daemon: TelegramDaemon):
        daemon.sessions_launched = 5
        daemon._launch_cooldown = 99.9
        daemon._write_state("launching")
        data = json.loads(daemon.state_file.read_text())
        assert data["state"] == "launching"
        assert data["sessions_launched"] == 5
        assert data["launch_cooldown"] == pytest.approx(99.9)

    def test_creates_parent_directory(self, project_root: Path):
        new_root = project_root.parent / "new_proj2"
        new_root.mkdir()
        (new_root / ".pocketteam").mkdir()
        d = TelegramDaemon(new_root, "tok", ["1"])
        import shutil
        shutil.rmtree(new_root / ".pocketteam")
        d._write_state("polling")
        assert d.state_file.exists()


# ---------------------------------------------------------------------------
# _reload_access
# ---------------------------------------------------------------------------


class TestReloadAccess:
    def test_updates_allowed_users(self, daemon: TelegramDaemon, tmp_path: Path):
        access_file = tmp_path / "access.json"
        access_file.write_text(json.dumps({"allowFrom": ["222", "333"]}))
        with patch("pathlib.Path.home", return_value=tmp_path):
            # Re-point the access file path by patching home
            access_path = Path(tmp_path) / ".claude" / "channels" / "telegram" / "access.json"
            access_path.parent.mkdir(parents=True, exist_ok=True)
            access_path.write_text(json.dumps({"allowFrom": ["222", "333"]}))
            daemon._reload_access()
        assert "222" in daemon.allowed_users
        assert "333" in daemon.allowed_users

    def test_keeps_existing_on_read_failure(self, daemon: TelegramDaemon):
        original = list(daemon.allowed_users)
        with patch("pathlib.Path.home", return_value=Path("/nonexistent/path")):
            daemon._reload_access()
        assert daemon.allowed_users == original


# ---------------------------------------------------------------------------
# _find_claude
# ---------------------------------------------------------------------------


class TestFindClaude:
    def test_returns_path_when_which_finds_it(self, daemon: TelegramDaemon, tmp_path: Path):
        fake_claude = tmp_path / "claude"
        fake_claude.touch()
        with patch("shutil.which", return_value=str(fake_claude)):
            result = daemon._find_claude()
        assert result == str(fake_claude)

    def test_returns_none_when_not_found(self, daemon: TelegramDaemon):
        with patch("shutil.which", return_value=None), \
             patch("os.path.isfile", return_value=False):
            result = daemon._find_claude()
        assert result is None

    def test_falls_back_to_known_location(self, daemon: TelegramDaemon, tmp_path: Path):
        fake_bun_claude = tmp_path / ".bun" / "bin" / "claude"
        fake_bun_claude.parent.mkdir(parents=True)
        fake_bun_claude.touch()

        def fake_isfile(path: str) -> bool:
            return path == str(fake_bun_claude)

        with patch("shutil.which", return_value=None), \
             patch("os.path.expanduser", side_effect=lambda p: p.replace("~", str(tmp_path))), \
             patch("os.path.isfile", side_effect=fake_isfile):
            result = daemon._find_claude()
        assert result == str(fake_bun_claude)


# ---------------------------------------------------------------------------
# _is_claude_running
# ---------------------------------------------------------------------------


class TestIsClaudeRunning:
    def test_returns_true_when_pgrep_finds_process(self, daemon: TelegramDaemon):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "99999\n"  # a PID that is not ours
        with patch("subprocess.run", return_value=mock_result):
            assert daemon._is_claude_running() is True

    def test_ignores_own_pid(self, daemon: TelegramDaemon):
        own_pid = str(os.getpid())
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = f"{own_pid}\n"
        with patch("subprocess.run", return_value=mock_result):
            # Only our own PID found — should NOT count as running
            # (Method 1b and 2 also absent, so returns False)
            result = daemon._is_claude_running()
        assert result is False

    def test_returns_false_when_pgrep_finds_nothing(self, daemon: TelegramDaemon):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        with patch("subprocess.run", return_value=mock_result):
            assert daemon._is_claude_running() is False

    def test_returns_true_for_fresh_launching_lock(self, daemon: TelegramDaemon):
        lock_data = {"ts": time.time(), "pid": os.getpid()}
        daemon.launching_lock.write_text(json.dumps(lock_data))
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        with patch("subprocess.run", return_value=mock_result):
            assert daemon._is_claude_running() is True

    def test_removes_stale_launching_lock(self, daemon: TelegramDaemon):
        stale_ts = time.time() - 200  # 200s old > 120s threshold
        lock_data = {"ts": stale_ts, "pid": 12345}
        daemon.launching_lock.write_text(json.dumps(lock_data))
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        with patch("subprocess.run", return_value=mock_result):
            result = daemon._is_claude_running()
        assert not daemon.launching_lock.exists()
        assert result is False

    def test_returns_true_for_fresh_session_lock(self, daemon: TelegramDaemon):
        session_lock = daemon.project_root / ".pocketteam" / "session.lock"
        session_lock.write_text("{}")
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        with patch("subprocess.run", return_value=mock_result):
            assert daemon._is_claude_running() is True

    def test_removes_stale_session_lock(self, daemon: TelegramDaemon, tmp_path: Path):
        session_lock = daemon.project_root / ".pocketteam" / "session.lock"
        session_lock.write_text("{}")
        # Set mtime to 200s ago
        stale_time = time.time() - 200
        os.utime(session_lock, (stale_time, stale_time))
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        with patch("subprocess.run", return_value=mock_result):
            result = daemon._is_claude_running()
        assert not session_lock.exists()
        assert result is False

    def test_handles_pgrep_exception(self, daemon: TelegramDaemon):
        with patch("subprocess.run", side_effect=Exception("pgrep not found")):
            # Should not raise; falls through to lock-file checks and returns False
            result = daemon._is_claude_running()
        assert result is False


# ---------------------------------------------------------------------------
# _handle_update
# ---------------------------------------------------------------------------


class TestHandleUpdate:
    @pytest.mark.asyncio
    async def test_rejects_unauthorized_user(self, daemon: TelegramDaemon):
        update = _make_update("hello", user_id="999")
        with patch.object(daemon, "_reload_access"), \
             patch.object(daemon, "_write_inbox") as mock_inbox:
            await daemon._handle_update(update)
        mock_inbox.assert_not_called()

    @pytest.mark.asyncio
    async def test_ignores_empty_text(self, daemon: TelegramDaemon):
        update = {"update_id": 1, "message": {"text": "", "from": {"id": 111}, "chat": {"id": 999}}}
        with patch.object(daemon, "_write_inbox") as mock_inbox:
            await daemon._handle_update(update)
        mock_inbox.assert_not_called()

    @pytest.mark.asyncio
    async def test_ignores_missing_user(self, daemon: TelegramDaemon):
        update = {"update_id": 1, "message": {"text": "hi", "from": {}, "chat": {"id": 999}}}
        with patch.object(daemon, "_write_inbox") as mock_inbox:
            await daemon._handle_update(update)
        mock_inbox.assert_not_called()

    @pytest.mark.asyncio
    async def test_normal_message_writes_inbox(self, daemon: TelegramDaemon):
        update = _make_update("run tests")
        with patch.object(daemon, "_is_claude_running", return_value=False), \
             patch.object(daemon, "_launch_session", new_callable=AsyncMock), \
             patch.object(daemon, "_write_inbox") as mock_inbox:
            # Set cooldown far in past so launch is triggered
            daemon._launch_cooldown = 0.0
            await daemon._handle_update(update)
        mock_inbox.assert_called_once_with("run tests", "111", "999")

    @pytest.mark.asyncio
    async def test_session_running_saves_to_inbox_only(self, daemon: TelegramDaemon):
        update = _make_update("do work")
        with patch.object(daemon, "_is_claude_running", return_value=True), \
             patch.object(daemon, "_launch_session", new_callable=AsyncMock) as mock_launch, \
             patch.object(daemon, "_write_inbox") as mock_inbox:
            await daemon._handle_update(update)
        mock_inbox.assert_called_once()
        mock_launch.assert_not_called()

    @pytest.mark.asyncio
    async def test_cooldown_active_saves_to_inbox_only(self, daemon: TelegramDaemon):
        update = _make_update("do work")
        daemon._launch_cooldown = time.time()  # just launched
        with patch.object(daemon, "_is_claude_running", return_value=False), \
             patch.object(daemon, "_launch_session", new_callable=AsyncMock) as mock_launch, \
             patch.object(daemon, "_write_inbox") as mock_inbox:
            await daemon._handle_update(update)
        mock_inbox.assert_called_once()
        mock_launch.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_cooldown_launches_session(self, daemon: TelegramDaemon):
        update = _make_update("start work")
        daemon._launch_cooldown = 0.0
        with patch.object(daemon, "_is_claude_running", return_value=False), \
             patch.object(daemon, "_launch_session", new_callable=AsyncMock) as mock_launch, \
             patch.object(daemon, "_write_inbox"):
            await daemon._handle_update(update)
        mock_launch.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_unknown_user_reloads_access_then_rejects(self, daemon: TelegramDaemon):
        """If user not in list initially, _reload_access is called; if still absent, rejected."""
        update = _make_update("hi", user_id="888")
        reloaded = False

        def fake_reload():
            nonlocal reloaded
            reloaded = True
            # does NOT add 888 to allowed_users

        with patch.object(daemon, "_reload_access", side_effect=fake_reload), \
             patch.object(daemon, "_write_inbox") as mock_inbox:
            await daemon._handle_update(update)
        assert reloaded
        mock_inbox.assert_not_called()

    @pytest.mark.asyncio
    async def test_unknown_user_allowed_after_reload(self, daemon: TelegramDaemon):
        """If _reload_access adds the user, message is processed."""
        update = _make_update("hi", user_id="888")

        def fake_reload():
            daemon.allowed_users.append("888")

        with patch.object(daemon, "_reload_access", side_effect=fake_reload), \
             patch.object(daemon, "_is_claude_running", return_value=True), \
             patch.object(daemon, "_write_inbox") as mock_inbox:
            await daemon._handle_update(update)
        mock_inbox.assert_called_once()

    @pytest.mark.asyncio
    async def test_launch_sets_cooldown_timestamp(self, daemon: TelegramDaemon):
        update = _make_update("go")
        daemon._launch_cooldown = 0.0
        with patch.object(daemon, "_is_claude_running", return_value=False), \
             patch.object(daemon, "_launch_session", new_callable=AsyncMock), \
             patch.object(daemon, "_write_inbox"):
            before = time.time()
            await daemon._handle_update(update)
            after = time.time()
        assert before <= daemon._launch_cooldown <= after


# ---------------------------------------------------------------------------
# Helper functions: load_bot_token / load_allowed_users
# ---------------------------------------------------------------------------


class TestLoadBotToken:
    def test_returns_token_from_env_file(self, tmp_path: Path):
        env_dir = tmp_path / ".claude" / "channels" / "telegram"
        env_dir.mkdir(parents=True)
        (env_dir / ".env").write_text('TELEGRAM_BOT_TOKEN="abc123"\n')
        with patch("pathlib.Path.home", return_value=tmp_path):
            token = load_bot_token()
        assert token == "abc123"

    def test_returns_token_without_quotes(self, tmp_path: Path):
        env_dir = tmp_path / ".claude" / "channels" / "telegram"
        env_dir.mkdir(parents=True)
        (env_dir / ".env").write_text("TELEGRAM_BOT_TOKEN=plain_token\n")
        with patch("pathlib.Path.home", return_value=tmp_path):
            token = load_bot_token()
        assert token == "plain_token"

    def test_returns_none_when_file_missing(self, tmp_path: Path):
        with patch("pathlib.Path.home", return_value=tmp_path):
            token = load_bot_token()
        assert token is None

    def test_returns_none_when_key_absent(self, tmp_path: Path):
        env_dir = tmp_path / ".claude" / "channels" / "telegram"
        env_dir.mkdir(parents=True)
        (env_dir / ".env").write_text("OTHER_KEY=value\n")
        with patch("pathlib.Path.home", return_value=tmp_path):
            token = load_bot_token()
        assert token is None

    def test_handles_single_quoted_token(self, tmp_path: Path):
        env_dir = tmp_path / ".claude" / "channels" / "telegram"
        env_dir.mkdir(parents=True)
        (env_dir / ".env").write_text("TELEGRAM_BOT_TOKEN='single_quoted'\n")
        with patch("pathlib.Path.home", return_value=tmp_path):
            token = load_bot_token()
        assert token == "single_quoted"

    def test_token_with_equals_in_value(self, tmp_path: Path):
        env_dir = tmp_path / ".claude" / "channels" / "telegram"
        env_dir.mkdir(parents=True)
        (env_dir / ".env").write_text("TELEGRAM_BOT_TOKEN=tok=en\n")
        with patch("pathlib.Path.home", return_value=tmp_path):
            token = load_bot_token()
        assert token == "tok=en"


class TestLoadAllowedUsers:
    def test_returns_list_from_access_json(self, tmp_path: Path):
        access_dir = tmp_path / ".claude" / "channels" / "telegram"
        access_dir.mkdir(parents=True)
        (access_dir / "access.json").write_text(json.dumps({"allowFrom": ["111", "222"]}))
        with patch("pathlib.Path.home", return_value=tmp_path):
            users = load_allowed_users()
        assert users == ["111", "222"]

    def test_returns_empty_list_when_file_missing(self, tmp_path: Path):
        with patch("pathlib.Path.home", return_value=tmp_path):
            users = load_allowed_users()
        assert users == []

    def test_returns_empty_list_on_corrupt_json(self, tmp_path: Path):
        access_dir = tmp_path / ".claude" / "channels" / "telegram"
        access_dir.mkdir(parents=True)
        (access_dir / "access.json").write_text("not-json")
        with patch("pathlib.Path.home", return_value=tmp_path):
            users = load_allowed_users()
        assert users == []

    def test_returns_empty_list_when_allowFrom_absent(self, tmp_path: Path):
        access_dir = tmp_path / ".claude" / "channels" / "telegram"
        access_dir.mkdir(parents=True)
        (access_dir / "access.json").write_text(json.dumps({"other_key": []}))
        with patch("pathlib.Path.home", return_value=tmp_path):
            users = load_allowed_users()
        assert users == []
