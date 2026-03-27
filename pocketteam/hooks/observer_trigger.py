"""
Observer Trigger Hook — SubagentStop post-hook (Stage 1 of 2).

Responsibilities (all <500ms):
1. Recursion guard: skip if the completing agent is the observer itself
2. Cooldown: skip if last observer run was <120s ago
3. Min-events: skip if stream.jsonl is too small (<100 bytes)
4. Write cooldown timestamp atomically
5. Fire background subprocess for Stage 2 (observer_cli.py)

Returns {} immediately — never blocks the hook pipeline.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def _find_project_root() -> Path | None:
    """Walk up from cwd to find the directory containing .pocketteam/."""
    d = Path.cwd()
    for _ in range(20):
        if (d / ".pocketteam").is_dir():
            return d
        parent = d.parent
        if parent == d:
            break
        d = parent
    return None


def handle(hook_input: dict) -> dict:
    """
    Non-blocking hook handler for SubagentStop → observer_analyze.

    Always returns {} so the hook pipeline continues immediately.
    """
    # ── 1. Recursion guard ──────────────────────────────────────────────────
    agent_type = hook_input.get("agent_type", hook_input.get("subagent_type", ""))
    if "observer" in str(agent_type).lower():
        return {}

    # ── 2. Find project root ─────────────────────────────────────────────────
    project_root = _find_project_root()
    if project_root is None:
        return {}

    pocketteam_dir = project_root / ".pocketteam"

    # ── 2b. Kill-switch guard ────────────────────────────────────────────────
    kill_file = pocketteam_dir / "KILL"
    if kill_file.exists():
        return {}

    # ── 3. Min-events guard ──────────────────────────────────────────────────
    events_path = pocketteam_dir / "events" / "stream.jsonl"
    if not events_path.exists():
        return {}
    try:
        if events_path.stat().st_size < 100:
            return {}
    except OSError:
        return {}

    # ── 4. Cooldown check ────────────────────────────────────────────────────
    from ..constants import OBSERVER_COOLDOWN_SECONDS

    cooldown_file = pocketteam_dir / ".observer-last-run"
    now = time.time()

    if cooldown_file.exists():
        try:
            last_run = float(cooldown_file.read_text().strip())
            if (now - last_run) < OBSERVER_COOLDOWN_SECONDS:
                return {}
        except (OSError, ValueError):
            pass

    # ── 5. Write cooldown atomically (temp → rename, mode 0o600) ─────────────
    try:
        fd, tmp_path = tempfile.mkstemp(dir=str(pocketteam_dir), prefix=".observer-tmp-")
        try:
            os.write(fd, str(now).encode())
        finally:
            os.close(fd)
        os.chmod(tmp_path, 0o600)
        os.replace(tmp_path, str(cooldown_file))
    except OSError:
        # If we can't write the cooldown file, skip to avoid duplicate runs
        return {}

    # ── 6. Fire background subprocess ────────────────────────────────────────
    devnull = subprocess.DEVNULL
    try:
        subprocess.Popen(
            [sys.executable, "-m", "pocketteam.agents.observer_cli", str(project_root)],
            start_new_session=True,
            stdout=devnull,
            stderr=devnull,
        )
    except OSError:
        pass

    return {}
