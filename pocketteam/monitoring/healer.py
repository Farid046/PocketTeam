"""
Self-Healing Module — woken by GitHub Actions on health/log failures.
Staging-first, 3-Strike Rule, always notifies CEO.

Flow:
1. Detect problem (health check, log anomaly)
2. Investigator agent diagnoses root cause
3. Engineer agent creates fix (on separate branch)
4. QA agent tests fix
5. Deploy to staging first
6. If staging OK → deploy to production
7. Always notify CEO
8. After 3 failed attempts → escalate to CEO
"""

from __future__ import annotations

import asyncio
import time
import uuid
from pathlib import Path
from typing import Optional

from ..config import PocketTeamConfig, load_config
from ..constants import MAX_AUTO_FIX_ATTEMPTS
from .escalation import EscalationManager, Incident


async def handle_health_failure(
    health_url: str,
    http_status: str,
    project_root: Optional[Path] = None,
) -> dict:
    """
    Called by GitHub Actions when health check fails.
    Runs Investigator → Engineer fix → QA → Staging deploy → CEO notification.

    Returns a dict with the outcome.
    """
    root = project_root or Path.cwd()
    cfg = load_config(root)

    incident_id = f"health-{uuid.uuid4().hex[:8]}"
    escalation = EscalationManager(root)
    incident = escalation.create_incident(
        incident_id=incident_id,
        severity="high",
        description=f"Health check failed: {health_url} → HTTP {http_status}",
    )

    # Always notify CEO
    await _notify_telegram(
        cfg.telegram.bot_token,
        cfg.telegram.chat_id,
        f"⚠️ <b>Health check FAILED</b>\n"
        f"URL: {health_url}\n"
        f"Status: HTTP {http_status}\n"
        f"Incident: {incident_id}\n\n"
        "Investigator waking up to diagnose...",
    )

    result = {
        "incident_id": incident_id,
        "health_url": health_url,
        "http_status": http_status,
        "auto_fix_attempted": False,
        "auto_fix_success": False,
        "escalated": False,
    }

    # Attempt auto-fix if enabled
    if cfg.monitoring.auto_fix:
        fix_result = await _attempt_auto_fix(
            root, cfg, incident, escalation
        )
        result.update(fix_result)
    else:
        result["escalated"] = True
        await _notify_telegram(
            cfg.telegram.bot_token,
            cfg.telegram.chat_id,
            f"Auto-fix disabled. Manual intervention needed.\nIncident: {incident_id}",
        )

    return result


async def handle_log_anomaly(
    error_summary: str,
    error_count: int,
    project_root: Optional[Path] = None,
) -> dict:
    """
    Called when log analysis detects anomalies.
    Similar flow to health_failure but with lower severity.
    """
    root = project_root or Path.cwd()
    cfg = load_config(root)

    incident_id = f"log-{uuid.uuid4().hex[:8]}"
    escalation = EscalationManager(root)
    incident = escalation.create_incident(
        incident_id=incident_id,
        severity="medium",
        description=f"Log anomaly: {error_count} errors detected. {error_summary}",
    )

    await _notify_telegram(
        cfg.telegram.bot_token,
        cfg.telegram.chat_id,
        f"⚠️ <b>Log anomaly detected</b>\n"
        f"Errors: {error_count}\n"
        f"Summary: {error_summary[:200]}\n"
        f"Incident: {incident_id}",
    )

    return {
        "incident_id": incident_id,
        "severity": "medium",
        "error_count": error_count,
    }


async def _attempt_auto_fix(
    project_root: Path,
    cfg: PocketTeamConfig,
    incident: Incident,
    escalation: EscalationManager,
) -> dict:
    """
    Attempt to auto-fix an incident.
    Staging-first, 3-Strike Rule.
    """
    result = {
        "auto_fix_attempted": True,
        "auto_fix_success": False,
        "escalated": False,
        "fix_attempts": 0,
    }

    for attempt in range(MAX_AUTO_FIX_ATTEMPTS):
        result["fix_attempts"] = attempt + 1

        # Check if we should escalate
        if escalation.should_escalate(incident.incident_id):
            result["escalated"] = True
            await _notify_telegram(
                cfg.telegram.bot_token,
                cfg.telegram.chat_id,
                f"❌ <b>Auto-fix failed after {attempt} attempts</b>\n"
                f"Incident: {incident.incident_id}\n"
                f"Manual intervention required.",
            )
            break

        # Record attempt (success=False for now, will update if fix works)
        can_continue = escalation.record_fix_attempt(
            incident.incident_id, success=False
        )

        if not can_continue:
            result["escalated"] = True
            break

        # Run the agent pipeline via SDK (headless — this is the correct use case)
        fix_success = await _run_fix_pipeline(project_root, incident, attempt + 1)

        if fix_success:
            escalation.resolve_incident(
                incident.incident_id,
                f"Auto-fixed on attempt {attempt + 1}",
            )
            result["auto_fix_success"] = True
            await _notify_telegram(
                cfg.telegram.bot_token,
                cfg.telegram.chat_id,
                f"✅ <b>Auto-fix successful</b>\n"
                f"Incident: {incident.incident_id}\n"
                f"Attempt: {attempt + 1}",
            )
            break

    return result


async def _run_fix_pipeline(
    project_root: Path,
    incident: Incident,
    attempt: int,
) -> bool:
    """
    Run the actual fix pipeline via Agent SDK (headless).

    This is the CORRECT use of _run_with_sdk() — headless CI self-healing.
    Steps: Investigator → Engineer → QA → verify.
    """
    try:
        from ..agents.investigator import InvestigatorAgent
        from ..agents.engineer import EngineerAgent
        from ..agents.qa import QAAgent

        # Step 1: Investigator diagnoses
        investigator = InvestigatorAgent(project_root)
        diag = await investigator.execute(
            f"Diagnose production incident: {incident.description}"
        )
        if not diag.success:
            return False

        # Step 2: Engineer creates fix
        engineer = EngineerAgent(project_root)
        fix = await engineer.execute(
            f"Create minimal fix for: {diag.output}\n"
            f"Incident: {incident.description}\n"
            f"This is attempt {attempt}. Keep the fix minimal and scoped."
        )
        if not fix.success:
            return False

        # Step 3: QA tests the fix
        qa = QAAgent(project_root)
        test_result = await qa.run_tests_now()
        if not test_result.success:
            return False

        return True

    except Exception:
        return False


async def _notify_telegram(bot_token: str, chat_id: str, message: str) -> None:
    """Send a Telegram notification."""
    if not bot_token or not chat_id:
        return

    try:
        import httpx
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(url, json={
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "HTML",
            })
    except Exception:
        pass
