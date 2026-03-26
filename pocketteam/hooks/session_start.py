"""
Session Start Hook — loads unread Telegram messages on new session.

Reads .pocketteam/telegram-inbox.jsonl, finds messages with status "received",
and outputs them so the COO sees them immediately.
"""

import json
from datetime import UTC, datetime
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
    """Check for unread Telegram messages and present them."""
    pt_dir = _find_pocketteam_dir()
    if not pt_dir:
        return {}

    inbox_path = pt_dir / "telegram-inbox.jsonl"
    if not inbox_path.exists():
        return {}

    # Read all entries
    lines = []
    try:
        with open(inbox_path) as f:
            lines = f.readlines()
    except OSError:
        return {}

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

    if not unread:
        return {}

    # Write back with updated statuses
    try:
        with open(inbox_path, "w") as f:
            for ul in updated_lines:
                f.write(ul + "\n")
    except OSError:
        pass

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
        # Truncate long messages
        if len(text) > 150:
            text = text[:150] + "..."

        summary_lines.append(f"  [{time_str}] {text}")

    summary_lines.append("")
    summary_lines.append("Review and respond to these messages.")

    # Return summary as additionalContext so Claude Code injects it into the session
    return {"additionalContext": "\n".join(summary_lines)}
