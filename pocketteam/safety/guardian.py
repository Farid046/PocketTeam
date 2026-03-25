"""
SafetyGuardian — PreToolUse Hook (runs on EVERY tool call)

This is NOT an agent. It's a deterministic script that:
1. Receives tool call info on stdin (JSON from Claude Code hooks)
2. Checks all 10 safety layers
3. Returns allow/deny decision on stdout

Registered as a PreToolUse hook in .claude/settings.json
Lives OUTSIDE conversation context → survives context compaction
Cannot be "convinced" or "overridden" by any prompt

Usage (invoked by Claude Code hook system):
  python guardian.py pre   < hook_input.json
  python guardian.py post  < hook_input.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def pre_tool_hook(tool_name: str, tool_input: Any, agent_id: str = "") -> dict:
    """
    Main pre-tool-use safety check.
    Returns {"allow": True/False, "reason": str, "layer": int}
    """
    # Import lazily to avoid import errors if called before install
    try:
        from .rules import check_never_allow, check_destructive
        from .mcp_rules import check_mcp_safety
        from .network_rules import check_network_safety, extract_url_from_tool_input
        from .sensitive_paths import check_sensitive_path, extract_path_from_tool_input
        from .allowlist import check_agent_allowlist
        from .kill_switch import KillSwitch
    except ImportError:
        # If modules not yet installed, allow (bootstrap phase)
        return {"allow": True, "reason": "safety modules not yet installed"}

    input_str = json.dumps(tool_input) if not isinstance(tool_input, str) else tool_input

    # For Bash tools, extract the actual command string for pattern matching
    # (dict input like {"command": "rm -rf ..."} needs unwrapping)
    if tool_name == "Bash" and isinstance(tool_input, dict):
        bash_cmd = tool_input.get("command", "")
        check_str = bash_cmd if bash_cmd else input_str
    else:
        check_str = input_str

    # ── Layer 10: Kill Switch (checked first, highest priority) ──────────────
    project_root = _find_project_root()
    if project_root:
        ks = KillSwitch(project_root)
        if ks.is_active:
            return {
                "allow": False,
                "layer": 10,
                "reason": "Kill switch is active (.pocketteam/KILL). Run: pocketteam resume",
            }

    # ── Layer 1: NEVER_ALLOW ─────────────────────────────────────────────────
    result = check_never_allow(tool_name, check_str)
    if not result.allowed:
        _log_denial(agent_id, tool_name, tool_input, 1, result.reason)
        return {
            "allow": False,
            "layer": 1,
            "reason": f"BLOCKED (Layer 1 - NEVER_ALLOW): {result.reason}",
        }

    # ── Layer 5: Sensitive File Check ────────────────────────────────────────
    if tool_name in ("Read", "Write", "Edit", "Bash"):
        paths = extract_path_from_tool_input(tool_name, tool_input)
        for path in paths:
            path_result = check_sensitive_path(tool_name, path, agent_id)
            if path_result.blocked:
                _log_denial(agent_id, tool_name, tool_input, 5, path_result.reason)
                return {
                    "allow": False,
                    "layer": 5,
                    "reason": f"BLOCKED (Layer 5 - Sensitive File): {path_result.reason}",
                }

    # ── Layer 3: MCP Tool Safety ─────────────────────────────────────────────
    if tool_name.startswith("mcp__"):
        mcp_result = check_mcp_safety(tool_name, tool_input)
        if not mcp_result.allowed:
            if mcp_result.requires_approval:
                # D-SAC flow needed — return requires_approval flag
                _log_denial(agent_id, tool_name, tool_input, 3, mcp_result.reason)
                return {
                    "allow": False,
                    "layer": 3,
                    "reason": f"BLOCKED (Layer 3 - MCP Safety): {mcp_result.reason}",
                    "requires_approval": True,
                }
            _log_denial(agent_id, tool_name, tool_input, 3, mcp_result.reason)
            return {
                "allow": False,
                "layer": 3,
                "reason": f"BLOCKED (Layer 3 - MCP Safety): {mcp_result.reason}",
            }

    # ── Layer 4: Network Safety ──────────────────────────────────────────────
    if tool_name in ("WebFetch", "WebSearch") or "curl" in input_str or "wget" in input_str:
        url = extract_url_from_tool_input(tool_name, tool_input)
        if url:
            # Load extra approved domains from config
            extra_domains = _load_extra_domains(project_root)
            net_result = check_network_safety(url, extra_approved_domains=extra_domains)
            if not net_result.allowed:
                _log_denial(agent_id, tool_name, tool_input, 4, net_result.reason)
                return {
                    "allow": False,
                    "layer": 4,
                    "reason": f"BLOCKED (Layer 4 - Network): {net_result.reason}",
                }

    # ── Layer 2: Destructive Patterns ────────────────────────────────────────
    destr_result = check_destructive(tool_name, check_str)
    if not destr_result.allowed:
        # Requires D-SAC approval — not an outright block
        _log_denial(agent_id, tool_name, tool_input, 2, destr_result.reason)
        return {
            "allow": False,
            "layer": 2,
            "reason": f"BLOCKED (Layer 2 - Destructive): {destr_result.reason}",
            "requires_approval": True,
        }

    # ── Layer 6: Agent Allowlist ─────────────────────────────────────────────
    if agent_id:
        allow_result = check_agent_allowlist(agent_id, tool_name)
        if not allow_result.allowed:
            _log_denial(agent_id, tool_name, tool_input, 6, allow_result.reason)
            return {
                "allow": False,
                "layer": 6,
                "reason": f"BLOCKED (Layer 6 - Allowlist): {allow_result.reason}",
            }

    # ── All layers passed ────────────────────────────────────────────────────
    return {"allow": True, "layer": None, "reason": ""}


def _log_denial(
    agent_id: str,
    tool_name: str,
    tool_input: Any,
    layer: int,
    reason: str,
) -> None:
    """Write denial to audit log without crashing."""
    try:
        project_root = _find_project_root()
        if project_root:
            from .audit_log import AuditLog, SafetyDecision
            audit = AuditLog(project_root)
            decision_map = {
                1: SafetyDecision.DENIED_NEVER_ALLOW,
                2: SafetyDecision.DENIED_REQUIRES_APPROVAL,
                3: SafetyDecision.DENIED_MCP_UNSAFE,
                4: SafetyDecision.DENIED_NETWORK,
                5: SafetyDecision.DENIED_SENSITIVE_FILE,
                6: SafetyDecision.DENIED_ALLOWLIST,
                7: SafetyDecision.DENIED_RATE_LIMIT,
            }
            decision = decision_map.get(layer, SafetyDecision.DENIED)
            audit.log(
                agent_id=agent_id or "unknown",
                tool_name=tool_name,
                tool_input=tool_input,
                decision=decision,
                layer=layer,
                reason=reason,
            )
    except Exception:
        pass


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


def _load_extra_domains(project_root: Path | None) -> list[str]:
    """Load extra approved domains from config."""
    if not project_root:
        return []
    try:
        import sys
        sys.path.insert(0, str(project_root))
        from pocketteam.config import load_config
        cfg = load_config(project_root)
        return cfg.network.approved_domains
    except Exception:
        return []


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry point (called by Claude Code hook system)
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "pre"

    try:
        hook_input = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, EOFError):
        # Malformed input — allow (don't block legitimate operations)
        print(json.dumps({"allow": True, "reason": "Could not parse hook input"}))
        sys.exit(0)

    if mode == "pre":
        tool_name = hook_input.get("tool_name", hook_input.get("name", ""))
        tool_input = hook_input.get("tool_input", hook_input.get("input", {}))
        agent_id = hook_input.get("agent_id", "")

        result = pre_tool_hook(tool_name, tool_input, agent_id)
        print(json.dumps(result))

        # Non-zero exit = block the tool call
        sys.exit(0 if result.get("allow") else 1)

    elif mode == "post":
        # PostToolUse: activity logging only (handled by activity_logger.py)
        print(json.dumps({"allow": True}))
        sys.exit(0)
