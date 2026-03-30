"""
Phase 3 Tests: Healer integration with fake app.

Tests the triage → notify CEO → trigger session flow:
1. Fake app running with chaos mode
2. HealthChecker detects failure
3. Healer creates incident, notifies CEO
4. Healer sends problem to bot (daemon starts session)
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from pocketteam.monitoring.escalation import EscalationManager
from pocketteam.monitoring.healer import (
    handle_health_failure,
    handle_log_anomaly,
)
from pocketteam.tools.health_check import HealthChecker


class TestHealthCheckerWithFakeApp:
    """HealthChecker against the real fake app."""

    @pytest.mark.asyncio
    async def test_checker_healthy(self, fake_app_url: str, chaos) -> None:
        checker = HealthChecker()
        result = await checker.check(f"{fake_app_url}/health")
        assert result.healthy is True
        assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_checker_detects_500(self, fake_app_url: str, chaos) -> None:
        chaos.set(health_status=500)
        checker = HealthChecker()
        result = await checker.check(f"{fake_app_url}/health")
        assert result.healthy is False
        assert result.status_code == 500

    @pytest.mark.asyncio
    async def test_checker_detects_503(self, fake_app_url: str, chaos) -> None:
        chaos.set(health_status=503)
        checker = HealthChecker()
        result = await checker.check(f"{fake_app_url}/health")
        assert result.healthy is False
        assert result.status_code == 503

    @pytest.mark.asyncio
    async def test_consecutive_check_confirms_failure(self, fake_app_url: str, chaos) -> None:
        chaos.set(health_status=500)
        checker = HealthChecker()
        results = await checker.check_consecutive(
            f"{fake_app_url}/health", count=3, interval=0.1
        )
        assert len(results) == 3
        assert all(not r.healthy for r in results)


class TestHealerHealthFailure:
    """Health failure → notify + trigger session."""

    @pytest.mark.asyncio
    async def test_creates_incident_and_triggers_session(
        self, fake_app_url: str, chaos, project_root: Path
    ) -> None:
        chaos.set(health_status=500)

        with patch("pocketteam.monitoring.healer._notify_telegram", new_callable=AsyncMock) as mock_tg:
            result = await handle_health_failure(
                health_url=f"{fake_app_url}/health",
                http_status="500",
                project_root=project_root,
            )

        assert result["incident_id"].startswith("health-")
        assert result["session_triggered"] is True
        # Two calls: CEO notification + session prompt to bot
        assert mock_tg.call_count == 2
        # First call: CEO notification
        assert "Health check FAILED" in mock_tg.call_args_list[0].args[2]
        # Second call: session prompt with analysis instructions
        session_msg = mock_tg.call_args_list[1].args[2]
        assert "INCIDENT" in session_msg
        assert "Fix-Plan" in session_msg
        assert "KEINE Änderungen" in session_msg

    @pytest.mark.asyncio
    async def test_no_telegram_without_credentials(
        self, fake_app_url: str, chaos, project_root: Path
    ) -> None:
        chaos.set(health_status=500)

        with patch("pocketteam.monitoring.healer._notify_telegram", new_callable=AsyncMock) as mock_tg, \
             patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": ""}, clear=False):
            result = await handle_health_failure(
                health_url=f"{fake_app_url}/health",
                http_status="500",
                project_root=project_root,
            )

        assert result["session_triggered"] is True
        # _notify_telegram is called but exits early (no token)
        assert mock_tg.call_count == 2


class TestHealerLogAnomaly:
    """Log anomaly → notify + trigger session."""

    @pytest.mark.asyncio
    async def test_creates_incident_and_triggers_session(
        self, project_root: Path
    ) -> None:
        with patch("pocketteam.monitoring.healer._notify_telegram", new_callable=AsyncMock) as mock_tg:
            result = await handle_log_anomaly(
                error_summary="Connection refused; OOM; JWT expired",
                error_count=42,
                project_root=project_root,
            )

        assert result["incident_id"].startswith("log-")
        assert result["session_triggered"] is True
        assert result["error_count"] == 42
        # Two calls: CEO notification + session prompt
        assert mock_tg.call_count == 2
        session_msg = mock_tg.call_args_list[1].args[2]
        assert "Connection refused" in session_msg
        assert "Root Cause" in session_msg

    @pytest.mark.asyncio
    async def test_truncates_long_error_summary(
        self, project_root: Path
    ) -> None:
        long_summary = "ERROR: " * 500  # Very long

        with patch("pocketteam.monitoring.healer._notify_telegram", new_callable=AsyncMock):
            result = await handle_log_anomaly(
                error_summary=long_summary,
                error_count=500,
                project_root=project_root,
            )

        assert result["session_triggered"] is True


class TestEscalationManager:
    """Escalation logic with real incident persistence."""

    def test_3_strike_rule(self, project_root: Path) -> None:
        mgr = EscalationManager(project_root)
        mgr.create_incident("test-001", "high", "Test failure")

        assert mgr.record_fix_attempt("test-001", success=False) is True
        assert mgr.record_fix_attempt("test-001", success=False) is True
        assert mgr.record_fix_attempt("test-001", success=False) is False
        assert mgr.should_escalate("test-001") is True

    def test_success_before_escalation(self, project_root: Path) -> None:
        mgr = EscalationManager(project_root)
        mgr.create_incident("test-002", "high", "Test failure")

        mgr.record_fix_attempt("test-002", success=False)
        mgr.record_fix_attempt("test-002", success=True)
        assert mgr.should_escalate("test-002") is False

    def test_critical_always_escalates(self, project_root: Path) -> None:
        mgr = EscalationManager(project_root)
        mgr.create_incident("test-003", "critical", "Critical failure")
        assert mgr.should_escalate("test-003") is True

    def test_incident_persisted_to_disk(self, project_root: Path) -> None:
        mgr = EscalationManager(project_root)
        mgr.create_incident("test-004", "high", "Disk test")

        incident_file = project_root / ".pocketteam" / "artifacts" / "incidents" / "test-004.json"
        assert incident_file.exists()
        data = json.loads(incident_file.read_text())
        assert data["incident_id"] == "test-004"
