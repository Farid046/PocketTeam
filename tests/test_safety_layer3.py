"""
Tests for Safety Layer 3: MCP Tool Safety
SQL injection prevention, Supabase mutation protection.
"""

from pocketteam.safety.mcp_rules import check_mcp_safety


class TestMcpSafety:
    """Layer 3: MCP tool safety."""

    # ── Always-require-approval tools ───────────────────────────────────────

    def test_blocks_apply_migration(self):
        result = check_mcp_safety("mcp__supabase__apply_migration", {})
        assert not result.allowed
        assert result.requires_approval

    def test_blocks_deploy_edge_function(self):
        result = check_mcp_safety("mcp__supabase__deploy_edge_function", {})
        assert not result.allowed
        assert result.requires_approval

    def test_blocks_kubectl_delete(self):
        result = check_mcp_safety("mcp__kubernetes__kubectl_delete", {"resource": "pod/my-pod"})
        assert not result.allowed
        assert result.requires_approval

    def test_blocks_kubectl_apply(self):
        result = check_mcp_safety("mcp__kubernetes__kubectl_apply", {"manifest": "..."})
        assert not result.allowed
        assert result.requires_approval

    def test_blocks_terraform_destroy(self):
        result = check_mcp_safety("mcp__terraform__destroy", {})
        assert not result.allowed
        assert result.requires_approval

    # ── Supabase SQL: mutations need approval ────────────────────────────────

    def test_blocks_delete_sql(self):
        result = check_mcp_safety(
            "mcp__supabase__execute_sql",
            {"query": "DELETE FROM users WHERE id = 1"},
        )
        assert not result.allowed
        assert result.requires_approval

    def test_blocks_drop_table_sql(self):
        result = check_mcp_safety(
            "mcp__supabase__execute_sql",
            {"query": "DROP TABLE sessions"},
        )
        assert not result.allowed

    def test_blocks_truncate_sql(self):
        result = check_mcp_safety(
            "mcp__supabase__execute_sql",
            {"query": "TRUNCATE TABLE logs"},
        )
        assert not result.allowed

    def test_blocks_alter_table(self):
        result = check_mcp_safety(
            "mcp__supabase__execute_sql",
            {"query": "ALTER TABLE users ADD COLUMN phone TEXT"},
        )
        assert not result.allowed
        assert result.requires_approval

    def test_blocks_update_without_where(self):
        result = check_mcp_safety(
            "mcp__supabase__execute_sql",
            {"query": "UPDATE users SET verified = false"},
        )
        assert not result.allowed

    def test_blocks_delete_without_where(self):
        result = check_mcp_safety(
            "mcp__supabase__execute_sql",
            {"query": "DELETE FROM sessions;"},
        )
        assert not result.allowed

    def test_allows_select_query(self):
        result = check_mcp_safety(
            "mcp__supabase__execute_sql",
            {"query": "SELECT * FROM users LIMIT 10"},
        )
        assert result.allowed

    def test_allows_select_with_join(self):
        result = check_mcp_safety(
            "mcp__supabase__execute_sql",
            {"query": "SELECT u.id, p.name FROM users u JOIN profiles p ON u.id = p.user_id"},
        )
        assert result.allowed

    # ── SQL Injection ────────────────────────────────────────────────────────

    def test_blocks_sql_injection_or_1_eq_1(self):
        result = check_mcp_safety(
            "mcp__supabase__execute_sql",
            {"query": "SELECT * FROM users WHERE id = '1' OR '1'='1'"},
        )
        assert not result.allowed

    def test_blocks_sql_injection_union_select(self):
        result = check_mcp_safety(
            "mcp__supabase__execute_sql",
            {"query": "SELECT id FROM users UNION SELECT password FROM admin"},
        )
        assert not result.allowed

    def test_blocks_sql_injection_semicolon_drop(self):
        result = check_mcp_safety(
            "mcp__supabase__execute_sql",
            {"query": "SELECT 1; DROP TABLE users"},
        )
        assert not result.allowed

    # ── Communication tools ──────────────────────────────────────────────────

    def test_blocks_send_email_mcp(self):
        result = check_mcp_safety("mcp__sendgrid__send_email", {"to": "user@example.com"})
        assert not result.allowed
        assert result.requires_approval

    def test_blocks_send_message(self):
        result = check_mcp_safety("mcp__slack__send_message", {"text": "hello"})
        assert not result.allowed
        assert result.requires_approval

    # ── Safe MCP operations ──────────────────────────────────────────────────

    def test_allows_list_tables(self):
        result = check_mcp_safety("mcp__supabase__list_tables", {})
        assert result.allowed

    def test_allows_search_docs(self):
        result = check_mcp_safety("mcp__supabase__search_docs", {"query": "auth"})
        assert result.allowed

    def test_allows_tavily_search(self):
        result = check_mcp_safety("mcp__tavily-mcp__tavily_search", {"query": "python async"})
        assert result.allowed

    def test_allows_get_project_url(self):
        result = check_mcp_safety("mcp__supabase__get_project_url", {})
        assert result.allowed

    def test_allows_update_with_where(self):
        """UPDATE with WHERE clause must NOT be blocked (regression for lookahead regex bug)."""
        result = check_mcp_safety(
            "mcp__supabase__execute_sql",
            {"query": "UPDATE users SET name='Alice' WHERE id=1"},
        )
        # Should require approval (it's a mutation) but not be outright denied as dangerous
        # The important thing: it should NOT be blocked as "UPDATE without WHERE"
        assert result.allowed or result.requires_approval

    def test_blocks_update_without_where_regression(self):
        """UPDATE without WHERE must still be caught after regex fix."""
        result = check_mcp_safety(
            "mcp__supabase__execute_sql",
            {"query": "UPDATE users SET verified = false"},
        )
        assert not result.allowed
