"""
Standalone black-box tests for guardian.pre_tool_hook.

These tests treat pre_tool_hook as a black box:
- only import it and assert on the returned dict
- no knowledge of internal layer implementation details beyond the contract

Contract: pre_tool_hook returns {"allow": bool, "layer": int|None, "reason": str}

Coverage:
- Return structure is always correct
- Layer order: 10 → 1 → 5 → 3 → 4 → 2 → 6 → 7
- Unknown (benign) tool name is allowed
- Empty / missing tool_input is handled safely
- session_id is threaded through to D-SAC token validation
- _check_dsac_token is called for destructive operations
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from pocketteam.safety.guardian import pre_tool_hook

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def project_root(tmp_path: Path) -> Path:
    (tmp_path / ".pocketteam").mkdir()
    return tmp_path


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _call(tool_name="Read", tool_input=None, agent_id="", session_id="", cwd=None, monkeypatch=None):
    """Call pre_tool_hook, optionally changing cwd first."""
    if tool_input is None:
        tool_input = {}
    if cwd and monkeypatch:
        monkeypatch.chdir(cwd)
    return pre_tool_hook(tool_name, tool_input, agent_id, session_id=session_id)


# ---------------------------------------------------------------------------
# Return-structure contract
# ---------------------------------------------------------------------------

class TestReturnStructure:
    def test_allow_result_has_required_keys(self, project_root: Path, monkeypatch) -> None:
        monkeypatch.chdir(project_root)
        result = _call("Read", {"file_path": "/tmp/foo.txt"})
        assert "allow" in result
        assert "layer" in result
        assert "reason" in result

    def test_deny_result_has_required_keys(self, project_root: Path, monkeypatch) -> None:
        monkeypatch.chdir(project_root)
        result = _call("Bash", {"command": "rm -rf /"})
        assert "allow" in result
        assert "layer" in result
        assert "reason" in result

    def test_allow_is_bool(self, project_root: Path, monkeypatch) -> None:
        monkeypatch.chdir(project_root)
        result = _call("Read", {"file_path": "/tmp/safe.txt"})
        assert isinstance(result["allow"], bool)

    def test_reason_is_string(self, project_root: Path, monkeypatch) -> None:
        monkeypatch.chdir(project_root)
        result = _call("Bash", {"command": "rm -rf /"})
        assert isinstance(result["reason"], str)


# ---------------------------------------------------------------------------
# Layer 10: Kill switch (checked before Layer 1)
# ---------------------------------------------------------------------------

class TestLayer10KillSwitch:
    def test_kill_switch_blocks_all_tools(self, project_root: Path, monkeypatch) -> None:
        monkeypatch.chdir(project_root)
        kill_file = project_root / ".pocketteam" / "KILL"
        kill_file.touch()

        result = _call("Read", {"file_path": "/tmp/foo.txt"}, cwd=project_root, monkeypatch=monkeypatch)
        assert not result["allow"]
        assert result["layer"] == 10
        assert "kill" in result["reason"].lower()

    def test_kill_switch_blocks_before_never_allow(self, project_root: Path, monkeypatch) -> None:
        """Layer 10 must fire before Layer 1 — kill switch takes priority."""
        monkeypatch.chdir(project_root)
        kill_file = project_root / ".pocketteam" / "KILL"
        kill_file.touch()

        # rm -rf / would normally be Layer 1, but kill switch is Layer 10 (fires first)
        result = _call("Bash", {"command": "rm -rf /"}, cwd=project_root, monkeypatch=monkeypatch)
        assert result["layer"] == 10


# ---------------------------------------------------------------------------
# Layer 1: NEVER_ALLOW
# ---------------------------------------------------------------------------

class TestLayer1NeverAllow:
    def test_rm_rf_root_blocked(self, project_root: Path, monkeypatch) -> None:
        monkeypatch.chdir(project_root)
        result = _call("Bash", {"command": "rm -rf /"})
        assert not result["allow"]
        assert result["layer"] == 1

    def test_drop_database_blocked(self, project_root: Path, monkeypatch) -> None:
        monkeypatch.chdir(project_root)
        result = _call("Bash", {"command": "DROP DATABASE production;"})
        assert not result["allow"]
        assert result["layer"] == 1


# ---------------------------------------------------------------------------
# Layer 2: Destructive patterns (requires approval)
# ---------------------------------------------------------------------------

class TestLayer2Destructive:
    def test_rm_rf_user_data_requires_approval(self, project_root: Path, monkeypatch) -> None:
        """Deleting a non-safe directory must require approval (Layer 2)."""
        monkeypatch.chdir(project_root)
        result = _call("Bash", {"command": "rm -rf ./user_data"})
        assert not result["allow"]
        assert result["layer"] == 2
        assert result["requires_approval"] is True

    def test_rm_rf_safe_target_is_allowed(self, project_root: Path, monkeypatch) -> None:
        """Known safe targets like build/, node_modules/ are explicitly allowed."""
        monkeypatch.chdir(project_root)
        result = _call("Bash", {"command": "rm -rf ./build"})
        assert result["allow"] is True


# ---------------------------------------------------------------------------
# Layer 5: Sensitive file paths
# ---------------------------------------------------------------------------

class TestLayer5SensitivePaths:
    def test_write_to_env_file_blocked(self, project_root: Path, monkeypatch) -> None:
        monkeypatch.chdir(project_root)
        result = _call("Write", {"file_path": str(project_root / ".env"), "content": "SECRET=x"})
        assert not result["allow"]
        assert result["layer"] == 5

    def test_write_to_pem_file_blocked(self, project_root: Path, monkeypatch) -> None:
        monkeypatch.chdir(project_root)
        result = _call("Write", {"file_path": "/home/user/.ssh/id_rsa.pem", "content": "key"})
        assert not result["allow"]
        assert result["layer"] == 5


# ---------------------------------------------------------------------------
# Unknown / benign tool name
# ---------------------------------------------------------------------------

class TestUnknownToolName:
    def test_unknown_tool_name_allowed(self, project_root: Path, monkeypatch) -> None:
        monkeypatch.chdir(project_root)
        result = _call("SomeCustomTool", {"param": "value"})
        assert result["allow"] is True

    def test_empty_tool_name_allowed(self, project_root: Path, monkeypatch) -> None:
        monkeypatch.chdir(project_root)
        result = _call("", {})
        assert result["allow"] is True


# ---------------------------------------------------------------------------
# Missing / empty tool_input
# ---------------------------------------------------------------------------

class TestMissingToolInput:
    def test_none_tool_input_does_not_crash(self, project_root: Path, monkeypatch) -> None:
        monkeypatch.chdir(project_root)
        result = pre_tool_hook("Read", None)
        assert "allow" in result

    def test_empty_dict_tool_input_allowed(self, project_root: Path, monkeypatch) -> None:
        monkeypatch.chdir(project_root)
        result = pre_tool_hook("Read", {})
        assert result["allow"] is True

    def test_empty_string_tool_input_does_not_crash(self, project_root: Path, monkeypatch) -> None:
        monkeypatch.chdir(project_root)
        result = pre_tool_hook("Bash", "")
        assert "allow" in result


# ---------------------------------------------------------------------------
# session_id threading
# ---------------------------------------------------------------------------

class TestSessionIdThreading:
    def test_session_id_passed_to_dsac_check(self, project_root: Path, monkeypatch) -> None:
        """session_id supplied to pre_tool_hook must reach _check_dsac_token."""
        monkeypatch.chdir(project_root)
        captured = {}

        original_check = __import__(
            "pocketteam.safety.guardian", fromlist=["_check_dsac_token"]
        )._check_dsac_token

        def spy(tool_name, tool_input, agent_id, session_id, proj_root):
            captured["session_id"] = session_id
            return original_check(tool_name, tool_input, agent_id, session_id, proj_root)

        with patch("pocketteam.safety.guardian._check_dsac_token", side_effect=spy):
            # Trigger Layer 2 (destructive) so _check_dsac_token is called
            _call(
                "Bash",
                {"command": "rm -rf ./staging"},
                session_id="my-session-123",
                cwd=project_root,
                monkeypatch=monkeypatch,
            )

        assert captured.get("session_id") == "my-session-123"


# ---------------------------------------------------------------------------
# _check_dsac_token called for destructive ops
# ---------------------------------------------------------------------------

class TestDsacTokenInvocation:
    def test_dsac_check_called_for_layer2(self, project_root: Path, monkeypatch) -> None:
        monkeypatch.chdir(project_root)
        with patch(
            "pocketteam.safety.guardian._check_dsac_token",
            return_value=None,
        ) as mock_dsac:
            _call("Bash", {"command": "rm -rf ./old_data"})

        mock_dsac.assert_called_once()

    def test_dsac_check_not_called_for_safe_read(self, project_root: Path, monkeypatch) -> None:
        monkeypatch.chdir(project_root)
        with patch(
            "pocketteam.safety.guardian._check_dsac_token",
            return_value=None,
        ) as mock_dsac:
            _call("Read", {"file_path": "/tmp/README.md"})

        mock_dsac.assert_not_called()

    def test_valid_dsac_token_allows_destructive_op(self, project_root: Path, monkeypatch) -> None:
        monkeypatch.chdir(project_root)
        with patch(
            "pocketteam.safety.guardian._check_dsac_token",
            return_value={"allow": True, "layer": 9, "reason": "approved"},
        ):
            result = _call("Bash", {"command": "rm -rf ./data", "__dsac_token": "fake-token"})

        assert result["allow"] is True
        assert result["layer"] == 9
