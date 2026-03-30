"""
Self-Healing Module — woken by GitHub Actions on health/log failures.

Flow (CEO-in-the-loop):
1. GitHub Actions detects problem (health check / log anomaly)
2. Healer notifies CEO via Telegram
3. Healer sends problem context to Telegram bot → daemon starts Claude Code session
4. Session (Opus/Sonnet) analyzes, creates plan, notifies CEO
5. CEO approves → session executes

Haiku is NOT used for analysis. It only decides "problem yes/no" (done in the workflow).
The actual thinking happens in a full Claude Code session.
"""

from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path

from ..config import load_config
from .escalation import EscalationManager

logger = logging.getLogger(__name__)


async def handle_health_failure(
    health_url: str,
    http_status: str,
    project_root: Path | None = None,
) -> dict:
    """
    Called by GitHub Actions when health check fails.
    Notifies CEO, then sends problem to bot to start a session.
    """
    root = project_root or Path.cwd()
    cfg = load_config(root)

    bot_token = cfg.telegram.bot_token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = cfg.telegram.chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")

    incident_id = f"health-{uuid.uuid4().hex[:8]}"
    escalation = EscalationManager(root)
    escalation.create_incident(
        incident_id=incident_id,
        severity="high",
        description=f"Health check failed: {health_url} → HTTP {http_status}",
    )

    # Step 1: Notify CEO
    await _notify_telegram(
        bot_token, chat_id,
        f"🚨 <b>Health check FAILED</b>\n"
        f"URL: {health_url}\n"
        f"Status: HTTP {http_status}\n"
        f"Incident: {incident_id}\n\n"
        f"Starting session to analyze and create fix plan...",
    )

    # Step 2: Send problem to bot → daemon picks up → starts session
    session_prompt = (
        f"INCIDENT {incident_id}: Health check failed.\n"
        f"URL: {health_url}\n"
        f"HTTP Status: {http_status}\n\n"
        f"Aufgaben:\n"
        f"1. Analysiere das Problem (prüfe Health-Endpoint, Logs, etc.)\n"
        f"2. Erstelle einen detaillierten Fix-Plan\n"
        f"3. Benachrichtige den CEO per Telegram mit dem Plan\n"
        f"4. Warte auf Genehmigung bevor du irgendetwas umsetzt\n\n"
        f"WICHTIG: Führe KEINE Änderungen durch. Nur analysieren und planen."
    )

    await _notify_telegram(bot_token, chat_id, session_prompt)

    return {
        "incident_id": incident_id,
        "health_url": health_url,
        "http_status": http_status,
        "session_triggered": True,
    }


async def handle_log_anomaly(
    error_summary: str,
    error_count: int,
    project_root: Path | None = None,
) -> dict:
    """
    Called when log analysis detects anomalies.
    Notifies CEO, then sends problem to bot to start a session.
    """
    root = project_root or Path.cwd()
    cfg = load_config(root)

    bot_token = cfg.telegram.bot_token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = cfg.telegram.chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")

    incident_id = f"log-{uuid.uuid4().hex[:8]}"
    escalation = EscalationManager(root)
    escalation.create_incident(
        incident_id=incident_id,
        severity="medium",
        description=f"Log anomaly: {error_count} errors detected. {error_summary}",
    )

    # Step 1: Notify CEO
    await _notify_telegram(
        bot_token, chat_id,
        f"⚠️ <b>Log anomaly detected</b>\n"
        f"Errors: {error_count}\n"
        f"Incident: {incident_id}\n\n"
        f"Starting session to analyze and create fix plan...",
    )

    # Step 2: Send problem to bot → daemon picks up → starts session
    session_prompt = (
        f"INCIDENT {incident_id}: Log anomaly detected.\n"
        f"Error count: {error_count}\n"
        f"Errors:\n{error_summary[:2000]}\n\n"
        f"Aufgaben:\n"
        f"1. Analysiere die Fehler (was ist die Root Cause?)\n"
        f"2. Bewerte die Severity (critical/high/medium/low)\n"
        f"3. Erstelle einen detaillierten Fix-Plan (max 5 Schritte)\n"
        f"4. Benachrichtige den CEO per Telegram mit dem Plan\n"
        f"5. Warte auf Genehmigung bevor du irgendetwas umsetzt\n\n"
        f"WICHTIG: Führe KEINE Änderungen durch. Nur analysieren und planen."
    )

    await _notify_telegram(bot_token, chat_id, session_prompt)

    return {
        "incident_id": incident_id,
        "severity": "medium",
        "error_count": error_count,
        "session_triggered": True,
    }


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
        logger.debug("Telegram notification failed in healer", exc_info=True)
