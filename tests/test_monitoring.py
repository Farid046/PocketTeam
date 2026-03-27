"""
Tests for Phase 13: Self-Healing (Watcher, Escalation, Healer).
No real HTTP/Telegram calls — all external calls are mocked.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

from pocketteam.config import MonitoringConfig, PocketTeamConfig
from pocketteam.monitoring.escalation import EscalationManager, Incident
from pocketteam.monitoring.healer import (
    _notify_telegram,
    handle_health_failure,
    handle_log_anomaly,
)
from pocketteam.monitoring.watcher import Watcher
from pocketteam.tools.health_check import HealthResult

# ── Escalation Manager ─────────────────────────────────────────────────────

class TestEscalationManager:
    def test_create_incident(self, tmp_path: Path):
        em = EscalationManager(tmp_path)
        incident = em.create_incident("inc-1", "high", "Server down")
        assert incident.incident_id == "inc-1"
        assert incident.severity == "high"
        assert incident.resolved is False

    def test_record_fix_attempt_success(self, tmp_path: Path):
        em = EscalationManager(tmp_path)
        em.create_incident("inc-2", "medium", "Error rate high")
        result = em.record_fix_attempt("inc-2", success=True)
        assert result is True
        incident = em.get_incident("inc-2")
        assert incident.resolved is True
        assert incident.fix_attempts == 1

    def test_three_strike_rule(self, tmp_path: Path):
        em = EscalationManager(tmp_path)
        em.create_incident("inc-3", "medium", "Bug")

        # Three failures → escalation
        em.record_fix_attempt("inc-3", success=False)
        em.record_fix_attempt("inc-3", success=False)
        result = em.record_fix_attempt("inc-3", success=False)

        assert result is False  # No more attempts allowed
        assert em.should_escalate("inc-3") is True

    def test_should_escalate_critical(self, tmp_path: Path):
        em = EscalationManager(tmp_path)
        em.create_incident("inc-4", "critical", "Data loss")
        assert em.should_escalate("inc-4") is True  # Always for critical

    def test_should_not_escalate_normal(self, tmp_path: Path):
        em = EscalationManager(tmp_path)
        em.create_incident("inc-5", "low", "Minor issue")
        assert em.should_escalate("inc-5") is False

    def test_resolve_incident(self, tmp_path: Path):
        em = EscalationManager(tmp_path)
        em.create_incident("inc-6", "high", "Outage")
        em.resolve_incident("inc-6", "Restarted service")
        incident = em.get_incident("inc-6")
        assert incident.resolved is True
        assert incident.resolution == "Restarted service"
        assert incident.resolved_at is not None

    def test_get_active_incidents(self, tmp_path: Path):
        em = EscalationManager(tmp_path)
        em.create_incident("inc-a", "high", "A")
        em.create_incident("inc-b", "medium", "B")
        em.resolve_incident("inc-a", "Fixed")

        active = em.get_active_incidents()
        assert len(active) == 1
        assert active[0].incident_id == "inc-b"

    def test_persist_and_load(self, tmp_path: Path):
        em1 = EscalationManager(tmp_path)
        em1.create_incident("inc-persist", "high", "Persist test")
        em1.record_fix_attempt("inc-persist", success=False)

        # Load in new instance
        em2 = EscalationManager(tmp_path)
        em2.load_incidents()
        incident = em2.get_incident("inc-persist")
        assert incident is not None
        assert incident.fix_attempts == 1

    def test_record_nonexistent_incident(self, tmp_path: Path):
        em = EscalationManager(tmp_path)
        result = em.record_fix_attempt("nonexistent", success=True)
        assert result is False

    def test_incident_to_dict(self):
        incident = Incident(
            incident_id="test-1",
            severity="high",
            description="Test",
        )
        d = incident.to_dict()
        assert d["incident_id"] == "test-1"
        assert d["severity"] == "high"
        assert d["resolved"] is False


# ── Watcher ─────────────────────────────────────────────────────────────────

class TestWatcher:
    def _make_config(self, tmp_path: Path, health_url: str = "") -> PocketTeamConfig:
        return PocketTeamConfig(
            project_root=tmp_path,
            health_url=health_url,
            monitoring=MonitoringConfig(health_url=health_url),
        )

    def test_no_health_url(self, tmp_path: Path):
        cfg = self._make_config(tmp_path)
        w = Watcher(tmp_path, config=cfg)
        assert w.health_url == ""

    def test_health_url_from_config(self, tmp_path: Path):
        cfg = self._make_config(tmp_path, "http://app.com/health")
        w = Watcher(tmp_path, config=cfg)
        assert w.health_url == "http://app.com/health"

    async def test_check_once_healthy(self, tmp_path: Path):
        cfg = self._make_config(tmp_path, "http://app.com/health")
        w = Watcher(tmp_path, config=cfg)

        mock_result = HealthResult(healthy=True, url="http://app.com/health", status_code=200)
        with patch.object(w._health_checker, "check", new_callable=AsyncMock) as mock_check:
            mock_check.return_value = mock_result
            result = await w.check_once()

        assert result["healthy"] is True
        assert w._consecutive_failures == 0

    async def test_check_once_unhealthy(self, tmp_path: Path):
        cfg = self._make_config(tmp_path, "http://app.com/health")
        w = Watcher(tmp_path, config=cfg)

        mock_result = HealthResult(
            healthy=False, url="http://app.com/health",
            status_code=500, error="HTTP 500",
        )
        with patch.object(w._health_checker, "check", new_callable=AsyncMock) as mock_check:
            mock_check.return_value = mock_result
            result = await w.check_once()

        assert result["healthy"] is False
        assert w._consecutive_failures == 1

    async def test_three_consecutive_failures_escalates(self, tmp_path: Path):
        cfg = self._make_config(tmp_path, "http://app.com/health")
        escalated = []
        w = Watcher(
            tmp_path, config=cfg,
            on_health_failure=lambda h: escalated.append(h),
        )

        mock_result = HealthResult(healthy=False, url="http://app.com/health", error="down")
        with patch.object(w._health_checker, "check", new_callable=AsyncMock) as mock_check:
            mock_check.return_value = mock_result
            await w.check_once()
            await w.check_once()
            await w.check_once()

        assert w._consecutive_failures == 3
        assert len(escalated) == 1

    async def test_healthy_resets_counter(self, tmp_path: Path):
        cfg = self._make_config(tmp_path, "http://app.com/health")
        w = Watcher(tmp_path, config=cfg)
        w._consecutive_failures = 2

        mock_result = HealthResult(healthy=True, url="http://app.com/health", status_code=200)
        with patch.object(w._health_checker, "check", new_callable=AsyncMock) as mock_check:
            mock_check.return_value = mock_result
            await w.check_once()

        assert w._consecutive_failures == 0

    def test_stop(self, tmp_path: Path):
        cfg = self._make_config(tmp_path, "http://app.com/health")
        w = Watcher(tmp_path, config=cfg)
        w._running = True
        w.stop()
        assert w._running is False


# ── Healer ──────────────────────────────────────────────────────────────────

class TestHealer:
    async def test_handle_health_failure(self, tmp_path: Path):
        # Create config
        (tmp_path / ".pocketteam").mkdir(parents=True)

        with patch("pocketteam.monitoring.healer._notify_telegram", new_callable=AsyncMock):
            result = await handle_health_failure(
                health_url="http://app.com/health",
                http_status="500",
                project_root=tmp_path,
            )

        assert "incident_id" in result
        assert result["http_status"] == "500"

    async def test_handle_health_failure_auto_fix_disabled(self, tmp_path: Path):
        cfg_dir = tmp_path / ".pocketteam"
        cfg_dir.mkdir(parents=True)
        # Write config with auto_fix disabled
        import yaml
        cfg_path = tmp_path / ".pocketteam/config.yaml"
        cfg_path.write_text(yaml.dump({
            "project": {"name": "test"},
            "monitoring": {"auto_fix": False},
        }))

        with patch("pocketteam.monitoring.healer._notify_telegram", new_callable=AsyncMock):
            result = await handle_health_failure(
                health_url="http://app.com/health",
                http_status="500",
                project_root=tmp_path,
            )

        assert result["escalated"] is True

    async def test_handle_log_anomaly(self, tmp_path: Path):
        (tmp_path / ".pocketteam").mkdir(parents=True)

        with patch("pocketteam.monitoring.healer._notify_telegram", new_callable=AsyncMock):
            result = await handle_log_anomaly(
                error_summary="47 connection timeouts",
                error_count=47,
                project_root=tmp_path,
            )

        assert result["incident_id"].startswith("log-")
        assert result["error_count"] == 47

    async def test_notify_telegram_no_token(self):
        """Should not crash when no token configured."""
        await _notify_telegram("", "", "test")

    async def test_notify_telegram_with_token(self):
        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            await _notify_telegram("tok", "123", "test message")
            mock_client.post.assert_awaited_once()
