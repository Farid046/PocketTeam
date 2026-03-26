"""
Agent Lifecycle Hooks — SubagentStart / SubagentStop

Writes real-time events to .pocketteam/events/stream.jsonl
when agents spawn or complete. This gives the dashboard
instant updates instead of relying on 5s polling.
"""

import json
from datetime import UTC, datetime
from pathlib import Path


def _find_event_stream() -> Path | None:
    """Find .pocketteam/events/stream.jsonl by walking up from cwd."""
    d = Path.cwd()
    for _ in range(20):
        candidate = d / ".pocketteam" / "events" / "stream.jsonl"
        if candidate.parent.exists():
            return candidate
        parent = d.parent
        if parent == d:
            break
        d = parent
    return None


def _write_event(event: dict) -> None:
    """Append a JSON event line to the event stream."""
    stream = _find_event_stream()
    if not stream:
        return
    # Import here to avoid circular imports; this module is used as a standalone hook
    from ..utils import append_jsonl
    append_jsonl(stream, event, default=str)


def _count_tool_calls_from_transcript(transcript_path: str) -> int:
    """Count tool_use items in a subagent JSONL transcript.

    Claude Code's SubagentStop hook input does not include a tool count field.
    The transcript (agent_transcript_path) is the only reliable source.
    Each assistant message entry may contain multiple tool_use content blocks.
    """
    if not transcript_path:
        return 0
    try:
        path = Path(transcript_path)
        if not path.exists():
            return 0
        count = 0
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("type") != "assistant":
                    continue
                message = entry.get("message", {})
                content = message.get("content", [])
                if not isinstance(content, list):
                    continue
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "tool_use":
                        count += 1
        return count
    except OSError:
        return 0


def handle_start(hook_input: dict) -> None:
    """Called on SubagentStart — log agent spawn."""
    agent_type = hook_input.get("agent_type", hook_input.get("subagent_type", ""))
    description = hook_input.get("description", hook_input.get("prompt", ""))
    agent_id = hook_input.get("agent_id", "")
    model = hook_input.get("model", "")

    _write_event({
        "ts": datetime.now(UTC).isoformat(),
        "agent": agent_type or "unknown",
        "type": "spawn",
        "tool": "",
        "status": "started",
        "action": description[:200] if description else "Agent started",
        "agent_id": agent_id,
        "model": model,
    })


def handle_stop(hook_input: dict) -> None:
    """Called on SubagentStop — log agent completion.

    Claude Code's SubagentStop hook input fields (as of v2.1+):
      agent_id, agent_transcript_path, agent_type, hook_event_name,
      last_assistant_message, num_turns, session_id, stop_reason,
      total_cost_usd, usage.

    There is no tool_call_count or num_tool_calls field.
    Tool call count is read directly from the JSONL transcript.
    """
    agent_type = hook_input.get("agent_type", hook_input.get("subagent_type", ""))
    agent_id = hook_input.get("agent_id", "")
    duration_ms = hook_input.get("duration_ms", 0)
    transcript_path = hook_input.get("agent_transcript_path", "")
    tool_count = _count_tool_calls_from_transcript(transcript_path)

    duration_s = round(duration_ms / 1000) if duration_ms else 0

    _write_event({
        "ts": datetime.now(UTC).isoformat(),
        "agent": agent_type or "unknown",
        "type": "complete",
        "tool": "",
        "status": "done",
        "action": f"Finished ({tool_count} tool calls, {duration_s}s)" if duration_s else f"Finished ({tool_count} tool calls)",
        "agent_id": agent_id,
    })
