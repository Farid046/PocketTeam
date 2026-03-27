"""
Phase-1 Regression Tests

Covers edge cases and regressions:
- mcp_rules: None query input does not crash or allow dangerous ops
- guardian: malformed JSON input results in allow=False
- network_rules: mcp__tavily tool name is correctly recognized
- rate_limiter: denies after N turns
"""

import json
import subprocess
import sys

from pocketteam.constants import AGENT_MAX_TURNS
from pocketteam.safety.mcp_rules import check_mcp_safety
from pocketteam.safety.network_rules import check_network_safety, extract_url_from_tool_input
from pocketteam.safety.rate_limiter import RateLimiter


class TestMcpRulesNoneQuery:
    """Regression: None in query field must not crash and must behave safely."""

    def test_none_query_does_not_crash(self):
        """check_mcp_safety must not raise when query is None."""
        result = check_mcp_safety("mcp__supabase__execute_sql", {"query": None})
        # Should return a result, not raise
        assert hasattr(result, "allowed")

    def test_none_query_is_not_passed_as_sql(self):
        """A None query should not be treated as dangerous SQL — it resolves to empty."""
        result = check_mcp_safety("mcp__supabase__execute_sql", {"query": None})
        # Empty/None sql → no mutation detected → allowed
        assert result.allowed

    def test_none_sql_field_does_not_crash(self):
        result = check_mcp_safety("mcp__supabase__execute_sql", {"sql": None})
        assert hasattr(result, "allowed")

    def test_empty_dict_input_does_not_crash(self):
        result = check_mcp_safety("mcp__supabase__execute_sql", {})
        assert result.allowed

    def test_none_input_entirely_does_not_crash(self):
        """tool_input=None falls back to string conversion, must not raise."""
        result = check_mcp_safety("mcp__supabase__list_tables", None)
        assert hasattr(result, "allowed")


class TestGuardianMalformedInput:
    """Regression: malformed JSON on guardian stdin must result in allow=False."""

    def _run_guardian(self, stdin_text: str) -> dict:
        """Run the guardian pre-tool-use hook via subprocess."""
        proc = subprocess.run(
            [sys.executable, "-m", "pocketteam.safety", "pre"],
            input=stdin_text,
            capture_output=True,
            text=True,
        )
        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError:
            # If stdout is empty, check stderr for error indication
            return {"allow": False, "reason": "guardian_error", "_stderr": proc.stderr}

    def test_malformed_json_results_in_deny(self):
        """Malformed JSON must never produce allow=True."""
        result = self._run_guardian("not valid json {{{")
        assert result.get("allow") is not True

    def test_empty_stdin_results_in_deny(self):
        """Empty stdin must not crash the guardian and must not allow."""
        result = self._run_guardian("")
        assert result.get("allow") is not True

    def test_truncated_json_results_in_deny(self):
        result = self._run_guardian('{"tool_name": "Bash", "tool_input":')
        assert result.get("allow") is not True


class TestNetworkRulesTavilyRecognition:
    """Regression: mcp__tavily tool name format is handled correctly."""

    def test_tavily_search_url_in_approved_domains(self):
        """api.tavily.com is in the approved domain list."""
        result = check_network_safety("https://api.tavily.com/search")
        assert result.allowed

    def test_mcp_tavily_tool_name_extract_url_string(self):
        """extract_url_from_tool_input recognizes mcp__tavily prefixed tool names."""
        url = extract_url_from_tool_input(
            "mcp__tavily__search",
            "https://api.tavily.com/search query=python",
        )
        assert url == "https://api.tavily.com/search"

    def test_mcp_tavily_search_allowed_for_approved_url(self):
        result = check_network_safety("https://api.tavily.com/v1/search")
        assert result.allowed

    def test_mcp_tavily_exfiltration_url_blocked(self):
        """Even if tool name is tavily, exfiltration domain must be blocked."""
        result = check_network_safety("https://requestbin.com/collect?data=secret")
        assert not result.allowed


class TestRateLimiterDeniesAfterNTurns:
    """Regression: rate limiter denies once per-agent turn limit is reached."""

    def test_allows_before_limit(self):
        rl = RateLimiter(task_id="test-task-1")
        result = rl.check_turn_limit("engineer")
        assert result.allowed

    def test_denies_at_limit(self):
        rl = RateLimiter(task_id="test-task-2")
        max_turns = AGENT_MAX_TURNS.get("engineer", 50)
        # Exhaust all turns
        for _ in range(max_turns):
            rl.record_turn("engineer")
        result = rl.check_turn_limit("engineer")
        assert not result.allowed
        assert result.current_turns == max_turns

    def test_denies_beyond_limit(self):
        rl = RateLimiter(task_id="test-task-3")
        max_turns = AGENT_MAX_TURNS.get("engineer", 50)
        for _ in range(max_turns + 10):
            rl.record_turn("engineer")
        result = rl.check_turn_limit("engineer")
        assert not result.allowed

    def test_different_agents_have_independent_counters(self):
        rl = RateLimiter(task_id="test-task-4")
        engineer_max = AGENT_MAX_TURNS.get("engineer", 50)
        # Exhaust engineer turns
        for _ in range(engineer_max):
            rl.record_turn("engineer")
        # QA agent should still be allowed
        result = rl.check_turn_limit("qa")
        assert result.allowed

    def test_turn_count_increments(self):
        rl = RateLimiter(task_id="test-task-5")
        for i in range(5):
            rl.record_turn("planner")
        result = rl.check_turn_limit("planner")
        assert result.current_turns == 5

    def test_rate_limit_result_has_layer_7(self):
        rl = RateLimiter(task_id="test-task-6")
        result = rl.check_turn_limit("engineer")
        assert result.layer == 7
