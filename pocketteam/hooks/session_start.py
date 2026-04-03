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
    """Send a notification to the CEO via Telegram Bot API.

    Only fires when Telegram is explicitly configured for THIS project.
    This prevents notifications leaking into projects that have not set
    up Telegram (the global ~/.claude/channels/telegram/.env is never
    sufficient on its own).
    """
    try:
        # Project-level gate: check that THIS project has a non-empty chat_id.
        # We avoid importing yaml to keep hooks lightweight; simple text scan
        # is safe because we only need to detect an empty/absent value.
        config_file = pt_dir / "config.yaml"
        if not config_file.exists():
            return
        config_text = config_file.read_text()
        # Skip if there is no telegram section or chat_id is empty / unset
        if "telegram:" not in config_text:
            return
        # Extract chat_id value via simple parsing (handles both '' and "")
        chat_id_configured = False
        for line in config_text.splitlines():
            stripped = line.strip()
            if stripped.startswith("chat_id:"):
                value = stripped[len("chat_id:"):].strip().strip("'\"")
                if value:
                    chat_id_configured = True
                break
        if not chat_id_configured:
            return

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
    # Also skip when session was auto-triggered (e.g. by GitHub Actions
    # via /trigger-session). The marker file is written by the trigger
    # endpoint and consumed here.
    auto_trigger_marker = pt_dir / "auto-triggered"
    is_automated = auto_trigger_marker.exists()
    if is_automated:
        try:
            auto_trigger_marker.unlink()
        except OSError:
            pass

    # Dedup: Only greet once per session (PreCompact triggers SessionStart again)
    # If the lock file is older than 60 seconds, it's from a stale session — ignore it
    greeted_file = pt_dir / "session-greeted.lock"
    already_greeted = False
    if greeted_file.exists():
        try:
            import time
            age = time.time() - greeted_file.stat().st_mtime
            already_greeted = age < 60  # Only consider fresh locks (< 60s)
        except OSError:
            already_greeted = False

    if not unread and not is_automated and not already_greeted:
        _notify_telegram(
            pt_dir,
            "PocketTeam Session gestartet. Wie kann ich helfen?"
        )
        try:
            greeted_file.write_text(str(os.getpid()))
        except OSError:
            pass

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
