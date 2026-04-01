"""
SafetyGuardian — PreToolUse Hook (runs on EVERY tool call)

This is NOT an agent. It's a deterministic script that:
1. Receives tool call info on stdin (JSON from Claude Code hooks)
2. Checks all 9 safety layers
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
import logging
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from ..constants import AGENT_ALLOWED_TOOLS

logger = logging.getLogger(__name__)


def _resolve_agent_type(agent_id: str) -> str | None:
    """Resolve an internal agent_id hash to a PocketTeam agent type name.

    Reads .pocketteam/agent-registry.json written by agent_lifecycle.py
    during SubagentStart. Returns None if not found.
    """
    d = Path.cwd()
    for _ in range(20):
        registry = d / ".pocketteam" / "agent-registry.json"
        if registry.exists():
            try:
                data = json.loads(registry.read_text())
                return data.get(agent_id)
            except (json.JSONDecodeError, OSError):
                return None
        parent = d.parent
        if parent == d:
            break
        d = parent
    return None


def pre_tool_hook(
    tool_name: str,
    tool_input: Any,
    agent_id: str = "",
    session_id: str = "",
) -> dict:
    """
    Main pre-tool-use safety check.
    Returns {"allow": True/False, "reason": str, "layer": int}

    Security note — agent_id trust level:
    The agent_id comes from hook_input["agent_id"], which is set by Claude Code's
    hook system from the agent's frontmatter (the YAML header in .claude/agents/).
    Claude Code sets this field before invoking the hook — it is NOT user-supplied
    free text that an agent can forge at runtime.  The agent_id is therefore
    considered TRUSTED for allowlist and rate-limit lookups (Layer 6 and 7).
    An agent cannot escalate its own privileges by manipulating agent_id because:
      1. The hook runs in a separate process outside conversation context.
      2. The agent_id is injected by Claude Code, not read from the agent's output.
    Risk level: LOW.  If Claude Code's hook injection mechanism were compromised
    the entire safety system would be bypassed regardless, so no additional
    cryptographic verification is warranted here.
    """
    # Import lazily to avoid import errors if called before install
    try:
        from .allowlist import check_agent_allowlist
        from .mcp_rules import check_mcp_safety
        from .network_rules import check_network_safety, extract_url_from_tool_input
        from .rules import check_destructive, check_never_allow
        from .sensitive_paths import check_sensitive_path, extract_path_from_tool_input
    except ImportError:
        # Safety modules missing — fail CLOSED, never open
        print(
            json.dumps({"allow": False, "reason": "safety modules not installed — cannot verify safety"}),
            file=sys.stderr,
        )
        sys.exit(1)

    input_str = json.dumps(tool_input) if not isinstance(tool_input, str) else tool_input

    # For Bash tools, extract the actual command string for pattern matching
    # (dict input like {"command": "rm -rf ..."} needs unwrapping)
    if tool_name == "Bash" and isinstance(tool_input, dict):
        bash_cmd = tool_input.get("command", "")
        check_str = bash_cmd if bash_cmd else input_str
    else:
        check_str = input_str

    # Compute project root once — reused by Layer 4, Layer 7, and _log_denial
    project_root = _find_project_root()

    # ── Resolve agent_id ────────────────────────────────────────────────────
    # Main session (no --agent flag) is the COO
    if not agent_id:
        agent_id = "coo"

    # Resolve agent_id hash to agent type name (e.g., "a9ed00d9aec628cf" → "engineer")
    # Hashes are not in AGENT_ALLOWED_TOOLS; known type names are.
    if agent_id not in AGENT_ALLOWED_TOOLS and agent_id != "coo":
        resolved = _resolve_agent_type(agent_id)
        if resolved:
            agent_id = resolved

    # ── Layer 1: NEVER_ALLOW ─────────────────────────────────────────────────
    result = check_never_allow(tool_name, check_str)
    if not result.allowed:
        _log_denial(agent_id, tool_name, tool_input, 1, result.reason, project_root)
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
                _log_denial(agent_id, tool_name, tool_input, 5, path_result.reason, project_root)
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
                # Check for valid D-SAC token
                dsac_result = _check_dsac_token(
                    tool_name, tool_input, agent_id, session_id,
                    project_root,
                )
                if dsac_result and dsac_result.get("allow"):
                    return dsac_result

                # No valid token -- D-SAC flow needed
                _log_denial(
                    agent_id, tool_name, tool_input, 3,
                    mcp_result.reason, project_root,
                )
                return {
                    "allow": False,
                    "layer": 3,
                    "reason": (
                        f"BLOCKED (Layer 3 - MCP Safety):"
                        f" {mcp_result.reason}"
                    ),
                    "requires_approval": True,
                }
            _log_denial(
                agent_id, tool_name, tool_input, 3,
                mcp_result.reason, project_root,
            )
            return {
                "allow": False,
                "layer": 3,
                "reason": (
                    f"BLOCKED (Layer 3 - MCP Safety): {mcp_result.reason}"
                ),
            }

    # ── Layer 4: Network Safety ──────────────────────────────────────────────
    input_str_lower = input_str.lower()
    # Hardened detection: cover obfuscated forms of curl/wget invocations.
    # Patterns covered:
    #   - Direct names: "curl", "wget"
    #   - Dynamic lookup: "$(which curl)", "$(which wget)", "`which curl`"
    #   - Variable assignment then use: not feasible to block statically, but
    #     any Bash command containing an unrecognised URL is flagged below.
    #   - Base64-encoded: detect "curl" / "wget" inside decoded base64 payloads.
    #     Base64 of "curl" = "Y3VybA==", of "wget" = "d2dldA=="
    _CURL_WGET_PATTERNS = (
        "curl",
        "wget",
        "$(which curl)",
        "$(which wget)",
        "`which curl`",
        "`which wget`",
        "y3vyba",   # base64 "curl" (lowercase, case-insensitive match below)
        "d2dlda",   # base64 "wget" (lowercase)
    )
    _has_curl_wget = any(pat in input_str_lower for pat in _CURL_WGET_PATTERNS)
    # Also flag Bash commands that contain bare http(s):// URLs even without
    # curl/wget — an agent could use python -c, nc, or other network tools.
    _has_bare_url = (
        tool_name == "Bash"
        and ("http://" in input_str_lower or "https://" in input_str_lower)
    )
    if tool_name in ("WebFetch", "WebSearch") or _has_curl_wget or _has_bare_url:
        url = extract_url_from_tool_input(tool_name, tool_input)
        if url:
            # Load extra approved domains from config
            extra_domains = _load_extra_domains(project_root)
            net_result = check_network_safety(url, extra_approved_domains=extra_domains)
            if not net_result.allowed:
                _log_denial(agent_id, tool_name, tool_input, 4, net_result.reason, project_root)
                return {
                    "allow": False,
                    "layer": 4,
                    "reason": f"BLOCKED (Layer 4 - Network): {net_result.reason}",
                }

    # ── Layer 2: Destructive Patterns ────────────────────────────────────────
    destr_result = check_destructive(tool_name, check_str)
    if not destr_result.allowed:
        # Check if a valid D-SAC token is present in tool_input
        dsac_result = _check_dsac_token(
            tool_name, tool_input, agent_id, session_id, project_root
        )
        if dsac_result and dsac_result.get("allow"):
            return dsac_result

        # No valid token -- require approval
        _log_denial(
            agent_id, tool_name, tool_input, 2,
            destr_result.reason, project_root,
        )
        return {
            "allow": False,
            "layer": 2,
            "reason": (
                f"BLOCKED (Layer 2 - Destructive): {destr_result.reason}"
            ),
            "requires_approval": True,
        }

    # ── Layer 6: Agent Allowlist ─────────────────────────────────────────────
    if agent_id:
        allow_result = check_agent_allowlist(agent_id, tool_name)
        if not allow_result.allowed:
            _log_denial(agent_id, tool_name, tool_input, 6, allow_result.reason, project_root)
            return {
                "allow": False,
                "layer": 6,
                "reason": f"BLOCKED (Layer 6 - Allowlist): {allow_result.reason}",
            }

    # ── Layer 7: Rate Limiting ────────────────────────────────────────────────
    if agent_id and project_root:
        rate_result = _check_rate_limit(agent_id, project_root)
        if not rate_result.get("allow", True):
            _log_denial(agent_id, tool_name, tool_input, 7, rate_result["reason"], project_root)
            return {
                "allow": False,
                "layer": 7,
                "reason": f"BLOCKED (Layer 7 - Rate Limit): {rate_result['reason']}",
            }

    # ── All layers passed ────────────────────────────────────────────────────
    _log_allowed(agent_id, tool_name, tool_input, project_root)
    return {"allow": True, "layer": None, "reason": ""}


def _log_coo_violation_to_stream(
    tool_name: str,
    tool_input: Any,
    reason: str,
    project_root: Path | None,
) -> None:
    """Log a COO direct-tool-use violation to the event stream."""
    if not project_root:
        return
    try:
        from datetime import datetime, UTC

        events_file = project_root / ".pocketteam" / "events" / "stream.jsonl"
        events_file.parent.mkdir(parents=True, exist_ok=True)
        event = {
            "ts": datetime.now(UTC).isoformat(),
            "agent": "coo",
            "type": "coo_direct_tool_use",
            "action": f"BLOCKED: {tool_name}",
            "tool": tool_name,
            "reason": reason,
            "severity": "critical",
        }
        with open(events_file, "a") as f:
            f.write(json.dumps(event) + "\n")
    except Exception:
        pass  # Event stream write is best-effort


def _log_denial(
    agent_id: str,
    tool_name: str,
    tool_input: Any,
    layer: int,
    reason: str,
    project_root: Path | None = None,
) -> None:
    """Write denial to audit log without crashing."""
    try:
        if project_root is None:
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
            # Map Layer 6 COO violations to a more specific decision type
            if layer == 6 and agent_id == "coo":
                decision = SafetyDecision.DENIED_COO_DIRECT_TOOL
                _log_coo_violation_to_stream(tool_name, tool_input, reason, project_root)
            else:
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
        logger.debug("Audit log write failed (non-critical)", exc_info=True)


def _log_allowed(
    agent_id: str,
    tool_name: str,
    tool_input: Any,
    project_root: Path | None = None,
) -> None:
    """Write ALLOWED decision to audit log without crashing."""
    try:
        if project_root is None:
            project_root = _find_project_root()
        if project_root:
            from .audit_log import AuditLog, SafetyDecision
            audit = AuditLog(project_root)
            audit.log(
                agent_id=agent_id or "unknown",
                tool_name=tool_name,
                tool_input=tool_input,
                decision=SafetyDecision.ALLOWED,
                layer=None,
                reason="All 9 safety layers passed",
            )
    except Exception:
        logger.debug("Audit log write failed (non-critical)", exc_info=True)


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


def _check_rate_limit(agent_id: str, project_root: Path) -> dict:
    """
    Layer 7: Disk-persistent turn counter for rate limiting.
    Each hook invocation is a new process, so state is stored in
    .pocketteam/rate_limit_state.json.
    Returns {"allow": True} or {"allow": False, "reason": str}.
    """
    import json as _json
    import time as _time

    state_file = project_root / ".pocketteam" / "rate_limit_state.json"
    from ..constants import AGENT_MAX_TURNS, RATE_LIMIT_WINDOW_SECONDS

    # Load existing state (file may not exist yet) — file I/O is best-effort
    state: dict = {}
    if state_file.exists():
        try:
            state = _json.loads(state_file.read_text())
        except Exception:
            state = {}

    agent_data = state.get(agent_id, {"turns": 0, "reset_at": 0})

    # Rolling window: reset counter if window has expired
    now = _time.time()
    if now - agent_data.get("reset_at", 0) > RATE_LIMIT_WINDOW_SECONDS:
        agent_data = {"turns": 0, "reset_at": now}

    max_turns = AGENT_MAX_TURNS.get(agent_id, AGENT_MAX_TURNS.get("engineer", 50))
    current_turns = agent_data.get("turns", 0)

    # Limit check is NOT wrapped in a fail-open try/except — failure here is fail-closed
    if current_turns >= max_turns:
        return {
            "allow": False,
            "reason": (
                f"Agent '{agent_id}' has reached its turn limit "
                f"({max_turns} turns in rolling 24h window). "
                "Escalating to CEO."
            ),
        }

    # Increment and persist atomically — concurrent agents won't corrupt each other
    agent_data["turns"] = current_turns + 1
    state[agent_id] = agent_data
    try:
        state_file.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(state_file.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                _json.dump(state, f)
            os.replace(tmp, str(state_file))
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
    except OSError:
        pass  # If we can't write, allow the call (don't break everything)

    return {"allow": True}


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


def _check_dsac_token(
    tool_name: str,
    tool_input: Any,
    agent_id: str,
    session_id: str,
    project_root: Path | None,
) -> dict | None:
    """Check if tool_input contains a valid D-SAC approval token.

    Returns an allow-dict if token is valid, None if no token or invalid.

    Guardian computes operation_hash ITSELF from the actual tool_input.
    The agent supplies ONLY __dsac_token, NOT any hash.
    This prevents scope-escalation attacks where an agent gets approval for
    "rm staging_data" then uses the same token for "rm production_data".

    Uses validate_and_consume_token() (atomic) instead of separate
    validate + consume.

    [v3.1 Fix A] session_id is resolved via get_or_create_session_id()
    before validation, so it is NEVER empty when passed to
    validate_and_consume_token(). This prevents session-binding from
    being silently skipped when both hook_input and env var are missing.
    """
    if not isinstance(tool_input, dict):
        return None

    try:
        from ..constants import DSAC_TOKEN_INPUT_KEY
    except ImportError:
        return None

    token_str = tool_input.get(DSAC_TOKEN_INPUT_KEY)
    if not token_str or not isinstance(token_str, str):
        return None

    if not project_root:
        return None

    try:
        from .dsac import DSACGuard, compute_operation_hash_for_tool_call

        guard = DSACGuard(project_root)

        # Compute hash from the ACTUAL tool call
        operation_hash = compute_operation_hash_for_tool_call(
            tool_name, tool_input
        )

        # [v3.1 Fix A] Resolve session_id so it is NEVER empty
        resolved_session_id = guard.get_or_create_session_id(session_id)

        # Atomic validate-and-consume
        valid, reason = guard.validate_and_consume_token(
            token_str=token_str,
            operation_hash=operation_hash,
            agent_id=agent_id,
            session_id=resolved_session_id,  # [v3.1 Fix A] was: session_id
        )

        if valid:
            # Log the approved operation
            try:
                from .audit_log import AuditLog, SafetyDecision

                audit = AuditLog(project_root)
                audit.log(
                    agent_id=agent_id or "unknown",
                    tool_name=tool_name,
                    tool_input={
                        "operation_hash": operation_hash[:16] + "...",
                        "token": token_str[:8] + "...",
                    },
                    decision=SafetyDecision.ALLOWED_WITH_APPROVAL,
                    layer=9,
                    reason=f"D-SAC token validated and consumed: {reason}",
                )
            except Exception:
                pass  # Audit failure must not block approved operation

            return {
                "allow": True,
                "layer": 9,
                "reason": f"D-SAC approved: {reason}",
            }
        else:
            # [v3.1 Fix I] Use specific audit decisions for known failure modes
            try:
                from .audit_log import AuditLog, SafetyDecision

                # Determine specific denial reason for audit
                if "mismatch" in reason.lower():
                    audit_decision = SafetyDecision.DENIED_DSAC_SCOPE_ESCALATION
                elif "already used" in reason.lower():
                    audit_decision = SafetyDecision.DENIED_DSAC_REINITIATION
                else:
                    audit_decision = SafetyDecision.DENIED_REQUIRES_APPROVAL

                audit = AuditLog(project_root)
                audit.log(
                    agent_id=agent_id or "unknown",
                    tool_name=tool_name,
                    tool_input={
                        "operation_hash": operation_hash[:16] + "...",
                        "token": token_str[:8] + "...",
                    },
                    decision=audit_decision,
                    layer=9,
                    reason=f"D-SAC token invalid: {reason}",
                )
            except Exception:
                pass
            return None  # Fall through to normal deny

    except Exception:
        # D-SAC check failure -- fail CLOSED
        logger.warning("D-SAC token check failed", exc_info=True)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry point (called by Claude Code hook system)
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "pre"

    try:
        hook_input = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, EOFError):
        # Malformed input — fail CLOSED, never open
        print(
            json.dumps({"allow": False, "reason": "Malformed hook input — cannot verify safety"}),
            file=sys.stderr,
        )
        sys.exit(1)

    if mode == "pre":
        tool_name = hook_input.get("tool_name", hook_input.get("name", ""))
        tool_input = hook_input.get("tool_input", hook_input.get("input", {}))
        agent_id = hook_input.get("agent_id", "")
        session_id = hook_input.get("session_id", "")

        # Resolve agent_id hash → agent_type name via registry
        # Written by agent_lifecycle.py SubagentStart hook
        if agent_id and agent_id not in AGENT_ALLOWED_TOOLS:
            agent_id = _resolve_agent_type(agent_id) or agent_id
        if not session_id:
            session_id = os.environ.get("CLAUDE_SESSION_ID", "")

        result = pre_tool_hook(
            tool_name, tool_input, agent_id, session_id=session_id
        )
        print(json.dumps(result))

        # Non-zero exit = block the tool call
        sys.exit(0 if result.get("allow") else 1)

    elif mode == "post":
        # PostToolUse: activity logging only (handled by activity_logger.py)
        print(json.dumps({"allow": True}))
        sys.exit(0)
