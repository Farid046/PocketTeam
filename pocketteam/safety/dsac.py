"""
Safety Layer 9: D-SAC Pattern
Dry-run -> Staged -> Approval -> Commit

For ALL destructive operations that are plan-approved (Layer 2 passed).
Prevents the OpenClaw email-deletion scenario:
  "200+ emails deleted because there was no dry-run step"

Approval tokens are:
  - Time-limited (5 min)
  - Bound to specific operation via tool-call hash (NOT preview hash)
  - Bound to agent_id and session_id
  - Never stored in conversation context (survive compaction)
  - Single-use (atomic validate-and-consume)

v3 changes from v2:
  - tool_name/tool_input REQUIRED on issue_approval_token (B1)
  - validate_token() REMOVED -- only validate_and_consume_token() (N2)
  - Re-initiation history in dsac_sequence.json, not dsac_tokens.json (N1)
  - create_dry_run_preview() requires session_id/agent_id (N4)
  - DryRunPreview.blocked field instead of ValueError (N5)
  - cleanup_expired() only removes expired+used tokens (N8)
  - Lock file created with 0o600 permissions (N7)
  - Persistent session_id fallback via dsac_session.txt (B3)
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import secrets
import tempfile
import time
from dataclasses import dataclass, field, fields
from pathlib import Path

from ..constants import (
    DSAC_APPROVAL_TOKEN_TTL,
    DSAC_MAX_BATCH_SIZE,
    DSAC_MAX_REINITIATIONS,
    DSAC_SEQUENCE_FILE,
    DSAC_SESSION_FILE,
    DSAC_TOKEN_INPUT_KEY,
    DSAC_TOKEN_STALE_THRESHOLD,
)


@dataclass
class DryRunPreview:
    """Preview of what a destructive operation will do."""

    operation: str  # e.g. "DELETE FROM users WHERE id = 5"
    tool_name: str  # e.g. "Bash", "mcp__supabase__execute_sql"
    scope: list[str]  # List of items that will be affected
    item_count: int  # Total items affected
    is_reversible: bool  # Can this be undone? (git stash, DB backup)
    preview_hash: str  # sha256 of operation + scope (human-readable identity)
    timestamp: float = field(default_factory=time.time)
    reinitiation_count: int = 0
    previous_operations: list[str] = field(default_factory=list)
    blocked: bool = False  # v3 N5: True when DSAC_MAX_REINITIATIONS exceeded
    blocked_reason: str = ""  # v3 N5: Explanation when blocked=True

    def to_human_readable(self) -> str:
        """Format for display to CEO."""
        lines = []

        # v3 N5: Hard block message
        if self.blocked:
            lines.extend([
                "!! D-SAC HARD BLOCK !!",
                self.blocked_reason,
                "",
                "Action required: CEO must intervene (press Esc in Claude Code).",
                "",
            ])
            return "\n".join(lines)

        # Re-initiation warning -- MUST be first
        if self.reinitiation_count > 0:
            lines.extend([
                "!! RE-INITIATION WARNING !!",
                f"This agent has already requested D-SAC approval"
                f" {self.reinitiation_count} time(s)",
                "in this session. This may indicate context compaction caused"
                " the agent",
                "to forget its previous approval and request a NEW (possibly"
                " expanded) scope.",
                f"Previous operation hashes:"
                f" {', '.join(self.previous_operations)}",
                "Compare the scope below with the original request before"
                " approving.",
                "",
            ])

        lines.extend([
            "!! DESTRUCTIVE OPERATION PREVIEW",
            "",
            f"Operation: {self.operation}",
            f"Tool: {self.tool_name}",
            f"Items affected: {self.item_count}",
            f"Reversible: {'Yes' if self.is_reversible else 'No'}",
            "",
            f"Scope ({min(self.item_count, 10)} of {self.item_count} shown):",
        ])
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
    operation_hash: str  # Hash from compute_operation_hash_for_tool_call()
    agent_id: str
    task_id: str
    issued_at: float
    expires_at: float
    max_batch_size: int = DSAC_MAX_BATCH_SIZE
    used: bool = False
    session_id: str = ""
    sequence_number: int = 0

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
            "session_id": self.session_id,
            "sequence_number": self.sequence_number,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ApprovalToken:
        """Create from dict, ignoring unknown keys (forward compatibility).

        Token dicts on disk may contain extra metadata keys like
        'operation_description' or 'scope_size' that are not part of
        the dataclass. This classmethod filters them out to prevent
        TypeError on construction.
        """
        known = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


class DSACGuard:
    """
    Manages the D-SAC approval flow for destructive operations.
    Stored on disk -- survives context compaction.
    """

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self._tokens_path = project_root / ".pocketteam" / "dsac_tokens.json"
        self._sequence_path = (
            project_root / ".pocketteam" / DSAC_SEQUENCE_FILE
        )
        self._lock_path = project_root / ".pocketteam" / "dsac_tokens.lock"
        self._sequence_lock_path = (
            project_root / ".pocketteam" / "dsac_sequence.lock"
        )
        self._session_path = (
            project_root / ".pocketteam" / DSAC_SESSION_FILE
        )

    # -- Token persistence ----------------------------------------------------

    def _load_tokens(self) -> dict[str, dict]:
        if not self._tokens_path.exists():
            return {}
        try:
            return json.loads(self._tokens_path.read_text())
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_tokens(self, tokens: dict[str, dict]) -> None:
        """Persist tokens atomically. chmod BEFORE replace."""
        self._tokens_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(
            dir=str(self._tokens_path.parent), suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(tokens, f, indent=2)
            os.chmod(tmp, 0o600)
            os.replace(tmp, str(self._tokens_path))
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    # -- Sequence state persistence (N1: separate from tokens) -----------------

    def _load_sequence_state(self) -> dict:
        """Load re-initiation history.

        Structure:
        {
            "<session_id>": {
                "<agent_id>": {
                    "count": int,
                    "history": [
                        {"operation_hash": str, "timestamp": float,
                         "operation_description": str, "scope_size": int}
                    ]
                }
            }
        }
        """
        if not self._sequence_path.exists():
            return {}
        try:
            return json.loads(self._sequence_path.read_text())
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_sequence_state(self, state: dict) -> None:
        """Persist sequence counters atomically."""
        self._sequence_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(
            dir=str(self._sequence_path.parent), suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(state, f, indent=2)
            os.chmod(tmp, 0o600)
            os.replace(tmp, str(self._sequence_path))
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def _next_sequence_and_record(
        self,
        session_id: str,
        agent_id: str,
        operation_hash: str,
        operation_description: str,
        scope_size: int,
    ) -> int:
        """Atomically increment sequence counter AND record history entry (Fix 3).

        Single load-modify-save prevents race conditions where parallel calls
        to _next_sequence_number() + _record_request_in_sequence() could
        produce colliding sequence numbers or lost history entries.

        Returns the new (incremented) sequence number.
        """
        self._sequence_lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_fd = os.open(
            str(self._sequence_lock_path), os.O_CREAT | os.O_RDWR, 0o600
        )
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            state = self._load_sequence_state()
            session_state = state.setdefault(session_id, {})
            agent_state = session_state.setdefault(
                agent_id, {"count": 0, "history": []}
            )
            current = agent_state.get("count", 0)
            next_seq = current + 1
            agent_state["count"] = next_seq
            agent_state["history"].append({
                "operation_hash": operation_hash,
                "timestamp": time.time(),
                "operation_description": operation_description[:200],
                "scope_size": scope_size,
            })
            self._save_sequence_state(state)
            return next_seq
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)

    # -- Session ID management (B3) -------------------------------------------

    def get_or_create_session_id(self, hook_session_id: str = "") -> str:
        """Resolve session_id with fallback chain (B3).

        Priority:
        1. hook_session_id (from hook_input or env var) -- if non-empty
        2. Persistent file .pocketteam/dsac_session.txt -- if exists
        3. Generate new one, persist it, return it

        NEVER returns empty string.
        """
        if hook_session_id:
            return hook_session_id

        # Try persistent file
        if self._session_path.exists():
            try:
                stored = self._session_path.read_text().strip()
                if stored:
                    return stored
            except OSError:
                pass

        # Generate new session ID and persist atomically
        new_id = f"dsac-{secrets.token_hex(8)}"
        try:
            self._session_path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(
                dir=str(self._session_path.parent), suffix=".tmp"
            )
            try:
                with os.fdopen(fd, "w") as f:
                    f.write(new_id)
                os.chmod(tmp, 0o600)
                os.replace(tmp, str(self._session_path))
            except Exception:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
                raise
        except OSError:
            pass  # If write fails, still return the generated ID
        return new_id

    # -- Re-initiation detection (N1: reads from sequence, not tokens) --------

    def count_reinitiations(self, session_id: str, agent_id: str) -> int:
        """Count how many D-SAC requests recorded for this session+agent.

        Reads from dsac_sequence.json (N1), NOT dsac_tokens.json.
        Returns 0 for no prior requests, 1 for first re-initiation, etc.
        """
        state = self._load_sequence_state()
        session_state = state.get(session_id, {})
        agent_state = session_state.get(agent_id, {})
        return len(agent_state.get("history", []))

    def get_request_history(
        self, session_id: str, agent_id: str
    ) -> list[dict]:
        """Return all D-SAC request records for a session+agent pair.

        Reads from dsac_sequence.json (N1). This data is NEVER cleaned
        by cleanup_expired().
        """
        state = self._load_sequence_state()
        session_state = state.get(session_id, {})
        agent_state = session_state.get(agent_id, {})
        history = agent_state.get("history", [])
        return sorted(history, key=lambda h: h.get("timestamp", 0))

    # -- Core D-SAC flow ------------------------------------------------------

    def create_dry_run_preview(
        self,
        tool_name: str,
        operation: str,
        scope: list[str],
        is_reversible: bool = False,
        *,
        session_id: str,
        agent_id: str,
    ) -> DryRunPreview:
        """Step 1: Create a dry-run preview of what will happen.

        Returns preview with hash -- agent shows this to CEO.
        session_id and agent_id are REQUIRED (N4, keyword-only).

        If DSAC_MAX_REINITIATIONS is exceeded, returns a DryRunPreview
        with blocked=True (N5). Does NOT raise ValueError.
        """
        scope_str = json.dumps(sorted(scope))
        preview_hash = hashlib.sha256(
            f"{operation}:{scope_str}".encode()
        ).hexdigest()

        reinit_count = self.count_reinitiations(session_id, agent_id)

        # N5: Hard block as blocked DryRunPreview, not ValueError
        if reinit_count >= DSAC_MAX_REINITIATIONS:
            return DryRunPreview(
                operation=operation,
                tool_name=tool_name,
                scope=scope[:DSAC_MAX_BATCH_SIZE],
                item_count=len(scope),
                is_reversible=is_reversible,
                preview_hash=preview_hash,
                reinitiation_count=reinit_count,
                blocked=True,
                blocked_reason=(
                    f"D-SAC hard block: agent '{agent_id}' has exceeded the"
                    f" maximum re-initiation limit"
                    f" ({DSAC_MAX_REINITIATIONS}) in session"
                    f" '{session_id}'. This may indicate a"
                    " compaction-loop attack. Kill switch or CEO"
                    " intervention required."
                ),
            )

        preview = DryRunPreview(
            operation=operation,
            tool_name=tool_name,
            scope=scope[:DSAC_MAX_BATCH_SIZE],
            item_count=len(scope),
            is_reversible=is_reversible,
            preview_hash=preview_hash,
        )

        if reinit_count > 0:
            preview.reinitiation_count = reinit_count
            history = self.get_request_history(session_id, agent_id)
            preview.previous_operations = [
                h.get("operation_hash", "unknown")[:12] for h in history
            ]

        return preview

    def issue_approval_token(
        self,
        preview: DryRunPreview,
        agent_id: str,
        task_id: str,
        *,
        tool_name: str,
        tool_input: str | dict,
        session_id: str,
        ttl_seconds: int = DSAC_APPROVAL_TOKEN_TTL,
    ) -> ApprovalToken:
        """Step 2+3: Issue a time-limited approval token after CEO approves.

        Token is stored on disk -- survives context compaction.

        B1 FIX: tool_name, tool_input, session_id are REQUIRED
        (keyword-only, no defaults). The operation_hash stored in the
        token is computed from the actual tool call via
        compute_operation_hash_for_tool_call(), NOT from preview_hash.
        This ensures Guardian's hash (computed from the real command)
        matches the stored hash.
        """
        if not session_id:
            raise ValueError("issue_approval_token: session_id must not be empty")

        token_str = secrets.token_urlsafe(32)
        now = time.time()

        # B1: Compute hash from actual tool call, not preview
        op_hash = compute_operation_hash_for_tool_call(tool_name, tool_input)

        # Fix 3: Atomically increment sequence number AND record history in one
        # load-modify-save, preventing race conditions from parallel token issuance.
        seq = self._next_sequence_and_record(
            session_id=session_id,
            agent_id=agent_id,
            operation_hash=op_hash,
            operation_description=preview.operation,
            scope_size=preview.item_count,
        )

        token = ApprovalToken(
            token=token_str,
            operation_hash=op_hash,
            agent_id=agent_id,
            task_id=task_id,
            issued_at=now,
            expires_at=now + ttl_seconds,
            session_id=session_id,
            sequence_number=seq,
        )

        # Persist token to disk
        tokens = self._load_tokens()
        token_dict = token.to_dict()
        # Extra metadata for debugging (not part of ApprovalToken fields)
        token_dict["operation_description"] = preview.operation[:200]
        token_dict["scope_size"] = preview.item_count
        tokens[token_str] = token_dict
        self._save_tokens(tokens)

        return token

    def validate_and_consume_token(
        self,
        token_str: str,
        operation_hash: str,
        agent_id: str,
        *,
        session_id: str,
    ) -> tuple[bool, str]:
        """Atomically validate AND consume a D-SAC token.

        Uses fcntl.flock for mutual exclusion so that two parallel agents
        cannot both validate the same token before either consumes it.

        Returns (is_valid, reason).

        The operation_hash parameter is computed by the CALLER (Guardian)
        from the actual tool call -- NOT supplied by the agent.
        """
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)

        # N7: Create lock file with 0o600 permissions
        lock_fd = os.open(
            str(self._lock_path), os.O_CREAT | os.O_RDWR, 0o600
        )
        try:
            # Acquire exclusive lock -- blocks if another process holds it
            fcntl.flock(lock_fd, fcntl.LOCK_EX)

            tokens = self._load_tokens()
            token_data = tokens.get(token_str)

            if not token_data:
                return False, "Approval token not found"

            token = ApprovalToken.from_dict(token_data)

            if token.used:
                return False, "Approval token already used"

            if token.is_expired():
                # Mark as used so cleanup_expired can remove it (N8)
                tokens[token_str]["used"] = True
                self._save_tokens(tokens)
                return False, f"Approval token expired at {token.expires_at}"

            if token.operation_hash != operation_hash:
                return False, (
                    "Operation hash mismatch: the command being executed"
                    " does not match what was approved. This may indicate"
                    " a scope escalation attempt."
                )

            if token.agent_id != agent_id:
                return False, (
                    f"Approval token issued for agent '{token.agent_id}',"
                    f" not '{agent_id}'"
                )

            # Session binding check — strict equality, no bypass via empty string
            if token.session_id != session_id:
                return False, (
                    f"Session mismatch: token={token.session_id!r},"
                    f" caller={session_id!r}"
                )

            # ---- ATOMIC CONSUME ----
            tokens[token_str]["used"] = True
            self._save_tokens(tokens)

            return True, "Token valid and consumed"

        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)

    # N2: validate_token() is REMOVED. Only validate_and_consume_token()
    # exists. No read-only validation path.

    def invalidate_all_tokens(self) -> int:
        """Invalidate ALL pending tokens.

        Returns count of tokens invalidated.
        """
        tokens = self._load_tokens()
        count = sum(1 for t in tokens.values() if not t.get("used"))
        for token in tokens.values():
            token["used"] = True
        self._save_tokens(tokens)
        return count

    def cleanup_expired(self) -> int:
        """Remove expired tokens in two passes.

        Pass 1 (N8): expired+used tokens are fully spent -- remove immediately.
        Pass 2 (stale pruning): expired+unused tokens that are older than
        DSAC_TOKEN_STALE_THRESHOLD seconds are orphaned (never validated in
        the normal D-SAC flow window) -- remove to prevent unbounded growth.

        Unexpired tokens stay regardless of used status.

        Returns total count removed.
        """
        tokens = self._load_tokens()
        now = time.time()

        to_remove: list[str] = []

        for k, v in tokens.items():
            expires_at = v.get("expires_at", 0)
            is_expired = expires_at < now
            if not is_expired:
                continue
            if v.get("used"):
                # Pass 1: expired+used -- always remove
                to_remove.append(k)
            elif (now - expires_at) > DSAC_TOKEN_STALE_THRESHOLD:
                # Pass 2: expired+unused but stale beyond threshold -- remove
                to_remove.append(k)

        for k in to_remove:
            del tokens[k]
        if to_remove:
            self._save_tokens(tokens)
        return len(to_remove)


# -- Module-level hash functions -----------------------------------------------


def compute_operation_hash(operation: str, scope: list[str]) -> str:
    """Compute a deterministic hash for an operation + scope.

    This is the PREVIEW hash -- used for human-readable display only.
    NOT used for token validation (that uses
    compute_operation_hash_for_tool_call).
    """
    scope_str = json.dumps(sorted(scope))
    return hashlib.sha256(f"{operation}:{scope_str}".encode()).hexdigest()


def compute_operation_hash_for_tool_call(
    tool_name: str,
    tool_input: str | dict,
) -> str:
    """Compute a deterministic hash for a tool call.

    CRITICAL: This function must be used by BOTH:
    1. issue_approval_token() -- when storing the hash in the token
    2. Guardian._check_dsac_token() -- when validating the token

    The hash is computed from tool_name + canonical form of tool_input,
    with the __dsac_token key stripped from dict inputs so the token
    itself does not affect the operation identity.

    For Bash tools: uses the 'command' field only.
    For other dict tools: uses the full dict minus __dsac_token.
    For string tools: uses the string as-is.
    """
    if isinstance(tool_input, dict):
        clean = {
            k: v
            for k, v in tool_input.items()
            if k != DSAC_TOKEN_INPUT_KEY
        }
        if tool_name == "Bash" and "command" in clean:
            canonical = clean["command"]
        else:
            canonical = json.dumps(clean, sort_keys=True, default=str)
    else:
        canonical = str(tool_input)

    return hashlib.sha256(
        f"{tool_name}:{canonical}".encode()
    ).hexdigest()
