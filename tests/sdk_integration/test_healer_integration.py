"""
Phase 3 Tests: Healer integration with fake app (mocked SDK).

Tests the full flow:
1. Fake app running with chaos mode
2. HealthChecker detects failure
3. Healer creates incident, attempts auto-fix pipeline
4. Escalation after 3 strikes
5. Telegram notification sent
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pocketteam.monitoring.escalation import EscalationManager
from pocketteam.monitoring.healer import (
    _attempt_auto_fix,
    _run_fix_pipeline,
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


class TestHealerWithFakeApp:
    """Healer integration — mocked SDK agents, real fake app."""

    @pytest.mark.asyncio
    async def test_handle_health_failure_creates_incident(
        self, fake_app_url: str, chaos, project_root: Path
    ) -> None:
        chaos.set(health_status=500)

        with patch("pocketteam.monitoring.healer._notify_telegram", new_callable=AsyncMock) as mock_tg, \
             patch("pocketteam.monitoring.healer._run_fix_pipeline", new_callable=AsyncMock) as mock_fix:
            mock_fix.return_value = False

            result = await handle_health_failure(
                health_url=f"{fake_app_url}/health",
                http_status="500",
                project_root=project_root,
            )

        assert result["incident_id"].startswith("health-")
        assert result["http_status"] == "500"
        # Telegram was called at least once (initial notification)
        assert mock_tg.call_count >= 1

    @pytest.mark.asyncio
    async def test_handle_health_failure_auto_fix_success(
        self, fake_app_url: str, chaos, project_root: Path
    ) -> None:
        chaos.set(health_status=500)

        with patch("pocketteam.monitoring.healer._notify_telegram", new_callable=AsyncMock), \
             patch("pocketteam.monitoring.healer._run_fix_pipeline", new_callable=AsyncMock) as mock_fix:
            mock_fix.return_value = True

            result = await handle_health_failure(
                health_url=f"{fake_app_url}/health",
                http_status="500",
                project_root=project_root,
            )

        assert result["auto_fix_attempted"] is True
        assert result["auto_fix_success"] is True
        assert result["escalated"] is False

    @pytest.mark.asyncio
    async def test_handle_health_failure_escalates_after_3_strikes(
        self, fake_app_url: str, chaos, project_root: Path
    ) -> None:
        chaos.set(health_status=500)

        with patch("pocketteam.monitoring.healer._notify_telegram", new_callable=AsyncMock) as mock_tg, \
             patch("pocketteam.monitoring.healer._run_fix_pipeline", new_callable=AsyncMock) as mock_fix:
            mock_fix.return_value = False  # All fix attempts fail

            result = await handle_health_failure(
                health_url=f"{fake_app_url}/health",
                http_status="500",
                project_root=project_root,
            )

        assert result["auto_fix_attempted"] is True
        assert result["auto_fix_success"] is False
        assert result["escalated"] is True
        # Check that escalation notification was sent
        escalation_calls = [
            c for c in mock_tg.call_args_list
            if "failed" in str(c).lower() or "manual" in str(c).lower()
        ]
        assert len(escalation_calls) >= 1

    @pytest.mark.asyncio
    async def test_handle_log_anomaly(
        self, fake_app_url: str, chaos, project_root: Path
    ) -> None:
        with patch("pocketteam.monitoring.healer._notify_telegram", new_callable=AsyncMock) as mock_tg:
            result = await handle_log_anomaly(
                error_summary="Connection refused errors spiking",
                error_count=42,
                project_root=project_root,
            )

        assert result["incident_id"].startswith("log-")
        assert result["severity"] == "medium"
        assert result["error_count"] == 42
        mock_tg.assert_called_once()


class TestEscalationManager:
    """Escalation logic with real incident persistence."""

    def test_3_strike_rule(self, project_root: Path) -> None:
        mgr = EscalationManager(project_root)
        incident = mgr.create_incident("test-001", "high", "Test failure")

        # First two attempts: can continue
        assert mgr.record_fix_attempt("test-001", success=False) is True
        assert mgr.record_fix_attempt("test-001", success=False) is True

        # Third attempt: escalation
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


class TestFixPipelineMocked:
    """_run_fix_pipeline with mocked agent SDK calls."""

    @pytest.mark.asyncio
    async def test_pipeline_success(self, project_root: Path) -> None:
        from pocketteam.monitoring.escalation import Incident

        incident = Incident(
            incident_id="pipe-001",
            severity="high",
            description="Health check failed: HTTP 500",
        )

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.output = "Root cause: OOM in worker process"

        mock_test_result = MagicMock()
        mock_test_result.success = True

        with patch("pocketteam.agents.investigator.InvestigatorAgent") as MockInv, \
             patch("pocketteam.agents.engineer.EngineerAgent") as MockEng, \
             patch("pocketteam.agents.qa.QAAgent") as MockQA:

            MockInv.return_value.execute = AsyncMock(return_value=mock_result)
            MockEng.return_value.execute = AsyncMock(return_value=mock_result)
            MockQA.return_value.run_tests_now = AsyncMock(return_value=mock_test_result)

            success = await _run_fix_pipeline(project_root, incident, attempt=1)

        assert success is True

    @pytest.mark.asyncio
    async def test_pipeline_fails_on_investigator_error(self, project_root: Path) -> None:
        from pocketteam.monitoring.escalation import Incident

        incident = Incident(
            incident_id="pipe-002",
            severity="high",
            description="Health check failed",
        )

        mock_result = MagicMock()
        mock_result.success = False

        with patch("pocketteam.agents.investigator.InvestigatorAgent") as MockInv:
            MockInv.return_value.execute = AsyncMock(return_value=mock_result)

            success = await _run_fix_pipeline(project_root, incident, attempt=1)

        assert success is False

    @pytest.mark.asyncio
    async def test_pipeline_fails_on_qa_error(self, project_root: Path) -> None:
        from pocketteam.monitoring.escalation import Incident

        incident = Incident(
            incident_id="pipe-003",
            severity="high",
            description="Health check failed",
        )

        ok_result = MagicMock()
        ok_result.success = True
        ok_result.output = "diagnosis"

        fail_result = MagicMock()
        fail_result.success = False

        with patch("pocketteam.agents.investigator.InvestigatorAgent") as MockInv, \
             patch("pocketteam.agents.engineer.EngineerAgent") as MockEng, \
             patch("pocketteam.agents.qa.QAAgent") as MockQA:

            MockInv.return_value.execute = AsyncMock(return_value=ok_result)
            MockEng.return_value.execute = AsyncMock(return_value=ok_result)
            MockQA.return_value.run_tests_now = AsyncMock(return_value=fail_result)

            success = await _run_fix_pipeline(project_root, incident, attempt=1)

        assert success is False
