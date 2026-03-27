"""
Tests for Safety Layer 7: Rate Limiting + Budget + Scope
"""

import pytest

from pocketteam.constants import AGENT_BUDGETS, AGENT_MAX_TURNS
from pocketteam.safety.rate_limiter import RateLimiter


class TestRateLimiter:
    """Layer 7: Rate limits, budget, scope enforcement."""

    def setup_method(self):
        self.limiter = RateLimiter(task_id="test-task-001")

    # ── Turn limits ───────────────────────────────────────────────────────────

    def test_allows_within_turn_limit(self):
        result = self.limiter.check_turn_limit("engineer")
        assert result.allowed

    def test_blocks_after_max_turns(self):
        max_turns = AGENT_MAX_TURNS["engineer"]
        for _ in range(max_turns):
            self.limiter.record_turn("engineer")

        result = self.limiter.check_turn_limit("engineer")
        assert not result.allowed
        assert "turn limit" in result.reason.lower()

    def test_turn_counter_increments(self):
        self.limiter.record_turn("engineer")
        self.limiter.record_turn("engineer")
        result = self.limiter.check_turn_limit("engineer")
        assert result.current_turns == 2

    def test_different_agents_have_separate_counters(self):
        max_turns = AGENT_MAX_TURNS["monitor"]
        for _ in range(max_turns):
            self.limiter.record_turn("monitor")

        # Monitor is blocked
        assert not self.limiter.check_turn_limit("monitor").allowed
        # Engineer is not affected
        assert self.limiter.check_turn_limit("engineer").allowed

    def test_haiku_agents_have_lower_limits(self):
        monitor_max = AGENT_MAX_TURNS["monitor"]
        engineer_max = AGENT_MAX_TURNS["engineer"]
        assert monitor_max < engineer_max

    # ── Budget limits ─────────────────────────────────────────────────────────

    def test_allows_within_budget(self):
        result = self.limiter.check_budget("engineer")
        assert result.allowed

    def test_blocks_after_budget_exceeded(self):
        max_budget = AGENT_BUDGETS["engineer"]
        self.limiter.record_spend("engineer", max_budget + 0.01)

        result = self.limiter.check_budget("engineer")
        assert not result.allowed
        assert "budget" in result.reason.lower()

    def test_budget_accumulates(self):
        self.limiter.record_spend("engineer", 1.0)
        self.limiter.record_spend("engineer", 2.0)
        result = self.limiter.check_budget("engineer")
        assert result.current_spend == pytest.approx(3.0)

    def test_monitor_has_lower_budget_than_engineer(self):
        assert AGENT_BUDGETS["monitor"] < AGENT_BUDGETS["engineer"]

    # ── Scope enforcement ─────────────────────────────────────────────────────

    def test_allows_when_no_scope_set(self):
        """Before a plan is approved, scope is unconstrained."""
        result = self.limiter.check_scope("engineer", "src/auth.py")
        assert result.allowed

    def test_allows_file_in_scope(self):
        self.limiter.set_approved_files("engineer", ["src/auth.py", "tests/test_auth.py"])
        result = self.limiter.check_scope("engineer", "src/auth.py")
        assert result.allowed

    def test_blocks_file_not_in_scope(self):
        self.limiter.set_approved_files("engineer", ["src/auth.py"])
        result = self.limiter.check_scope("engineer", "src/billing.py")
        assert not result.allowed
        assert "not in the approved plan" in result.reason

    def test_allows_file_under_approved_directory(self):
        self.limiter.set_approved_files("engineer", ["src/"])
        result = self.limiter.check_scope("engineer", "src/auth/oauth.py")
        assert result.allowed

    def test_can_add_file_to_scope(self):
        self.limiter.set_approved_files("engineer", ["src/auth.py"])
        self.limiter.add_approved_file("engineer", "src/utils.py")
        result = self.limiter.check_scope("engineer", "src/utils.py")
        assert result.allowed

    # ── Usage summary ─────────────────────────────────────────────────────────

    def test_usage_summary(self):
        self.limiter.record_turn("engineer")
        self.limiter.record_spend("engineer", 0.5)
        summary = self.limiter.get_usage_summary()
        assert "engineer" in summary
        assert summary["engineer"]["turns"] == 1
        assert summary["engineer"]["spend_usd"] == pytest.approx(0.5)

    def test_total_spend(self):
        self.limiter.record_spend("engineer", 1.0)
        self.limiter.record_spend("reviewer", 0.5)
        assert self.limiter.get_total_spend() == pytest.approx(1.5)
