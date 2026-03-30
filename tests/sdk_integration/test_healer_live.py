"""
Phase 3 Tests: LIVE Agent SDK tests (requires ANTHROPIC_API_KEY).

These tests call the real Claude API via the Agent SDK.
They are skipped in CI unless ANTHROPIC_API_KEY is set and
the pytest marker --run-live is passed.

Usage:
    # Run live tests locally:
    ANTHROPIC_API_KEY=sk-ant-... pytest tests/sdk_integration/test_healer_live.py -v

    # In GitHub Actions: triggered manually with live matrix
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

# Skip entire module if no API key
pytestmark = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set — skipping live SDK tests",
)


class TestLiveSDKHealthCheck:
    """Live tests that actually call Claude API."""

    @pytest.mark.asyncio
    async def test_live_handle_health_failure_investigates(
        self, fake_app_url: str, chaos, project_root: Path
    ) -> None:
        """
        Full live test:
        1. Fake app returns 500
        2. Healer calls real SDK to investigate
        3. Verify it produces a diagnosis
        """
        from unittest.mock import AsyncMock, patch

        from pocketteam.monitoring.healer import handle_health_failure

        chaos.set(health_status=500)

        # Mock Telegram to avoid real messages, but let SDK run for real
        with patch("pocketteam.monitoring.healer._notify_telegram", new_callable=AsyncMock):
            result = await handle_health_failure(
                health_url=f"{fake_app_url}/health",
                http_status="500",
                project_root=project_root,
            )

        assert result["incident_id"].startswith("health-")
        assert result["auto_fix_attempted"] is True
        # With real SDK, the fix might succeed or fail depending on
        # the project state — we just verify the pipeline ran
        assert "auto_fix_success" in result

    @pytest.mark.asyncio
    async def test_live_investigator_diagnosis(
        self, fake_app_url: str, chaos, project_root: Path
    ) -> None:
        """
        Test that the Investigator agent produces a meaningful diagnosis
        when given a health failure scenario.
        """
        from pocketteam.agents.investigator import InvestigatorAgent

        chaos.set(health_status=503)

        investigator = InvestigatorAgent(project_root)
        result = await investigator.execute(
            f"Diagnose: Health endpoint {fake_app_url}/health returns HTTP 503. "
            "Check the endpoint and determine the root cause."
        )

        # The investigator should produce some output
        assert result.output  # Non-empty diagnosis
        # It should recognize this is a service unavailable issue
        assert any(
            keyword in result.output.lower()
            for keyword in ["503", "unavailable", "service", "health", "chaos"]
        )
