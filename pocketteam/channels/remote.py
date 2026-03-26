"""
Remote Control — manages remote Claude Code sessions.

Wraps `claude --remote-control` and `claude --resume` for:
- Starting remote sessions that can be accessed from mobile
- Resuming existing sessions after disconnect
- Session discovery and lifecycle management
"""

from __future__ import annotations

import asyncio
from pathlib import Path


class RemoteSession:
    """
    Manages a remote Claude Code session for a project.

    Remote sessions allow controlling Claude Code from:
    - Mobile app (claude.ai/code)
    - Another machine
    - Telegram (via TelegramChannel routing)
    """

    def __init__(self, project_root: Path, session_id: str | None = None) -> None:
        self.project_root = project_root
        self.session_id = session_id
        self._process: asyncio.subprocess.Process | None = None

    async def start(self, task: str | None = None) -> bool:
        """
        Start a new remote Claude Code session.
        Returns True if session started successfully.
        """
        cmd = ["claude", "--remote-control"]

        if task:
            cmd.extend(["-p", task])

        try:
            self._process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(self.project_root),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            return self._process.returncode is None  # Still running
        except FileNotFoundError:
            return False

    async def resume(self, session_id: str | None = None) -> bool:
        """
        Resume an existing session.
        Uses stored session_id or the provided one.
        """
        sid = session_id or self.session_id
        if not sid:
            return False

        cmd = ["claude", "--resume", sid]

        try:
            self._process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(self.project_root),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            self.session_id = sid
            return self._process.returncode is None
        except FileNotFoundError:
            return False

    async def send_message(self, message: str) -> str | None:
        """
        Send a message to the running session.
        Returns the response, or None if session isn't running.
        """
        if not self._process or self._process.returncode is not None:
            return None

        try:
            self._process.stdin.write(f"{message}\n".encode())
            await self._process.stdin.drain()

            # Read response (with timeout)
            output = await asyncio.wait_for(
                self._process.stdout.readline(),
                timeout=120,
            )
            return output.decode("utf-8", errors="replace").strip()
        except Exception:
            return None

    async def stop(self) -> None:
        """Stop the remote session."""
        if self._process and self._process.returncode is None:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5)
            except TimeoutError:
                self._process.kill()

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.returncode is None


async def discover_sessions(project_root: Path) -> list[dict]:
    """
    Discover existing Claude Code sessions for a project.
    Reads from ~/.claude/projects/ directory.
    """
    claude_projects = Path.home() / ".claude" / "projects"
    if not claude_projects.exists():
        return []

    sessions = []
    # Claude Code stores sessions by project path hash
    project_str = str(project_root).replace("/", "-")

    for session_dir in claude_projects.iterdir():
        if not session_dir.is_dir():
            continue
        # Check if this session belongs to our project
        if project_str in session_dir.name:
            for jsonl_file in session_dir.glob("*.jsonl"):
                sessions.append({
                    "session_id": jsonl_file.stem,
                    "path": str(jsonl_file),
                    "size_bytes": jsonl_file.stat().st_size,
                    "modified": jsonl_file.stat().st_mtime,
                })

    return sorted(sessions, key=lambda s: s["modified"], reverse=True)
