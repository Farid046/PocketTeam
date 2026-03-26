"""
Activity Logger — PostToolUse hook for the event stream.
Called after every successful tool use to log agent activity.
Feeds the .pocketteam/events/stream.jsonl for the Habbo-style dashboard.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from ..utils import append_jsonl


def log_activity(
    agent_id: str,
    tool_name: str,
    tool_input: str,
    project_root: Path,
) -> None:
    """Append an event to the stream.jsonl file."""
    try:
        events_path = project_root / ".pocketteam/events/stream.jsonl"
        events_path.parent.mkdir(parents=True, exist_ok=True)

        # Determine action description from tool + input
        action = _describe_action(tool_name, tool_input)

        event = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "agent": agent_id or "unknown",
            "type": "tool_use",
            "tool": tool_name,
            "status": "working",
            "action": action,
        }

        append_jsonl(events_path, event)
    except Exception:
        pass  # Activity logging must never crash hook execution


def _describe_action(tool_name: str, tool_input: str) -> str:
    """Generate a human-readable action description."""
    input_preview = str(tool_input)[:80].replace("\n", " ")

    descriptions = {
        "Read": f"Reading {input_preview}",
        "Write": f"Writing {input_preview}",
        "Edit": f"Editing {input_preview}",
        "Bash": f"Running: {input_preview}",
        "Glob": f"Searching files: {input_preview}",
        "Grep": f"Searching: {input_preview}",
        "WebSearch": f"Searching web: {input_preview}",
        "WebFetch": f"Fetching: {input_preview}",
        "Agent": f"Spawning sub-agent: {input_preview}",
    }

    if tool_name.startswith("mcp__supabase__"):
        op = tool_name.replace("mcp__supabase__", "")
        return f"Supabase {op}: {input_preview}"
    if tool_name.startswith("mcp__"):
        return f"MCP {tool_name}: {input_preview}"

    return descriptions.get(tool_name, f"{tool_name}: {input_preview}")


# ── CLI entry point (called by Claude Code hook system) ────────────────────

if __name__ == "__main__":
    try:
        hook_input = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    tool_name = hook_input.get("tool_name", hook_input.get("name", ""))
    tool_input = hook_input.get("tool_input", hook_input.get("input", ""))
    agent_id = hook_input.get("agent_id", "")

    # Find project root
    current = Path.cwd()
    for _ in range(10):
        if (current / ".pocketteam").exists():
            log_activity(agent_id, tool_name, str(tool_input), current)
            break
        parent = current.parent
        if parent == current:
            break
        current = parent

    sys.exit(0)
