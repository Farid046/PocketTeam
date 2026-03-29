"""
Unit tests for context_warning.py — Feature 3: Context Awareness System.

Tests cover:
  1. Return {} when session-status.json does not exist
  2. Return {} when contextUsedPct < 70
  3. Return yellow warning when contextUsedPct = 75
  4. Return red/critical warning when contextUsedPct = 95
  5. Return {} when file is older than 60 seconds (stale)
  6. Return {} when file contains invalid JSON
  7. Debouncing: second call within the 5-call window returns {}
"""

from __future__ import annotations

import importlib
import json
import time
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_status(path: Path, pct: float) -> None:
    path.write_text(json.dumps({"contextUsedPct": pct, "updatedAt": "2026-03-29T00:00:00.000Z"}))


def _reset_module():
    """Re-import context_warning to reset its module-level call counter."""
    import pocketteam.hooks.context_warning as mod
    importlib.reload(mod)
    return mod


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestContextWarning:

    def test_returns_empty_when_file_missing(self, tmp_path, monkeypatch):
        """Return {} when session-status.json does not exist."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".pocketteam").mkdir()

        mod = _reset_module()
        result = mod.handle({})
        assert result == {}

    def test_returns_empty_below_threshold(self, tmp_path, monkeypatch):
        """Return {} when contextUsedPct is below 70."""
        monkeypatch.chdir(tmp_path)
        pt = tmp_path / ".pocketteam"
        pt.mkdir()
        _write_status(pt / "session-status.json", 50.0)

        mod = _reset_module()
        result = mod.handle({})
        assert result == {}

    def test_returns_yellow_warning_at_75(self, tmp_path, monkeypatch):
        """Return a warning message when contextUsedPct is 75 (>= 70, < 90)."""
        monkeypatch.chdir(tmp_path)
        pt = tmp_path / ".pocketteam"
        pt.mkdir()
        _write_status(pt / "session-status.json", 75.0)

        mod = _reset_module()
        result = mod.handle({})

        assert "additionalContext" in result
        assert "75" in result["additionalContext"]
        # Must contain guidance — not a critical message
        assert "compact" in result["additionalContext"].lower() or "subagent" in result["additionalContext"].lower()
        assert "CRITICAL" not in result["additionalContext"]

    def test_returns_critical_warning_at_95(self, tmp_path, monkeypatch):
        """Return a critical warning when contextUsedPct is 95 (>= 90)."""
        monkeypatch.chdir(tmp_path)
        pt = tmp_path / ".pocketteam"
        pt.mkdir()
        _write_status(pt / "session-status.json", 95.0)

        mod = _reset_module()
        result = mod.handle({})

        assert "additionalContext" in result
        assert "CRITICAL" in result["additionalContext"]
        assert "95" in result["additionalContext"]

    def test_returns_empty_for_stale_file(self, tmp_path, monkeypatch):
        """Return {} when session-status.json is older than 60 seconds."""
        monkeypatch.chdir(tmp_path)
        pt = tmp_path / ".pocketteam"
        pt.mkdir()
        status_file = pt / "session-status.json"
        _write_status(status_file, 80.0)

        # Back-date the file's mtime by 61 seconds
        old_mtime = time.time() - 61
        import os
        os.utime(status_file, (old_mtime, old_mtime))

        mod = _reset_module()
        result = mod.handle({})
        assert result == {}

    def test_returns_empty_for_invalid_json(self, tmp_path, monkeypatch):
        """Return {} when session-status.json contains invalid JSON."""
        monkeypatch.chdir(tmp_path)
        pt = tmp_path / ".pocketteam"
        pt.mkdir()
        (pt / "session-status.json").write_text("{ this is not valid json }")

        mod = _reset_module()
        result = mod.handle({})
        assert result == {}

    def test_debouncing_second_call_returns_empty(self, tmp_path, monkeypatch):
        """Second call within the 5-call debounce window returns {}."""
        monkeypatch.chdir(tmp_path)
        pt = tmp_path / ".pocketteam"
        pt.mkdir()
        _write_status(pt / "session-status.json", 80.0)

        mod = _reset_module()

        # First call (counter=1, 1 % 5 == 1) — should warn
        first = mod.handle({})
        assert "additionalContext" in first

        # Second call (counter=2, 2 % 5 != 1) — debounced, should return {}
        second = mod.handle({})
        assert second == {}
