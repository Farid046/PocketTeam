"""
PreCompact Hook — preserves critical context before compression.

Saves a timestamp so that after compression, the SessionStart hook
knows which Telegram messages were already in context vs. lost.
Also saves a brief context snapshot to .pocketteam/context-preservation.md.
"""

import json
import time
from pathlib import Path


def _find_pocketteam_dir() -> Path | None:
    d = Path.cwd()
    for _ in range(20):
        candidate = d / ".pocketteam"
        if candidate.exists():
            return candidate
        parent = d.parent
        if parent == d:
            break
        d = parent
    return None


def handle(hook_input: dict) -> dict:
    """Save compact timestamp + mark unprocessed messages."""
    pt_dir = _find_pocketteam_dir()
    if not pt_dir:
        return {}

    # Save timestamp
    ts_file = pt_dir / ".last-compact-ts"
    try:
        ts_file.write_text(str(int(time.time())))
    except OSError:
        pass

    # Re-mark any "presented" messages as "received" so they get
    # re-presented after compression (the context that saw them is gone)
    inbox_path = pt_dir / "telegram-inbox.jsonl"
    if not inbox_path.exists():
        return {}

    try:
        lines = inbox_path.read_text().strip().split("\n")
    except OSError:
        return {}

    updated = []
    for line in lines:
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            updated.append(line)
            continue

        # Messages that were "presented" in the now-compressed context
        # need to be re-presented in the new context
        if entry.get("status") == "presented":
            entry["status"] = "received"
            entry["requeued_reason"] = "pre_compact"

        updated.append(json.dumps(entry, default=str))

    try:
        inbox_path.write_text("\n".join(updated) + "\n")
    except OSError:
        pass

    return {}
