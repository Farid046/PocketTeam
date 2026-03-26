"""
Telegram Inbox — persists every Telegram message to disk.

Called on UserPromptSubmit. Checks if the message came from a Telegram channel
and saves it to .pocketteam/telegram-inbox.jsonl for recovery after session
restarts, context compression, or plan mode.
"""

import json
import os
from datetime import datetime, timezone
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
    """Save Telegram-sourced messages to the inbox file."""
    # The hook input for UserPromptSubmit contains the user's message
    message = hook_input.get("input", hook_input.get("content", hook_input.get("message", "")))

    if not isinstance(message, str):
        return {}

    # Detect if this came from Telegram (channel source metadata)
    # Telegram messages contain <channel source="telegram" ...> tags
    is_telegram = "channel" in str(hook_input) and "telegram" in str(hook_input)

    # Also check the message itself for channel tags
    if not is_telegram and '<channel source="' in message:
        is_telegram = True
    if not is_telegram and "plugin:telegram" in message:
        is_telegram = True

    if not is_telegram:
        return {}

    pt_dir = _find_pocketteam_dir()
    if not pt_dir:
        return {}

    inbox_path = pt_dir / "telegram-inbox.jsonl"

    # Extract text content (strip XML-like channel tags if present)
    text = message
    if "<channel" in text:
        # Try to extract just the text content
        import re
        match = re.search(r'<channel[^>]*>(.*?)</channel>', text, re.DOTALL)
        if match:
            text = match.group(1).strip()

    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "from": hook_input.get("user_id", hook_input.get("sender", "unknown")),
        "text": text[:2000],  # cap at 2000 chars
        "status": "received",
        "session_id": hook_input.get("session_id", os.environ.get("CLAUDE_SESSION_ID", "")),
    }

    try:
        with open(inbox_path, "a") as f:
            f.write(json.dumps(entry, default=str) + "\n")
    except OSError:
        pass

    return {}
