"""
Safety Layer 7: Rate Limiting + Budget + Scope Enforcement
- Max turns per agent per task
- Max spend per agent per task (USD)
- Scope enforcement: agents may only touch files in the approved plan
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..constants import AGENT_BUDGETS, AGENT_MAX_TURNS, DEFAULT_BUDGET_USD


@dataclass
class RateLimitResult:
    allowed: bool
    layer: int = 7
    reason: str = ""
    current_turns: int = 0
    max_turns: int = 0
    current_spend: float = 0.0
    max_spend: float = 0.0


@dataclass
class AgentUsage:
    """Tracks usage for a single agent in a single task."""
    agent_id: str
    task_id: str
    turns: int = 0
    spend_usd: float = 0.0
    start_time: float = field(default_factory=time.time)
    approved_files: set[str] = field(default_factory=set)  # Files in approved plan


class RateLimiter:
    """
    Layer 7: Per-agent rate limits and budget enforcement.
    Instance is created per task run.
    """

    def __init__(self, task_id: str) -> None:
        self.task_id = task_id
        self._usage: dict[str, AgentUsage] = {}

    def _get_or_create(self, agent_id: str) -> AgentUsage:
        if agent_id not in self._usage:
            self._usage[agent_id] = AgentUsage(
                agent_id=agent_id,
                task_id=self.task_id,
            )
        return self._usage[agent_id]

    def check_turn_limit(self, agent_id: str) -> RateLimitResult:
        """Check if agent has exceeded its turn limit."""
        usage = self._get_or_create(agent_id)
        max_turns = AGENT_MAX_TURNS.get(agent_id, AGENT_MAX_TURNS.get("engineer", 50))

        if usage.turns >= max_turns:
            return RateLimitResult(
                allowed=False,
                reason=(
                    f"Agent '{agent_id}' has reached its turn limit ({max_turns} turns). "
                    "Escalating to CEO."
                ),
                current_turns=usage.turns,
                max_turns=max_turns,
            )
        return RateLimitResult(
            allowed=True,
            current_turns=usage.turns,
            max_turns=max_turns,
        )

    def check_budget(self, agent_id: str) -> RateLimitResult:
        """Check if agent has exceeded its budget."""
        usage = self._get_or_create(agent_id)
        max_budget = AGENT_BUDGETS.get(agent_id, DEFAULT_BUDGET_USD)

        if usage.spend_usd >= max_budget:
            return RateLimitResult(
                allowed=False,
                reason=(
                    f"Agent '{agent_id}' has reached its budget limit "
                    f"(${max_budget:.2f} USD). Escalating to CEO."
                ),
                current_spend=usage.spend_usd,
                max_spend=max_budget,
            )
        return RateLimitResult(
            allowed=True,
            current_spend=usage.spend_usd,
            max_spend=max_budget,
        )

    def check_scope(self, agent_id: str, file_path: str) -> RateLimitResult:
        """
        Check if an agent is trying to modify a file not in the approved plan.
        Only enforced for write operations (Write, Edit).
        """
        usage = self._get_or_create(agent_id)

        # If no approved files set yet, scope is unconstrained (pre-plan phase)
        if not usage.approved_files:
            return RateLimitResult(allowed=True, reason="No scope restriction set")

        # Normalize path
        normalized = str(Path(file_path).resolve()) if file_path else ""

        # Check against approved files
        for approved in usage.approved_files:
            approved_norm = str(Path(approved).resolve())
            if normalized == approved_norm or normalized.startswith(approved_norm + "/"):
                return RateLimitResult(allowed=True)

        return RateLimitResult(
            allowed=False,
            reason=(
                f"File '{file_path}' is not in the approved plan scope for agent '{agent_id}'. "
                "Modify the plan to include this file, or get CEO approval."
            ),
        )

    def record_turn(self, agent_id: str) -> None:
        """Record one turn of agent activity."""
        usage = self._get_or_create(agent_id)
        usage.turns += 1

    def record_spend(self, agent_id: str, amount_usd: float) -> None:
        """Record API spend for an agent."""
        usage = self._get_or_create(agent_id)
        usage.spend_usd += amount_usd

    def set_approved_files(self, agent_id: str, files: list[str]) -> None:
        """Set the files an agent is allowed to modify (from approved plan)."""
        usage = self._get_or_create(agent_id)
        usage.approved_files = set(files)

    def add_approved_file(self, agent_id: str, file_path: str) -> None:
        """Add a file to an agent's scope."""
        usage = self._get_or_create(agent_id)
        usage.approved_files.add(file_path)

    def get_usage_summary(self) -> dict[str, dict]:
        """Return usage summary for all agents in this task."""
        return {
            agent_id: {
                "turns": usage.turns,
                "spend_usd": round(usage.spend_usd, 4),
                "max_turns": AGENT_MAX_TURNS.get(agent_id, 50),
                "max_budget": AGENT_BUDGETS.get(agent_id, DEFAULT_BUDGET_USD),
                "runtime_seconds": round(time.time() - usage.start_time, 1),
            }
            for agent_id, usage in self._usage.items()
        }

    def get_total_spend(self) -> float:
        """Total spend across all agents in this task."""
        return sum(u.spend_usd for u in self._usage.values())
