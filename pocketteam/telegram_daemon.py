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
import shlex
import signal
import sys
import time
from datetime import datetime, UTC
from pathlib import Path

import httpx

logger = logging.getLogger("pocketteam.telegram_daemon")

LAUNCH_COOLDOWN_SECONDS = 300.0


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
        self.launching_lock = project_root / ".pocketteam" / "launching.lock"
        self.inbox_file = project_root / ".pocketteam" / "telegram-inbox.jsonl"
        self.kill_file = project_root / ".pocketteam" / "KILL"
        self.sessions_launched = 0

        # Restore persisted cooldown so daemon restarts don't reset the guard
        try:
            saved = json.loads(self.state_file.read_text())
            self._launch_cooldown = float(saved.get("launch_cooldown", 0.0))
        except Exception:
            pass  # state file missing or unreadable — start with zero cooldown

    async def run(self) -> None:
        """Main polling loop."""
        self._write_state("polling")
        logger.info("Telegram daemon started for %s", self.project_root)

        # Harden .pocketteam directory — no world or group access
        pt_dir = self.project_root / ".pocketteam"
        try:
            pt_dir.chmod(0o700)
        except Exception:
            pass

        async with httpx.AsyncClient(timeout=httpx.Timeout(35.0, connect=10.0)) as client:
            while not self._shutdown:
                # If a Claude session is running, don't poll getUpdates (MCP plugin owns it).
                # BUT: still check for /kill commands via a lightweight file-based approach.
                if self._is_claude_running():
                    self._write_state("session_active")
                    logger.debug("Claude session running, sleeping (no getUpdates)")
                    await asyncio.sleep(10.0)
                    continue

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
                        logger.debug("409 Conflict — session active, pausing polling")
                        self._write_state("session_active")
                        await asyncio.sleep(10.0)
                        continue

                    resp.raise_for_status()
                    data = resp.json()

                    for update in data.get("result", []):
                        self.offset = update["update_id"] + 1
                        await self._handle_update(update)

                    self._write_state("polling")

                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 409:
                        self._write_state("session_active")
                        await asyncio.sleep(10.0)
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

        # /kill command — activate kill switch IMMEDIATELY, even during active session
        if text.strip().lower() in ("/kill", "/stop"):
            logger.warning("KILL SWITCH activated via Telegram by user %s", user_id)
            self.kill_file.parent.mkdir(parents=True, exist_ok=True)
            self.kill_file.touch()
            await self._send_message(
                chat_id,
                "🛑 Kill switch activated. All agents stopped.\n"
                "Run `pocketteam resume` to re-enable.",
            )
            return

        # Kill switch check — ignore messages if already killed
        if self.kill_file.exists():
            logger.warning("Kill switch active, ignoring message from %s", user_id)
            return

        # Always write to inbox first
        self._write_inbox(text, user_id, chat_id)

        # Check if a Claude session is already running.
        # With the pgrep guard at the top of run(), this should never trigger,
        # but it remains as a safety net for unforeseen timing gaps.
        if self._is_claude_running():
            logger.warning(
                "Race: got message while session running — saved to inbox only (this should be rare)"
            )
            return

        # Cooldown: avoid launching multiple sessions in quick succession
        now = datetime.now(UTC).timestamp()
        if now - self._launch_cooldown < LAUNCH_COOLDOWN_SECONDS:
            logger.info(
                "Cooldown active (%.0fs remaining), message saved to inbox only",
                LAUNCH_COOLDOWN_SECONDS - (now - self._launch_cooldown),
            )
            return

        # Launch Claude session
        self._launch_cooldown = now
        await self._launch_session(text)

    async def _send_message(self, chat_id: str, text: str) -> None:
        """Send a message to the user via Telegram Bot API."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    f"{self.api_base}/sendMessage",
                    json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
                )
        except Exception:
            logger.debug("Failed to send Telegram message", exc_info=True)

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
        try:
            self.inbox_file.chmod(0o600)
        except Exception:
            pass
        logger.info("Wrote message to inbox: %.60s", text)

    async def _launch_session(self, message_text: str):  # noqa: ARG002 — kept for API compatibility; inbox prompt is now in COO initialPrompt
        claude_path = self._find_claude()
        if not claude_path:
            logger.error("claude CLI not found in PATH")
            return

        logger.info("Launching Claude session in new Terminal window")
        self.launching_lock.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.launching_lock.parent / f".launching.lock.{os.getpid()}.tmp"
        tmp.write_text(json.dumps({"ts": time.time(), "pid": os.getpid()}))
        os.replace(tmp, self.launching_lock)
        self.sessions_launched += 1
        self._write_state("launching")

        launch_script = self.project_root / ".pocketteam" / "launch-session.sh"
        launch_script.parent.mkdir(parents=True, exist_ok=True)
        launch_script.write_text(
            f'#!/bin/bash\n'
            f'cd "{self.project_root}"\n'
            f"exec {claude_path} --continue --agent=pocketteam/coo --dangerously-skip-permissions --effort medium"
            f" --channels plugin:telegram@claude-plugins-official\n"
        )
        launch_script.chmod(0o700)

        # Use osascript to open a new Terminal window running the script
        quoted_script = shlex.quote(str(launch_script))
        osascript = (
            'tell application "Terminal"\n'
            '    activate\n'
            f'    do script {quoted_script}\n'
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
                self.launching_lock.unlink(missing_ok=True)
            else:
                logger.info("Terminal window opened with Claude session")
                # Write a temporary session.lock so _is_claude_running() works immediately
                temp_lock = self.project_root / ".pocketteam" / "session.lock"
                temp_lock.write_text(json.dumps({"ts": time.time(), "pid": "pending", "source": "daemon"}))
                logger.info("Waiting for session.lock to appear (max 120s)...")
                boot_deadline = asyncio.get_running_loop().time() + 120.0
                while asyncio.get_running_loop().time() < boot_deadline:
                    await asyncio.sleep(5.0)
                    if (self.project_root / ".pocketteam" / "session.lock").exists():
                        logger.info("session.lock detected — Claude session is live")
                        self.launching_lock.unlink(missing_ok=True)
                        break
                else:
                    logger.warning("session.lock never appeared after 120s — refreshing cooldown and removing launching.lock")
                    # Refresh cooldown before removing the lock so the next incoming
                    # message doesn't trigger an immediate re-launch (the cooldown
                    # and the boot timeout are otherwise equal, creating a race).
                    self._launch_cooldown = datetime.now(UTC).timestamp()
                    self._write_state("polling")
                    self.launching_lock.unlink(missing_ok=True)
        except Exception:
            logger.exception("Failed to launch Terminal window")
            self.launching_lock.unlink(missing_ok=True)

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

    def _is_claude_running(self) -> bool:
        """Check if any Claude Code session is already running."""
        import subprocess as sp

        # Method 1: Check for Claude CLI processes
        try:
            result = sp.run(
                ["pgrep", "-f", "claude.*--dangerously-skip-permissions"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                pids = [p.strip() for p in result.stdout.strip().split("\n") if p.strip()]
                own_pid = str(os.getpid())
                other_pids = [p for p in pids if p != own_pid]
                if other_pids:
                    logger.debug("Found running Claude sessions via pgrep: %s", other_pids)
                    return True
        except Exception:
            pass

        # Method 1b: launching.lock written immediately at launch time
        if self.launching_lock.exists():
            try:
                data = json.loads(self.launching_lock.read_text())
                age = time.time() - data.get("ts", 0)
                if age < 120:
                    logger.debug("Launch in progress (launching.lock is %.0fs old)", age)
                    return True
                else:
                    logger.debug("launching.lock stale (%.0fs old), removing", age)
                    self.launching_lock.unlink(missing_ok=True)
            except Exception:
                logger.warning("launching.lock unreadable — removing stale lock")
                self.launching_lock.unlink(missing_ok=True)

        # Method 2: Check for the lock file written by Claude Code sessions
        # The session_start hook creates this lock when a session becomes active
        lock_file = self.project_root / ".pocketteam" / "session.lock"
        if lock_file.exists():
            try:
                age = time.time() - lock_file.stat().st_mtime
                if age < 120:
                    logger.debug("Found active session lock (%.0fs old)", age)
                    return True
                else:
                    logger.debug("Session lock stale (%.0fs old), ignoring", age)
                    lock_file.unlink(missing_ok=True)
            except Exception:
                pass

        return False

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
            "launch_cooldown": self._launch_cooldown,
        }
        try:
            self.state_file.write_text(json.dumps(info, indent=2))
            self.state_file.chmod(0o600)
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
    # Suppress httpx INFO logs — they include full URLs with the bot token
    logging.getLogger("httpx").setLevel(logging.WARNING)

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
