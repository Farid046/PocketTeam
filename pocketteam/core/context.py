"""
SharedContext — In-process MCP message bus for agent-to-agent communication.
Artifacts pass between agents without IPC or network calls.

This is the "Artifact-First" design from gstack:
each agent picks up where the previous left off via the shared context.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class Artifact:
    """
    A named piece of output from an agent.
    Plans, reviews, code diffs, test results — all are artifacts.
    """
    name: str
    agent_id: str
    content: Any
    artifact_type: str     # "plan", "review", "diff", "test_result", "security_audit"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "agent_id": self.agent_id,
            "artifact_type": self.artifact_type,
            "created_at": self.created_at,
            "metadata": self.metadata,
            # Content stored separately (may be large)
        }


class SharedContext:
    """
    In-process shared context passed through the pipeline.
    Agents read from and write to this — no network calls needed.

    Persisted to disk so it survives crashes and context compaction.
    """

    def __init__(
        self,
        task_id: str,
        task_description: str,
        project_root: Path,
        plan_id: str | None = None,
    ) -> None:
        self.task_id = task_id
        self.task_description = task_description
        self.project_root = project_root
        self.plan_id = plan_id
        self.phase = "init"
        self.approved_files: list[str] = []
        self._artifacts: dict[str, Artifact] = {}
        self._messages: list[dict] = []  # Agent-to-agent messages
        self._metadata: dict[str, Any] = {}

        # Persistence path
        self._ctx_path = (
            project_root / ".pocketteam/sessions" / f"{task_id}.json"
        )

    # ── Artifact Management ────────────────────────────────────────────────

    def add_artifact(
        self,
        name: str,
        agent_id: str,
        content: Any,
        artifact_type: str,
        **metadata,
    ) -> Artifact:
        """Store an artifact from an agent."""
        artifact = Artifact(
            name=name,
            agent_id=agent_id,
            content=content,
            artifact_type=artifact_type,
            metadata=dict(metadata),
        )
        self._artifacts[name] = artifact
        self._persist()
        return artifact

    def get_artifact(self, name: str) -> Artifact | None:
        """Get an artifact by name."""
        return self._artifacts.get(name)

    def get_artifacts_by_type(self, artifact_type: str) -> list[Artifact]:
        """Get all artifacts of a given type."""
        return [a for a in self._artifacts.values() if a.artifact_type == artifact_type]

    def get_latest_plan(self) -> Artifact | None:
        """Get the most recent plan artifact."""
        plans = self.get_artifacts_by_type("plan")
        return plans[-1] if plans else None

    def get_latest_review(self) -> Artifact | None:
        """Get the most recent review artifact."""
        reviews = self.get_artifacts_by_type("review")
        return reviews[-1] if reviews else None

    # ── Messaging ────────────────────────────────────────────────────────────

    def send_message(self, from_agent: str, to_agent: str, content: str) -> None:
        """Agent-to-agent message."""
        self._messages.append({
            "from": from_agent,
            "to": to_agent,
            "content": content,
            "ts": datetime.now().isoformat(),
        })
        self._persist()

    def get_messages_for(self, agent_id: str) -> list[dict]:
        """Get all messages directed to an agent."""
        return [m for m in self._messages if m["to"] == agent_id]

    # ── Metadata ─────────────────────────────────────────────────────────────

    def set(self, key: str, value: Any) -> None:
        self._metadata[key] = value
        self._persist()

    def get(self, key: str, default: Any = None) -> Any:
        return self._metadata.get(key, default)

    # ── Phase Management ──────────────────────────────────────────────────────

    def advance_phase(self, new_phase: str) -> None:
        """Advance to the next pipeline phase."""
        self.phase = new_phase
        self._persist()

    # ── Human Gates ───────────────────────────────────────────────────────────

    def record_approval(self, gate: str, approved_by: str = "ceo") -> None:
        """Record a human gate approval."""
        self._metadata[f"approved_{gate}"] = {
            "by": approved_by,
            "at": datetime.now().isoformat(),
        }
        self._persist()

    def is_approved(self, gate: str) -> bool:
        return f"approved_{gate}" in self._metadata

    # ── Persistence ───────────────────────────────────────────────────────────

    def _persist(self) -> None:
        """Write context to disk (survives context compaction)."""
        try:
            self._ctx_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "task_id": self.task_id,
                "task_description": self.task_description,
                "phase": self.phase,
                "plan_id": self.plan_id,
                "approved_files": self.approved_files,
                "messages": self._messages,
                "metadata": self._metadata,
                "artifacts": {
                    name: {
                        **a.to_dict(),
                        "content": a.content if not isinstance(a.content, (dict, list)) else a.content,
                    }
                    for name, a in self._artifacts.items()
                },
            }
            self._ctx_path.write_text(json.dumps(data, indent=2, default=str))
        except Exception:
            pass  # Context persistence must never crash the pipeline

    @classmethod
    def load(cls, task_id: str, project_root: Path) -> SharedContext | None:
        """Load a previously persisted context."""
        ctx_path = project_root / ".pocketteam/sessions" / f"{task_id}.json"
        if not ctx_path.exists():
            return None

        try:
            data = json.loads(ctx_path.read_text())
            ctx = cls(
                task_id=data["task_id"],
                task_description=data["task_description"],
                project_root=project_root,
                plan_id=data.get("plan_id"),
            )
            ctx.phase = data.get("phase", "init")
            ctx.approved_files = data.get("approved_files", [])
            ctx._messages = data.get("messages", [])
            ctx._metadata = data.get("metadata", {})

            # Restore artifacts
            for name, a_data in data.get("artifacts", {}).items():
                ctx._artifacts[name] = Artifact(
                    name=a_data["name"],
                    agent_id=a_data["agent_id"],
                    content=a_data.get("content"),
                    artifact_type=a_data["artifact_type"],
                    created_at=a_data.get("created_at", ""),
                    metadata=a_data.get("metadata", {}),
                )
            return ctx
        except Exception:
            return None

    @classmethod
    def create_new(
        cls,
        task_description: str,
        project_root: Path,
    ) -> SharedContext:
        """Create a fresh context for a new task."""
        task_id = f"task-{uuid.uuid4().hex[:8]}"
        return cls(
            task_id=task_id,
            task_description=task_description,
            project_root=project_root,
        )
