"""
Budget tracker — monitors API spend across all agents in a task.
Warns CEO when API costs accrue (subscription mode is $0 marginal cost).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..constants import DEFAULT_BUDGET_USD


@dataclass
class BudgetEntry:
    agent_id: str
    amount_usd: float
    reason: str
    ts: str


@dataclass
class TaskBudget:
    task_id: str
    max_usd: float = DEFAULT_BUDGET_USD
    entries: list[BudgetEntry] = field(default_factory=list)

    @property
    def total_usd(self) -> float:
        return sum(e.amount_usd for e in self.entries)

    @property
    def remaining_usd(self) -> float:
        return max(0.0, self.max_usd - self.total_usd)

    @property
    def is_over_budget(self) -> bool:
        return self.total_usd >= self.max_usd

    def by_agent(self) -> dict[str, float]:
        result: dict[str, float] = {}
        for e in self.entries:
            result[e.agent_id] = result.get(e.agent_id, 0.0) + e.amount_usd
        return result


class BudgetTracker:
    """Tracks API spend per task. Zero-cost in subscription mode."""

    def __init__(
        self,
        project_root: Path,
        task_id: str,
        max_usd: float = DEFAULT_BUDGET_USD,
        subscription_mode: bool = True,
    ) -> None:
        self.project_root = project_root
        self.task_id = task_id
        self.subscription_mode = subscription_mode
        self._budget = TaskBudget(task_id=task_id, max_usd=max_usd)
        self._path = project_root / f".pocketteam/artifacts/budget_{task_id}.json"

    def record(self, agent_id: str, amount_usd: float, reason: str = "") -> bool:
        """
        Record spend. Returns False if budget exceeded.
        In subscription mode: always returns True (no API cost).
        """
        if self.subscription_mode:
            return True  # Subscription = $0 marginal cost

        from datetime import datetime
        self._budget.entries.append(BudgetEntry(
            agent_id=agent_id,
            amount_usd=amount_usd,
            reason=reason,
            ts=datetime.now().isoformat(),
        ))
        self._persist()
        return not self._budget.is_over_budget

    def check(self, agent_id: Optional[str] = None) -> tuple[bool, str]:
        """
        Check if budget is available.
        Returns (ok, reason).
        """
        if self.subscription_mode:
            return True, ""

        if self._budget.is_over_budget:
            return False, (
                f"Budget exceeded: ${self._budget.total_usd:.2f} / "
                f"${self._budget.max_usd:.2f}"
            )
        return True, ""

    def summary(self) -> dict:
        return {
            "task_id": self.task_id,
            "mode": "subscription" if self.subscription_mode else "api_key",
            "total_usd": round(self._budget.total_usd, 4),
            "max_usd": self._budget.max_usd,
            "remaining_usd": round(self._budget.remaining_usd, 4),
            "by_agent": {k: round(v, 4) for k, v in self._budget.by_agent().items()},
        }

    def _persist(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(self.summary(), indent=2))
        except Exception:
            pass
