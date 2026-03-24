"""
Tests for Safety Layer 2: DESTRUCTIVE_PATTERNS
These require plan approval but are not absolutely forbidden.
"""

import pytest
from pocketteam.safety.rules import check_destructive


class TestDestructivePatterns:
    """Layer 2: Requires plan approval."""

    # ── rm -rf subdir ───────────────────────────────────────────────────────

    def test_blocks_rm_rf_subdir(self):
        result = check_destructive("Bash", "rm -rf ./data")
        assert not result.allowed
        assert result.requires_approval
        assert result.layer == 2

    def test_blocks_rm_rf_src(self):
        result = check_destructive("Bash", "rm -rf src/legacy")
        assert not result.allowed
        assert result.requires_approval

    def test_allows_rm_rf_node_modules(self):
        """node_modules is a safe delete target."""
        result = check_destructive("Bash", "rm -rf node_modules")
        assert result.allowed

    def test_allows_rm_rf_pycache(self):
        result = check_destructive("Bash", "rm -rf __pycache__")
        assert result.allowed

    def test_allows_rm_rf_dist(self):
        result = check_destructive("Bash", "rm -rf dist/")
        assert result.allowed

    def test_allows_rm_rf_build(self):
        result = check_destructive("Bash", "rm -rf build/")
        assert result.allowed

    # ── SQL mutations ────────────────────────────────────────────────────────

    def test_blocks_drop_table(self):
        result = check_destructive("Bash", "DROP TABLE users;")
        assert not result.allowed
        assert result.requires_approval

    def test_blocks_truncate(self):
        result = check_destructive("Bash", "TRUNCATE TABLE logs;")
        assert not result.allowed
        assert result.requires_approval

    def test_blocks_delete_without_where(self):
        result = check_destructive("Bash", "DELETE FROM sessions;")
        assert not result.allowed
        assert result.requires_approval

    # ── Git dangerous operations ─────────────────────────────────────────────

    def test_blocks_git_push_force(self):
        result = check_destructive("Bash", "git push origin main --force")
        assert not result.allowed
        assert result.requires_approval

    def test_blocks_git_push_force_flag(self):
        result = check_destructive("Bash", "git push --force origin feature/branch")
        assert not result.allowed
        assert result.requires_approval

    def test_blocks_git_reset_hard(self):
        result = check_destructive("Bash", "git reset --hard HEAD~1")
        assert not result.allowed
        assert result.requires_approval

    def test_blocks_git_clean(self):
        result = check_destructive("Bash", "git clean -fd")
        assert not result.allowed
        assert result.requires_approval

    def test_allows_git_push_no_force(self):
        result = check_destructive("Bash", "git push origin feature/my-branch")
        assert result.allowed

    def test_allows_git_reset_soft(self):
        result = check_destructive("Bash", "git reset --soft HEAD~1")
        assert result.allowed

    # ── Infrastructure ───────────────────────────────────────────────────────

    def test_blocks_kubectl_delete(self):
        result = check_destructive("Bash", "kubectl delete deployment my-app")
        assert not result.allowed

    def test_blocks_docker_rm_force(self):
        result = check_destructive("Bash", "docker rm -f my-container")
        assert not result.allowed

    def test_blocks_terraform_destroy(self):
        result = check_destructive("Bash", "terraform destroy -auto-approve")
        assert not result.allowed

    def test_blocks_systemctl_stop(self):
        result = check_destructive("Bash", "systemctl stop nginx")
        assert not result.allowed

    # ── Write tool — sensitive extensions ────────────────────────────────────

    def test_blocks_write_env_file(self):
        result = check_destructive("Write", ".env")
        assert not result.allowed

    def test_blocks_write_pem(self):
        result = check_destructive("Write", "server.pem")
        assert not result.allowed

    def test_blocks_write_key(self):
        result = check_destructive("Write", "private.key")
        assert not result.allowed

    def test_allows_write_env_example(self):
        """env.example is always safe."""
        result = check_destructive("Write", ".env.example")
        assert result.allowed

    def test_allows_write_python_file(self):
        result = check_destructive("Write", "src/auth.py")
        assert result.allowed

    # ── Normal Bash commands ─────────────────────────────────────────────────

    def test_allows_pytest(self):
        result = check_destructive("Bash", "python -m pytest tests/ -v")
        assert result.allowed

    def test_allows_npm_install(self):
        result = check_destructive("Bash", "npm install")
        assert result.allowed

    def test_allows_git_commit(self):
        result = check_destructive("Bash", "git commit -m 'feat: add auth'")
        assert result.allowed

    def test_allows_git_branch(self):
        result = check_destructive("Bash", "git checkout -b feature/user-auth")
        assert result.allowed

    # ── Safe delete bypass prevention (regression tests for substring check bug) ──

    def test_blocks_rm_rf_path_containing_pycache(self):
        """rm -rf /data/__pycache__/../../sensitive must NOT be allowed (path traversal)."""
        result = check_destructive("Bash", "rm -rf /data/__pycache__/../../sensitive")
        assert not result.allowed

    def test_blocks_rm_rf_path_with_pycache_subdirectory(self):
        """rm -rf /var/__pycache__ must NOT be allowed (has parent path)."""
        result = check_destructive("Bash", "rm -rf /var/__pycache__")
        assert not result.allowed

    def test_blocks_rm_rf_with_safe_name_in_comment(self):
        """rm -rf /data  # clean node_modules must NOT bypass — node_modules is in comment."""
        result = check_destructive("Bash", "rm -rf /data  # clean node_modules")
        assert not result.allowed

    def test_allows_multiple_safe_targets(self):
        """rm -rf dist/ build/ is fine — both are safe."""
        result = check_destructive("Bash", "rm -rf dist/ build/")
        assert result.allowed

    def test_allows_dotslash_safe_target(self):
        """rm -rf ./node_modules should be allowed."""
        result = check_destructive("Bash", "rm -rf ./node_modules")
        assert result.allowed
