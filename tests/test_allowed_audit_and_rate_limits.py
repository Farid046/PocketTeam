"""
TDD tests for two fixes:

Fix 1: ALLOWED decisions are logged to the audit log (guardian.pre_tool_hook)
Fix 2: Agent turn limits — documentation: 30, engineer: 60
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pocketteam.safety.audit_log import AuditLog, SafetyDecision
from pocketteam.safety.guardian import pre_tool_hook


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def project_root(tmp_path: Path) -> Path:
    (tmp_path / ".pocketteam").mkdir()
    (tmp_path / ".pocketteam" / "artifacts" / "audit").mkdir(parents=True)
    return tmp_path


# ---------------------------------------------------------------------------
# Fix 1: ALLOWED decisions logged to audit file
# ---------------------------------------------------------------------------

class TestAllowedDecisionAuditLogging:
    """pre_tool_hook must write an ALLOWED entry to the audit log when all
    safety layers pass, so the dashboard can display both allow and deny rows."""

    def _read_audit_entries(self, project_root: Path) -> list[dict]:
        audit_dir = project_root / ".pocketteam" / "artifacts" / "audit"
        entries = []
        for log_file in sorted(audit_dir.glob("*.jsonl")):
            if log_file.name == "CRITICAL_ALERTS.jsonl":
                continue
            for line in log_file.read_text().splitlines():
                if line.strip():
                    entries.append(json.loads(line))
        return entries

    def test_allowed_decision_written_to_audit_log(
        self, project_root: Path, monkeypatch
    ) -> None:
        """A benign Read call that passes all layers must produce an ALLOWED
        entry in the audit log."""
        monkeypatch.chdir(project_root)

        result = pre_tool_hook(
            "Read",
            {"file_path": str(project_root / "README.md")},
            agent_id="engineer",
            session_id="",
        )

        assert result["allow"] is True, f"Precondition failed: {result}"

        entries = self._read_audit_entries(project_root)
        assert len(entries) >= 1, "No audit entries written for ALLOWED decision"

        allowed_entries = [e for e in entries if e.get("decision") == "ALLOWED"]
        assert len(allowed_entries) >= 1, (
            f"Expected at least one ALLOWED entry, got: {entries}"
        )

    def test_allowed_entry_has_correct_fields(
        self, project_root: Path, monkeypatch
    ) -> None:
        """The ALLOWED audit entry must contain agent, tool, input_hash,
        decision, and reason fields."""
        monkeypatch.chdir(project_root)

        pre_tool_hook(
            "Read",
            {"file_path": str(project_root / "README.md")},
            agent_id="engineer",
            session_id="",
        )

        entries = self._read_audit_entries(project_root)
        allowed_entries = [e for e in entries if e.get("decision") == "ALLOWED"]
        assert len(allowed_entries) >= 1

        entry = allowed_entries[0]
        assert entry["agent"] == "engineer"
        assert entry["tool"] == "Read"
        assert entry["input_hash"].startswith("sha256:")
        assert entry["decision"] == "ALLOWED"
        assert isinstance(entry.get("reason"), str)
        assert len(entry["reason"]) > 0, "ALLOWED reason must not be empty"

    def test_allowed_reason_mentions_layers(
        self, project_root: Path, monkeypatch
    ) -> None:
        """The ALLOWED reason string should mention that safety layers passed."""
        monkeypatch.chdir(project_root)

        pre_tool_hook(
            "Read",
            {"file_path": str(project_root / "README.md")},
            agent_id="engineer",
            session_id="",
        )

        entries = self._read_audit_entries(project_root)
        allowed_entries = [e for e in entries if e.get("decision") == "ALLOWED"]
        assert len(allowed_entries) >= 1

        reason = allowed_entries[0]["reason"].lower()
        # Reason should mention "layer" or "passed" or "safety"
        assert any(kw in reason for kw in ("layer", "passed", "safety")), (
            f"ALLOWED reason should describe layers passed, got: {reason!r}"
        )

    def test_allowed_audit_does_not_store_raw_input(
        self, project_root: Path, monkeypatch
    ) -> None:
        """Raw tool input must never appear in the audit log (may contain secrets)."""
        monkeypatch.chdir(project_root)
        secret_path = "/home/user/safe_but_sensitive/report.txt"

        pre_tool_hook(
            "Read",
            {"file_path": secret_path},
            agent_id="engineer",
            session_id="",
        )

        audit_dir = project_root / ".pocketteam" / "artifacts" / "audit"
        for log_file in audit_dir.glob("*.jsonl"):
            if log_file.name == "CRITICAL_ALERTS.jsonl":
                continue
            content = log_file.read_text()
            assert secret_path not in content, (
                "Raw file path must not appear in audit log"
            )

    def test_denied_decision_still_written(
        self, project_root: Path, monkeypatch
    ) -> None:
        """Adding ALLOWED logging must not break DENIED logging."""
        monkeypatch.chdir(project_root)

        result = pre_tool_hook(
            "Bash",
            {"command": "rm -rf /"},
            agent_id="engineer",
            session_id="",
        )

        assert result["allow"] is False, f"Precondition: must be denied, got: {result}"

        entries = self._read_audit_entries(project_root)
        denied_entries = [e for e in entries if "DENIED" in e.get("decision", "")]
        assert len(denied_entries) >= 1, (
            f"Expected DENIED entry, got: {entries}"
        )

    def test_allowed_entry_not_written_when_no_project_root(
        self, monkeypatch, tmp_path
    ) -> None:
        """When no project root is found (no .pocketteam/), the hook must not
        crash. It just cannot write the audit entry."""
        # Use a temp dir with no .pocketteam/
        monkeypatch.chdir(tmp_path)

        result = pre_tool_hook(
            "Read",
            {"file_path": "/tmp/safe.txt"},
            agent_id="engineer",
            session_id="",
        )

        # Must not raise — audit failure is non-critical
        assert "allow" in result


# ---------------------------------------------------------------------------
# Fix 2: Agent turn limits
# ---------------------------------------------------------------------------

class TestAgentTurnLimits:
    """documentation agent: 30 turns, engineer: 60 turns."""

    def test_documentation_max_turns_is_30(self) -> None:
        from pocketteam.constants import AGENT_MAX_TURNS
        assert AGENT_MAX_TURNS["documentation"] == 30, (
            f"documentation max turns should be 30, got {AGENT_MAX_TURNS['documentation']}"
        )

    def test_engineer_max_turns_is_60(self) -> None:
        from pocketteam.constants import AGENT_MAX_TURNS
        assert AGENT_MAX_TURNS["engineer"] == 60, (
            f"engineer max turns should be 60, got {AGENT_MAX_TURNS['engineer']}"
        )

    def test_coo_max_turns_unchanged(self) -> None:
        from pocketteam.constants import AGENT_MAX_TURNS
        assert AGENT_MAX_TURNS["coo"] == 30, (
            f"coo max turns should remain 30, got {AGENT_MAX_TURNS['coo']}"
        )

    def test_all_agents_have_turn_limits_defined(self) -> None:
        """Every agent that exists should have a max turn limit defined."""
        from pocketteam.constants import AGENT_MAX_TURNS, AGENT_MODELS
        for agent in AGENT_MODELS:
            assert agent in AGENT_MAX_TURNS, (
                f"Agent '{agent}' has no max turn limit in AGENT_MAX_TURNS"
            )

    def test_documentation_rate_limit_enforced_at_30(
        self, project_root: Path, monkeypatch
    ) -> None:
        """documentation agent must be blocked after 30 turns in a session."""
        import time
        from pocketteam.safety.guardian import _check_rate_limit

        monkeypatch.chdir(project_root)

        # Simulate 30 turns already consumed
        state_file = project_root / ".pocketteam" / "rate_limit_state.json"
        state = {
            "documentation": {
                "turns": 30,
                "reset_at": time.time(),  # fresh window — won't reset
            }
        }
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(json.dumps(state))

        result = _check_rate_limit("documentation", project_root)

        assert result.get("allow") is False, (
            f"documentation agent should be blocked at turn 30, got: {result}"
        )
        assert "30" in result.get("reason", ""), (
            f"Reason should mention limit of 30, got: {result.get('reason')}"
        )

    def test_engineer_rate_limit_enforced_at_60(
        self, project_root: Path, monkeypatch
    ) -> None:
        """engineer agent must be blocked after 60 turns in a session."""
        import time
        from pocketteam.safety.guardian import _check_rate_limit

        monkeypatch.chdir(project_root)

        state_file = project_root / ".pocketteam" / "rate_limit_state.json"
        state = {
            "engineer": {
                "turns": 60,
                "reset_at": time.time(),
            }
        }
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(json.dumps(state))

        result = _check_rate_limit("engineer", project_root)

        assert result.get("allow") is False, (
            f"engineer agent should be blocked at turn 60, got: {result}"
        )
        assert "60" in result.get("reason", ""), (
            f"Reason should mention limit of 60, got: {result.get('reason')}"
        )
