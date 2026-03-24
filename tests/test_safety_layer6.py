"""
Tests for Safety Layer 6: Per-Agent Tool Allowlist
Each agent may only use the tools permitted for their role.
"""

import pytest
from pocketteam.safety.allowlist import check_agent_allowlist


class TestAgentAllowlist:
    """Layer 6: Per-agent permissions."""

    # ── COO: delegates only ──────────────────────────────────────────────────

    def test_coo_can_use_agent_tool(self):
        result = check_agent_allowlist("coo", "Agent")
        assert result.allowed

    def test_coo_can_read(self):
        result = check_agent_allowlist("coo", "Read")
        assert result.allowed

    def test_coo_cannot_write(self):
        result = check_agent_allowlist("coo", "Write")
        assert not result.allowed

    def test_coo_cannot_bash(self):
        result = check_agent_allowlist("coo", "Bash")
        assert not result.allowed

    def test_coo_cannot_edit(self):
        result = check_agent_allowlist("coo", "Edit")
        assert not result.allowed

    # ── Planner: read-only ────────────────────────────────────────────────────

    def test_planner_can_read(self):
        result = check_agent_allowlist("planner", "Read")
        assert result.allowed

    def test_planner_can_glob(self):
        result = check_agent_allowlist("planner", "Glob")
        assert result.allowed

    def test_planner_can_grep(self):
        result = check_agent_allowlist("planner", "Grep")
        assert result.allowed

    def test_planner_cannot_write(self):
        result = check_agent_allowlist("planner", "Write")
        assert not result.allowed

    def test_planner_cannot_bash(self):
        result = check_agent_allowlist("planner", "Bash")
        assert not result.allowed

    # ── Reviewer: read-only ───────────────────────────────────────────────────

    def test_reviewer_can_read(self):
        result = check_agent_allowlist("reviewer", "Read")
        assert result.allowed

    def test_reviewer_cannot_write(self):
        result = check_agent_allowlist("reviewer", "Write")
        assert not result.allowed

    def test_reviewer_cannot_edit(self):
        result = check_agent_allowlist("reviewer", "Edit")
        assert not result.allowed

    # ── Engineer: read + write + bash ────────────────────────────────────────

    def test_engineer_can_write(self):
        result = check_agent_allowlist("engineer", "Write")
        assert result.allowed

    def test_engineer_can_edit(self):
        result = check_agent_allowlist("engineer", "Edit")
        assert result.allowed

    def test_engineer_can_bash(self):
        result = check_agent_allowlist("engineer", "Bash")
        assert result.allowed

    def test_engineer_can_read(self):
        result = check_agent_allowlist("engineer", "Read")
        assert result.allowed

    # ── Security: read + bash (read-only bash) ────────────────────────────────

    def test_security_can_read(self):
        result = check_agent_allowlist("security", "Read")
        assert result.allowed

    def test_security_can_bash(self):
        result = check_agent_allowlist("security", "Bash")
        assert result.allowed

    def test_security_cannot_write(self):
        result = check_agent_allowlist("security", "Write")
        assert not result.allowed

    # ── Monitor: read + bash only ─────────────────────────────────────────────

    def test_monitor_can_read(self):
        result = check_agent_allowlist("monitor", "Read")
        assert result.allowed

    def test_monitor_can_bash(self):
        result = check_agent_allowlist("monitor", "Bash")
        assert result.allowed

    def test_monitor_cannot_write(self):
        result = check_agent_allowlist("monitor", "Write")
        assert not result.allowed

    def test_monitor_cannot_edit(self):
        result = check_agent_allowlist("monitor", "Edit")
        assert not result.allowed

    # ── Documentation: read + write + edit ───────────────────────────────────

    def test_documentation_can_write(self):
        result = check_agent_allowlist("documentation", "Write")
        assert result.allowed

    def test_documentation_cannot_bash(self):
        result = check_agent_allowlist("documentation", "Bash")
        assert not result.allowed

    # ── TodoWrite: always allowed ─────────────────────────────────────────────

    def test_any_agent_can_use_todo_write(self):
        for agent in ("planner", "reviewer", "engineer", "qa", "monitor"):
            result = check_agent_allowlist(agent, "TodoWrite")
            assert result.allowed, f"{agent} should be able to use TodoWrite"

    # ── MCP tools: passed to Layer 3 ─────────────────────────────────────────

    def test_mcp_tools_bypass_allowlist(self):
        """MCP tools are handled by Layer 3, not Layer 6."""
        result = check_agent_allowlist("planner", "mcp__supabase__list_tables")
        assert result.allowed  # Layer 3 handles this

    # ── Unknown agent ─────────────────────────────────────────────────────────

    def test_unknown_agent_can_read(self):
        result = check_agent_allowlist("unknown_bot", "Read")
        assert result.allowed

    def test_unknown_agent_cannot_write(self):
        result = check_agent_allowlist("unknown_bot", "Write")
        assert not result.allowed

    def test_unknown_agent_cannot_bash(self):
        result = check_agent_allowlist("unknown_bot", "Bash")
        assert not result.allowed

    # ── Empty agent_id (no restriction) ──────────────────────────────────────

    def test_empty_agent_id_allows_all(self):
        """No agent_id means safety is handled by other layers."""
        result = check_agent_allowlist("", "Bash")
        assert result.allowed
