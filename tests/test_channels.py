"""
Tests for Phase 10: Channels + Session Management.
No real Telegram API calls — all HTTP is mocked.
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from pocketteam.channels.remote import RemoteSession, discover_sessions
from pocketteam.channels.setup import SessionManager, TelegramChannel
from pocketteam.config import PocketTeamConfig, TelegramConfig

# ── TelegramChannel ─────────────────────────────────────────────────────────

class TestTelegramChannelConfig:
    def test_not_configured_without_token(self, tmp_path: Path):
        cfg = PocketTeamConfig(project_root=tmp_path)
        ch = TelegramChannel(tmp_path, config=cfg)
        assert ch.is_configured is False

    def test_configured_with_token(self, tmp_path: Path):
        cfg = PocketTeamConfig(
            project_root=tmp_path,
            telegram=TelegramConfig(bot_token="tok", chat_id="123"),
        )
        ch = TelegramChannel(tmp_path, config=cfg)
        assert ch.is_configured is True

    async def test_send_message_not_configured(self, tmp_path: Path):
        cfg = PocketTeamConfig(project_root=tmp_path)
        ch = TelegramChannel(tmp_path, config=cfg)
        result = await ch.send_message("hello")
        assert result is False

    async def test_send_message_success(self, tmp_path: Path):
        cfg = PocketTeamConfig(
            project_root=tmp_path,
            telegram=TelegramConfig(bot_token="tok", chat_id="123"),
        )
        ch = TelegramChannel(tmp_path, config=cfg)

        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client
            result = await ch.send_message("test")

        assert result is True

    async def test_send_message_failure(self, tmp_path: Path):
        cfg = PocketTeamConfig(
            project_root=tmp_path,
            telegram=TelegramConfig(bot_token="tok", chat_id="123"),
        )
        ch = TelegramChannel(tmp_path, config=cfg)

        with patch("httpx.AsyncClient", side_effect=Exception("network")):
            result = await ch.send_message("test")
        assert result is False


class TestTelegramChannelCallbacks:
    def test_on_message_callback(self, tmp_path: Path):
        cfg = PocketTeamConfig(
            project_root=tmp_path,
            telegram=TelegramConfig(bot_token="tok", chat_id="123"),
        )
        ch = TelegramChannel(tmp_path, config=cfg)
        received = []
        ch.on_message(lambda msg: received.append(msg))
        assert ch._on_message is not None

    def test_resolve_approval(self, tmp_path: Path):
        cfg = PocketTeamConfig(
            project_root=tmp_path,
            telegram=TelegramConfig(bot_token="tok", chat_id="123"),
        )
        ch = TelegramChannel(tmp_path, config=cfg)

        loop = asyncio.new_event_loop()
        future = loop.create_future()
        ch._pending_approvals["req-1"] = future
        ch.resolve_approval("req-1", True)

        assert future.result() is True
        assert "req-1" not in ch._pending_approvals
        loop.close()

    def test_resolve_nonexistent_approval(self, tmp_path: Path):
        cfg = PocketTeamConfig(
            project_root=tmp_path,
            telegram=TelegramConfig(bot_token="tok", chat_id="123"),
        )
        ch = TelegramChannel(tmp_path, config=cfg)
        # Should not raise
        ch.resolve_approval("nonexistent", False)


class TestTelegramChannelUpdates:
    async def test_handle_approval_callback(self, tmp_path: Path):
        cfg = PocketTeamConfig(
            project_root=tmp_path,
            telegram=TelegramConfig(bot_token="tok", chat_id="123"),
        )
        ch = TelegramChannel(tmp_path, config=cfg)

        loop = asyncio.get_running_loop()
        future = loop.create_future()
        ch._pending_approvals["task-42"] = future

        update = {
            "callback_query": {
                "id": "cb-1",
                "data": "approve:task-42",
            }
        }

        with patch.object(ch, "_answer_callback", new_callable=AsyncMock):
            await ch._handle_update(update)

        assert future.result() is True

    async def test_handle_reject_callback(self, tmp_path: Path):
        cfg = PocketTeamConfig(
            project_root=tmp_path,
            telegram=TelegramConfig(bot_token="tok", chat_id="123"),
        )
        ch = TelegramChannel(tmp_path, config=cfg)

        loop = asyncio.get_running_loop()
        future = loop.create_future()
        ch._pending_approvals["task-99"] = future

        update = {
            "callback_query": {
                "id": "cb-2",
                "data": "reject:task-99",
            }
        }

        with patch.object(ch, "_answer_callback", new_callable=AsyncMock):
            await ch._handle_update(update)

        assert future.result() is False

    async def test_handle_message_wrong_chat(self, tmp_path: Path):
        cfg = PocketTeamConfig(
            project_root=tmp_path,
            telegram=TelegramConfig(bot_token="tok", chat_id="123"),
        )
        ch = TelegramChannel(tmp_path, config=cfg)
        received = []
        ch.on_message(lambda msg: received.append(msg))

        update = {
            "message": {
                "text": "hello",
                "chat": {"id": 999},  # Wrong chat ID
            }
        }
        await ch._handle_update(update)
        assert len(received) == 0  # Message ignored

    async def test_handle_message_correct_chat(self, tmp_path: Path):
        cfg = PocketTeamConfig(
            project_root=tmp_path,
            telegram=TelegramConfig(bot_token="tok", chat_id="123"),
        )
        ch = TelegramChannel(tmp_path, config=cfg)
        received = []
        ch.on_message(lambda msg: received.append(msg))

        update = {
            "message": {
                "text": "Build a landing page",
                "chat": {"id": 123},
            }
        }
        await ch._handle_update(update)
        assert received == ["Build a landing page"]

    def test_stop_polling(self, tmp_path: Path):
        cfg = PocketTeamConfig(
            project_root=tmp_path,
            telegram=TelegramConfig(bot_token="tok", chat_id="123"),
        )
        ch = TelegramChannel(tmp_path, config=cfg)
        ch._running = True
        ch.stop()
        assert ch._running is False


# ── SessionManager ──────────────────────────────────────────────────────────

class TestSessionManager:
    def test_list_empty(self, tmp_path: Path):
        sm = SessionManager(tmp_path)
        assert sm.list_sessions() == []

    def test_list_sessions(self, tmp_path: Path):
        sessions_dir = tmp_path / ".pocketteam/sessions"
        sessions_dir.mkdir(parents=True)

        (sessions_dir / "task-abc.json").write_text(json.dumps({
            "task_id": "task-abc",
            "task_description": "Build auth",
            "phase": "implementation",
        }))
        (sessions_dir / "task-def.json").write_text(json.dumps({
            "task_id": "task-def",
            "task_description": "Fix bug",
            "phase": "done",
        }))

        sm = SessionManager(tmp_path)
        sessions = sm.list_sessions()
        assert len(sessions) == 2
        assert sessions[0]["task_id"] in ("task-abc", "task-def")

    def test_get_latest_session_id(self, tmp_path: Path):
        sessions_dir = tmp_path / ".pocketteam/sessions"
        sessions_dir.mkdir(parents=True)

        (sessions_dir / "task-old.json").write_text("{}")
        time.sleep(0.01)  # Ensure different mtime
        (sessions_dir / "task-new.json").write_text("{}")

        sm = SessionManager(tmp_path)
        latest = sm.get_latest_session_id()
        assert latest is not None

    def test_get_latest_session_id_empty(self, tmp_path: Path):
        sm = SessionManager(tmp_path)
        assert sm.get_latest_session_id() is None

    def test_session_exists(self, tmp_path: Path):
        sessions_dir = tmp_path / ".pocketteam/sessions"
        sessions_dir.mkdir(parents=True)
        (sessions_dir / "task-exists.json").write_text("{}")

        sm = SessionManager(tmp_path)
        assert sm.session_exists("task-exists") is True
        assert sm.session_exists("task-nope") is False

    def test_delete_session(self, tmp_path: Path):
        sessions_dir = tmp_path / ".pocketteam/sessions"
        sessions_dir.mkdir(parents=True)
        (sessions_dir / "task-del.json").write_text("{}")

        sm = SessionManager(tmp_path)
        assert sm.delete_session("task-del") is True
        assert sm.delete_session("task-del") is False

    def test_cleanup_old_sessions(self, tmp_path: Path):
        sessions_dir = tmp_path / ".pocketteam/sessions"
        sessions_dir.mkdir(parents=True)

        old_file = sessions_dir / "task-old.json"
        old_file.write_text("{}")
        # Make it appear old
        import os
        old_time = time.time() - (31 * 86400)
        os.utime(old_file, (old_time, old_time))

        new_file = sessions_dir / "task-new.json"
        new_file.write_text("{}")

        sm = SessionManager(tmp_path)
        removed = sm.cleanup_old_sessions(max_age_days=30)
        assert removed == 1
        assert not old_file.exists()
        assert new_file.exists()


# ── RemoteSession ───────────────────────────────────────────────────────────

class TestRemoteSession:
    async def test_start_command_not_found(self, tmp_path: Path):
        rs = RemoteSession(tmp_path)

        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
            result = await rs.start("test task")
        assert result is False

    async def test_start_success(self, tmp_path: Path):
        rs = RemoteSession(tmp_path)

        mock_proc = MagicMock()
        mock_proc.returncode = None  # Still running

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await rs.start("test task")
        assert result is True

    async def test_resume_no_session_id(self, tmp_path: Path):
        rs = RemoteSession(tmp_path)
        result = await rs.resume()
        assert result is False

    async def test_resume_success(self, tmp_path: Path):
        rs = RemoteSession(tmp_path, session_id="sess-123")

        mock_proc = MagicMock()
        mock_proc.returncode = None

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await rs.resume()
        assert result is True

    async def test_stop(self, tmp_path: Path):
        rs = RemoteSession(tmp_path)
        mock_proc = MagicMock()
        mock_proc.returncode = None
        mock_proc.wait = AsyncMock()
        rs._process = mock_proc

        await rs.stop()
        mock_proc.terminate.assert_called_once()

    def test_is_running(self, tmp_path: Path):
        rs = RemoteSession(tmp_path)
        assert rs.is_running is False

        mock_proc = MagicMock()
        mock_proc.returncode = None
        rs._process = mock_proc
        assert rs.is_running is True

        mock_proc.returncode = 0
        assert rs.is_running is False


# ── discover_sessions ───────────────────────────────────────────────────────

class TestDiscoverSessions:
    async def test_no_claude_dir(self, tmp_path: Path):
        with patch("pocketteam.channels.remote.Path") as mock_path:
            mock_home = MagicMock()
            mock_home.__truediv__ = MagicMock(return_value=tmp_path / "nonexistent")
            mock_path.home.return_value = mock_home
            sessions = await discover_sessions(tmp_path)
        assert sessions == []
