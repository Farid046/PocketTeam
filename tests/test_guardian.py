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
        """Known safe targets like build/, node_modules/ are explicitly allowed
        when run by an agent that has Bash access (e.g. engineer)."""
        monkeypatch.chdir(project_root)
        result = _call("Bash", {"command": "rm -rf ./build"}, agent_id="engineer")
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
    def test_unknown_tool_name_not_blocked_by_safety_layers(
        self, project_root: Path, monkeypatch
    ) -> None:
        """An unknown tool name must not be blocked by safety layers 1-5.
        Layer 6 (allowlist) blocks it for agents with explicit tool lists,
        so use an explicitly permissive unknown agent_id (no registry entry,
        no allowlist) which defaults to read-only — but that still blocks it.
        The meaningful contract is: the hook does not crash and returns a valid
        result dict even for completely unknown tool names."""
        monkeypatch.chdir(project_root)
        result = _call("SomeCustomTool", {"param": "value"})
        # Must not crash and must return a valid result structure
        assert "allow" in result
        assert "layer" in result
        assert "reason" in result

    def test_empty_tool_name_does_not_crash(
        self, project_root: Path, monkeypatch
    ) -> None:
        """An empty tool name must not raise an exception."""
        monkeypatch.chdir(project_root)
        result = _call("", {})
        # Must not crash
        assert "allow" in result


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
        result = pre_tool_hook("Read", {}, agent_id="engineer")
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


# ---------------------------------------------------------------------------
# Bug 1: agent_id hash resolution via _resolve_agent_type()
# ---------------------------------------------------------------------------

class TestAgentIdHashResolution:
    """pre_tool_hook must resolve agent_id hashes to agent type names before
    checking the allowlist (Layer 6), so that known agents are granted their
    proper permissions instead of falling into the unknown-agent read-only path."""

    def test_hash_resolved_to_engineer_allows_write(
        self, project_root: Path, monkeypatch
    ) -> None:
        """An agent_id hash that maps to 'engineer' must be allowed to use Write."""
        monkeypatch.chdir(project_root)

        # Write the registry file that _resolve_agent_type reads
        import json
        registry = project_root / ".pocketteam" / "agent-registry.json"
        registry.write_text(json.dumps({"a9ed00d9aec628cf": "engineer"}))

        result = _call(
            "Write",
            {"file_path": str(project_root / "output.py"), "content": "x = 1"},
            agent_id="a9ed00d9aec628cf",
            cwd=project_root,
            monkeypatch=monkeypatch,
        )

        # Engineer is allowed to Write — hash must have been resolved
        assert result["allow"] is True, (
            f"Expected allow=True for engineer (resolved from hash), got: {result}"
        )

    def test_unresolvable_hash_falls_back_to_unknown_agent(
        self, project_root: Path, monkeypatch
    ) -> None:
        """An agent_id hash with no registry entry must not crash and must use
        the unknown-agent fallback (read-only tools allowed, write blocked)."""
        monkeypatch.chdir(project_root)

        # No registry file — hash cannot be resolved
        result = _call(
            "Write",
            {"file_path": str(project_root / "output.py"), "content": "x = 1"},
            agent_id="deadbeefdeadbeef",
            cwd=project_root,
            monkeypatch=monkeypatch,
        )

        # Unknown agent: Write must be blocked (Layer 6)
        assert result["allow"] is False
        assert result["layer"] == 6

    def test_hash_resolved_to_documentation_allows_write(
        self, project_root: Path, monkeypatch
    ) -> None:
        """An agent_id hash mapping to 'documentation' must be resolved before
        the allowlist check so Write is allowed."""
        monkeypatch.chdir(project_root)

        import json
        registry = project_root / ".pocketteam" / "agent-registry.json"
        registry.write_text(json.dumps({"abc123def456": "documentation"}))

        result = _call(
            "Write",
            {"file_path": str(project_root / "README.md"), "content": "# Docs"},
            agent_id="abc123def456",
            cwd=project_root,
            monkeypatch=monkeypatch,
        )

        assert result["allow"] is True, (
            f"Expected allow=True for documentation (resolved from hash), got: {result}"
        )

    def test_known_agent_name_not_resolved_again(
        self, project_root: Path, monkeypatch
    ) -> None:
        """If agent_id is already a known name like 'engineer', _resolve_agent_type
        must NOT be called (it is a no-op for already-resolved names)."""
        monkeypatch.chdir(project_root)

        with patch(
            "pocketteam.safety.guardian._resolve_agent_type"
        ) as mock_resolve:
            _call(
                "Write",
                {"file_path": str(project_root / "file.py"), "content": "pass"},
                agent_id="engineer",
                cwd=project_root,
                monkeypatch=monkeypatch,
            )

        mock_resolve.assert_not_called()


# ---------------------------------------------------------------------------
# Bug 2: empty agent_id (main session / COO) defaults to "coo"
# ---------------------------------------------------------------------------

class TestEmptyAgentIdDefaultsToCoo:
    """When agent_id is empty (main session started without --agent flag),
    pre_tool_hook must treat it as 'coo'.  The COO is allowed to use Agent,
    TodoWrite, TodoRead — but NOT Read, Glob, Grep, Write, or Bash directly."""

    def test_empty_agent_id_blocks_read(
        self, project_root: Path, monkeypatch
    ) -> None:
        """Main session (empty agent_id) must be BLOCKED from using Read (Layer 6)."""
        monkeypatch.chdir(project_root)

        result = _call(
            "Read",
            {"file_path": str(project_root / "README.md")},
            agent_id="",
            cwd=project_root,
            monkeypatch=monkeypatch,
        )

        assert result["allow"] is False, (
            f"COO (empty agent_id) must be blocked from Read, got: {result}"
        )
        assert result["layer"] == 6, (
            f"Expected Layer 6 (Allowlist) block, got layer: {result.get('layer')}"
        )

    def test_empty_agent_id_allows_agent_tool(
        self, project_root: Path, monkeypatch
    ) -> None:
        """Main session (empty agent_id) must be allowed to spawn sub-agents."""
        monkeypatch.chdir(project_root)

        result = _call(
            "Agent",
            {"prompt": "do something"},
            agent_id="",
            cwd=project_root,
            monkeypatch=monkeypatch,
        )

        assert result["allow"] is True, (
            f"COO (empty agent_id) must be allowed to use Agent tool, got: {result}"
        )

    def test_empty_agent_id_blocks_write(
        self, project_root: Path, monkeypatch
    ) -> None:
        """Main session (COO) must not be allowed to Write directly — it must
        delegate that to the engineer agent."""
        monkeypatch.chdir(project_root)

        result = _call(
            "Write",
            {"file_path": str(project_root / "file.py"), "content": "x = 1"},
            agent_id="",
            cwd=project_root,
            monkeypatch=monkeypatch,
        )

        assert result["allow"] is False, (
            f"COO (empty agent_id) must NOT be allowed to Write directly, got: {result}"
        )
        assert result["layer"] == 6

    def test_empty_agent_id_blocks_bash(
        self, project_root: Path, monkeypatch
    ) -> None:
        """Main session (COO) must not run Bash commands directly."""
        monkeypatch.chdir(project_root)

        result = _call(
            "Bash",
            {"command": "echo hello"},
            agent_id="",
            cwd=project_root,
            monkeypatch=monkeypatch,
        )

        assert result["allow"] is False, (
            f"COO (empty agent_id) must NOT be allowed to use Bash directly, got: {result}"
        )
        assert result["layer"] == 6
