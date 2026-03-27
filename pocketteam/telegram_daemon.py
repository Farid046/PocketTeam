#!/usr/bin/env python3
"""
Telegram Auto-Session Daemon for PocketTeam.
Polls Telegram Bot API when no Claude Code session is active.
On CEO message: writes to inbox + starts claude --continue.
Uses 409 Conflict as session-detection (Telegram allows only 1 consumer).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import sys
from datetime import datetime, UTC
from pathlib import Path

import httpx

logger = logging.getLogger("pocketteam.telegram_daemon")

LAUNCH_COOLDOWN_SECONDS = 30.0


class TelegramDaemon:
    def __init__(self, project_root: Path, bot_token: str, allowed_users: list[str]):
        self.project_root = project_root
        self.bot_token = bot_token
        self.allowed_users = allowed_users
        self.api_base = f"https://api.telegram.org/bot{bot_token}"
        self.offset = 0
        self._shutdown = False
        self._launch_cooldown = 0.0  # timestamp of last launch
        self.state_file = project_root / ".pocketteam" / "telegram-daemon.json"
        self.inbox_file = project_root / ".pocketteam" / "telegram-inbox.jsonl"
        self.kill_file = project_root / ".pocketteam" / "KILL"
        self.sessions_launched = 0

    async def run(self) -> None:
        """Main polling loop."""
        self._write_state("polling")
        logger.info("Telegram daemon started for %s", self.project_root)

        async with httpx.AsyncClient(timeout=httpx.Timeout(35.0, connect=10.0)) as client:
            backoff = 2.0
            while not self._shutdown:
                try:
                    resp = await client.get(
                        f"{self.api_base}/getUpdates",
                        params={
                            "offset": self.offset,
                            "timeout": 30,
                            "allowed_updates": '["message"]',
                        },
                    )

                    if resp.status_code == 409:
                        # MCP plugin is polling — session is active
                        logger.debug("409 Conflict — session active, backing off %.0fs", backoff)
                        self._write_state("session_active")
                        await asyncio.sleep(backoff)
                        backoff = min(backoff * 1.5, 60.0)
                        continue

                    resp.raise_for_status()
                    data = resp.json()
                    backoff = 2.0  # reset on success

                    for update in data.get("result", []):
                        self.offset = update["update_id"] + 1
                        await self._handle_update(update)

                    self._write_state("polling")

                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 409:
                        self._write_state("session_active")
                        await asyncio.sleep(backoff)
                        backoff = min(backoff * 1.5, 60.0)
                    else:
                        logger.error("HTTP error: %s", e)
                        await asyncio.sleep(5)
                except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout):
                    logger.warning("Network issue, retrying in 5s")
                    await asyncio.sleep(5)
                except Exception:
                    logger.exception("Unexpected error in polling loop")
                    await asyncio.sleep(10)

        self._write_state("stopped")
        logger.info("Telegram daemon stopped")

    async def _handle_update(self, update: dict) -> None:
        msg = update.get("message", {})
        text = msg.get("text", "")
        user_id = str(msg.get("from", {}).get("id", ""))
        chat_id = str(msg.get("chat", {}).get("id", ""))

        if not text or not user_id:
            return

        # Reload access control on every message in case allowlist changed
        if user_id not in self.allowed_users:
            self._reload_access()
            if user_id not in self.allowed_users:
                logger.info("Rejected message from unauthorized user %s", user_id)
                return

        # Kill switch check
        if self.kill_file.exists():
            logger.warning("Kill switch active, ignoring message from %s", user_id)
            return

        # Cooldown: avoid launching multiple sessions in quick succession
        now = datetime.now(UTC).timestamp()
        if now - self._launch_cooldown < LAUNCH_COOLDOWN_SECONDS:
            logger.info(
                "Cooldown active (%.0fs remaining), writing to inbox only",
                LAUNCH_COOLDOWN_SECONDS - (now - self._launch_cooldown),
            )
            self._write_inbox(text, user_id, chat_id)
            return

        # Write message to inbox before launching
        self._write_inbox(text, user_id, chat_id)

        # Launch Claude session
        self._launch_cooldown = now
        await self._launch_session(text)

    def _write_inbox(self, text: str, user_id: str, chat_id: str) -> None:
        self.inbox_file.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": datetime.now(UTC).isoformat(),
            "from": user_id,
            "chat_id": chat_id,
            "text": text,
            "status": "received",
            "source": "daemon",
        }
        with open(self.inbox_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
        logger.info("Wrote message to inbox: %.60s", text)

    async def _launch_session(self, message_text: str):
        claude_path = self._find_claude()
        if not claude_path:
            logger.error("claude CLI not found in PATH")
            return

        logger.info("Launching Claude session in new Terminal window")
        self.sessions_launched += 1
        self._write_state("launching")

        # Write a temporary launch script to avoid shell/AppleScript quoting issues
        import tempfile

        launch_script = self.project_root / ".pocketteam" / "launch-session.sh"
        launch_script.parent.mkdir(parents=True, exist_ok=True)
        launch_script.write_text(
            f'#!/bin/bash\n'
            f'cd "{self.project_root}"\n'
            f'exec {claude_path} --dangerously-skip-permissions --effort medium --channels plugin:telegram@claude-plugins-official\n'
        )
        launch_script.chmod(0o755)

        # Use osascript to open a new Terminal window running the script
        osascript = (
            'tell application "Terminal"\n'
            '    activate\n'
            f'    do script "{launch_script}"\n'
            'end tell'
        )

        try:
            process = await asyncio.create_subprocess_exec(
                "osascript", "-e", osascript,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await process.communicate()
            if process.returncode != 0:
                logger.error("osascript failed: %s", stderr.decode())
            else:
                logger.info("Terminal window opened with Claude session")
        except Exception:
            logger.exception("Failed to launch Terminal window")

    def _find_claude(self) -> str | None:
        """Find the claude CLI binary in PATH and known install locations."""
        import shutil

        candidates = [
            shutil.which("claude"),
            os.path.expanduser("~/.claude/local/claude"),
            os.path.expanduser("~/.bun/bin/claude"),
            "/usr/local/bin/claude",
        ]
        for path in candidates:
            if path and os.path.isfile(path):
                return path
        return None

    def _reload_access(self) -> None:
        """Re-read access.json so runtime allowlist changes take effect."""
        access_file = Path.home() / ".claude" / "channels" / "telegram" / "access.json"
        try:
            data = json.loads(access_file.read_text())
            self.allowed_users = data.get("allowFrom", [])
        except Exception:
            pass  # keep existing list on read failure

    def _write_state(self, state: str) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        info = {
            "pid": os.getpid(),
            "state": state,
            "last_update": datetime.now(UTC).isoformat(),
            "sessions_launched": self.sessions_launched,
            "project_root": str(self.project_root),
        }
        try:
            self.state_file.write_text(json.dumps(info, indent=2))
        except Exception:
            pass  # non-fatal


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def load_bot_token() -> str | None:
    """Load Telegram bot token from ~/.claude/channels/telegram/.env."""
    env_file = Path.home() / ".claude" / "channels" / "telegram" / ".env"
    if not env_file.exists():
        return None
    for line in env_file.read_text().splitlines():
        if line.startswith("TELEGRAM_BOT_TOKEN="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def load_allowed_users() -> list[str]:
    """Load allowed Telegram user IDs from access.json."""
    access_file = Path.home() / ".claude" / "channels" / "telegram" / "access.json"
    try:
        data = json.loads(access_file.read_text())
        return data.get("allowFrom", [])
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="PocketTeam Telegram Auto-Session Daemon"
    )
    parser.add_argument("--project-root", required=True, type=Path)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )

    project_root = args.project_root.resolve()
    if not (project_root / ".pocketteam").exists():
        logger.error("Not a PocketTeam project: %s", project_root)
        sys.exit(1)

    token = load_bot_token()
    if not token:
        logger.error(
            "No Telegram bot token found. Run telegram:configure first."
        )
        sys.exit(1)

    users = load_allowed_users()
    if not users:
        logger.warning(
            "No allowed users configured. Daemon will reject all messages."
        )

    daemon = TelegramDaemon(project_root, token, users)

    loop = asyncio.new_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: setattr(daemon, "_shutdown", True))

    try:
        loop.run_until_complete(daemon.run())
    finally:
        loop.close()


if __name__ == "__main__":
    main()
