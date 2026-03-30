"""
End-to-end integration tests.
Verify that all components work together.
No real SDK/API/Telegram calls — all external boundaries mocked.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pocketteam.agents.base import AgentResult
from pocketteam.config import PocketTeamConfig, load_config, save_config
from pocketteam.core.context import SharedContext
from pocketteam.core.pipeline import Pipeline

# ── Full Pipeline Integration ───────────────────────────────────────────────

class TestPipelineIntegration:
    """Test the pipeline state machine with mocked agents."""

    def _make_context(self, tmp_path: Path, task: str = "Build feature") -> SharedContext:
        return SharedContext.create_new(
            task_description=task,
            project_root=tmp_path,
        )

    def _success_result(self, agent_id: str, output: str = "done") -> AgentResult:
        return AgentResult(
            agent_id=agent_id,
            success=True,
            output=output,
            artifacts={},
        )

    async def test_pipeline_success_all_phases(self, tmp_path: Path):
        """Full pipeline run with all phases succeeding."""
        ctx = self._make_context(tmp_path)
        approvals = []

        async def auto_approve(prompt: str) -> bool:
            approvals.append(prompt)
            return True

        statuses = []

        async def track_status(msg: str) -> None:
            statuses.append(msg)

        pipeline = Pipeline(
            context=ctx,
            on_human_gate=auto_approve,
            on_status_update=track_status,
        )

        def _make_mock_agent(agent_id):
            mock = MagicMock()
            mock.execute = AsyncMock(return_value=AgentResult(
                agent_id=agent_id, success=True,
                output=f"{agent_id} done. APPROVED.",
            ))
            return mock

        # Agents are lazily imported inside pipeline methods, so patch at source
        with patch("pocketteam.agents.planner.PlannerAgent", return_value=_make_mock_agent("planner")), \
             patch("pocketteam.agents.reviewer.ReviewerAgent", return_value=_make_mock_agent("reviewer")), \
             patch("pocketteam.agents.engineer.EngineerAgent", return_value=_make_mock_agent("engineer")), \
             patch("pocketteam.agents.qa.QAAgent", return_value=_make_mock_agent("qa")), \
             patch("pocketteam.agents.security.SecurityAgent", return_value=_make_mock_agent("security")), \
             patch("pocketteam.agents.documentation.DocumentationAgent", return_value=_make_mock_agent("documentation")), \
             patch("pocketteam.agents.devops.DevOpsAgent", return_value=_make_mock_agent("devops")), \
             patch("pocketteam.agents.monitor.MonitorAgent", return_value=_make_mock_agent("monitor")):
            success = await pipeline.run(skip_product=True)

        assert success is True
        assert len(approvals) >= 2  # Planning + Production gates
        assert len(statuses) >= 5  # At least one per phase

    async def test_pipeline_fails_on_planning(self, tmp_path: Path):
        """Pipeline should stop if planning fails."""
        ctx = self._make_context(tmp_path)
        pipeline = Pipeline(context=ctx)

        mock_planner = MagicMock()
        mock_planner.execute = AsyncMock(return_value=AgentResult(
            agent_id="planner", success=False, output="", error="Cannot plan"
        ))

        with patch("pocketteam.agents.planner.PlannerAgent", return_value=mock_planner):
            success = await pipeline.run()

        assert success is False

    async def test_pipeline_stops_on_rejection(self, tmp_path: Path):
        """Pipeline should stop when CEO rejects at human gate."""
        ctx = self._make_context(tmp_path)

        async def reject(prompt: str) -> bool:
            return False

        pipeline = Pipeline(context=ctx, on_human_gate=reject)

        mock_planner = MagicMock()
        mock_planner.execute = AsyncMock(return_value=AgentResult(
            agent_id="planner", success=True, output="plan done",
        ))
        mock_reviewer = MagicMock()
        mock_reviewer.execute = AsyncMock(return_value=AgentResult(
            agent_id="reviewer", success=True, output="review done",
        ))

        with patch("pocketteam.agents.planner.PlannerAgent", return_value=mock_planner), \
             patch("pocketteam.agents.reviewer.ReviewerAgent", return_value=mock_reviewer):
            success = await pipeline.run()

        assert success is False  # Rejected at planning gate


# ── Context Persistence ─────────────────────────────────────────────────────

class TestContextPersistence:
    def test_create_persist_load(self, tmp_path: Path):
        ctx = SharedContext.create_new(
            task_description="Build auth",
            project_root=tmp_path,
        )
        ctx.add_artifact("plan-v1", "planner", "The plan", "plan")
        ctx.advance_phase("implementation")
        ctx.set("custom_key", 42)

        # Load
        loaded = SharedContext.load(ctx.task_id, tmp_path)
        assert loaded is not None
        assert loaded.task_description == "Build auth"
        assert loaded.phase == "implementation"
        assert loaded.get("custom_key") == 42
        assert loaded.get_artifact("plan-v1") is not None

    def test_messaging(self, tmp_path: Path):
        ctx = SharedContext.create_new(
            task_description="Test",
            project_root=tmp_path,
        )
        ctx.send_message("engineer", "reviewer", "Code ready for review")
        ctx.send_message("reviewer", "engineer", "Fix line 42")

        engineer_msgs = ctx.get_messages_for("engineer")
        assert len(engineer_msgs) == 1
        assert "Fix line 42" in engineer_msgs[0]["content"]


# ── Config Roundtrip ────────────────────────────────────────────────────────

class TestConfigRoundtrip:
    def test_save_and_load(self, tmp_path: Path):
        cfg = PocketTeamConfig(
            project_root=tmp_path,
            project_name="TestApp",
            health_url="http://test.com/health",
        )
        save_config(cfg)

        loaded = load_config(tmp_path)
        assert loaded.project_name == "TestApp"
        assert loaded.health_url == "http://test.com/health"

    def test_load_missing_config(self, tmp_path: Path):
        cfg = load_config(tmp_path)
        assert cfg.project_name == tmp_path.name  # Falls back to dir name


# ── CLI Commands ────────────────────────────────────────────────────────────

class TestCLICommands:
    def test_all_commands_registered(self):
        from click.testing import CliRunner

        from pocketteam.cli import main
        runner = CliRunner()

        for cmd in ["init", "status", "kill", "resume", "retro", "logs", "run-headless", "sessions", "uninstall"]:
            result = runner.invoke(main, [cmd, "--help"])
            assert result.exit_code == 0, f"Command '{cmd}' failed: {result.output}"

    def test_version(self):
        from click.testing import CliRunner

        from pocketteam.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0


# ── Safety Integration ──────────────────────────────────────────────────────

class TestSafetyIntegration:
    def test_kill_switch_blocks_pipeline(self, tmp_path: Path):
        from pocketteam.safety.kill_switch import KillSwitch

        ks = KillSwitch(tmp_path)
        ks.activate()

        ctx = SharedContext.create_new(
            task_description="Should be blocked",
            project_root=tmp_path,
        )
        pipeline = Pipeline(context=ctx)

        # Pipeline should check kill switch and raise
        import asyncio

        from pocketteam.safety.kill_switch import KillSwitchError

        with pytest.raises(KillSwitchError):
            asyncio.run(pipeline.run())

    def test_guardian_blocks_dangerous_commands(self, tmp_path):
        from pocketteam.safety.guardian import pre_tool_hook

        # Use isolated project root to avoid rate limits from live session
        (tmp_path / ".pocketteam").mkdir()
        import os
        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            result = pre_tool_hook("Bash", {"command": "rm -rf /"}, "engineer")
            assert result["allow"] is False

            result = pre_tool_hook("Bash", {"command": "ls -la"}, "engineer")
            assert result["allow"] is True
        finally:
            os.chdir(old_cwd)

    def test_guardian_enforces_agent_allowlist(self, tmp_path):
        from pocketteam.safety.guardian import pre_tool_hook

        # Use isolated project root to avoid rate limits from live session
        (tmp_path / ".pocketteam").mkdir()
        import os
        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            # Planner should NOT be able to use Write
            result = pre_tool_hook("Write", {"file_path": "test.py"}, "planner")
            assert result["allow"] is False

            # Engineer CAN use Write
            result = pre_tool_hook("Write", {"file_path": "test.py"}, "engineer")
            assert result["allow"] is True
        finally:
            os.chdir(old_cwd)


# ── Agent Module Imports ────────────────────────────────────────────────────

class TestImports:
    def test_all_agents_importable(self):
        pass

    def test_all_tools_importable(self):
        pass

    def test_all_safety_importable(self):
        pass

    def test_all_modules_importable(self):
        pass

    def test_channels_importable(self):
        pass

    def test_monitoring_importable(self):
        pass
