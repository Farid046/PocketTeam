"""
Escalation — rules for when and how to escalate issues.

Escalation levels:
1. Auto-fix: Investigator → Engineer → QA → Deploy (staging-first)
2. CEO notification: Telegram alert with diagnosis
3. Full stop: Kill switch + CEO alert (critical failures)
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..constants import (
    EVENTS_FILE,
    INCIDENTS_DIR,
    MAX_AUTO_FIX_ATTEMPTS,
)


@dataclass
class Incident:
    """A tracked production incident."""
    incident_id: str
    severity: str  # "low", "medium", "high", "critical"
    description: str
    detected_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%S"))
    fix_attempts: int = 0
    resolved: bool = False
    resolved_at: Optional[str] = None
    resolution: str = ""
    escalated_to_ceo: bool = False

    def to_dict(self) -> dict:
        return {
            "incident_id": self.incident_id,
            "severity": self.severity,
            "description": self.description,
            "detected_at": self.detected_at,
            "fix_attempts": self.fix_attempts,
            "resolved": self.resolved,
            "resolved_at": self.resolved_at,
            "resolution": self.resolution,
            "escalated_to_ceo": self.escalated_to_ceo,
        }


class EscalationManager:
    """
    Manages incident escalation with the 3-Strike Rule.

    After 3 failed auto-fix attempts → escalate to CEO.
    Critical issues → immediate CEO notification.
    All incidents are logged to .pocketteam/artifacts/incidents/.
    """

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self._incidents_dir = project_root / INCIDENTS_DIR
        self._active_incidents: dict[str, Incident] = {}

    def create_incident(
        self,
        incident_id: str,
        severity: str,
        description: str,
    ) -> Incident:
        """Create and track a new incident."""
        incident = Incident(
            incident_id=incident_id,
            severity=severity,
            description=description,
        )
        self._active_incidents[incident_id] = incident
        self._persist_incident(incident)
        return incident

    def record_fix_attempt(self, incident_id: str, success: bool) -> bool:
        """
        Record a fix attempt.
        Returns True if more attempts are allowed, False if escalation needed.
        """
        incident = self._active_incidents.get(incident_id)
        if not incident:
            return False

        incident.fix_attempts += 1

        if success:
            incident.resolved = True
            incident.resolved_at = time.strftime("%Y-%m-%dT%H:%M:%S")
            incident.resolution = f"Auto-fixed on attempt {incident.fix_attempts}"
            self._persist_incident(incident)
            return True

        self._persist_incident(incident)

        # 3-Strike Rule
        if incident.fix_attempts >= MAX_AUTO_FIX_ATTEMPTS:
            incident.escalated_to_ceo = True
            self._persist_incident(incident)
            return False

        return True

    def should_escalate(self, incident_id: str) -> bool:
        """Check if an incident should be escalated to CEO."""
        incident = self._active_incidents.get(incident_id)
        if not incident:
            return False

        # Critical severity → always escalate
        if incident.severity == "critical":
            return True

        # 3-Strike Rule
        if incident.fix_attempts >= MAX_AUTO_FIX_ATTEMPTS:
            return True

        return False

    def resolve_incident(self, incident_id: str, resolution: str) -> None:
        """Mark an incident as resolved."""
        incident = self._active_incidents.get(incident_id)
        if incident:
            incident.resolved = True
            incident.resolved_at = time.strftime("%Y-%m-%dT%H:%M:%S")
            incident.resolution = resolution
            self._persist_incident(incident)

    def get_active_incidents(self) -> list[Incident]:
        """Get all unresolved incidents."""
        return [i for i in self._active_incidents.values() if not i.resolved]

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        return self._active_incidents.get(incident_id)

    def _persist_incident(self, incident: Incident) -> None:
        """Save incident to disk."""
        try:
            self._incidents_dir.mkdir(parents=True, exist_ok=True)
            path = self._incidents_dir / f"{incident.incident_id}.json"
            path.write_text(json.dumps(incident.to_dict(), indent=2))
        except Exception:
            pass

    def load_incidents(self) -> None:
        """Load incidents from disk."""
        if not self._incidents_dir.exists():
            return

        for f in self._incidents_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                incident = Incident(**data)
                self._active_incidents[incident.incident_id] = incident
            except Exception:
                pass
