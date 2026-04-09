"""
Watcher — periodic health monitoring loop.

Runs as a background task checking:
- HTTP health endpoints
- Log files for error patterns
- Error rate thresholds

When anomalies are detected, escalates to the healer.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from pathlib import Path

from ..config import PocketTeamConfig, load_config
from ..constants import (
    EVENTS_FILE,
    MONITOR_INTERVAL_ANOMALY,
    MONITOR_INTERVAL_STEADY,
    RESPONSE_TIME_THRESHOLD,
)
from ..tools.health_check import HealthChecker, HealthResult, LogAnalyzer
from ..jsonl import append_jsonl

logger = logging.getLogger(__name__)


class Watcher:
    """
    Periodic health monitoring loop.

    Steady state: checks every 5 minutes.
    Anomaly detected: checks every 30 seconds.
    3 consecutive failures: triggers escalation.
    """

    def __init__(
        self,
        project_root: Path,
        config: PocketTeamConfig | None = None,
        on_anomaly: Callable | None = None,
        on_health_failure: Callable | None = None,
        on_status: Callable | None = None,
    ) -> None:
        self.project_root = project_root
        self.config = config or load_config(project_root)
        self.on_anomaly = on_anomaly
        self.on_health_failure = on_health_failure
        self.on_status = on_status

        self._health_checker = HealthChecker(
            max_response_time_ms=RESPONSE_TIME_THRESHOLD * 1000,
        )
        self._log_analyzer = LogAnalyzer()
        self._running = False
        self._consecutive_failures = 0
        self._current_interval = MONITOR_INTERVAL_STEADY

    @property
    def health_url(self) -> str:
        return self.config.monitoring.health_url or self.config.health_url

    async def start(self) -> None:
        """Start the monitoring loop."""
        if not self.health_url:
            await self._log("No health URL configured, watcher idle")
            return

        self._running = True
        await self._log(f"Watcher started. Monitoring: {self.health_url}")

        while self._running:
            await self._check_cycle()
            await asyncio.sleep(self._current_interval)

    def stop(self) -> None:
        """Stop the monitoring loop."""
        self._running = False

    async def check_once(self) -> dict:
        """Run a single health check (for CLI / one-off use)."""
        return await self._check_cycle()

    async def _check_cycle(self) -> dict:
        """Run one check cycle: health + optional log analysis."""
        result: dict = {"healthy": True, "checks": []}

        # HTTP health check
        health = await self._health_checker.check(self.health_url)
        result["health"] = {
            "healthy": health.healthy,
            "status_code": health.status_code,
            "response_time_ms": health.response_time_ms,
            "error": health.error,
        }

        if health.healthy:
            self._consecutive_failures = 0
            self._current_interval = MONITOR_INTERVAL_STEADY
        else:
            self._consecutive_failures += 1
            self._current_interval = MONITOR_INTERVAL_ANOMALY
            result["healthy"] = False

            await self._log(
                f"Health check failed ({self._consecutive_failures}x): {health.error}"
            )

            # 3 consecutive failures → escalate
            if self._consecutive_failures >= 3:
                await self._escalate_health_failure(health)

        # Log event
        self._log_check_event(health)

        return result

    async def _escalate_health_failure(self, health: HealthResult) -> None:
        """Escalate after 3 consecutive health check failures."""
        await self._log(
            f"ESCALATING: 3 consecutive health failures for {health.url}"
        )

        if self.on_health_failure:
            try:
                result = self.on_health_failure(health)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                logger.debug("Health failure callback raised an exception", exc_info=True)

    async def _log(self, message: str) -> None:
        """Log a watcher event."""
        try:
            events_path = self.project_root / EVENTS_FILE
            events_path.parent.mkdir(parents=True, exist_ok=True)
            event = {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "agent": "monitor",
                "type": "health_check",
                "status": "working",
                "action": message,
            }
            append_jsonl(events_path, event)
        except Exception:
            logger.debug("Watcher event logging failed (non-critical)", exc_info=True)

        if self.on_status:
            try:
                result = self.on_status(message)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                logger.debug("Watcher status callback raised an exception", exc_info=True)

    def _log_check_event(self, health: HealthResult) -> None:
        """Log health check result to event stream."""
        try:
            events_path = self.project_root / EVENTS_FILE
            events_path.parent.mkdir(parents=True, exist_ok=True)
            event = {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "agent": "monitor",
                "type": "health_result",
                "healthy": health.healthy,
                "status_code": health.status_code,
                "response_time_ms": health.response_time_ms,
            }
            append_jsonl(events_path, event)
        except Exception:
            logger.debug("Watcher health check event logging failed (non-critical)", exc_info=True)
