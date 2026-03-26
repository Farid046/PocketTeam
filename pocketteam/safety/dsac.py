"""
Safety Layer 9: D-SAC Pattern
Dry-run → Staged → Approval → Commit

For ALL destructive operations that are plan-approved (Layer 2 passed).
Prevents the OpenClaw email-deletion scenario:
  "200+ emails deleted because there was no dry-run step"

Approval tokens are:
  - Time-limited (5 min)
  - Bound to specific operation + preview hash
  - Never stored in conversation context (survive compaction)
  - Invalidated by kill switch
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path

from ..constants import DSAC_APPROVAL_TOKEN_TTL, DSAC_MAX_BATCH_SIZE


@dataclass
class DryRunPreview:
    """Preview of what a destructive operation will do."""
    operation: str          # e.g. "DELETE FROM users WHERE id = 5"
    tool_name: str          # e.g. "Bash", "mcp__supabase__execute_sql"
    scope: list[str]        # List of items that will be affected
    item_count: int         # Total items affected
    is_reversible: bool     # Can this be undone? (git stash, DB backup)
    preview_hash: str       # sha256 of operation + scope
    timestamp: float = field(default_factory=time.time)

    def to_human_readable(self) -> str:
        """Format for display to CEO."""
        lines = [
            "⚠️  DESTRUCTIVE OPERATION PREVIEW",
            "",
            f"Operation: {self.operation}",
            f"Tool: {self.tool_name}",
            f"Items affected: {self.item_count}",
            f"Reversible: {'✅ Yes' if self.is_reversible else '❌ No'}",
            "",
            f"Scope ({min(self.item_count, 10)} of {self.item_count} shown):",
        ]
        for item in self.scope[:10]:
            lines.append(f"  - {item}")
        if self.item_count > 10:
            lines.append(f"  ... and {self.item_count - 10} more")
        lines.append("")
        lines.append(f"Preview hash: {self.preview_hash[:12]}...")
        return "\n".join(lines)


@dataclass
class ApprovalToken:
    """Time-limited token authorizing a specific destructive operation."""
    token: str
    operation_hash: str     # Must match the dry-run preview hash
    agent_id: str
    task_id: str
    issued_at: float
    expires_at: float
    max_batch_size: int = DSAC_MAX_BATCH_SIZE
    used: bool = False

    def is_valid(self) -> bool:
        return not self.used and time.time() < self.expires_at

    def is_expired(self) -> bool:
        return time.time() >= self.expires_at

    def to_dict(self) -> dict:
        return {
            "token": self.token,
            "operation_hash": self.operation_hash,
            "agent_id": self.agent_id,
            "task_id": self.task_id,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "max_batch_size": self.max_batch_size,
            "used": self.used,
        }


class DSACGuard:
    """
    Manages the D-SAC approval flow for destructive operations.
    Stored on disk — survives context compaction.
    """

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self._tokens_path = project_root / ".pocketteam/dsac_tokens.json"

    def _load_tokens(self) -> dict[str, dict]:
        if not self._tokens_path.exists():
            return {}
        try:
            return json.loads(self._tokens_path.read_text())
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_tokens(self, tokens: dict[str, dict]) -> None:
        self._tokens_path.parent.mkdir(parents=True, exist_ok=True)
        self._tokens_path.write_text(json.dumps(tokens, indent=2))
        # Restrict to owner read/write — approval tokens are sensitive credentials.
        os.chmod(self._tokens_path, 0o600)

    def create_dry_run_preview(
        self,
        tool_name: str,
        operation: str,
        scope: list[str],
        is_reversible: bool = False,
    ) -> DryRunPreview:
        """
        Step 1: Create a dry-run preview of what will happen.
        Returns preview with hash — agent shows this to CEO.
        """
        scope_str = json.dumps(sorted(scope))
        preview_hash = hashlib.sha256(
            f"{operation}:{scope_str}".encode()
        ).hexdigest()

        return DryRunPreview(
            operation=operation,
            tool_name=tool_name,
            scope=scope[:DSAC_MAX_BATCH_SIZE],
            item_count=len(scope),
            is_reversible=is_reversible,
            preview_hash=preview_hash,
        )

    def issue_approval_token(
        self,
        preview: DryRunPreview,
        agent_id: str,
        task_id: str,
        ttl_seconds: int = DSAC_APPROVAL_TOKEN_TTL,
    ) -> ApprovalToken:
        """
        Step 2+3: Issue a time-limited approval token after CEO approves.
        Token is stored on disk — not in conversation context.
        """
        token_str = secrets.token_urlsafe(32)
        now = time.time()

        token = ApprovalToken(
            token=token_str,
            operation_hash=preview.preview_hash,
            agent_id=agent_id,
            task_id=task_id,
            issued_at=now,
            expires_at=now + ttl_seconds,
        )

        # Persist to disk
        tokens = self._load_tokens()
        tokens[token_str] = token.to_dict()
        self._save_tokens(tokens)

        return token

    def validate_token(
        self,
        token_str: str,
        operation_hash: str,
        agent_id: str,
    ) -> tuple[bool, str]:
        """
        Step 4: Validate an approval token before executing destructive operation.
        Returns (is_valid, reason).
        """
        tokens = self._load_tokens()
        token_data = tokens.get(token_str)

        if not token_data:
            return False, "Approval token not found"

        token = ApprovalToken(**token_data)

        if token.used:
            return False, "Approval token already used"

        if token.is_expired():
            return False, f"Approval token expired at {token.expires_at}"

        if token.operation_hash != operation_hash:
            return False, "Approval token does not match this operation (hash mismatch)"

        if token.agent_id != agent_id:
            return False, f"Approval token issued for agent '{token.agent_id}', not '{agent_id}'"

        return True, "Token valid"

    def consume_token(self, token_str: str) -> None:
        """Mark a token as used (single-use)."""
        tokens = self._load_tokens()
        if token_str in tokens:
            tokens[token_str]["used"] = True
            self._save_tokens(tokens)

    def invalidate_all_tokens(self) -> int:
        """
        Invalidate ALL pending tokens (called by kill switch).
        Returns count of tokens invalidated.
        """
        tokens = self._load_tokens()
        count = sum(1 for t in tokens.values() if not t.get("used"))
        # Mark all as used
        for token in tokens.values():
            token["used"] = True
        self._save_tokens(tokens)
        return count

    def cleanup_expired(self) -> int:
        """Remove expired tokens from disk. Returns count removed."""
        tokens = self._load_tokens()
        now = time.time()
        to_remove = [
            k for k, v in tokens.items()
            if v.get("expires_at", 0) < now or v.get("used")
        ]
        for k in to_remove:
            del tokens[k]
        self._save_tokens(tokens)
        return len(to_remove)


def compute_operation_hash(operation: str, scope: list[str]) -> str:
    """Compute a deterministic hash for an operation + scope."""
    scope_str = json.dumps(sorted(scope))
    return hashlib.sha256(f"{operation}:{scope_str}".encode()).hexdigest()
