"""
Safety Layer 8: Audit Log + Incident Playbooks
Immutable append-only log of every safety decision.
Every block, every allow of a sensitive operation — logged.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from ..constants import AUDIT_DIR
from ..utils import append_jsonl


class SafetyDecision(StrEnum):
    ALLOWED = "ALLOWED"
    DENIED = "DENIED"
    DENIED_NEVER_ALLOW = "DENIED_NEVER_ALLOW"
    DENIED_REQUIRES_APPROVAL = "DENIED_REQUIRES_APPROVAL"
    DENIED_MCP_UNSAFE = "DENIED_MCP_UNSAFE"
    DENIED_NETWORK = "DENIED_NETWORK"
    DENIED_SENSITIVE_FILE = "DENIED_SENSITIVE_FILE"
    DENIED_ALLOWLIST = "DENIED_ALLOWLIST"
    DENIED_RATE_LIMIT = "DENIED_RATE_LIMIT"
    DENIED_SCOPE = "DENIED_SCOPE"
    ALLOWED_WITH_APPROVAL = "ALLOWED_WITH_APPROVAL"
    KILL_SWITCH = "KILL_SWITCH"
    DENIED_DSAC_REINITIATION = "DENIED_DSAC_REINITIATION"
    DENIED_DSAC_SCOPE_ESCALATION = "DENIED_DSAC_SCOPE_ESCALATION"


class AuditLog:
    """
    Append-only audit log for all safety decisions.
    Never modifies existing entries — only appends.
    """

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self._log_dir = project_root / AUDIT_DIR
        try:
            self._log_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass  # Read-only or nonexistent path — log calls will silently fail

    def _log_path(self) -> Path:
        """Daily log file."""
        date = datetime.now().strftime("%Y-%m-%d")
        return self._log_dir / f"{date}.jsonl"

    def log(
        self,
        agent_id: str,
        tool_name: str,
        tool_input: Any,
        decision: SafetyDecision,
        layer: int | None,
        reason: str,
        task_id: str | None = None,
        plan_id: str | None = None,
    ) -> None:
        """Append a safety decision to the audit log."""
        # Hash the input — never store raw tool input (may contain secrets)
        input_str = json.dumps(tool_input, default=str) if not isinstance(tool_input, str) else tool_input
        input_hash = hashlib.sha256(input_str.encode()).hexdigest()[:16]

        entry = {
            "ts": datetime.now().isoformat(),
            "agent": agent_id,
            "tool": tool_name,
            "input_hash": f"sha256:{input_hash}",
            "decision": decision.value,
            "layer": layer,
            "reason": reason,
        }
        if task_id:
            entry["task_id"] = task_id
        if plan_id:
            entry["plan_id"] = plan_id

        try:
            append_jsonl(self._log_path(), entry)
        except OSError:
            # Audit log must never crash the safety system
            pass

        # Escalate immediately for Layer 1 blocks and kill switch
        if decision in (SafetyDecision.DENIED_NEVER_ALLOW, SafetyDecision.KILL_SWITCH):
            self._escalate_immediately(entry)

    def log_kill_switch(self, trigger_source: str, project_root: Path) -> None:
        """Log kill switch activation."""
        entry = {
            "ts": datetime.now().isoformat(),
            "agent": "system",
            "tool": "kill_switch",
            "input_hash": "n/a",
            "decision": SafetyDecision.KILL_SWITCH.value,
            "layer": 10,
            "reason": f"Kill switch activated via: {trigger_source}",
            "project": str(project_root),
        }
        try:
            append_jsonl(self._log_path(), entry)
        except OSError:
            pass

    def _escalate_immediately(self, entry: dict) -> None:
        """
        Write a CRITICAL alert to a separate high-priority file.
        The Telegram bot and monitoring pick this up immediately.
        """
        critical_path = self._log_dir / "CRITICAL_ALERTS.jsonl"
        try:
            append_jsonl(critical_path, {"alert": True, **entry})
        except OSError:
            pass

    def get_recent_denials(self, hours: int = 24) -> list[dict]:
        """Return recent denial events for the monitoring system."""
        results = []
        cutoff = datetime.now().timestamp() - (hours * 3600)

        for log_file in sorted(self._log_dir.glob("*.jsonl"), reverse=True):
            if log_file.name == "CRITICAL_ALERTS.jsonl":
                continue
            try:
                for line in log_file.read_text().splitlines():
                    entry = json.loads(line)
                    try:
                        ts = datetime.fromisoformat(entry.get("ts", "1970-01-01")).timestamp()
                    except ValueError:
                        ts = 0.0  # Treat corrupted timestamps as very old
                    if ts < cutoff:
                        continue
                    if "DENIED" in entry.get("decision", ""):
                        results.append(entry)
            except (OSError, json.JSONDecodeError):
                continue

        return results

    def get_stats(self) -> dict:
        """Return aggregate statistics from today's log."""
        stats: dict[str, int] = {
            "total": 0, "allowed": 0, "denied": 0,
            "layer1_blocks": 0, "mcp_blocks": 0,
            "network_blocks": 0, "sensitive_blocks": 0,
        }

        try:
            for line in self._log_path().read_text().splitlines():
                entry = json.loads(line)
                stats["total"] += 1
                decision = entry.get("decision", "")
                if "DENIED" in decision or "KILL" in decision:
                    stats["denied"] += 1
                    layer = entry.get("layer", 0)
                    if layer == 1:
                        stats["layer1_blocks"] += 1
                    elif layer == 3:
                        stats["mcp_blocks"] += 1
                    elif layer == 4:
                        stats["network_blocks"] += 1
                    elif layer == 5:
                        stats["sensitive_blocks"] += 1
                else:
                    stats["allowed"] += 1
        except (OSError, json.JSONDecodeError):
            pass

        return stats


# ─────────────────────────────────────────────────────────────────────────────
# Incident Playbooks
# Defines what to do when each safety layer fires
# ─────────────────────────────────────────────────────────────────────────────

INCIDENT_PLAYBOOKS = {
    1: {
        "name": "NEVER_ALLOW violation",
        "severity": "CRITICAL",
        "immediate_action": "Log + alert CEO immediately via Telegram",
        "agent_action": "Refuse and explain why this is never allowed",
        "escalate": True,
    },
    2: {
        "name": "Destructive pattern without approval",
        "severity": "HIGH",
        "immediate_action": "Log + request plan approval via D-SAC flow",
        "agent_action": "Pause and request plan approval before proceeding",
        "escalate": False,
    },
    3: {
        "name": "Unsafe MCP operation",
        "severity": "HIGH",
        "immediate_action": "Log + agent gets safe alternative suggestion",
        "agent_action": "Use parameterized queries or read-only alternative",
        "escalate": False,
    },
    4: {
        "name": "Unauthorized network access",
        "severity": "MEDIUM",
        "immediate_action": "Log + alert CEO (possible exfiltration attempt)",
        "agent_action": "Use only approved domains or request domain addition",
        "escalate": True,
    },
    5: {
        "name": "Sensitive file access",
        "severity": "HIGH",
        "immediate_action": "Log + agent gets safe alternative",
        "agent_action": "Use .env.example or environment variables",
        "escalate": False,
    },
    6: {
        "name": "Agent tool permission violation",
        "severity": "MEDIUM",
        "immediate_action": "Log + agent gets permission denied message",
        "agent_action": "Delegate to an agent with appropriate permissions",
        "escalate": False,
    },
    7: {
        "name": "Rate limit / budget exceeded",
        "severity": "MEDIUM",
        "immediate_action": "Log + escalate to CEO",
        "agent_action": "Stop and report progress to CEO",
        "escalate": True,
    },
    9: {
        "name": "D-SAC approval required",
        "severity": "MEDIUM",
        "immediate_action": "Generate approval token, await CEO confirmation",
        "agent_action": "Present dry-run preview and await approval",
        "escalate": False,
    },
    10: {
        "name": "Kill switch activated",
        "severity": "CRITICAL",
        "immediate_action": "Stop all agents, stash changes, notify CEO",
        "agent_action": "Terminate immediately",
        "escalate": True,
    },
}


def get_playbook(layer: int) -> dict:
    """Get the incident playbook for a given safety layer."""
    return INCIDENT_PLAYBOOKS.get(layer, {
        "name": f"Unknown layer {layer}",
        "severity": "MEDIUM",
        "immediate_action": "Log and investigate",
        "agent_action": "Pause and await instructions",
        "escalate": False,
    })
