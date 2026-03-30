"""
Session Start Hook — loads unread Telegram messages and notifies CEO.

Reads .pocketteam/telegram-inbox.jsonl, finds messages with status "received",
sends a Telegram notification that the session is active, and outputs the
messages so the COO sees them immediately.
"""

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from ._utils import _find_pocketteam_dir


def _notify_telegram(pt_dir: Path, message: str) -> None:
    """Send a notification to the CEO via Telegram Bot API."""
    try:
        env_file = Path.home() / ".claude" / "channels" / "telegram" / ".env"
        access_file = Path.home() / ".claude" / "channels" / "telegram" / "access.json"

        if not env_file.exists() or not access_file.exists():
            return

        bot_token = ""
        for line in env_file.read_text().splitlines():
            if line.startswith("TELEGRAM_BOT_TOKEN="):
                bot_token = line.split("=", 1)[1].strip()
                break

        if not bot_token:
            return

        access_data = json.loads(access_file.read_text())
        allowed = access_data.get("allowFrom", [])
        if not allowed:
            return

        # Send to first allowed user (CEO)
        chat_id = allowed[0]

        import urllib.request
        import urllib.parse

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": message,
        }).encode()

        req = urllib.request.Request(url, data=data, method="POST")
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass  # Notification is best-effort, never block session start


def handle(hook_input: dict) -> dict:
    """Check for unread Telegram messages, notify CEO, present them."""
    pt_dir = _find_pocketteam_dir()
    if not pt_dir:
        return {}

    # Write session lock so the daemon knows a session is active
    lock_file = pt_dir / "session.lock"
    try:
        lock_file.write_text(str(os.getpid()))
    except OSError:
        pass

    inbox_path = pt_dir / "telegram-inbox.jsonl"

    # Read all entries
    lines = []
    if inbox_path.exists():
        try:
            with open(inbox_path) as f:
                lines = f.readlines()
        except OSError:
            pass

    updated_lines = []
    unread = []

    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            updated_lines.append(line)
            continue

        if entry.get("status") == "received":
            unread.append(entry)
            # Mark as presented
            entry["status"] = "presented"
            entry["presented_at"] = datetime.now(UTC).isoformat()

        updated_lines.append(json.dumps(entry, default=str))

    # Write back with updated statuses
    if updated_lines:
        try:
            with open(inbox_path, "w") as f:
                for ul in updated_lines:
                    f.write(ul + "\n")
        except OSError:
            pass

    # Send Telegram notification that session is active
    # Only notify when no unread messages — the COO will reply to unread
    # messages directly, so a separate greeting would be a duplicate.
    if not unread:
        _notify_telegram(
            pt_dir,
            "PocketTeam Session gestartet. Wie kann ich helfen?"
        )

    if not unread:
        return {}

    # Build summary message for the COO
    summary_lines = [f"📨 {len(unread)} unread Telegram message(s) from CEO:"]
    summary_lines.append("")

    for msg in unread[-10:]:  # Show last 10
        ts = msg.get("ts", "")
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            time_str = dt.strftime("%H:%M")
        except (ValueError, AttributeError):
            time_str = "??:??"

        text = msg.get("text", "")
        if len(text) > 150:
            text = text[:150] + "..."

        summary_lines.append(f"  [{time_str}] {text}")

    summary_lines.append("")
    summary_lines.append("Review and respond to these messages.")

    return {"additionalContext": "\n".join(summary_lines)}
