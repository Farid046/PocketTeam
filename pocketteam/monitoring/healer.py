"""
Self-Healing Module — woken by GitHub Actions on health/log failures.

Flow (CEO-in-the-loop):
1. Detect problem (health check, log anomaly)
2. Notify CEO via Telegram immediately
3. Claude API analyzes the problem and creates a fix plan
4. Send plan to CEO via Telegram for approval
5. CEO approves → starts a session to execute the plan

No autonomous fixing — CEO always approves before any changes.
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
    Triages the issue, creates a plan, sends to CEO for approval.
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

    # Step 1: Notify CEO immediately
    await _notify_telegram(
        bot_token, chat_id,
        f"🚨 <b>Health check FAILED</b>\n"
        f"URL: {health_url}\n"
        f"Status: HTTP {http_status}\n"
        f"Incident: {incident_id}\n\n"
        f"Analyzing and creating fix plan...",
    )

    # Step 2: Triage + Plan via Claude API
    plan = await _triage_and_plan(
        problem_type="health_failure",
        details=f"Health endpoint {health_url} returned HTTP {http_status}.",
        incident_id=incident_id,
    )

    # Step 3: Send plan to CEO for approval
    await _notify_telegram(
        bot_token, chat_id,
        f"📋 <b>Fix Plan — {incident_id}</b>\n\n"
        f"{plan}\n\n"
        f"Reply <b>approve {incident_id}</b> to start a session that executes this plan.",
    )

    return {
        "incident_id": incident_id,
        "health_url": health_url,
        "http_status": http_status,
        "plan_created": bool(plan),
        "awaiting_approval": True,
    }


async def handle_log_anomaly(
    error_summary: str,
    error_count: int,
    project_root: Path | None = None,
) -> dict:
    """
    Called when log analysis detects anomalies.
    Triages, creates plan, sends to CEO for approval.
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

    # Step 1: Notify CEO immediately
    await _notify_telegram(
        bot_token, chat_id,
        f"⚠️ <b>Log anomaly detected</b>\n"
        f"Errors: {error_count}\n"
        f"Summary: {error_summary[:300]}\n"
        f"Incident: {incident_id}\n\n"
        f"Analyzing and creating fix plan...",
    )

    # Step 2: Triage + Plan via Claude API
    plan = await _triage_and_plan(
        problem_type="log_anomaly",
        details=(
            f"{error_count} errors detected in application logs.\n"
            f"Error summary:\n{error_summary[:1000]}"
        ),
        incident_id=incident_id,
    )

    # Step 3: Send plan to CEO for approval
    await _notify_telegram(
        bot_token, chat_id,
        f"📋 <b>Fix Plan — {incident_id}</b>\n\n"
        f"{plan}\n\n"
        f"Reply <b>approve {incident_id}</b> to start a session that executes this plan.",
    )

    return {
        "incident_id": incident_id,
        "severity": "medium",
        "error_count": error_count,
        "plan_created": bool(plan),
        "awaiting_approval": True,
    }


async def _triage_and_plan(
    problem_type: str,
    details: str,
    incident_id: str,
) -> str:
    """
    Use Claude API to analyze the problem and create a fix plan.
    Returns a concise plan as text (no code execution, just analysis).
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return "⚠️ No API key — cannot generate plan. Manual investigation needed."

    prompt = (
        f"You are PocketTeam's incident triage agent. A production issue was detected.\n\n"
        f"Problem type: {problem_type}\n"
        f"Incident: {incident_id}\n"
        f"Details:\n{details}\n\n"
        f"Create a concise fix plan. Include:\n"
        f"1. Root cause analysis (what likely went wrong)\n"
        f"2. Severity assessment (critical/high/medium/low)\n"
        f"3. Step-by-step fix plan (max 5 steps)\n"
        f"4. Risk assessment (what could go wrong with the fix)\n"
        f"5. Estimated effort (quick fix / medium / large refactor)\n\n"
        f"Keep it under 500 words. Be specific and actionable.\n"
        f"Format for Telegram (plain text, no markdown headers)."
    )

    try:
        import httpx

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 1024,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )

            if resp.status_code != 200:
                logger.error("Claude API error: %s %s", resp.status_code, resp.text[:200])
                return f"⚠️ Could not generate plan (API error {resp.status_code}). Manual investigation needed."

            data = resp.json()
            content = data.get("content", [])
            if content and content[0].get("type") == "text":
                return content[0]["text"]

            return "⚠️ Empty response from Claude API. Manual investigation needed."

    except Exception as e:
        logger.error("Triage failed: %s", e, exc_info=True)
        return f"⚠️ Triage failed: {e}. Manual investigation needed."


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
