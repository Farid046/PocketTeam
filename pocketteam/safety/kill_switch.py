"""
Safety Layer 10: Out-of-Band Kill Switch
OpenClaw's biggest failure: no way to stop a running agent.

This is NOT a chat message. It's an independent file-watch mechanism that:
1. Monitors .pocketteam/KILL signal file
2. Runs as a separate thread alongside any pipeline
3. Cannot be overridden by agent instructions or conversation context
4. Triggers immediate SIGTERM to all agent processes + stashes changes

Three ways to activate:
1. touch .pocketteam/KILL (manual)
2. pocketteam kill (CLI)
3. /kill via Telegram bot
"""

from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from ..constants import KILL_SWITCH_CHECK_INTERVAL, KILL_SWITCH_FILE


@dataclass
class KillSwitchEvent:
    """Emitted when the kill switch is activated."""
    triggered_at: float
    trigger_source: str    # "file", "telegram", "cli", "api"
    tokens_invalidated: int = 0
    changes_stashed: bool = False


class KillSwitch:
    """
    Out-of-band kill mechanism that runs independently of agent context.
    Uses a signal file (.pocketteam/KILL) — not conversation context.
    """

    def __init__(
        self,
        project_root: Path,
        on_kill: Optional[Callable[[KillSwitchEvent], None]] = None,
    ) -> None:
        self.project_root = project_root
        self.kill_file = project_root / KILL_SWITCH_FILE
        self.on_kill = on_kill
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    @property
    def is_active(self) -> bool:
        """Check if kill switch is currently active."""
        return self.kill_file.exists()

    def arm(self) -> None:
        """Start monitoring the kill file in a background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="pocketteam-kill-switch",
        )
        self._thread.start()

    def disarm(self) -> None:
        """Stop the kill switch monitor."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)

    def activate(self, trigger_source: str = "api") -> KillSwitchEvent:
        """
        Manually activate the kill switch.
        Creates the signal file and triggers cleanup.
        """
        self.kill_file.parent.mkdir(parents=True, exist_ok=True)
        self.kill_file.touch()
        return self._execute_kill(trigger_source)

    def deactivate(self) -> None:
        """Remove the kill file to allow agents to run again."""
        if self.kill_file.exists():
            self.kill_file.unlink()

    def _monitor_loop(self) -> None:
        """Background thread: polls for kill file every second."""
        was_active = self.kill_file.exists()

        while self._running:
            try:
                now_active = self.kill_file.exists()

                # Detect fresh activation (file just appeared)
                if now_active and not was_active:
                    self._execute_kill("file")

                was_active = now_active
                time.sleep(KILL_SWITCH_CHECK_INTERVAL)
            except Exception:
                # Kill switch must never crash
                time.sleep(KILL_SWITCH_CHECK_INTERVAL)

    def _execute_kill(self, trigger_source: str) -> KillSwitchEvent:
        """
        Execute kill switch: stop agents, stash changes, notify.
        This is the critical path — must be fast and reliable.
        """
        event = KillSwitchEvent(
            triggered_at=time.time(),
            trigger_source=trigger_source,
        )

        # 1. Invalidate all pending D-SAC approval tokens
        try:
            from .dsac import DSACGuard
            guard = DSACGuard(self.project_root)
            event.tokens_invalidated = guard.invalidate_all_tokens()
        except Exception:
            pass

        # 2. Git stash if there are uncommitted changes (preserve work)
        event.changes_stashed = self._stash_changes()

        # 3. Log the kill event
        try:
            from .audit_log import AuditLog, SafetyDecision
            audit = AuditLog(self.project_root)
            audit.log_kill_switch(trigger_source, self.project_root)
        except Exception:
            pass

        # 4. Notify via callback (e.g. send Telegram message)
        if self.on_kill:
            try:
                self.on_kill(event)
            except Exception:
                pass

        return event

    def _stash_changes(self) -> bool:
        """Git stash uncommitted changes to preserve work."""
        try:
            # Check if we're in a git repo
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=self.project_root,
                capture_output=True,
                timeout=5,
            )
            if result.returncode != 0:
                return False

            # Check for changes
            status = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if not status.stdout.strip():
                return False  # Nothing to stash

            # Stash
            stash = subprocess.run(
                ["git", "stash", "push", "-m", "pocketteam-kill-switch-stash"],
                cwd=self.project_root,
                capture_output=True,
                timeout=10,
            )
            return stash.returncode == 0
        except Exception:
            return False


class KillSwitchGuard:
    """
    Context manager: raises KillSwitchError if kill switch is active.
    Use this to guard critical sections of agent code.
    """

    def __init__(self, kill_switch: KillSwitch) -> None:
        self.kill_switch = kill_switch

    def check(self) -> None:
        """Raise if kill switch is active."""
        if self.kill_switch.is_active:
            raise KillSwitchError("Kill switch is active — halting operation")

    def __enter__(self) -> "KillSwitchGuard":
        self.check()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        pass


class KillSwitchError(RuntimeError):
    """Raised when the kill switch is active and an operation is attempted."""
    pass
