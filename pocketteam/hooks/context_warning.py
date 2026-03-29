"""
PostToolUse Hook — context awareness warnings.

Reads .pocketteam/session-status.json (written by the statusline) and
injects an additionalContext warning when context usage exceeds thresholds.

Behaviour:
- Returns {} if the file is missing, invalid, or stale (>60 s old).
- Returns a yellow warning at >= CONTEXT_WARNING_YELLOW_PCT (70%).
- Returns a red critical warning at >= CONTEXT_WARNING_RED_PCT (90%).
- Debounces: only emits a warning once every CONTEXT_WARNING_DEBOUNCE_CALLS
  tool calls so the noise stays manageable.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from ._utils import _find_pocketteam_dir
from ..constants import (
    CONTEXT_BRIDGE_PATH,
    CONTEXT_WARNING_YELLOW_PCT,
    CONTEXT_WARNING_RED_PCT,
)

# Maximum age (seconds) for session-status.json before it is considered stale
_STALE_SECONDS = 60

# Emit a warning at most once per N tool calls
CONTEXT_WARNING_DEBOUNCE_CALLS = 5

# Module-level call counter — survives for the lifetime of the Python process
# (each hook invocation is a new process, so this resets automatically)
_call_counter: int = 0


def handle(hook_input: dict) -> dict:  # noqa: ARG001
    """Return additionalContext if context usage is high, else {}."""
    global _call_counter
    _call_counter += 1

    # Debounce: only act on the first call of each window
    if _call_counter % CONTEXT_WARNING_DEBOUNCE_CALLS != 1:
        return {}

    pt_dir = _find_pocketteam_dir()
    if not pt_dir:
        return {}

    status_path = pt_dir.parent / CONTEXT_BRIDGE_PATH
    # CONTEXT_BRIDGE_PATH is relative to the repo root, not .pocketteam/
    # Resolve properly: pt_dir IS .pocketteam/, so parent is the repo root.
    if not status_path.exists():
        return {}

    # Staleness check
    try:
        mtime = status_path.stat().st_mtime
    except OSError:
        return {}

    if time.time() - mtime > _STALE_SECONDS:
        return {}

    # Parse JSON
    try:
        data = json.loads(status_path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}

    pct = data.get("contextUsedPct")
    if pct is None:
        return {}

    try:
        pct = float(pct)
    except (TypeError, ValueError):
        return {}

    if pct >= CONTEXT_WARNING_RED_PCT:
        msg = (
            f"CRITICAL: Context at {pct:.0f}%. "
            "Save state and compact NOW."
        )
        return {"additionalContext": msg}

    if pct >= CONTEXT_WARNING_YELLOW_PCT:
        msg = (
            f"Warning: Context usage at {pct:.0f}%. "
            "Consider /compact or delegating to subagents."
        )
        return {"additionalContext": msg}

    return {}
