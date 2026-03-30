"""
Phase 1 Tests: Verify the fake app works correctly.

Tests all endpoints and chaos modes before we use it for SDK testing.
"""

from __future__ import annotations

import json
import urllib.request

import pytest


class TestHealthEndpoint:
    """GET /health tests."""

    def test_healthy_by_default(self, fake_app_url: str, chaos) -> None:
        with urllib.request.urlopen(f"{fake_app_url}/health", timeout=5) as resp:
            assert resp.status == 200
            data = json.loads(resp.read())
            assert data["status"] == "healthy"

    def test_chaos_500(self, fake_app_url: str, chaos) -> None:
        chaos.set(health_status=500)
        try:
            urllib.request.urlopen(f"{fake_app_url}/health", timeout=5)
            pytest.fail("Expected HTTP 500")
        except urllib.error.HTTPError as e:
            assert e.code == 500
            data = json.loads(e.read())
            assert data["status"] == "unhealthy"

    def test_chaos_503(self, fake_app_url: str, chaos) -> None:
        chaos.set(health_status=503)
        try:
            urllib.request.urlopen(f"{fake_app_url}/health", timeout=5)
            pytest.fail("Expected HTTP 503")
        except urllib.error.HTTPError as e:
            assert e.code == 503

    def test_reset_restores_health(self, fake_app_url: str, chaos) -> None:
        chaos.set(health_status=500)
        chaos.reset()
        with urllib.request.urlopen(f"{fake_app_url}/health", timeout=5) as resp:
            assert resp.status == 200


class TestLogsEndpoint:
    """GET /logs tests."""

    def test_logs_default_no_errors(self, fake_app_url: str, chaos) -> None:
        with urllib.request.urlopen(f"{fake_app_url}/logs", timeout=5) as resp:
            data = json.loads(resp.read())
            assert data["total_errors"] == 0
            assert data["total_warnings"] == 0
            assert len(data["lines"]) == 2  # 2 info lines

    def test_logs_with_errors(self, fake_app_url: str, chaos) -> None:
        chaos.set(log_errors=3)
        with urllib.request.urlopen(f"{fake_app_url}/logs", timeout=5) as resp:
            data = json.loads(resp.read())
            assert data["total_errors"] == 6  # 2 error lines per injection
            error_lines = [l for l in data["lines"] if "ERROR" in l or "FATAL" in l]
            assert len(error_lines) == 6

    def test_logs_with_warnings(self, fake_app_url: str, chaos) -> None:
        chaos.set(log_warnings=2)
        with urllib.request.urlopen(f"{fake_app_url}/logs", timeout=5) as resp:
            data = json.loads(resp.read())
            assert data["total_warnings"] == 4
            warn_lines = [l for l in data["lines"] if "WARN" in l]
            assert len(warn_lines) == 4

    def test_logs_mixed_chaos(self, fake_app_url: str, chaos) -> None:
        chaos.set(log_errors=2, log_warnings=1)
        with urllib.request.urlopen(f"{fake_app_url}/logs", timeout=5) as resp:
            data = json.loads(resp.read())
            assert data["total_errors"] == 4
            assert data["total_warnings"] == 2


class TestChaosEndpoint:
    """POST /chaos + GET /chaos tests."""

    def test_get_chaos_state(self, fake_app_url: str, chaos) -> None:
        state = chaos.get()
        assert state["health_status"] == 200
        assert state["error_rate"] == 0.0

    def test_update_multiple_fields(self, fake_app_url: str, chaos) -> None:
        chaos.set(health_status=503, log_errors=5, log_warnings=10)
        state = chaos.get()
        assert state["health_status"] == 503
        assert state["log_errors"] == 5
        assert state["log_warnings"] == 10

    def test_request_counter(self, fake_app_url: str, chaos) -> None:
        # Each fixture reset + get = some requests already. Just check it increments.
        state1 = chaos.get()
        count1 = state1["request_count"]
        chaos.get()
        state2 = chaos.get()
        assert state2["request_count"] > count1


class TestResetEndpoint:
    """POST /reset tests."""

    def test_reset_clears_chaos(self, fake_app_url: str, chaos) -> None:
        chaos.set(health_status=500, log_errors=10)
        result = chaos.reset()
        assert result["state"]["health_status"] == 200
        assert result["state"]["log_errors"] == 0
