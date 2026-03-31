"""
Channel Setup — Telegram notifications and session management.

IMPORTANT: The main Telegram communication uses Claude Code's native
Channels system (plugin:telegram@claude-plugins-official), NOT this module.

This module provides:
1. TelegramNotifier — one-way notifications (health alerts, init confirmation)
2. SessionManager — manages pipeline session files

For two-way Telegram chat:
  claude --channels plugin:telegram@claude-plugins-official
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ..config import PocketTeamConfig, load_config
from ..constants import EVENTS_FILE, SESSIONS_DIR

logger = logging.getLogger(__name__)


class TelegramChannel:
    """
    Telegram notification sender for PocketTeam.

    Used for ONE-WAY notifications only:
    - Init confirmation messages
    - Health failure alerts (from GitHub Actions)
    - Self-healing status updates

    For TWO-WAY Telegram chat (send tasks, get responses), use
    Claude Code's native Channels system instead:
      claude --channels plugin:telegram@claude-plugins-official
    """

    def __init__(
        self,
        project_root: Path,
        config: PocketTeamConfig | None = None,
    ) -> None:
        self.project_root = project_root
        self.config = config or load_config(project_root)
        self.bot_token = self.config.telegram.bot_token
        self.chat_id = self.config.telegram.chat_id
        self._running = False
        self._on_message: Callable | None = None
        self._on_approval_response: Callable | None = None
        self._pending_approvals: dict[str, asyncio.Future] = {}

    @property
    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    def on_message(self, callback: Callable[[str], Any]) -> None:
        """Register callback for incoming CEO messages."""
        self._on_message = callback

    def on_approval_response(self, callback: Callable[[str, bool], Any]) -> None:
        """Register callback for approval responses."""
        self._on_approval_response = callback

    async def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """Send a message to the CEO via Telegram."""
        if not self.is_configured:
            return False

        try:
            import httpx
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(url, json={
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": parse_mode,
                })
                return resp.status_code == 200
        except Exception:
            logger.debug("Telegram send failed", exc_info=True)
            return False

    async def send_approval_request(
        self,
        prompt: str,
        request_id: str,
        timeout: float = 300.0,
    ) -> bool:
        """
        Send an approval request to CEO and wait for response.
        Returns True if approved, False if rejected or timed out.
        """
        # Send message with inline keyboard
        keyboard = {
            "inline_keyboard": [[
                {"text": "Approve", "callback_data": f"approve:{request_id}"},
                {"text": "Reject", "callback_data": f"reject:{request_id}"},
            ]]
        }

        try:
            import httpx
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(url, json={
                    "chat_id": self.chat_id,
                    "text": f"⛔ <b>Approval Required</b>\n\n{prompt}",
                    "parse_mode": "HTML",
                    "reply_markup": keyboard,
                })
        except Exception:
            logger.debug("Telegram send failed", exc_info=True)
            return False

        # Wait for callback
        loop = asyncio.get_running_loop()
        future: asyncio.Future[bool] = loop.create_future()
        self._pending_approvals[request_id] = future

        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except TimeoutError:
            self._pending_approvals.pop(request_id, None)
            await self.send_message(f"Approval request timed out: {request_id}")
            return False

    def resolve_approval(self, request_id: str, approved: bool) -> None:
        """Resolve a pending approval (called when Telegram callback arrives)."""
        future = self._pending_approvals.pop(request_id, None)
        if future and not future.done():
            future.set_result(approved)

    async def start_polling(self) -> None:
        """Start long-polling for Telegram updates."""
        if not self.is_configured:
            return

        self._running = True
        offset = 0

        while self._running:
            try:
                import httpx
                url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
                async with httpx.AsyncClient(timeout=35) as client:
                    resp = await client.get(url, params={
                        "offset": offset,
                        "timeout": 30,
                        "allowed_updates": json.dumps(["message", "callback_query"]),
                    })

                if resp.status_code != 200:
                    await asyncio.sleep(5)
                    continue

                data = resp.json()
                for update in data.get("result", []):
                    offset = update["update_id"] + 1
                    await self._handle_update(update)

            except asyncio.CancelledError:
                break
            except Exception:
                logger.debug("Telegram polling error, retrying in 5s", exc_info=True)
                await asyncio.sleep(5)

    def stop(self) -> None:
        """Stop polling."""
        self._running = False

    async def _handle_update(self, update: dict) -> None:
        """Process a single Telegram update."""
        # Handle callback queries (approval buttons)
        if "callback_query" in update:
            cb = update["callback_query"]
            data = cb.get("data", "")

            if data.startswith("approve:"):
                request_id = data[8:]
                self.resolve_approval(request_id, True)
                await self._answer_callback(cb["id"], "Approved")
            elif data.startswith("reject:"):
                request_id = data[7:]
                self.resolve_approval(request_id, False)
                await self._answer_callback(cb["id"], "Rejected")
            return

        # Handle regular messages
        message = update.get("message", {})
        text = message.get("text", "")
        from_id = str(message.get("chat", {}).get("id", ""))

        # Security: only accept messages from configured chat_id
        if from_id != self.chat_id:
            return

        # Handle special commands
        if text == "/status":
            await self._send_status()
            return

        # Route to message callback
        if self._on_message and text:
            try:
                result = self._on_message(text)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                await self.send_message(f"Error processing message: {e}")

    async def _answer_callback(self, callback_id: str, text: str) -> None:
        """Answer a Telegram callback query."""
        try:
            import httpx
            url = f"https://api.telegram.org/bot{self.bot_token}/answerCallbackQuery"
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(url, json={
                    "callback_query_id": callback_id,
                    "text": text,
                })
        except Exception:
            logger.debug("Telegram answer_callback failed", exc_info=True)

    async def _send_status(self) -> None:
        """Send current project status via Telegram."""
        # Read last event
        events_path = self.project_root / EVENTS_FILE
        last_event = ""
        if events_path.exists():
            try:
                lines = events_path.read_text().strip().splitlines()
                if lines:
                    e = json.loads(lines[-1])
                    last_event = f"{e.get('agent', '?')}: {e.get('action', '')} ({e.get('ts', '')[:19]})"
            except Exception:
                logger.debug("Failed to parse last event for status", exc_info=True)

        status_text = (
            f"<b>{self.config.project_name}</b>\n\n"
            f"Last Activity: {last_event or 'none'}\n"
        )
        await self.send_message(status_text)


class SessionManager:
    """
    Manages persistent sessions for a project.

    Sessions persist as JSON files in .pocketteam/sessions/.
    Each task gets a unique session that can be resumed.
    """

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self._sessions_dir = project_root / SESSIONS_DIR

    def list_sessions(self) -> list[dict]:
        """List all sessions with metadata."""
        if not self._sessions_dir.exists():
            return []

        sessions = []
        for f in sorted(self._sessions_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                data = json.loads(f.read_text())
                sessions.append({
                    "task_id": data.get("task_id", f.stem),
                    "task_description": data.get("task_description", ""),
                    "phase": data.get("phase", "unknown"),
                    "file": str(f),
                    "modified": time.ctime(f.stat().st_mtime),
                })
            except Exception:
                logger.debug("Failed to parse session file %s", f, exc_info=True)
        return sessions

    def get_latest_session_id(self) -> str | None:
        """Get the most recently modified session ID."""
        sessions = self.list_sessions()
        return sessions[0]["task_id"] if sessions else None

    def session_exists(self, task_id: str) -> bool:
        return (self._sessions_dir / f"{task_id}.json").exists()

    def delete_session(self, task_id: str) -> bool:
        path = self._sessions_dir / f"{task_id}.json"
        if path.exists():
            path.unlink()
            return True
        return False

    def cleanup_old_sessions(self, max_age_days: int = 30) -> int:
        """Remove sessions older than max_age_days. Returns count removed."""
        if not self._sessions_dir.exists():
            return 0

        cutoff = time.time() - (max_age_days * 86400)
        removed = 0
        for f in self._sessions_dir.glob("*.json"):
            if f.stat().st_mtime < cutoff:
                f.unlink()
                removed += 1
        return removed
