"""
Tests for Safety Layer 9: D-SAC Pattern
Dry-run → Staged → Approval → Commit
"""

import time
import pytest
from pathlib import Path
from pocketteam.safety.dsac import DSACGuard, DryRunPreview, compute_operation_hash


@pytest.fixture
def tmp_project(tmp_path):
    """Create a temporary project directory."""
    (tmp_path / ".pocketteam").mkdir()
    return tmp_path


class TestDSACPattern:
    """Layer 9: D-SAC approval flow."""

    def test_dry_run_creates_preview(self, tmp_project):
        guard = DSACGuard(tmp_project)
        preview = guard.create_dry_run_preview(
            tool_name="Bash",
            operation="rm -rf ./old-data",
            scope=["old-data/file1.txt", "old-data/file2.txt"],
            is_reversible=False,
        )

        assert isinstance(preview, DryRunPreview)
        assert preview.item_count == 2
        assert preview.preview_hash
        assert not preview.is_reversible

    def test_preview_hash_is_deterministic(self, tmp_project):
        guard = DSACGuard(tmp_project)
        scope = ["users.csv", "logs.txt"]

        p1 = guard.create_dry_run_preview("Bash", "rm files", scope)
        p2 = guard.create_dry_run_preview("Bash", "rm files", scope)

        assert p1.preview_hash == p2.preview_hash

    def test_different_operations_have_different_hashes(self, tmp_project):
        guard = DSACGuard(tmp_project)
        p1 = guard.create_dry_run_preview("Bash", "rm file1.txt", ["file1.txt"])
        p2 = guard.create_dry_run_preview("Bash", "rm file2.txt", ["file2.txt"])

        assert p1.preview_hash != p2.preview_hash

    def test_issue_approval_token(self, tmp_project):
        guard = DSACGuard(tmp_project)
        preview = guard.create_dry_run_preview("Bash", "rm old.txt", ["old.txt"])

        token = guard.issue_approval_token(
            preview=preview,
            agent_id="devops",
            task_id="task-001",
        )

        assert token.token
        assert token.agent_id == "devops"
        assert token.is_valid()
        assert not token.is_expired()

    def test_token_validates_correctly(self, tmp_project):
        guard = DSACGuard(tmp_project)
        preview = guard.create_dry_run_preview("Bash", "rm old.txt", ["old.txt"])
        token = guard.issue_approval_token(preview, "devops", "task-001")

        valid, reason = guard.validate_token(token.token, preview.preview_hash, "devops")
        assert valid
        assert "valid" in reason.lower()

    def test_token_invalid_for_wrong_operation(self, tmp_project):
        guard = DSACGuard(tmp_project)
        preview = guard.create_dry_run_preview("Bash", "rm file1.txt", ["file1.txt"])
        token = guard.issue_approval_token(preview, "devops", "task-001")

        wrong_hash = compute_operation_hash("rm file2.txt", ["file2.txt"])
        valid, reason = guard.validate_token(token.token, wrong_hash, "devops")
        assert not valid
        assert "hash mismatch" in reason.lower()

    def test_token_invalid_for_wrong_agent(self, tmp_project):
        guard = DSACGuard(tmp_project)
        preview = guard.create_dry_run_preview("Bash", "rm old.txt", ["old.txt"])
        token = guard.issue_approval_token(preview, "devops", "task-001")

        valid, reason = guard.validate_token(token.token, preview.preview_hash, "engineer")
        assert not valid
        assert "devops" in reason.lower()

    def test_token_single_use(self, tmp_project):
        guard = DSACGuard(tmp_project)
        preview = guard.create_dry_run_preview("Bash", "rm old.txt", ["old.txt"])
        token = guard.issue_approval_token(preview, "devops", "task-001")

        # First use: valid
        valid, _ = guard.validate_token(token.token, preview.preview_hash, "devops")
        assert valid

        # Consume it
        guard.consume_token(token.token)

        # Second use: invalid
        valid, reason = guard.validate_token(token.token, preview.preview_hash, "devops")
        assert not valid
        assert "already used" in reason.lower()

    def test_expired_token_is_invalid(self, tmp_project):
        guard = DSACGuard(tmp_project)
        preview = guard.create_dry_run_preview("Bash", "rm old.txt", ["old.txt"])
        token = guard.issue_approval_token(
            preview, "devops", "task-001",
            ttl_seconds=0,  # Expired immediately
        )

        time.sleep(0.01)  # Ensure expiry
        valid, reason = guard.validate_token(token.token, preview.preview_hash, "devops")
        assert not valid
        assert "expired" in reason.lower()

    def test_token_not_found(self, tmp_project):
        guard = DSACGuard(tmp_project)
        valid, reason = guard.validate_token("fake-token", "fake-hash", "devops")
        assert not valid
        assert "not found" in reason.lower()

    def test_invalidate_all_tokens_on_kill(self, tmp_project):
        guard = DSACGuard(tmp_project)

        # Create multiple tokens
        for i in range(3):
            preview = guard.create_dry_run_preview("Bash", f"rm file{i}.txt", [f"file{i}.txt"])
            guard.issue_approval_token(preview, "devops", "task-001")

        count = guard.invalidate_all_tokens()
        assert count == 3

        # All tokens should now be invalid
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
        )

        text = preview.to_human_readable()
        assert "DESTRUCTIVE OPERATION PREVIEW" in text
        assert "DELETE FROM old_logs" in text
        assert "15" in text  # Total items
        assert "more" in text  # Truncation notice (shows items beyond 10)
        assert "❌ No" in text  # Not reversible

    def test_tokens_persist_across_instances(self, tmp_project):
        """Tokens survive between DSACGuard instances (survives context compaction)."""
        guard1 = DSACGuard(tmp_project)
        preview = guard1.create_dry_run_preview("Bash", "rm old.txt", ["old.txt"])
        token = guard1.issue_approval_token(preview, "devops", "task-001")

        # New instance (simulates context compaction / process restart)
        guard2 = DSACGuard(tmp_project)
        valid, _ = guard2.validate_token(token.token, preview.preview_hash, "devops")
        assert valid
