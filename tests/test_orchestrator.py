"""
Tests for Phase 11: Orchestrator + CLI integration.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from pocketteam.core.orchestrator import run_task, run_retro, _log_event


# ── run_task ────────────────────────────────────────────────────────────────

class TestRunTask:
    async def test_run_task_creates_context(self, tmp_path: Path):
        """run_task creates a SharedContext and Pipeline."""
        # Create minimal config
        cfg_dir = tmp_path / ".pocketteam"
        cfg_dir.mkdir(parents=True)

        with patch("pocketteam.core.orchestrator.Pipeline") as MockPipeline:
            mock_pipeline = MagicMock()
            mock_pipeline.run = AsyncMock(return_value=True)
            MockPipeline.return_value = mock_pipeline

            result = await run_task(
                task_description="Build auth",
                project_root=tmp_path,
            )

        assert result is True
        MockPipeline.assert_called_once()
        mock_pipeline.run.assert_awaited_once_with(skip_product=True)

    async def test_run_task_pipeline_failure(self, tmp_path: Path):
        with patch("pocketteam.core.orchestrator.Pipeline") as MockPipeline:
            mock_pipeline = MagicMock()
            mock_pipeline.run = AsyncMock(return_value=False)
            MockPipeline.return_value = mock_pipeline

            result = await run_task(
                task_description="Broken task",
                project_root=tmp_path,
            )

        assert result is False

    async def test_run_task_with_callbacks(self, tmp_path: Path):
        status_msgs = []
        approval_calls = []

        async def on_status(msg):
            status_msgs.append(msg)

        async def on_approval(prompt):
            approval_calls.append(prompt)
            return True

        with patch("pocketteam.core.orchestrator.Pipeline") as MockPipeline:
            mock_pipeline = MagicMock()
            mock_pipeline.run = AsyncMock(return_value=True)
            MockPipeline.return_value = mock_pipeline

            await run_task(
                "Test task",
                project_root=tmp_path,
                on_status=on_status,
                on_approval=on_approval,
            )

        # Verify callbacks were passed to Pipeline
        call_kwargs = MockPipeline.call_args[1]
        assert call_kwargs["on_status_update"] is on_status
        assert call_kwargs["on_human_gate"] is on_approval

    async def test_run_task_logs_events(self, tmp_path: Path):
        with patch("pocketteam.core.orchestrator.Pipeline") as MockPipeline:
            mock_pipeline = MagicMock()
            mock_pipeline.run = AsyncMock(return_value=True)
            MockPipeline.return_value = mock_pipeline

            await run_task("Log test", project_root=tmp_path)

        events_path = tmp_path / ".pocketteam/events/stream.jsonl"
        assert events_path.exists()
        lines = events_path.read_text().strip().splitlines()
        assert len(lines) >= 2  # pipeline_start + pipeline_done
        first = json.loads(lines[0])
        assert first["type"] == "pipeline_start"

    async def test_run_task_skip_product_false(self, tmp_path: Path):
        with patch("pocketteam.core.orchestrator.Pipeline") as MockPipeline:
            mock_pipeline = MagicMock()
            mock_pipeline.run = AsyncMock(return_value=True)
            MockPipeline.return_value = mock_pipeline

            await run_task(
                "Feature request",
                project_root=tmp_path,
                skip_product=False,
            )

        mock_pipeline.run.assert_awaited_once_with(skip_product=False)


# ── _log_event ──────────────────────────────────────────────────────────────

class TestLogEvent:
    def test_log_event_creates_file(self, tmp_path: Path):
        _log_event(tmp_path, "coo", "test", "hello")
        path = tmp_path / ".pocketteam/events/stream.jsonl"
        assert path.exists()
        event = json.loads(path.read_text().strip())
        assert event["agent"] == "coo"
        assert event["type"] == "test"
        assert event["action"] == "hello"

    def test_log_event_appends(self, tmp_path: Path):
        _log_event(tmp_path, "coo", "e1", "first")
        _log_event(tmp_path, "engineer", "e2", "second")
        path = tmp_path / ".pocketteam/events/stream.jsonl"
        lines = path.read_text().strip().splitlines()
        assert len(lines) == 2


# ── CLI: pocketteam run ─────────────────────────────────────────────────────

class TestCLIRun:
    def test_run_command_exists(self):
        from pocketteam.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["run", "--help"])
        assert result.exit_code == 0
        assert "pipeline" in result.output.lower()

    def test_sessions_command_exists(self):
        from pocketteam.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["sessions", "--help"])
        assert result.exit_code == 0

    def test_status_requires_config(self):
        from pocketteam.cli import main
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["status"])
        assert result.exit_code != 0


# ── run_retro ───────────────────────────────────────────────────────────────

class TestRunRetro:
    async def test_retro_no_data(self, tmp_path: Path):
        """retro should not crash when no data exists."""
        await run_retro(days=7, project_root=tmp_path)
        # No exception = success

    async def test_retro_with_events(self, tmp_path: Path):
        events_path = tmp_path / ".pocketteam/events/stream.jsonl"
        events_path.parent.mkdir(parents=True)
        events_path.write_text(
            json.dumps({"agent": "engineer", "status": "awake", "action": "coding"}) + "\n"
            + json.dumps({"agent": "qa", "status": "awake", "action": "testing"}) + "\n"
        )
        await run_retro(days=7, project_root=tmp_path)
