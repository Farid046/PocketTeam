"""
Safety Layer 3: MCP Tool Safety
Prevents SQL injection, unauthorized mutations, and dangerous MCP operations.
Lesson from OpenClaw: MCP tools can bypass normal safety if not checked.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class McpCheckResult:
    allowed: bool
    layer: int = 3
    reason: str = ""
    requires_approval: bool = False


# ─────────────────────────────────────────────────────────────────────────────
# SQL mutation patterns — block unless pre-approved in plan
# ─────────────────────────────────────────────────────────────────────────────

SQL_MUTATION_PATTERNS = [
    r"\bDELETE\b",
    r"\bDROP\b",
    r"\bTRUNCATE\b",
    r"\bALTER\s+TABLE\b",
    r"\bALTER\s+COLUMN\b",
    r"\bREVOKE\b",
    r"\bGRANT\b",
    r"\bUPDATE\b.*\bSET\b",    # UPDATE ... SET (with WHERE check below)
    r"\bINSERT\s+(?:INTO\s+)?(?:OR\s+REPLACE\s+INTO\s+)?",  # INSERT
]

# UPDATE without WHERE is dangerous (affects all rows).
# Two-pattern approach: match UPDATE...SET, then verify WHERE is absent.
# A negative lookahead in the same regex doesn't work correctly with greedy .+ and DOTALL.
_SQL_UPDATE_SET_RE = re.compile(r"\bUPDATE\b.+\bSET\b", re.IGNORECASE | re.DOTALL)
_SQL_WHERE_RE = re.compile(r"\bWHERE\b", re.IGNORECASE)


def _is_update_without_where(sql: str) -> bool:
    """True if SQL contains UPDATE...SET but no WHERE clause."""
    return bool(_SQL_UPDATE_SET_RE.search(sql)) and not bool(_SQL_WHERE_RE.search(sql))


SQL_UPDATE_NO_WHERE = None  # Replaced by _is_update_without_where()

# DELETE without WHERE
SQL_DELETE_NO_WHERE = re.compile(
    r"\bDELETE\s+FROM\s+\w+\s*(?:;|$)",
    re.IGNORECASE,
)

_SQL_MUTATION_RE = [re.compile(p, re.IGNORECASE) for p in SQL_MUTATION_PATTERNS]

# SQL injection markers — these are NEVER allowed in SQL params
SQL_INJECTION_PATTERNS = [
    r"'.*OR.*'.*=.*'",            # ' OR '1'='1
    r";\s*DROP\s+",               # ; DROP
    r";\s*DELETE\s+",             # ; DELETE
    r"UNION\s+SELECT",             # UNION SELECT
    r"--\s*$",                     # SQL comment at end
    r"/\*.*\*/",                   # Block comment in SQL
    r"EXEC\s*\(",                  # EXEC(
    r"xp_cmdshell",               # SQL Server command execution
    r"LOAD_FILE\s*\(",            # MySQL file read
    r"INTO\s+OUTFILE",            # MySQL file write
]

_SQL_INJECTION_RE = [re.compile(p, re.IGNORECASE) for p in SQL_INJECTION_PATTERNS]

# ─────────────────────────────────────────────────────────────────────────────
# MCP tool rules
# ─────────────────────────────────────────────────────────────────────────────

# Tools that require plan approval for ANY use
MCP_ALWAYS_REQUIRE_APPROVAL = {
    "mcp__supabase__apply_migration",
    "mcp__supabase__deploy_edge_function",
    "mcp__kubernetes__kubectl_delete",
    "mcp__kubernetes__kubectl_apply",
    "mcp__kubernetes__install_helm_chart",
    "mcp__kubernetes__uninstall_helm_chart",
    "mcp__terraform__apply",
    "mcp__terraform__destroy",
}

# MCP tool patterns that require approval — any tool whose name contains these verbs
MCP_REQUIRES_APPROVAL_PATTERNS = [
    # Communication (send, email, message, notify, post)
    re.compile(r"mcp__\w+__(send|email|message|notify|post)\w*", re.IGNORECASE),
    # Deletion (delete, remove, purge, destroy, drop)
    re.compile(r"mcp__\w+__(delete|remove|purge|destroy|drop)\w*", re.IGNORECASE),
    # Bulk writes (bulk, mass, batch that writes)
    re.compile(r"mcp__\w+__(bulk_write|mass_delete|batch_delete)\w*", re.IGNORECASE),
]

# Compiled glob patterns for communication tools (kept for backward compat)
_MCP_COMM_PATTERNS = MCP_REQUIRES_APPROVAL_PATTERNS

# Supabase: delete operations always need approval
MCP_SUPABASE_DELETE_PATTERNS = [
    "mcp__supabase__delete",
    "mcp__supabase__remove",
]


def check_mcp_safety(tool_name: str, tool_input: Any) -> McpCheckResult:
    """
    Layer 3: Check MCP tool calls for safety.
    tool_input can be dict (parsed JSON) or string.
    """
    # Normalize input
    if isinstance(tool_input, dict):
        input_str = str(tool_input)
        sql = tool_input.get("query", tool_input.get("sql", ""))
    else:
        input_str = str(tool_input)
        sql = input_str

    # 1. Always-require-approval tools
    if tool_name in MCP_ALWAYS_REQUIRE_APPROVAL:
        return McpCheckResult(
            allowed=False,
            reason=f"MCP tool {tool_name} always requires plan approval",
            requires_approval=True,
        )

    # 2. Supabase SQL: check for mutations
    if "mcp__supabase__execute_sql" in tool_name or "mcp__supabase__query" in tool_name:
        result = _check_supabase_sql(sql)
        if not result.allowed:
            return result

    # 3. Communication and destructive verb tools
    for pattern in _MCP_COMM_PATTERNS:
        if pattern.match(tool_name) or pattern.search(tool_name):
            return McpCheckResult(
                allowed=False,
                reason=f"MCP tool '{tool_name}' performs a destructive/communication action and requires plan approval",
                requires_approval=True,
            )

    # 4. Supabase delete operations
    for delete_prefix in MCP_SUPABASE_DELETE_PATTERNS:
        if tool_name.startswith(delete_prefix):
            return McpCheckResult(
                allowed=False,
                reason=f"Supabase delete operation requires plan approval",
                requires_approval=True,
            )

    # 5. Check for SQL injection in any MCP input
    if sql:
        for pattern in _SQL_INJECTION_RE:
            if pattern.search(sql):
                return McpCheckResult(
                    allowed=False,
                    reason=f"SQL injection pattern detected in MCP input",
                    requires_approval=False,  # Never allow SQL injection
                )

    return McpCheckResult(allowed=True, reason="")


def _check_supabase_sql(sql: str) -> McpCheckResult:
    """Check a Supabase SQL query for dangerous patterns."""
    if not sql:
        return McpCheckResult(allowed=True, reason="")

    # Check for mutations that need approval
    for pattern in _SQL_MUTATION_RE:
        if pattern.search(sql):
            # Extra check: DELETE/UPDATE without WHERE is extra dangerous
            if SQL_DELETE_NO_WHERE.search(sql):
                return McpCheckResult(
                    allowed=False,
                    reason="DELETE without WHERE clause — requires plan approval",
                    requires_approval=True,
                )
            if _is_update_without_where(sql):
                return McpCheckResult(
                    allowed=False,
                    reason="UPDATE without WHERE clause — requires plan approval",
                    requires_approval=True,
                )
            return McpCheckResult(
                allowed=False,
                reason=f"SQL mutation requires plan approval",
                requires_approval=True,
            )

    return McpCheckResult(allowed=True, reason="")
