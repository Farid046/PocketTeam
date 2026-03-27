"""
Tests for Observer Auto-Trigger system.

Covers:
- observer_trigger.py (Stage 1 hook)
- observer_cli.py (Stage 2 background entry point)
- ObserverAgent pattern detection, learnings, and event emission
- __main__ dispatch for observer_analyze hook
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """Create a minimal .pocketteam project structure."""
    pt = tmp_path / ".pocketteam"
    pt.mkdir()
    (pt / "events").mkdir()
    (pt / "learnings").mkdir()
    return tmp_path


@pytest.fixture
def events_file(tmp_project: Path) -> Path:
    """Return the events stream path (not yet populated)."""
    return tmp_project / ".pocketteam" / "events" / "stream.jsonl"


def _write_events(path: Path, events: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# observer_trigger.py tests
# ─────────────────────────────────────────────────────────────────────────────


class TestObserverTrigger:
    """Unit tests for the observer_trigger hook handler."""

    def _handle(self, hook_input: dict, cwd: Path | None = None) -> dict:
        """Call observer_trigger.handle with an optional cwd override."""
        from pocketteam.hooks.observer_trigger import handle

        if cwd is not None:
            with patch("pocketteam.hooks.observer_trigger.Path.cwd", return_value=cwd):
                return handle(hook_input)
        return handle(hook_input)

    def test_observer_trigger_skips_observer_agent(self, tmp_project: Path, events_file: Path):
        """Recursion guard: skip when the completing agent is 'observer'."""
        _write_events(events_file, [{"agent": "engineer", "status": "done"} for _ in range(5)])
        result = self._handle({"agent_type": "observer"}, cwd=tmp_project)
        assert result == {}

    def test_observer_trigger_skips_observer_subtype(self, tmp_project: Path, events_file: Path):
        """Recursion guard: also catches subagent_type field."""
        _write_events(events_file, [{"agent": "engineer", "status": "done"} for _ in range(5)])
        result = self._handle({"subagent_type": "observer"}, cwd=tmp_project)
        assert result == {}

    def test_observer_trigger_skips_on_cooldown(self, tmp_project: Path, events_file: Path):
        """Skip if last run was less than COOLDOWN_SECONDS ago."""
        _write_events(events_file, [{"agent": "engineer", "status": "done"} for _ in range(5)])
        cooldown_file = tmp_project / ".pocketteam" / ".observer-last-run"
        cooldown_file.write_text(str(time.time()))  # just now

        with patch("pocketteam.hooks.observer_trigger.subprocess.Popen") as mock_popen:
            result = self._handle({"agent_type": "engineer"}, cwd=tmp_project)
        assert result == {}
        mock_popen.assert_not_called()

    def test_observer_trigger_skips_no_pocketteam_dir(self, tmp_path: Path):
        """Skip silently when no .pocketteam directory exists."""
        from pocketteam.hooks.observer_trigger import handle

        with patch("pocketteam.hooks.observer_trigger.Path.cwd", return_value=tmp_path):
            result = handle({"agent_type": "engineer"})
        assert result == {}

    def test_observer_trigger_skips_no_events_file(self, tmp_project: Path):
        """Skip when stream.jsonl does not exist."""
        with patch("pocketteam.hooks.observer_trigger.subprocess.Popen") as mock_popen:
            result = self._handle({"agent_type": "engineer"}, cwd=tmp_project)
        assert result == {}
        mock_popen.assert_not_called()

    def test_observer_trigger_skips_events_too_small(self, tmp_project: Path, events_file: Path):
        """Skip when events file is smaller than 100 bytes."""
        events_file.write_text('{"agent": "x"}\n')  # < 100 bytes
        with patch("pocketteam.hooks.observer_trigger.subprocess.Popen") as mock_popen:
            result = self._handle({"agent_type": "engineer"}, cwd=tmp_project)
        assert result == {}
        mock_popen.assert_not_called()

    def test_observer_trigger_fires_after_cooldown(self, tmp_project: Path, events_file: Path):
        """Fire subprocess when cooldown has expired."""
        _write_events(events_file, [{"agent": "engineer", "status": "done"} for _ in range(10)])
        # Write an old cooldown file (>120s ago)
        cooldown_file = tmp_project / ".pocketteam" / ".observer-last-run"
        cooldown_file.write_text(str(time.time() - 200))

        with patch("pocketteam.hooks.observer_trigger.subprocess.Popen") as mock_popen:
            result = self._handle({"agent_type": "engineer"}, cwd=tmp_project)

        assert result == {}
        mock_popen.assert_called_once()
        call_args = mock_popen.call_args
        assert "observer_cli" in " ".join(call_args[0][0])
        assert str(tmp_project) in " ".join(call_args[0][0])

    def test_observer_trigger_fires_no_cooldown_file(self, tmp_project: Path, events_file: Path):
        """Fire subprocess when no cooldown file exists yet."""
        _write_events(events_file, [{"agent": "engineer", "status": "done"} for _ in range(10)])

        with patch("pocketteam.hooks.observer_trigger.subprocess.Popen") as mock_popen:
            result = self._handle({"agent_type": "engineer"}, cwd=tmp_project)

        assert result == {}
        mock_popen.assert_called_once()

    def test_observer_trigger_writes_cooldown_file(self, tmp_project: Path, events_file: Path):
        """Cooldown file is created/updated after a successful trigger."""
        _write_events(events_file, [{"agent": "engineer", "status": "done"} for _ in range(10)])
        cooldown_file = tmp_project / ".pocketteam" / ".observer-last-run"
        assert not cooldown_file.exists()

        with patch("pocketteam.hooks.observer_trigger.subprocess.Popen"):
            self._handle({"agent_type": "engineer"}, cwd=tmp_project)

        assert cooldown_file.exists()
        written = float(cooldown_file.read_text().strip())
        assert abs(written - time.time()) < 5  # within 5 seconds

    def test_observer_trigger_cooldown_file_permissions(
        self, tmp_project: Path, events_file: Path
    ):
        """Cooldown file must be written with 0o600 permissions."""
        import stat

        _write_events(events_file, [{"agent": "engineer", "status": "done"} for _ in range(10)])
        cooldown_file = tmp_project / ".pocketteam" / ".observer-last-run"

        with patch("pocketteam.hooks.observer_trigger.subprocess.Popen"):
            self._handle({"agent_type": "engineer"}, cwd=tmp_project)

        mode = stat.S_IMODE(cooldown_file.stat().st_mode)
        assert mode == 0o600

    def test_observer_trigger_returns_empty_dict(self, tmp_project: Path, events_file: Path):
        """handle() always returns {} regardless of outcome."""
        _write_events(events_file, [{"agent": "engineer", "status": "done"} for _ in range(10)])
        with patch("pocketteam.hooks.observer_trigger.subprocess.Popen"):
            result = self._handle({"agent_type": "engineer"}, cwd=tmp_project)
        assert result == {}


# ─────────────────────────────────────────────────────────────────────────────
# ObserverAgent._detect_patterns tests
# ─────────────────────────────────────────────────────────────────────────────


class TestObserverDetectPatterns:
    """Unit tests for ObserverAgent._detect_patterns."""

    def _make_agent(self, tmp_project: Path):
        from pocketteam.agents.observer import ObserverAgent

        return ObserverAgent(tmp_project)

    def test_observer_detect_patterns_errors(self, tmp_project: Path):
        """3+ errors by an agent should produce a warning pattern."""
        agent = self._make_agent(tmp_project)
        events = [
            {"agent": "engineer", "status": "error", "action": "fail"}
            for _ in range(3)
        ]
        patterns = agent._detect_patterns(events)
        assert any(p["agent"] == "engineer" and p["severity"] == "warning" for p in patterns)

    def test_observer_detect_patterns_errors_below_threshold(self, tmp_project: Path):
        """2 errors should NOT produce a pattern."""
        agent = self._make_agent(tmp_project)
        events = [{"agent": "engineer", "status": "error", "action": "fail"} for _ in range(2)]
        patterns = agent._detect_patterns(events)
        assert not any(p["agent"] == "engineer" and p["severity"] == "warning" for p in patterns)

    def test_observer_detect_patterns_retries(self, tmp_project: Path):
        """3+ retries for an agent should produce an info pattern."""
        agent = self._make_agent(tmp_project)
        events = [
            {"agent": "qa", "status": "info", "action": "retry attempt"}
            for _ in range(3)
        ]
        patterns = agent._detect_patterns(events)
        assert any(p["agent"] == "qa" and "retries" in p["pattern"] for p in patterns)

    def test_observer_detect_patterns_below_threshold(self, tmp_project: Path):
        """Fewer than 3 retries: no pattern emitted."""
        agent = self._make_agent(tmp_project)
        events = [
            {"agent": "qa", "status": "info", "action": "retry attempt"}
            for _ in range(2)
        ]
        patterns = agent._detect_patterns(events)
        assert not any("retries" in p.get("pattern", "") for p in patterns)

    def test_observer_detect_patterns_duration(self, tmp_project: Path):
        """Agents averaging >120s should be flagged as slow."""
        agent = self._make_agent(tmp_project)
        events = [
            {"agent": "engineer", "status": "done", "action": "Finished (10 tool calls, 150s)"},
            {"agent": "engineer", "status": "done", "action": "Finished (5 tool calls, 160s)"},
        ]
        patterns = agent._detect_patterns(events)
        slow = [p for p in patterns if "slow" in p.get("pattern", "")]
        assert slow, "Expected a slow-agent pattern"
        assert slow[0]["agent"] == "engineer"

    def test_observer_detect_patterns_duration_fast(self, tmp_project: Path):
        """Agents under threshold must not be flagged as slow."""
        agent = self._make_agent(tmp_project)
        events = [
            {"agent": "engineer", "status": "done", "action": "Finished (10 tool calls, 50s)"},
        ]
        patterns = agent._detect_patterns(events)
        assert not any("slow" in p.get("pattern", "") for p in patterns)

    def test_observer_detect_patterns_schema_validation_invalid_agent(self, tmp_project: Path):
        """Events with invalid agent names (e.g. path traversal) are dropped."""
        agent = self._make_agent(tmp_project)
        events = [
            {"agent": "../etc/passwd", "status": "error", "action": "fail"},
            {"agent": "../etc/passwd", "status": "error", "action": "fail"},
            {"agent": "../etc/passwd", "status": "error", "action": "fail"},
        ]
        patterns = agent._detect_patterns(events)
        # The malformed agent name should be filtered out — no patterns from it
        assert not any("passwd" in p.get("agent", "") for p in patterns)

    def test_observer_detect_patterns_schema_validation_invalid_status(self, tmp_project: Path):
        """Events with invalid status values are dropped."""
        agent = self._make_agent(tmp_project)
        events = [
            {"agent": "engineer", "status": "HACKED", "action": "fail"},
            {"agent": "engineer", "status": "HACKED", "action": "fail"},
            {"agent": "engineer", "status": "HACKED", "action": "fail"},
        ]
        patterns = agent._detect_patterns(events)
        assert not any(p["agent"] == "engineer" for p in patterns)


# ─────────────────────────────────────────────────────────────────────────────
# ObserverAgent._update_learnings tests
# ─────────────────────────────────────────────────────────────────────────────


class TestObserverUpdateLearnings:
    def _make_agent(self, tmp_project: Path):
        from pocketteam.agents.observer import ObserverAgent

        return ObserverAgent(tmp_project)

    def test_observer_update_learnings_creates_file(self, tmp_project: Path):
        """A new YAML file is created for a new agent."""
        agent = self._make_agent(tmp_project)
        patterns = [
            {
                "agent": "engineer",
                "pattern": "Agent engineer had 3 errors",
                "severity": "warning",
                "count": 3,
                "timestamp": "2026-01-01",
            }
        ]
        agent._update_learnings(patterns)
        learnings_file = tmp_project / ".pocketteam" / "learnings" / "engineer.yaml"
        assert learnings_file.exists()

    def test_observer_update_learnings_increments_count(self, tmp_project: Path):
        """Calling _update_learnings twice increments the count."""
        agent = self._make_agent(tmp_project)
        pattern = {
            "agent": "qa",
            "pattern": "Agent qa had 3 errors",
            "severity": "warning",
            "count": 3,
            "timestamp": "2026-01-01",
        }
        agent._update_learnings([pattern])
        agent._update_learnings([pattern])

        learnings_file = tmp_project / ".pocketteam" / "learnings" / "qa.yaml"
        data = yaml.safe_load(learnings_file.read_text())
        assert data["patterns"][0]["count"] == 6

    def test_observer_update_learnings_adds_new_pattern(self, tmp_project: Path):
        """Different patterns for the same agent are both recorded."""
        agent = self._make_agent(tmp_project)
        agent._update_learnings(
            [
                {
                    "agent": "engineer",
                    "pattern": "Pattern A",
                    "severity": "warning",
                    "count": 3,
                    "timestamp": "2026-01-01",
                }
            ]
        )
        agent._update_learnings(
            [
                {
                    "agent": "engineer",
                    "pattern": "Pattern B",
                    "severity": "info",
                    "count": 2,
                    "timestamp": "2026-01-02",
                }
            ]
        )
        learnings_file = tmp_project / ".pocketteam" / "learnings" / "engineer.yaml"
        data = yaml.safe_load(learnings_file.read_text())
        patterns_text = [p["pattern"] for p in data["patterns"]]
        assert "Pattern A" in patterns_text
        assert "Pattern B" in patterns_text

    def test_observer_agent_name_sanitization(self, tmp_project: Path):
        """Path traversal in agent names is blocked."""
        agent = self._make_agent(tmp_project)
        evil_pattern = {
            "agent": "../../../tmp/evil",
            "pattern": "evil",
            "severity": "warning",
            "count": 1,
            "timestamp": "2026-01-01",
        }
        # Should not raise; the file must not appear outside learnings dir
        agent._update_learnings([evil_pattern])
        # No file should have been written outside learnings/
        learnings_dir = tmp_project / ".pocketteam" / "learnings"
        written = list(learnings_dir.iterdir())
        # If something was written, it must be "tmp" → safe name "tmp", not outside
        for f in written:
            assert str(f.resolve()).startswith(str(learnings_dir.resolve()))

    def test_observer_yaml_corrupt_backup(self, tmp_project: Path):
        """Corrupt YAML triggers a backup before resetting."""
        agent = self._make_agent(tmp_project)
        learnings_dir = tmp_project / ".pocketteam" / "learnings"
        learnings_dir.mkdir(parents=True, exist_ok=True)
        corrupt_file = learnings_dir / "engineer.yaml"
        corrupt_file.write_text("{broken: yaml: content: [[[", encoding="utf-8")

        agent._update_learnings(
            [
                {
                    "agent": "engineer",
                    "pattern": "new pattern",
                    "severity": "info",
                    "count": 1,
                    "timestamp": "2026-01-01",
                }
            ]
        )
        # A backup should have been created
        backup = corrupt_file.with_suffix(".yaml.bak")
        assert backup.exists()
        # Original should now be valid YAML
        data = yaml.safe_load(corrupt_file.read_text())
        assert isinstance(data, dict)


# ─────────────────────────────────────────────────────────────────────────────
# ObserverAgent._emit_finding_event
# ─────────────────────────────────────────────────────────────────────────────


class TestObserverEmitFindingEvent:
    def _make_agent(self, tmp_project: Path):
        from pocketteam.agents.observer import ObserverAgent

        return ObserverAgent(tmp_project)

    def test_observer_emit_finding_event(self, tmp_project: Path, events_file: Path):
        """_emit_finding_event writes a valid JSON line to the stream."""
        agent = self._make_agent(tmp_project)
        patterns = [
            {
                "agent": "engineer",
                "pattern": "Agent engineer had 3 errors",
                "severity": "warning",
                "count": 3,
                "timestamp": "2026-01-01",
            }
        ]
        agent._emit_finding_event(patterns)
        lines = [json.loads(l) for l in events_file.read_text().splitlines() if l.strip()]
        assert lines
        evt = lines[-1]
        assert evt["agent"] == "observer"
        assert evt["type"] == "observation"
        assert evt["status"] == "info"
        assert "1 pattern" in evt["action"]


# ─────────────────────────────────────────────────────────────────────────────
# ObserverAgent.analyze_task
# ─────────────────────────────────────────────────────────────────────────────


class TestObserverAnalyzeTask:
    def _make_agent(self, tmp_project: Path):
        from pocketteam.agents.observer import ObserverAgent

        return ObserverAgent(tmp_project)

    def test_observer_analyze_task_no_events(self, tmp_project: Path):
        """analyze_task with no events returns success with no patterns."""
        import asyncio

        agent = self._make_agent(tmp_project)
        result = asyncio.run(agent.analyze_task())
        assert result.success
        assert result.artifacts.get("patterns") is None or result.artifacts.get("patterns") == []

    def test_observer_read_events_large_file(self, tmp_project: Path, events_file: Path):
        """OOM prevention: only last 200 events are returned."""
        # Write 500 events
        _write_events(
            events_file,
            [
                {"agent": "engineer", "status": "done", "action": f"step {i}"}
                for i in range(500)
            ],
        )
        agent = self._make_agent(tmp_project)
        events = agent._read_recent_events()
        assert len(events) <= 200


# ─────────────────────────────────────────────────────────────────────────────
# observer_cli.py tests
# ─────────────────────────────────────────────────────────────────────────────


class TestObserverCli:
    def test_observer_cli_main_no_args(self):
        """observer_cli exits with code 1 when no project root is given."""
        proc = subprocess.run(
            [sys.executable, "-m", "pocketteam.agents.observer_cli"],
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 1

    def test_observer_cli_main_invalid_path(self, tmp_path: Path):
        """observer_cli exits with code 1 for a non-existent path."""
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "pocketteam.agents.observer_cli",
                str(tmp_path / "does_not_exist"),
            ],
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 1

    def test_observer_cli_main_valid_path(self, tmp_project: Path, events_file: Path):
        """observer_cli exits cleanly with a valid project root."""
        _write_events(
            events_file,
            [{"agent": "engineer", "status": "done", "action": "ok"} for _ in range(5)],
        )
        proc = subprocess.run(
            [sys.executable, "-m", "pocketteam.agents.observer_cli", str(tmp_project)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        # Should not crash
        assert proc.returncode == 0


# ─────────────────────────────────────────────────────────────────────────────
# __main__ dispatch test for observer_analyze
# ─────────────────────────────────────────────────────────────────────────────


class TestHookDispatchObserverAnalyze:
    """Integration test: hook dispatcher routes observer_analyze correctly."""

    def _run_hook(self, hook_type: str, hook_input: dict) -> dict:
        proc = subprocess.run(
            [sys.executable, "-m", "pocketteam.hooks", hook_type],
            input=json.dumps(hook_input),
            capture_output=True,
            text=True,
        )
        return json.loads(proc.stdout)

    def test_hook_dispatch_observer_analyze(self):
        """observer_analyze hook dispatches without error and returns {}."""
        # With no .pocketteam dir in cwd, the trigger returns {} immediately
        result = self._run_hook("observer_analyze", {"agent_type": "engineer"})
        assert result == {}

    def test_hook_dispatch_observer_analyze_skips_observer(self):
        """observer_analyze is a no-op when the agent IS the observer."""
        result = self._run_hook("observer_analyze", {"agent_type": "observer"})
        assert result == {}
