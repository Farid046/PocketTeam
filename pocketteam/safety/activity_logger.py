"""
Activity Logger — PostToolUse Hook
Logs every tool call to .pocketteam/artifacts/audit/{date}.jsonl
Input is hashed (SHA256) — no raw tool input stored (may contain secrets).

Called by Claude Code's PostToolUse hook in .claude/settings.json:
  python -m pocketteam.safety post
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

from ..jsonl import append_jsonl


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


def _resolve_agent_name(agent_id: str, project_root: Path) -> str:
    """Resolve agent hash ID to human-readable name via registry."""
    if not agent_id:
        return "coo"  # Main session = COO
    # Check if it's already a known name
    known = {"coo", "product", "planner", "reviewer", "engineer", "qa",
             "security", "devops", "investigator", "documentation", "monitor", "observer"}
    if agent_id in known:
        return agent_id
    # Try registry
    registry = project_root / ".pocketteam" / "agent-registry.json"
    if registry.exists():
        try:
            data = json.loads(registry.read_text())
            resolved = data.get(agent_id)
            if resolved:
                return resolved
        except (json.JSONDecodeError, OSError):
            pass
    return agent_id  # Return hash if unresolvable


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

    # Resolve agent hash → name
    agent_name = _resolve_agent_name(agent_id, project_root)

    # Hash input — never store raw content
    input_str = tool_input if isinstance(tool_input, str) else json.dumps(tool_input, default=str)
    input_hash = hashlib.sha256(input_str.encode()).hexdigest()[:16]

    entry = {
        "ts": datetime.now().isoformat(),
        "event": "tool_use",
        "agent": agent_name,
        "tool": tool_name,
        "input_hash": f"sha256:{input_hash}",
        "decision": "ALLOWED",
        "layer": None,
        "reason": "",
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
