"""
Activity Logger — PostToolUse Hook
Logs every tool call to .pocketteam/artifacts/audit/{date}.jsonl
Input is hashed (SHA256) — no raw tool input stored (may contain secrets).

Called by Claude Code's PostToolUse hook in .claude/settings.json:
  cd /project && PYTHONPATH=. python -m pocketteam.safety post
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

from ..utils import append_jsonl


def _find_project_root() -> Path | None:
    """Walk up from cwd to find .pocketteam/ directory."""
    current = Path.cwd()
    for _ in range(10):
        if (current / ".pocketteam").exists():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


def log_activity(tool_name: str, tool_input: str, agent_id: str = "") -> None:
    """Append a tool-use event to the daily audit log."""
    project_root = _find_project_root()
    if not project_root:
        return

    audit_dir = project_root / ".pocketteam" / "artifacts" / "audit"
    try:
        audit_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return

    # Hash input — never store raw content
    input_str = tool_input if isinstance(tool_input, str) else json.dumps(tool_input, default=str)
    input_hash = hashlib.sha256(input_str.encode()).hexdigest()[:16]

    entry = {
        "ts": datetime.now().isoformat(),
        "event": "tool_use",
        "agent": agent_id or "unknown",
        "tool": tool_name,
        "input_hash": f"sha256:{input_hash}",
    }

    date = datetime.now().strftime("%Y-%m-%d")
    log_path = audit_dir / f"{date}.jsonl"

    try:
        append_jsonl(log_path, entry)
    except OSError:
        pass  # Activity logging must never crash the system


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry point (called by PostToolUse hook)
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    try:
        hook_input = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    tool_name = hook_input.get("tool_name", hook_input.get("name", ""))
    tool_input = hook_input.get("tool_input", hook_input.get("input", {}))
    agent_id = hook_input.get("agent_id", "")

    input_str = json.dumps(tool_input, default=str) if not isinstance(tool_input, str) else tool_input
    log_activity(tool_name, input_str, agent_id)

    # PostToolUse: always allow (logging only, never blocks)
    print(json.dumps({"allow": True}))
    sys.exit(0)
