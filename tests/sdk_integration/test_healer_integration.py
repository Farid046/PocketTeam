"""
Phase 3 Tests: Healer integration with fake app.

Tests the triage + plan flow:
1. Fake app running with chaos mode
2. HealthChecker detects failure
3. Healer creates incident, calls Claude API for plan
4. Sends plan to CEO via Telegram
5. Log anomaly detection and planning
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pocketteam.monitoring.escalation import EscalationManager
from pocketteam.monitoring.healer import (
    _triage_and_plan,
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
        assert result.response_time_ms < 2000

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


class TestHealerTriageFlow:
    """Healer triage + plan flow with mocked Claude API."""

    @pytest.mark.asyncio
    async def test_health_failure_creates_incident_and_plan(
        self, fake_app_url: str, chaos, project_root: Path
    ) -> None:
        chaos.set(health_status=500)

        with patch("pocketteam.monitoring.healer._notify_telegram", new_callable=AsyncMock) as mock_tg, \
             patch("pocketteam.monitoring.healer._triage_and_plan", new_callable=AsyncMock) as mock_plan:
            mock_plan.return_value = "1. Root cause: server OOM\n2. Fix: increase memory limit"

            result = await handle_health_failure(
                health_url=f"{fake_app_url}/health",
                http_status="500",
                project_root=project_root,
            )

        assert result["incident_id"].startswith("health-")
        assert result["plan_created"] is True
        assert result["awaiting_approval"] is True
        # Two Telegram calls: notification + plan
        assert mock_tg.call_count == 2
        # Plan was sent in second call
        plan_call = mock_tg.call_args_list[1]
        assert "Fix Plan" in plan_call.args[2]

    @pytest.mark.asyncio
    async def test_health_failure_without_api_key(
        self, fake_app_url: str, chaos, project_root: Path
    ) -> None:
        chaos.set(health_status=500)

        with patch("pocketteam.monitoring.healer._notify_telegram", new_callable=AsyncMock) as mock_tg, \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": ""}, clear=False):
            result = await handle_health_failure(
                health_url=f"{fake_app_url}/health",
                http_status="500",
                project_root=project_root,
            )

        assert result["plan_created"] is True  # Returns warning text, still truthy
        assert result["awaiting_approval"] is True

    @pytest.mark.asyncio
    async def test_log_anomaly_creates_plan(
        self, fake_app_url: str, chaos, project_root: Path
    ) -> None:
        with patch("pocketteam.monitoring.healer._notify_telegram", new_callable=AsyncMock) as mock_tg, \
             patch("pocketteam.monitoring.healer._triage_and_plan", new_callable=AsyncMock) as mock_plan:
            mock_plan.return_value = "1. Root cause: DB connection leak\n2. Fix: add connection pooling"

            result = await handle_log_anomaly(
                error_summary="Connection refused errors spiking",
                error_count=42,
                project_root=project_root,
            )

        assert result["incident_id"].startswith("log-")
        assert result["plan_created"] is True
        assert result["awaiting_approval"] is True
        assert mock_tg.call_count == 2


class TestTriageAndPlan:
    """Test the Claude API triage call."""

    @pytest.mark.asyncio
    async def test_triage_no_api_key(self) -> None:
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": ""}, clear=False):
            plan = await _triage_and_plan("health_failure", "HTTP 500", "test-001")
        assert "No API key" in plan

    @pytest.mark.asyncio
    async def test_triage_with_mocked_api(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "content": [{"type": "text", "text": "Root cause: OOM. Fix: restart."}]
        }

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test"}, clear=False), \
             patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_client

            plan = await _triage_and_plan("health_failure", "HTTP 500", "test-002")

        assert "OOM" in plan
        assert "restart" in plan

    @pytest.mark.asyncio
    async def test_triage_api_error(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = "rate limited"

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test"}, clear=False), \
             patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_client

            plan = await _triage_and_plan("health_failure", "HTTP 500", "test-003")

        assert "API error 429" in plan


class TestEscalationManager:
    """Escalation logic with real incident persistence."""

    def test_3_strike_rule(self, project_root: Path) -> None:
        mgr = EscalationManager(project_root)
        incident = mgr.create_incident("test-001", "high", "Test failure")

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
        assert data["severity"] == "high"
