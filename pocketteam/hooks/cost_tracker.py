"""Cost tracker — records per-agent cost data to JSONL files."""

import json
from datetime import UTC, datetime
from pathlib import Path

from ._utils import _find_pocketteam_dir


def record_agent_cost(agent_type: str, cost_usd: float, usage: dict) -> None:
    """Append per-agent cost record to .pocketteam/costs/YYYY-MM-DD.jsonl"""
    try:
        pt_dir = _find_pocketteam_dir()
        if not pt_dir:
            return

        costs_dir = pt_dir / "costs"
        costs_dir.mkdir(parents=True, exist_ok=True)

        today = datetime.now(UTC).strftime("%Y-%m-%d")
        cost_file = costs_dir / f"{today}.jsonl"

        record = {
            "ts": datetime.now(UTC).isoformat(),
            "agent": agent_type,
            "cost_usd": cost_usd or 0.0,
            "input_tokens": usage.get("input_tokens", 0) if usage else 0,
            "output_tokens": usage.get("output_tokens", 0) if usage else 0,
            "cache_read_tokens": usage.get("cache_read_input_tokens", 0) if usage else 0,
        }

        with open(cost_file, "a") as f:
            f.write(json.dumps(record) + "\n")
    except Exception:
        pass  # Cost tracking is best-effort
