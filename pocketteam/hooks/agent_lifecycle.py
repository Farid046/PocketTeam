"""
Agent Lifecycle Hooks — SubagentStart / SubagentStop

Writes real-time events to .pocketteam/events/stream.jsonl
when agents spawn or complete. This gives the dashboard
instant updates instead of relying on 5s polling.
"""

import json
import re
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


_STATUS_RE = re.compile(
    r'^STATUS:\s+(DONE(?:_WITH_CONCERNS)?|NEEDS_CONTEXT|BLOCKED)(?:\s+—\s+(.+))?$'
)


def _parse_agent_status(last_message: str) -> tuple[str, str]:
    """Parse the structured status token from the last line of an agent's output.

    Returns a (status, reason) tuple. Defaults to ("DONE", "") when no valid
    STATUS token is found on the last non-empty line.

    Examples:
        "STATUS: DONE"                              -> ("DONE", "")
        "STATUS: DONE_WITH_CONCERNS — low coverage" -> ("DONE_WITH_CONCERNS", "low coverage")
        "STATUS: NEEDS_CONTEXT — missing DB schema"  -> ("NEEDS_CONTEXT", "missing DB schema")
        "STATUS: BLOCKED — staging is down"          -> ("BLOCKED", "staging is down")
        "some text with no token"                   -> ("DONE", "")
    """
    if not last_message:
        return ("DONE", "")

    lines = last_message.splitlines()
    # Find the last non-empty line
    for line in reversed(lines):
        stripped = line.strip()
        if stripped:
            match = _STATUS_RE.match(stripped)
            if match:
                status = match.group(1)
                reason = match.group(2) or ""
                return (status, reason)
            break

    return ("DONE", "")


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
    last_message = hook_input.get("last_assistant_message", "")
    tool_count = _count_tool_calls_from_transcript(transcript_path)

    duration_s = round(duration_ms / 1000) if duration_ms else 0

    agent_status, agent_status_reason = _parse_agent_status(last_message)

    event: dict = {
        "ts": datetime.now(UTC).isoformat(),
        "agent": agent_type or "unknown",
        "type": "complete",
        "tool": "",
        "status": "done",
        "action": f"Finished ({tool_count} tool calls, {duration_s}s)" if duration_s else f"Finished ({tool_count} tool calls)",
        "agent_id": agent_id,
        "agent_status": agent_status,
    }
    if agent_status_reason:
        event["agent_status_reason"] = agent_status_reason

    _write_event(event)

    # Record cost data for per-agent cost tracking
    total_cost_usd = hook_input.get("total_cost_usd", 0.0)
    usage = hook_input.get("usage")
    from .cost_tracker import record_agent_cost
    record_agent_cost(agent_type or "unknown", total_cost_usd, usage)
