"""
Tests for Safety Layer 9: D-SAC Pattern
Dry-run -> Staged -> Approval -> Commit

v3: All tests use tool_name/tool_input on issue_approval_token (N3).
    validate_token() removed -- only validate_and_consume_token() (N2).
"""

import time

import pytest

from pocketteam.constants import DSAC_MAX_REINITIATIONS
from pocketteam.safety.dsac import (
    ApprovalToken,
    DryRunPreview,
    DSACGuard,
    compute_operation_hash_for_tool_call,
)


@pytest.fixture
def tmp_project(tmp_path):
    """Create a temporary project directory."""
    (tmp_path / ".pocketteam").mkdir()
    return tmp_path


# -- Helper to issue a token with all required params -------------------------


def _issue_token(
    guard: DSACGuard,
    operation: str = "rm old.txt",
    scope: list[str] | None = None,
    tool_name: str = "Bash",
    tool_input: "str | dict" = "",
    agent_id: str = "devops",
    task_id: str = "task-001",
    session_id: str = "test-session",
    ttl_seconds: int | None = None,
) -> tuple[DryRunPreview, ApprovalToken]:
    """Helper: create preview + issue token with all required params."""
    if scope is None:
        scope = ["old.txt"]
    if not tool_input:
        tool_input = {"command": operation}

    preview = guard.create_dry_run_preview(
        tool_name=tool_name,
        operation=operation,
        scope=scope,
        session_id=session_id,
        agent_id=agent_id,
    )

    kwargs = {
        "preview": preview,
        "agent_id": agent_id,
        "task_id": task_id,
        "tool_name": tool_name,
        "tool_input": tool_input,
        "session_id": session_id,
    }
    if ttl_seconds is not None:
        kwargs["ttl_seconds"] = ttl_seconds

    token = guard.issue_approval_token(**kwargs)
    return preview, token


class TestDSACPattern:
    """Layer 9: D-SAC approval flow."""

    def test_dry_run_creates_preview(self, tmp_project):
        guard = DSACGuard(tmp_project)
        preview = guard.create_dry_run_preview(
            tool_name="Bash",
            operation="rm -rf ./old-data",
            scope=["old-data/file1.txt", "old-data/file2.txt"],
            is_reversible=False,
            session_id="sess-1",
            agent_id="devops",
        )

        assert isinstance(preview, DryRunPreview)
        assert preview.item_count == 2
        assert preview.preview_hash
        assert not preview.is_reversible
        assert not preview.blocked

    def test_preview_hash_is_deterministic(self, tmp_project):
        guard = DSACGuard(tmp_project)
        scope = ["users.csv", "logs.txt"]

        p1 = guard.create_dry_run_preview(
            "Bash", "rm files", scope,
            session_id="s", agent_id="a",
        )
        p2 = guard.create_dry_run_preview(
            "Bash", "rm files", scope,
            session_id="s", agent_id="a",
        )

        assert p1.preview_hash == p2.preview_hash

    def test_different_operations_have_different_hashes(self, tmp_project):
        guard = DSACGuard(tmp_project)
        p1 = guard.create_dry_run_preview(
            "Bash", "rm file1.txt", ["file1.txt"],
            session_id="s", agent_id="a",
        )
        p2 = guard.create_dry_run_preview(
            "Bash", "rm file2.txt", ["file2.txt"],
            session_id="s", agent_id="a",
        )

        assert p1.preview_hash != p2.preview_hash

    def test_issue_approval_token(self, tmp_project):
        guard = DSACGuard(tmp_project)
        _, token = _issue_token(guard)

        assert token.token
        assert token.agent_id == "devops"
        assert token.is_valid()
        assert not token.is_expired()

    def test_token_validates_correctly(self, tmp_project):
        guard = DSACGuard(tmp_project)
        _, token = _issue_token(guard)

        valid, reason = guard.validate_and_consume_token(
            token.token, token.operation_hash, "devops",
            session_id="test-session",
        )
        assert valid
        assert "consumed" in reason.lower()

    def test_token_invalid_for_wrong_operation(self, tmp_project):
        guard = DSACGuard(tmp_project)
        _, token = _issue_token(
            guard, operation="rm file1.txt",
            tool_input={"command": "rm file1.txt"},
        )

        wrong_hash = compute_operation_hash_for_tool_call(
            "Bash", {"command": "rm file2.txt"}
        )
        valid, reason = guard.validate_and_consume_token(
            token.token, wrong_hash, "devops",
            session_id=token.session_id,
        )
        assert not valid
        assert "mismatch" in reason.lower()

    def test_token_invalid_for_wrong_agent(self, tmp_project):
        guard = DSACGuard(tmp_project)
        _, token = _issue_token(guard)

        valid, reason = guard.validate_and_consume_token(
            token.token, token.operation_hash, "engineer",
            session_id=token.session_id,
        )
        assert not valid
        assert "devops" in reason.lower()

    def test_token_single_use(self, tmp_project):
        guard = DSACGuard(tmp_project)
        _, token = _issue_token(guard)

        # First use: valid
        valid, _ = guard.validate_and_consume_token(
            token.token, token.operation_hash, "devops",
            session_id=token.session_id,
        )
        assert valid

        # Second use: invalid (already consumed)
        valid, reason = guard.validate_and_consume_token(
            token.token, token.operation_hash, "devops",
            session_id=token.session_id,
        )
        assert not valid
        assert "already used" in reason.lower()

    def test_expired_token_is_invalid(self, tmp_project):
        guard = DSACGuard(tmp_project)
        _, token = _issue_token(guard, ttl_seconds=0)

        time.sleep(0.01)  # Ensure expiry
        valid, reason = guard.validate_and_consume_token(
            token.token, token.operation_hash, "devops",
            session_id=token.session_id,
        )
        assert not valid
        assert "expired" in reason.lower()

    def test_token_not_found(self, tmp_project):
        guard = DSACGuard(tmp_project)
        valid, reason = guard.validate_and_consume_token(
            "fake-token", "fake-hash", "devops",
            session_id="any-session",
        )
        assert not valid
        assert "not found" in reason.lower()

    def test_invalidate_all_tokens_on_kill(self, tmp_project):
        guard = DSACGuard(tmp_project)

        for i in range(3):
            _issue_token(
                guard,
                operation=f"rm file{i}.txt",
                scope=[f"file{i}.txt"],
                tool_input={"command": f"rm file{i}.txt"},
            )

        count = guard.invalidate_all_tokens()
        assert count == 3

        tokens = guard._load_tokens()
        assert all(t["used"] for t in tokens.values())

    def test_preview_human_readable(self, tmp_project):
        guard = DSACGuard(tmp_project)
        scope = [f"data/file{i}.csv" for i in range(15)]
        preview = guard.create_dry_run_preview(
            "mcp__supabase__execute_sql",
            "DELETE FROM old_logs",
            scope,
            is_reversible=False,
            session_id="s",
            agent_id="a",
        )

        text = preview.to_human_readable()
        assert "DESTRUCTIVE OPERATION PREVIEW" in text
        assert "DELETE FROM old_logs" in text
        assert "15" in text
        assert "more" in text

    def test_tokens_persist_across_instances(self, tmp_project):
        """Tokens survive between DSACGuard instances (context compaction)."""
        guard1 = DSACGuard(tmp_project)
        _, token = _issue_token(guard1)

        # New instance (simulates context compaction / process restart)
        guard2 = DSACGuard(tmp_project)
        valid, _ = guard2.validate_and_consume_token(
            token.token, token.operation_hash, "devops",
            session_id=token.session_id,
        )
        assert valid


class TestDSACSessionBinding:
    """Tokens bound to session_id + sequence_number."""

    def test_token_with_session_id(self, tmp_project):
        guard = DSACGuard(tmp_project)
        _, token = _issue_token(guard, session_id="sess-abc")

        valid, _ = guard.validate_and_consume_token(
            token.token, token.operation_hash, "devops",
            session_id="sess-abc",
        )
        assert valid

    def test_token_invalid_for_different_session(self, tmp_project):
        guard = DSACGuard(tmp_project)
        _, token = _issue_token(guard, session_id="sess-abc")

        valid, reason = guard.validate_and_consume_token(
            token.token, token.operation_hash, "devops",
            session_id="sess-xyz",
        )
        assert not valid
        assert "session" in reason.lower()

    def test_sequence_number_increments(self, tmp_project):
        guard = DSACGuard(tmp_project)
        tokens = []
        for i in range(3):
            _, t = _issue_token(
                guard,
                operation=f"rm file{i}.txt",
                scope=[f"file{i}.txt"],
                tool_input={"command": f"rm file{i}.txt"},
                session_id="sess-1",
            )
            tokens.append(t)
        assert tokens[0].sequence_number == 1
        assert tokens[1].sequence_number == 2
        assert tokens[2].sequence_number == 3

    def test_different_agents_have_independent_sequences(self, tmp_project):
        guard = DSACGuard(tmp_project)
        _, t1 = _issue_token(
            guard, operation="rm a.txt", scope=["a.txt"],
            tool_input={"command": "rm a.txt"},
            agent_id="devops", session_id="sess-1",
        )
        _, t2 = _issue_token(
            guard, operation="rm b.txt", scope=["b.txt"],
            tool_input={"command": "rm b.txt"},
            agent_id="engineer", session_id="sess-1",
        )
        assert t1.sequence_number == 1
        assert t2.sequence_number == 1


class TestDSACAtomicConsumeToken:
    """validate_and_consume_token is atomic."""

    def test_validate_and_consume_returns_valid(self, tmp_project):
        guard = DSACGuard(tmp_project)
        _, token = _issue_token(guard)

        valid, reason = guard.validate_and_consume_token(
            token.token, token.operation_hash, "devops",
            session_id=token.session_id,
        )
        assert valid
        assert "consumed" in reason.lower()

    def test_second_validate_and_consume_fails(self, tmp_project):
        guard = DSACGuard(tmp_project)
        _, token = _issue_token(guard)

        valid1, _ = guard.validate_and_consume_token(
            token.token, token.operation_hash, "devops",
            session_id=token.session_id,
        )
        assert valid1

        valid2, reason = guard.validate_and_consume_token(
            token.token, token.operation_hash, "devops",
            session_id=token.session_id,
        )
        assert not valid2
        assert "already used" in reason.lower()


class TestDSACReinitiationDetection:
    """Detect re-initiated D-SAC requests after compaction."""

    def test_first_request_has_no_warning(self, tmp_project):
        guard = DSACGuard(tmp_project)
        preview = guard.create_dry_run_preview(
            "Bash", "rm old.txt", ["old.txt"],
            session_id="sess-1", agent_id="devops",
        )
        assert preview.reinitiation_count == 0
        assert not preview.blocked

    def test_second_request_triggers_warning(self, tmp_project):
        guard = DSACGuard(tmp_project)
        # First: issue token (records in sequence)
        _issue_token(
            guard, session_id="sess-1", agent_id="devops",
        )
        # Second: new preview shows warning
        p2 = guard.create_dry_run_preview(
            "Bash", "rm -rf ./data", ["data/a.txt", "data/b.txt"],
            session_id="sess-1", agent_id="devops",
        )
        assert p2.reinitiation_count == 1
        assert "RE-INITIATION WARNING" in p2.to_human_readable()

    def test_max_reinitiations_returns_blocked_preview(self, tmp_project):
        """N5: Hard block returns DryRunPreview(blocked=True)."""
        guard = DSACGuard(tmp_project)
        for i in range(DSAC_MAX_REINITIATIONS):
            _issue_token(
                guard,
                operation=f"rm file{i}.txt",
                scope=[f"file{i}.txt"],
                tool_input={"command": f"rm file{i}.txt"},
                session_id="sess-1",
                agent_id="devops",
            )
        # Next request returns blocked preview
        preview = guard.create_dry_run_preview(
            "Bash", "rm everything", ["everything"],
            session_id="sess-1", agent_id="devops",
        )
        assert preview.blocked
        assert "hard block" in preview.blocked_reason.lower()
        assert "D-SAC HARD BLOCK" in preview.to_human_readable()

    def test_reinitiation_count_reads_from_sequence_not_tokens(
        self, tmp_project
    ):
        """N1: count_reinitiations reads from dsac_sequence.json."""
        guard = DSACGuard(tmp_project)
        _issue_token(guard, session_id="sess-1", agent_id="devops")

        # Clean up expired tokens (would have deleted in v2)
        guard.cleanup_expired()

        # Count should still be 1 (reads from sequence, not tokens)
        assert guard.count_reinitiations("sess-1", "devops") == 1

    def test_from_dict_ignores_unknown_keys(self):
        data = {
            "token": "abc",
            "operation_hash": "def",
            "agent_id": "devops",
            "task_id": "t1",
            "issued_at": 1.0,
            "expires_at": 9999999999.0,
            "operation_description": "rm old.txt",
            "scope_size": 5,
            "future_field": True,
        }
        token = ApprovalToken.from_dict(data)
        assert token.token == "abc"
        assert token.agent_id == "devops"


class TestDSACSessionIdFallback:
    """B3: Persistent session_id via dsac_session.txt."""

    def test_generates_session_id_when_none_provided(self, tmp_project):
        guard = DSACGuard(tmp_project)
        sid = guard.get_or_create_session_id("")
        assert sid.startswith("dsac-")
        assert len(sid) > 10

    def test_persists_session_id_to_file(self, tmp_project):
        guard = DSACGuard(tmp_project)
        sid1 = guard.get_or_create_session_id("")
        # Second call reads from file
        sid2 = guard.get_or_create_session_id("")
        assert sid1 == sid2

    def test_hook_session_id_takes_priority(self, tmp_project):
        guard = DSACGuard(tmp_project)
        # First generate a persistent ID
        guard.get_or_create_session_id("")
        # Hook session_id overrides it
        sid = guard.get_or_create_session_id("hook-sess-123")
        assert sid == "hook-sess-123"

    def test_never_returns_empty_string(self, tmp_project):
        guard = DSACGuard(tmp_project)
        sid = guard.get_or_create_session_id("")
        assert sid != ""


class TestDSACCleanupExpired:
    """N8: cleanup_expired only removes expired+used tokens."""

    def test_keeps_unexpired_unused_tokens(self, tmp_project):
        guard = DSACGuard(tmp_project)
        _issue_token(guard, ttl_seconds=3600)  # Long TTL
        removed = guard.cleanup_expired()
        assert removed == 0
        assert len(guard._load_tokens()) == 1

    def test_keeps_expired_unused_tokens(self, tmp_project):
        guard = DSACGuard(tmp_project)
        _issue_token(guard, ttl_seconds=0)
        time.sleep(0.01)
        removed = guard.cleanup_expired()
        assert removed == 0  # Expired but NOT used -- keep as history

    def test_removes_expired_and_used_tokens(self, tmp_project):
        guard = DSACGuard(tmp_project)
        _, token = _issue_token(guard, ttl_seconds=0)
        time.sleep(0.01)
        # Consume it (already expired, will be marked used)
        guard.validate_and_consume_token(
            token.token, token.operation_hash, "devops",
            session_id=token.session_id,
        )
        removed = guard.cleanup_expired()
        assert removed == 1
        assert len(guard._load_tokens()) == 0


class TestComputeOperationHashForToolCall:
    """Hash function used by both issue and guardian."""

    def test_strips_dsac_token_key(self):
        h1 = compute_operation_hash_for_tool_call(
            "Bash", {"command": "rm -rf ./data"}
        )
        h2 = compute_operation_hash_for_tool_call(
            "Bash",
            {"command": "rm -rf ./data", "__dsac_token": "abc123"},
        )
        assert h1 == h2

    # [v3.1 Fix H] NOT IMPLEMENT -- the test below (`test_bash_uses_command_field_only`)
    # contained an incorrect assertion (assert h1 != h2) and is fully replaced by
    # `test_bash_uses_only_command_field` which correctly verifies the behavior.
    # DO NOT add test_bash_uses_command_field_only back.

    def test_bash_uses_only_command_field(self):
        """Bash hashing ignores extra keys like timeout."""
        h1 = compute_operation_hash_for_tool_call(
            "Bash", {"command": "rm -rf ./data"}
        )
        h2 = compute_operation_hash_for_tool_call(
            "Bash", {"command": "rm -rf ./data", "timeout": 30}
        )
        assert h1 == h2

    def test_different_commands_different_hashes(self):
        h1 = compute_operation_hash_for_tool_call(
            "Bash", {"command": "rm staging"}
        )
        h2 = compute_operation_hash_for_tool_call(
            "Bash", {"command": "rm production"}
        )
        assert h1 != h2

    def test_string_input(self):
        h = compute_operation_hash_for_tool_call("Bash", "rm -rf ./data")
        assert isinstance(h, str)
        assert len(h) == 64  # sha256 hex

    def test_non_bash_dict_uses_full_json(self):
        h1 = compute_operation_hash_for_tool_call(
            "mcp__supabase__execute_sql",
            {"query": "DELETE FROM logs"},
        )
        h2 = compute_operation_hash_for_tool_call(
            "mcp__supabase__execute_sql",
            {"query": "DELETE FROM users"},
        )
        assert h1 != h2
