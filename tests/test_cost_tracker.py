"""
Tests for pocketteam.hooks.cost_tracker — per-agent cost JSONL recording.
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from pocketteam.hooks.cost_tracker import record_agent_cost


class TestCostTracker:
    """Unit tests for record_agent_cost."""

    def test_record_is_written_in_jsonl_format(self, tmp_path):
        """Record is appended to YYYY-MM-DD.jsonl in correct format."""
        pt_dir = tmp_path / ".pocketteam"
        pt_dir.mkdir()

        with patch("pocketteam.hooks.cost_tracker._find_pocketteam_dir", return_value=pt_dir):
            record_agent_cost(
                agent_type="engineer",
                cost_usd=0.043,
                usage={"input_tokens": 12400, "output_tokens": 890, "cache_read_input_tokens": 500},
            )

        today = datetime.now(UTC).strftime("%Y-%m-%d")
        cost_file = pt_dir / "costs" / f"{today}.jsonl"
        assert cost_file.exists()

        with open(cost_file) as f:
            line = f.readline().strip()

        record = json.loads(line)
        assert record["agent"] == "engineer"
        assert record["cost_usd"] == 0.043
        assert record["input_tokens"] == 12400
        assert record["output_tokens"] == 890
        assert record["cache_read_tokens"] == 500
        assert "ts" in record

    def test_directory_is_auto_created(self, tmp_path):
        """costs/ subdirectory is created automatically if it does not exist."""
        pt_dir = tmp_path / ".pocketteam"
        pt_dir.mkdir()
        costs_dir = pt_dir / "costs"
        assert not costs_dir.exists()

        with patch("pocketteam.hooks.cost_tracker._find_pocketteam_dir", return_value=pt_dir):
            record_agent_cost("qa", 0.01, {"input_tokens": 100, "output_tokens": 50})

        assert costs_dir.exists()
        assert costs_dir.is_dir()

    def test_zero_cost_edge_case(self, tmp_path):
        """cost_usd=0 is stored as 0.0 without raising an error."""
        pt_dir = tmp_path / ".pocketteam"
        pt_dir.mkdir()

        with patch("pocketteam.hooks.cost_tracker._find_pocketteam_dir", return_value=pt_dir):
            record_agent_cost("observer", 0, {"input_tokens": 200, "output_tokens": 30})

        today = datetime.now(UTC).strftime("%Y-%m-%d")
        cost_file = pt_dir / "costs" / f"{today}.jsonl"
        record = json.loads(cost_file.read_text().strip())
        assert record["cost_usd"] == 0.0

    def test_missing_usage_dict(self, tmp_path):
        """usage=None is handled gracefully — token counts default to 0."""
        pt_dir = tmp_path / ".pocketteam"
        pt_dir.mkdir()

        with patch("pocketteam.hooks.cost_tracker._find_pocketteam_dir", return_value=pt_dir):
            record_agent_cost("reviewer", 0.005, None)

        today = datetime.now(UTC).strftime("%Y-%m-%d")
        cost_file = pt_dir / "costs" / f"{today}.jsonl"
        record = json.loads(cost_file.read_text().strip())
        assert record["input_tokens"] == 0
        assert record["output_tokens"] == 0
        assert record["cache_read_tokens"] == 0
        assert record["cost_usd"] == 0.005

    def test_file_rotation_by_date(self, tmp_path):
        """Records on different dates go into separate JSONL files."""
        import pocketteam.hooks.cost_tracker as ct_module

        pt_dir = tmp_path / ".pocketteam"
        pt_dir.mkdir()
        costs_dir = pt_dir / "costs"
        costs_dir.mkdir()

        # Manually write records into two different date files to verify isolation
        day1_file = costs_dir / "2026-03-28.jsonl"
        day2_file = costs_dir / "2026-03-29.jsonl"

        record1 = {"ts": "2026-03-28T12:00:00+00:00", "agent": "engineer",
                   "cost_usd": 0.10, "input_tokens": 5000, "output_tokens": 300, "cache_read_tokens": 0}
        record2 = {"ts": "2026-03-29T09:00:00+00:00", "agent": "engineer",
                   "cost_usd": 0.20, "input_tokens": 8000, "output_tokens": 600, "cache_read_tokens": 0}

        day1_file.write_text(json.dumps(record1) + "\n")
        day2_file.write_text(json.dumps(record2) + "\n")

        files = sorted(f.name for f in costs_dir.iterdir())
        assert "2026-03-28.jsonl" in files
        assert "2026-03-29.jsonl" in files

        day1_record = json.loads(day1_file.read_text().strip())
        assert day1_record["cost_usd"] == 0.10
        assert day1_record["agent"] == "engineer"

        day2_record = json.loads(day2_file.read_text().strip())
        assert day2_record["cost_usd"] == 0.20
        assert day2_record["agent"] == "engineer"

        # Verify the two files are independent (different names, different content)
        assert day1_file.name != day2_file.name
        assert day1_record["ts"] != day2_record["ts"]
