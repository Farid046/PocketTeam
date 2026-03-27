"""
Integration tests: D-SAC token validation in guardian hook.
Tests the full flow: guardian blocks -> token issued -> guardian allows.
Includes scope-escalation attack test (B1).
"""

import time

import pytest

from pocketteam.safety.dsac import DSACGuard
from pocketteam.safety.guardian import pre_tool_hook


@pytest.fixture
def tmp_project(tmp_path):
    (tmp_path / ".pocketteam").mkdir()
    return tmp_path


class TestGuardianDSACTokenFlow:

    def test_destructive_bash_blocked_without_token(
        self, tmp_project, monkeypatch
    ):
        monkeypatch.chdir(tmp_project)
        result = pre_tool_hook(
            "Bash", {"command": "rm -rf ./data"}, "engineer",
        )
        assert not result["allow"]
        assert result.get("requires_approval") is True

    def test_destructive_bash_allowed_with_valid_token(
        self, tmp_project, monkeypatch
    ):
        monkeypatch.chdir(tmp_project)
        guard = DSACGuard(tmp_project)
        tool_input = {"command": "rm -rf ./data"}
        preview = guard.create_dry_run_preview(
            "Bash", "rm -rf ./data", ["data/"],
            session_id="sess-1", agent_id="engineer",
        )
        token = guard.issue_approval_token(
            preview, "engineer", "task-001",
            tool_name="Bash", tool_input=tool_input,
            session_id="sess-1",
        )
        result = pre_tool_hook(
            "Bash",
            {"command": "rm -rf ./data", "__dsac_token": token.token},
            "engineer",
            session_id="sess-1",
        )
        assert result["allow"] is True
        assert result.get("layer") == 9

    def test_token_consumed_after_use(self, tmp_project, monkeypatch):
        monkeypatch.chdir(tmp_project)
        guard = DSACGuard(tmp_project)
        tool_input = {"command": "rm -rf ./data"}
        preview = guard.create_dry_run_preview(
            "Bash", "rm -rf ./data", ["data/"],
            session_id="sess-1", agent_id="engineer",
        )
        token = guard.issue_approval_token(
            preview, "engineer", "task-001",
            tool_name="Bash", tool_input=tool_input,
            session_id="sess-1",
        )
        ti = {"command": "rm -rf ./data", "__dsac_token": token.token}
        r1 = pre_tool_hook("Bash", ti, "engineer", session_id="sess-1")
        assert r1["allow"]
        r2 = pre_tool_hook("Bash", ti, "engineer", session_id="sess-1")
        assert not r2["allow"]

    def test_scope_escalation_attack_blocked(
        self, tmp_project, monkeypatch
    ):
        """B1: Agent gets token for staging, tries to use for production.

        In v3, Guardian computes the hash from the ACTUAL command.
        The hash of "rm -rf ./production_data" does not match the hash
        stored in the token (which was for "rm -rf ./staging_data").
        """
        monkeypatch.chdir(tmp_project)
        guard = DSACGuard(tmp_project)

        staging_input = {"command": "rm -rf ./staging_data"}
        preview = guard.create_dry_run_preview(
            "Bash", "rm -rf ./staging_data", ["staging_data/"],
            session_id="sess-1", agent_id="engineer",
        )
        token = guard.issue_approval_token(
            preview, "engineer", "task-001",
            tool_name="Bash", tool_input=staging_input,
            session_id="sess-1",
        )

        # Agent tries to use token for PRODUCTION operation
        result = pre_tool_hook(
            "Bash",
            {
                "command": "rm -rf ./production_data",
                "__dsac_token": token.token,
            },
            "engineer",
        )

        # MUST be blocked: hash mismatch
        assert not result["allow"]
        assert result.get("requires_approval") is True

    def test_layer1_never_bypassed_by_token(
        self, tmp_project, monkeypatch
    ):
        monkeypatch.chdir(tmp_project)
        guard = DSACGuard(tmp_project)
        preview = guard.create_dry_run_preview(
            "Bash", "rm -rf /", ["/"],
            session_id="sess-1", agent_id="engineer",
        )
        token = guard.issue_approval_token(
            preview, "engineer", "task-001",
            tool_name="Bash",
            tool_input={"command": "rm -rf /"},
            session_id="sess-1",
        )
        result = pre_tool_hook(
            "Bash",
            {"command": "rm -rf /", "__dsac_token": token.token},
            "engineer",
        )
        assert not result["allow"]
        assert result.get("layer") == 1

    def test_wrong_agent_token_rejected(
        self, tmp_project, monkeypatch
    ):
        monkeypatch.chdir(tmp_project)
        guard = DSACGuard(tmp_project)
        tool_input = {"command": "rm -rf ./data"}
        preview = guard.create_dry_run_preview(
            "Bash", "rm -rf ./data", ["data/"],
            session_id="sess-1", agent_id="devops",
        )
        token = guard.issue_approval_token(
            preview, "devops", "task-001",
            tool_name="Bash", tool_input=tool_input,
            session_id="sess-1",
        )
        result = pre_tool_hook(
            "Bash",
            {"command": "rm -rf ./data", "__dsac_token": token.token},
            "engineer",  # Wrong agent
            session_id="sess-1",
        )
        assert not result["allow"]

    def test_expired_token_rejected(self, tmp_project, monkeypatch):
        monkeypatch.chdir(tmp_project)
        guard = DSACGuard(tmp_project)
        tool_input = {"command": "rm -rf ./data"}
        preview = guard.create_dry_run_preview(
            "Bash", "rm -rf ./data", ["data/"],
            session_id="sess-1", agent_id="engineer",
        )
        token = guard.issue_approval_token(
            preview, "engineer", "task-001",
            ttl_seconds=0,
            tool_name="Bash", tool_input=tool_input,
            session_id="sess-1",
        )
        time.sleep(0.01)
        result = pre_tool_hook(
            "Bash",
            {"command": "rm -rf ./data", "__dsac_token": token.token},
            "engineer",
            session_id="sess-1",
        )
        assert not result["allow"]

    def test_fake_token_rejected(self, tmp_project, monkeypatch):
        monkeypatch.chdir(tmp_project)
        result = pre_tool_hook(
            "Bash",
            {
                "command": "rm -rf ./data",
                "__dsac_token": "fake_token_12345",
            },
            "engineer",
        )
        assert not result["allow"]

    def test_non_destructive_ignores_token(
        self, tmp_project, monkeypatch
    ):
        monkeypatch.chdir(tmp_project)
        result = pre_tool_hook("Bash", {"command": "ls -la"}, "engineer")
        assert result["allow"]

    def test_dsac_operation_hash_key_not_accepted(
        self, tmp_project, monkeypatch
    ):
        """__dsac_operation_hash is NOT used. Only __dsac_token."""
        monkeypatch.chdir(tmp_project)
        result = pre_tool_hook(
            "Bash",
            {
                "command": "rm -rf ./data",
                "__dsac_token": "some_token",
                "__dsac_operation_hash": "some_hash",
            },
            "engineer",
        )
        # Still blocked because token is fake
        assert not result["allow"]


class TestDSACTokenRegressions:

    def test_token_key_does_not_match_destructive_patterns(self):
        import json
        import secrets

        from pocketteam.safety.rules import (
            check_destructive,
            check_never_allow,
        )

        token = secrets.token_urlsafe(32)
        input_str = json.dumps(
            {"command": "ls", "__dsac_token": token}
        )
        r1 = check_never_allow("Bash", input_str)
        assert r1.allowed
        r2 = check_destructive("Bash", input_str)
        assert r2.allowed

    def test_missing_token_does_not_crash(self):
        result = pre_tool_hook(
            "Bash", {"command": "rm -rf ./data"}, "engineer",
        )
        assert not result["allow"]

    def test_non_dict_tool_input_still_blocked(self):
        result = pre_tool_hook("Bash", "rm -rf ./data", "engineer")
        assert not result["allow"]
