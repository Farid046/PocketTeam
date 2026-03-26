"""
Tests for Phase 6 CLI additions:
  - pocketteam health
  - pocketteam logs --since
  - _parse_since helper
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from click.testing import CliRunner

from pocketteam.cli import _parse_since, main


# ─────────────────────────────────────────────────────────────────────────────
# _parse_since unit tests
# ─────────────────────────────────────────────────────────────────────────────


class TestParseSince:
    def test_minutes(self):
        before = datetime.now(tz=timezone.utc)
        result = _parse_since("30m")
        after = datetime.now(tz=timezone.utc)
        assert result is not None
        expected_approx = before - timedelta(minutes=30)
        assert abs((result - expected_approx).total_seconds()) < 2

    def test_hours(self):
        before = datetime.now(tz=timezone.utc)
        result = _parse_since("2h")
        assert result is not None
        expected_approx = before - timedelta(hours=2)
        assert abs((result - expected_approx).total_seconds()) < 2

    def test_days(self):
        before = datetime.now(tz=timezone.utc)
        result = _parse_since("3d")
        assert result is not None
        expected_approx = before - timedelta(days=3)
        assert abs((result - expected_approx).total_seconds()) < 2

    def test_single_minute(self):
        result = _parse_since("1m")
        assert result is not None

    def test_invalid_unit(self):
        assert _parse_since("5w") is None

    def test_invalid_no_unit(self):
        assert _parse_since("60") is None

    def test_invalid_empty(self):
        assert _parse_since("") is None

    def test_invalid_text(self):
        assert _parse_since("yesterday") is None

    def test_whitespace_stripped(self):
        result = _parse_since("  1h  ")
        assert result is not None


# ─────────────────────────────────────────────────────────────────────────────
# pocketteam health tests
# ─────────────────────────────────────────────────────────────────────────────


class TestHealthCommand:
    def test_health_no_pocketteam_dir(self, tmp_path, monkeypatch):
        """Health exits gracefully when .pocketteam/ does not exist."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(main, ["health"])
        assert result.exit_code == 0
        assert "FAIL" in result.output
        assert ".pocketteam/ not found" in result.output

    def test_health_with_pocketteam_dir_no_config(self, tmp_path, monkeypatch):
        """Health shows WARN for missing config.yaml when .pocketteam/ exists."""
        (tmp_path / ".pocketteam").mkdir()
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(main, ["health"])
        assert result.exit_code == 0
        assert "OK" in result.output  # project found
        assert "config.yaml missing" in result.output

    def test_health_with_valid_config(self, tmp_path, monkeypatch):
        """Health shows OK for project and config when both are valid."""
        pt_dir = tmp_path / ".pocketteam"
        pt_dir.mkdir()
        config = pt_dir / "config.yaml"
        config.write_text("project:\n  name: test-proj\n  health_url: ''\n")
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(main, ["health"])
        assert result.exit_code == 0
        assert "config.yaml valid" in result.output

    def test_health_kill_switch_active(self, tmp_path, monkeypatch):
        """Health shows ACTIVE when kill switch file exists."""
        pt_dir = tmp_path / ".pocketteam"
        pt_dir.mkdir()
        (pt_dir / "KILL").touch()
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(main, ["health"])
        assert result.exit_code == 0
        assert "ACTIVE" in result.output

    def test_health_kill_switch_inactive(self, tmp_path, monkeypatch):
        """Health shows inactive (OK) when no kill switch file."""
        pt_dir = tmp_path / ".pocketteam"
        pt_dir.mkdir()
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(main, ["health"])
        assert result.exit_code == 0
        assert "inactive" in result.output

    def test_health_last_event_shown(self, tmp_path, monkeypatch):
        """Health reads last event from stream and displays it."""
        pt_dir = tmp_path / ".pocketteam"
        (pt_dir / "events").mkdir(parents=True)
        ts = datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")
        event = {"ts": ts, "agent": "engineer", "action": "Edit on src/main.py"}
        (pt_dir / "events" / "stream.jsonl").write_text(json.dumps(event) + "\n")
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(main, ["health"])
        assert result.exit_code == 0
        assert "engineer" in result.output

    def test_health_no_events_yet(self, tmp_path, monkeypatch):
        """Health shows WARN when event stream does not exist."""
        (tmp_path / ".pocketteam").mkdir()
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(main, ["health"])
        assert result.exit_code == 0
        assert "no events yet" in result.output

    def test_health_dashboard_not_configured(self, tmp_path, monkeypatch):
        """Health shows WARN when health_url is not configured."""
        pt_dir = tmp_path / ".pocketteam"
        pt_dir.mkdir()
        config = pt_dir / "config.yaml"
        config.write_text("project:\n  name: test\n  health_url: ''\n")
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(main, ["health"])
        assert result.exit_code == 0
        assert "not configured" in result.output


# ─────────────────────────────────────────────────────────────────────────────
# pocketteam logs --since tests
# ─────────────────────────────────────────────────────────────────────────────


class TestLogsCommand:
    def _make_event_stream(self, tmp_path: Path, events: list[dict]) -> Path:
        """Write a JSONL event stream and return the stream file path."""
        pt_dir = tmp_path / ".pocketteam" / "events"
        pt_dir.mkdir(parents=True)
        stream = pt_dir / "stream.jsonl"
        stream.write_text("\n".join(json.dumps(e) for e in events) + "\n")
        return stream

    def test_logs_no_events(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(main, ["logs"])
        assert result.exit_code == 0
        assert "No events logged yet" in result.output

    def test_logs_since_filters_old_events(self, tmp_path, monkeypatch):
        """Events older than --since cutoff are not shown."""
        now = datetime.now(tz=timezone.utc)
        old_ts = (now - timedelta(hours=3)).isoformat().replace("+00:00", "Z")
        new_ts = (now - timedelta(minutes=10)).isoformat().replace("+00:00", "Z")
        events = [
            {"ts": old_ts, "agent": "coo", "action": "old event"},
            {"ts": new_ts, "agent": "engineer", "action": "recent event"},
        ]
        self._make_event_stream(tmp_path, events)
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(main, ["logs", "--since", "1h"])
        assert result.exit_code == 0
        assert "recent event" in result.output
        assert "old event" not in result.output

    def test_logs_since_includes_all_recent(self, tmp_path, monkeypatch):
        """--since 24h includes events from the past day."""
        now = datetime.now(tz=timezone.utc)
        events = [
            {
                "ts": (now - timedelta(hours=h)).isoformat().replace("+00:00", "Z"),
                "agent": "qa",
                "action": f"event-{h}h-ago",
            }
            for h in [1, 5, 12, 23]
        ]
        self._make_event_stream(tmp_path, events)
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(main, ["logs", "--since", "24h"])
        assert result.exit_code == 0
        for h in [1, 5, 12, 23]:
            assert f"event-{h}h-ago" in result.output

    def test_logs_since_invalid_value_exits_nonzero(self, tmp_path, monkeypatch):
        """--since with invalid format exits with code 1."""
        pt_dir = tmp_path / ".pocketteam" / "events"
        pt_dir.mkdir(parents=True)
        (pt_dir / "stream.jsonl").write_text(
            json.dumps({"agent": "coo", "action": "x"}) + "\n"
        )
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(main, ["logs", "--since", "yesterday"])
        assert result.exit_code == 1
        assert "Invalid --since value" in result.output

    def test_logs_since_30m(self, tmp_path, monkeypatch):
        """--since 30m shows only events from last 30 minutes."""
        now = datetime.now(tz=timezone.utc)
        events = [
            {
                "ts": (now - timedelta(minutes=15)).isoformat().replace("+00:00", "Z"),
                "agent": "planner",
                "action": "fresh",
            },
            {
                "ts": (now - timedelta(hours=2)).isoformat().replace("+00:00", "Z"),
                "agent": "planner",
                "action": "stale",
            },
        ]
        self._make_event_stream(tmp_path, events)
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(main, ["logs", "--since", "30m"])
        assert result.exit_code == 0
        assert "fresh" in result.output
        assert "stale" not in result.output

    def test_logs_agent_filter_combined_with_since(self, tmp_path, monkeypatch):
        """--agent and --since can be combined."""
        now = datetime.now(tz=timezone.utc)
        recent = (now - timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
        events = [
            {"ts": recent, "agent": "qa", "action": "qa-recent"},
            {"ts": recent, "agent": "engineer", "action": "eng-recent"},
        ]
        self._make_event_stream(tmp_path, events)
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(main, ["logs", "--since", "1h", "--agent", "qa"])
        assert result.exit_code == 0
        assert "qa-recent" in result.output
        assert "eng-recent" not in result.output

    def test_logs_event_without_ts_passes_since_filter(self, tmp_path, monkeypatch):
        """Events with missing timestamps are always included (safe default)."""
        events = [{"agent": "monitor", "action": "no-timestamp"}]
        self._make_event_stream(tmp_path, events)
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(main, ["logs", "--since", "1h"])
        assert result.exit_code == 0
        assert "no-timestamp" in result.output
