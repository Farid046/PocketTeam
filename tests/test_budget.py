"""
Tests for pocketteam/core/budget.py — BudgetEntry, TaskBudget, BudgetTracker.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pocketteam.core.budget import BudgetEntry, BudgetTracker, TaskBudget
from pocketteam.constants import DEFAULT_BUDGET_USD


# ─────────────────────────────────────────────────────────────────────────────
# BudgetEntry
# ─────────────────────────────────────────────────────────────────────────────


class TestBudgetEntry:
    def test_fields_stored(self):
        entry = BudgetEntry(
            agent_id="engineer",
            amount_usd=1.25,
            reason="planner call",
            ts="2026-01-01T00:00:00",
        )
        assert entry.agent_id == "engineer"
        assert entry.amount_usd == 1.25
        assert entry.reason == "planner call"
        assert entry.ts == "2026-01-01T00:00:00"


# ─────────────────────────────────────────────────────────────────────────────
# TaskBudget
# ─────────────────────────────────────────────────────────────────────────────


class TestTaskBudget:
    def _make_budget(self, max_usd=10.0) -> TaskBudget:
        return TaskBudget(task_id="task-1", max_usd=max_usd)

    def test_default_max_is_default_constant(self):
        budget = TaskBudget(task_id="task-x")
        assert budget.max_usd == DEFAULT_BUDGET_USD

    def test_total_usd_zero_initially(self):
        budget = self._make_budget()
        assert budget.total_usd == 0.0

    def test_remaining_usd_equals_max_when_empty(self):
        budget = self._make_budget(max_usd=5.0)
        assert budget.remaining_usd == 5.0

    def test_total_usd_accumulates(self):
        budget = self._make_budget(max_usd=10.0)
        budget.entries.append(BudgetEntry("eng", 1.0, "", ""))
        budget.entries.append(BudgetEntry("qa", 2.5, "", ""))
        assert budget.total_usd == pytest.approx(3.5)

    def test_remaining_usd_decreases_with_spend(self):
        budget = self._make_budget(max_usd=10.0)
        budget.entries.append(BudgetEntry("eng", 3.0, "", ""))
        assert budget.remaining_usd == pytest.approx(7.0)

    def test_remaining_usd_never_negative(self):
        budget = self._make_budget(max_usd=2.0)
        budget.entries.append(BudgetEntry("eng", 5.0, "", ""))
        assert budget.remaining_usd == 0.0

    def test_is_over_budget_false_when_under(self):
        budget = self._make_budget(max_usd=10.0)
        budget.entries.append(BudgetEntry("eng", 4.99, "", ""))
        assert not budget.is_over_budget

    def test_is_over_budget_true_when_at_limit(self):
        budget = self._make_budget(max_usd=5.0)
        budget.entries.append(BudgetEntry("eng", 5.0, "", ""))
        assert budget.is_over_budget

    def test_is_over_budget_true_when_exceeded(self):
        budget = self._make_budget(max_usd=2.0)
        budget.entries.append(BudgetEntry("eng", 3.0, "", ""))
        assert budget.is_over_budget

    def test_by_agent_groups_per_agent(self):
        budget = self._make_budget()
        budget.entries.extend([
            BudgetEntry("engineer", 1.0, "", ""),
            BudgetEntry("qa", 0.5, "", ""),
            BudgetEntry("engineer", 2.0, "", ""),
        ])
        by_agent = budget.by_agent()
        assert by_agent["engineer"] == pytest.approx(3.0)
        assert by_agent["qa"] == pytest.approx(0.5)

    def test_by_agent_empty_when_no_entries(self):
        budget = self._make_budget()
        assert budget.by_agent() == {}


# ─────────────────────────────────────────────────────────────────────────────
# BudgetTracker — subscription mode (default)
# ─────────────────────────────────────────────────────────────────────────────


class TestBudgetTrackerSubscriptionMode:
    def _tracker(self, tmp_path: Path) -> BudgetTracker:
        return BudgetTracker(
            project_root=tmp_path,
            task_id="task-sub",
            max_usd=DEFAULT_BUDGET_USD,
            subscription_mode=True,
        )

    def test_record_always_returns_true(self, tmp_path):
        tracker = self._tracker(tmp_path)
        assert tracker.record("engineer", 999.0, "expensive") is True

    def test_record_does_not_persist_in_subscription_mode(self, tmp_path):
        tracker = self._tracker(tmp_path)
        tracker.record("engineer", 5.0, "call")
        budget_file = tmp_path / ".pocketteam/artifacts/budget_task-sub.json"
        assert not budget_file.exists()

    def test_check_always_ok_in_subscription_mode(self, tmp_path):
        tracker = self._tracker(tmp_path)
        ok, reason = tracker.check()
        assert ok is True
        assert reason == ""

    def test_check_with_agent_id_still_ok(self, tmp_path):
        tracker = self._tracker(tmp_path)
        ok, reason = tracker.check(agent_id="qa")
        assert ok is True

    def test_summary_shows_subscription_mode(self, tmp_path):
        tracker = self._tracker(tmp_path)
        s = tracker.summary()
        assert s["mode"] == "subscription"

    def test_summary_shows_zero_total_in_subscription_mode(self, tmp_path):
        tracker = self._tracker(tmp_path)
        tracker.record("eng", 10.0, "")
        s = tracker.summary()
        assert s["total_usd"] == 0.0

    def test_summary_keys_present(self, tmp_path):
        tracker = self._tracker(tmp_path)
        s = tracker.summary()
        assert set(s.keys()) == {
            "task_id", "mode", "total_usd", "max_usd", "remaining_usd", "by_agent"
        }

    def test_summary_task_id(self, tmp_path):
        tracker = self._tracker(tmp_path)
        assert tracker.summary()["task_id"] == "task-sub"


# ─────────────────────────────────────────────────────────────────────────────
# BudgetTracker — API key mode (metered)
# ─────────────────────────────────────────────────────────────────────────────


class TestBudgetTrackerApiKeyMode:
    def _tracker(self, tmp_path: Path, max_usd: float = 5.0) -> BudgetTracker:
        return BudgetTracker(
            project_root=tmp_path,
            task_id="task-api",
            max_usd=max_usd,
            subscription_mode=False,
        )

    def test_record_returns_true_while_under_budget(self, tmp_path):
        tracker = self._tracker(tmp_path, max_usd=5.0)
        result = tracker.record("engineer", 2.0, "test call")
        assert result is True

    def test_record_returns_false_when_budget_exceeded(self, tmp_path):
        tracker = self._tracker(tmp_path, max_usd=3.0)
        tracker.record("engineer", 2.0, "first")
        result = tracker.record("engineer", 2.0, "over budget")
        assert result is False

    def test_record_returns_false_exactly_at_limit(self, tmp_path):
        tracker = self._tracker(tmp_path, max_usd=2.0)
        result = tracker.record("engineer", 2.0, "exactly at limit")
        # total_usd == max_usd → is_over_budget → returns False
        assert result is False

    def test_check_ok_when_under_budget(self, tmp_path):
        tracker = self._tracker(tmp_path, max_usd=10.0)
        tracker.record("engineer", 1.0, "")
        ok, reason = tracker.check()
        assert ok is True
        assert reason == ""

    def test_check_fails_when_over_budget(self, tmp_path):
        tracker = self._tracker(tmp_path, max_usd=1.0)
        tracker.record("engineer", 2.0, "")
        ok, reason = tracker.check()
        assert ok is False
        assert "Budget exceeded" in reason
        assert "$" in reason

    def test_check_reason_includes_totals(self, tmp_path):
        tracker = self._tracker(tmp_path, max_usd=1.0)
        tracker.record("engineer", 2.0, "")
        _, reason = tracker.check()
        assert "2.00" in reason
        assert "1.00" in reason

    def test_entries_accumulate_across_records(self, tmp_path):
        tracker = self._tracker(tmp_path, max_usd=100.0)
        tracker.record("engineer", 1.0, "a")
        tracker.record("qa", 0.5, "b")
        tracker.record("engineer", 0.5, "c")
        s = tracker.summary()
        assert s["total_usd"] == pytest.approx(2.0)
        assert s["by_agent"]["engineer"] == pytest.approx(1.5)
        assert s["by_agent"]["qa"] == pytest.approx(0.5)

    def test_persists_json_to_disk(self, tmp_path):
        tracker = self._tracker(tmp_path, max_usd=10.0)
        tracker.record("engineer", 1.5, "persist test")
        budget_file = tmp_path / ".pocketteam/artifacts/budget_task-api.json"
        assert budget_file.exists()
        data = json.loads(budget_file.read_text())
        assert data["task_id"] == "task-api"
        assert data["total_usd"] == pytest.approx(1.5)

    def test_persisted_json_contains_by_agent(self, tmp_path):
        tracker = self._tracker(tmp_path, max_usd=10.0)
        tracker.record("qa", 0.75, "")
        budget_file = tmp_path / ".pocketteam/artifacts/budget_task-api.json"
        data = json.loads(budget_file.read_text())
        assert data["by_agent"]["qa"] == pytest.approx(0.75)

    def test_summary_mode_api_key(self, tmp_path):
        tracker = self._tracker(tmp_path)
        assert tracker.summary()["mode"] == "api_key"

    def test_summary_remaining_decreases_with_spend(self, tmp_path):
        tracker = self._tracker(tmp_path, max_usd=5.0)
        tracker.record("engineer", 2.0, "")
        s = tracker.summary()
        assert s["remaining_usd"] == pytest.approx(3.0)

    def test_summary_remaining_never_negative(self, tmp_path):
        tracker = self._tracker(tmp_path, max_usd=1.0)
        tracker.record("engineer", 5.0, "")
        s = tracker.summary()
        assert s["remaining_usd"] == 0.0

    def test_persist_creates_parent_dirs(self, tmp_path):
        tracker = self._tracker(tmp_path, max_usd=10.0)
        tracker.record("engineer", 1.0, "")
        assert (tmp_path / ".pocketteam" / "artifacts").is_dir()

    def test_persist_failure_does_not_raise(self, tmp_path, monkeypatch):
        """_persist swallows all exceptions silently."""
        tracker = self._tracker(tmp_path, max_usd=10.0)

        def broken_mkdir(*a, **kw):
            raise OSError("disk full")

        monkeypatch.setattr(Path, "mkdir", broken_mkdir)
        # Should not raise
        tracker._persist()

    def test_custom_max_usd(self, tmp_path):
        tracker = BudgetTracker(
            project_root=tmp_path,
            task_id="t",
            max_usd=42.0,
            subscription_mode=False,
        )
        assert tracker.summary()["max_usd"] == 42.0

    def test_default_max_usd_uses_constant(self, tmp_path):
        tracker = BudgetTracker(
            project_root=tmp_path,
            task_id="t",
            subscription_mode=False,
        )
        assert tracker.summary()["max_usd"] == DEFAULT_BUDGET_USD
