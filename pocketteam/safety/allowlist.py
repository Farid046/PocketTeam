"""
Safety Layer 6: Per-Agent Tool Allowlist
Each agent may only use the tools explicitly permitted for its role.
A planner cannot write files. A monitor cannot make destructive changes.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..constants import AGENT_ALLOWED_TOOLS


@dataclass
class AllowlistResult:
    allowed: bool
    layer: int = 6
    reason: str = ""
    agent_id: str = ""
    tool_name: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# Tool family mappings
# Maps Claude Code tool names to their canonical families
# ─────────────────────────────────────────────────────────────────────────────

TOOL_FAMILIES: dict[str, str] = {
    # Read family
    "Read":        "Read",
    "Glob":        "Glob",
    "Grep":        "Grep",

    # Write family
    "Write":       "Write",
    "Edit":        "Edit",

    # Execution
    "Bash":        "Bash",

    # Search
    "WebSearch":   "WebSearch",
    "WebFetch":    "WebFetch",

    # Agent spawning (always allowed for COO, blocked for others by default)
    "Agent":       "Agent",

    # Task management
    "TodoWrite":   "TodoWrite",
    "TodoRead":    "TodoRead",

    # Notebooks
    "NotebookRead":  "NotebookRead",
    "NotebookEdit":  "NotebookEdit",
}


def check_agent_allowlist(agent_id: str, tool_name: str) -> AllowlistResult:
    """
    Layer 6: Is this agent allowed to use this tool?
    MCP tools (mcp__*) are checked separately in mcp_rules.py
    """
    if not agent_id:
        # Unknown agent (includes sub-agents spawned by COO).
        # Allow standard tools but block Agent spawning (only COO delegates).
        blocked_for_unknown = {"Agent"}
        if tool_name in blocked_for_unknown:
            return AllowlistResult(
                allowed=False,
                reason="Unknown agent — only the COO can delegate to other agents",
                agent_id=agent_id,
                tool_name=tool_name,
            )
        return AllowlistResult(
            allowed=True,
            reason="Unknown agent — standard tools allowed, delegation blocked",
            agent_id=agent_id,
            tool_name=tool_name,
        )

    # MCP tools: checked by Layer 3, not here
    if tool_name.startswith("mcp__"):
        return AllowlistResult(
            allowed=True,
            reason="MCP tools checked by Layer 3",
            agent_id=agent_id,
            tool_name=tool_name,
        )

    # COO delegates ALL work. Only Agent (spawn), TodoWrite/TodoRead (task tracking)
    # are permitted. Read/Glob/Grep are intentionally excluded — the COO must
    # delegate file reading to a sub-agent (e.g., planner, reviewer, engineer).
    if agent_id == "coo":
        coo_allowed = {"Agent", "TodoWrite", "TodoRead"}
        if tool_name in coo_allowed:
            return AllowlistResult(allowed=True, agent_id=agent_id, tool_name=tool_name)
        return AllowlistResult(
            allowed=False,
            reason=f"COO is not allowed to use {tool_name} directly. Delegate to a specialized sub-agent (planner, reviewer, engineer, etc.). Only Agent, TodoWrite, and TodoRead are permitted for the COO.",
            agent_id=agent_id,
            tool_name=tool_name,
        )

    allowed_tools = AGENT_ALLOWED_TOOLS.get(agent_id)

    if allowed_tools is None:
        # Unknown agent type — default deny Write/Bash, allow read
        read_only = {"Read", "Glob", "Grep", "WebSearch", "WebFetch"}
        if tool_name in read_only:
            return AllowlistResult(allowed=True, agent_id=agent_id, tool_name=tool_name)
        return AllowlistResult(
            allowed=False,
            reason=f"Unknown agent '{agent_id}' — only read-only tools allowed",
            agent_id=agent_id,
            tool_name=tool_name,
        )

    # Empty list means no tools (COO delegates)
    if not allowed_tools:
        return AllowlistResult(
            allowed=False,
            reason=f"Agent '{agent_id}' has no direct tool access — it delegates to sub-agents",
            agent_id=agent_id,
            tool_name=tool_name,
        )

    # Check if tool is in allowlist
    if tool_name in allowed_tools:
        return AllowlistResult(allowed=True, agent_id=agent_id, tool_name=tool_name)

    # TodoWrite/TodoRead: allowed for all agents (task tracking)
    if tool_name in ("TodoWrite", "TodoRead"):
        return AllowlistResult(allowed=True, agent_id=agent_id, tool_name=tool_name)

    return AllowlistResult(
        allowed=False,
        reason=(
            f"Agent '{agent_id}' is not allowed to use {tool_name}.\n"
            f"Allowed tools: {', '.join(sorted(allowed_tools))}"
        ),
        agent_id=agent_id,
        tool_name=tool_name,
    )


def get_agent_permissions_summary() -> dict[str, list[str]]:
    """Return a human-readable summary of all agent permissions."""
    return {
        agent: tools if tools else ["(delegates only — no direct tools)"]
        for agent, tools in AGENT_ALLOWED_TOOLS.items()
    }
