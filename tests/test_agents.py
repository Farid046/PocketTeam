"""
Tests for Phase 8: Agent SDK Integration.

All tests mock the Claude Agent SDK so no real API calls are made.
Covers: instantiation, agent IDs, system prompts, SDK wiring,
artifact extraction, error handling, kill switch, and upgrade path.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pocketteam.agents.coo import COOAgent
from pocketteam.agents.devops import DevOpsAgent
from pocketteam.agents.documentation import DocumentationAgent
from pocketteam.agents.engineer import EngineerAgent
from pocketteam.agents.investigator import InvestigatorAgent
from pocketteam.agents.monitor import MonitorAgent
from pocketteam.agents.planner import PlannerAgent
from pocketteam.agents.product import ProductAgent
from pocketteam.agents.qa import QAAgent
from pocketteam.agents.reviewer import ReviewerAgent
from pocketteam.agents.security import SecurityAgent

# ── Helpers ───────────────────────────────────────────────────────────────────

def make_result_message(
    output: str = "Task completed.",
    is_error: bool = False,
    num_turns: int = 3,
    cost: float = 0.05,
) -> Any:
    """Build a minimal fake ResultMessage."""
    msg = MagicMock()
    msg.__class__.__name__ = "ResultMessage"
    msg.result = output
    msg.is_error = is_error
    msg.num_turns = num_turns
    msg.total_cost_usd = cost
    return msg


def make_assistant_message(text: str) -> Any:
    """Build a minimal fake AssistantMessage with a TextBlock."""
    block = MagicMock()
    block.__class__.__name__ = "TextBlock"
    block.text = text

    msg = MagicMock()
    msg.__class__.__name__ = "AssistantMessage"
    msg.content = [block]
    return msg


async def _fake_query_success(prompt: str, options: Any) -> AsyncIterator[Any]:
    """Fake query() that yields one AssistantMessage then a ResultMessage."""
    from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock

    # We use real SDK types so isinstance() checks in _run_with_sdk work
    text_block = MagicMock(spec=TextBlock)
    text_block.text = "This is the agent output."

    assistant = MagicMock(spec=AssistantMessage)
    assistant.content = [text_block]
    yield assistant

    result = MagicMock(spec=ResultMessage)
    result.result = "This is the agent output."
    result.is_error = False
    result.num_turns = 2
    result.total_cost_usd = 0.03
    yield result


async def _fake_query_error(prompt: str, options: Any) -> AsyncIterator[Any]:
    """Fake query() that returns an error ResultMessage."""
    from claude_agent_sdk import ResultMessage

    result = MagicMock(spec=ResultMessage)
    result.result = "Authentication failed"
    result.is_error = True
    result.num_turns = 1
    result.total_cost_usd = 0.0
    yield result


# ── Instantiation & agent IDs ─────────────────────────────────────────────────

class TestAgentInstantiation:
    """All 11 agents can be created and report the correct ID."""

    @pytest.mark.parametrize("agent_class, expected_id", [
        (COOAgent,           "coo"),
        (ProductAgent,       "product"),
        (PlannerAgent,       "planner"),
        (ReviewerAgent,      "reviewer"),
        (EngineerAgent,      "engineer"),
        (QAAgent,            "qa"),
        (SecurityAgent,      "security"),
        (DevOpsAgent,        "devops"),
        (InvestigatorAgent,  "investigator"),
        (DocumentationAgent, "documentation"),
        (MonitorAgent,       "monitor"),
    ])
    def test_agent_id(self, tmp_path: Path, agent_class: type, expected_id: str):
        agent = agent_class(tmp_path)
        assert agent.agent_id == expected_id

    @pytest.mark.parametrize("agent_class", [
        COOAgent, ProductAgent, PlannerAgent, ReviewerAgent, EngineerAgent,
        QAAgent, SecurityAgent, DevOpsAgent, InvestigatorAgent,
        DocumentationAgent, MonitorAgent,
    ])
    def test_system_prompt_fallback(self, tmp_path: Path, agent_class: type):
        """system_prompt returns a non-empty string even without installed prompts."""
        agent = agent_class(tmp_path)
        prompt = agent.system_prompt
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    @pytest.mark.parametrize("agent_class", [
        COOAgent, ProductAgent, PlannerAgent, ReviewerAgent, EngineerAgent,
        QAAgent, SecurityAgent, DevOpsAgent, InvestigatorAgent,
        DocumentationAgent, MonitorAgent,
    ])
    def test_model_assigned(self, tmp_path: Path, agent_class: type):
        """Each agent gets a model string from AGENT_MODELS."""
        agent = agent_class(tmp_path)
        assert agent._model.startswith("claude-")


# ── _run_with_sdk wiring ──────────────────────────────────────────────────────

class TestRunWithSDK:
    """_run_with_sdk() correctly handles success and error ResultMessages."""

    async def test_success_returns_output(self, tmp_path: Path):
        agent = PlannerAgent(tmp_path)
        agent._start_time = __import__("time").time()

        with patch("claude_agent_sdk.query", side_effect=_fake_query_success):
            result = await agent._run_with_sdk("Write a plan")

        assert result.success is True
        assert "agent output" in result.output
        assert result.turns_used == 2
        assert result.spend_usd == pytest.approx(0.03)

    async def test_error_result_returns_failure(self, tmp_path: Path):
        agent = PlannerAgent(tmp_path)
        agent._start_time = __import__("time").time()

        with patch("claude_agent_sdk.query", side_effect=_fake_query_error):
            result = await agent._run_with_sdk("Write a plan")

        assert result.success is False
        assert result.error is not None
        assert "Authentication" in result.error

    async def test_can_use_tool_allows_safe_tool(self, tmp_path: Path):
        """can_use_tool callback allows tools that pass the safety guardian."""
        agent = EngineerAgent(tmp_path)
        captured_options: list[Any] = []

        async def _capture_options(prompt: str, options: Any) -> AsyncIterator[Any]:
            captured_options.append(options)
            yield MagicMock(spec=__import__("claude_agent_sdk").ResultMessage,
                            result="done", is_error=False, num_turns=1, total_cost_usd=0.0)

        agent._start_time = __import__("time").time()
        with patch("claude_agent_sdk.query", side_effect=_capture_options):
            await agent._run_with_sdk("implement feature")

        assert len(captured_options) == 1
        options = captured_options[0]
        assert options.can_use_tool is not None

    async def test_can_use_tool_denies_never_allow(self, tmp_path: Path):
        """can_use_tool callback denies tools blocked by safety guardian."""
        from claude_agent_sdk import ClaudeAgentOptions, PermissionResultDeny
        agent = EngineerAgent(tmp_path)

        captured_options: list[ClaudeAgentOptions] = []

        async def _capture_options(prompt: str, options: Any) -> AsyncIterator[Any]:
            captured_options.append(options)
            # Test the callback directly — rm -rf / is Layer 1 NEVER_ALLOW
            deny_result = await options.can_use_tool(
                "Bash", {"command": "rm -rf /"}, None
            )
            assert isinstance(deny_result, PermissionResultDeny)
            assert deny_result.behavior == "deny"
            yield MagicMock(spec=__import__("claude_agent_sdk").ResultMessage,
                            result="done", is_error=False, num_turns=1, total_cost_usd=0.0)

        agent._start_time = __import__("time").time()
        with patch("claude_agent_sdk.query", side_effect=_capture_options):
            await agent._run_with_sdk("implement feature")


# ── Agent-specific artifact extraction ───────────────────────────────────────

class TestArtifactExtraction:
    """Each agent populates the expected artifacts from SDK output."""

    @pytest.fixture()
    def mock_sdk_success(self):
        return patch("claude_agent_sdk.query", side_effect=_fake_query_success)

    async def test_planner_artifacts(self, tmp_path: Path, mock_sdk_success: Any):
        agent = PlannerAgent(tmp_path)
        with mock_sdk_success:
            result = await agent.execute("Create a plan")
        assert "plan" in result.artifacts
        assert len(result.artifacts["plan"]) > 0

    async def test_reviewer_approved_flag_true(self, tmp_path: Path):
        """ReviewerAgent sets approved=True when 'APPROVED' in output."""
        async def _approved_query(prompt: str, options: Any) -> AsyncIterator[Any]:
            from claude_agent_sdk import ResultMessage
            r = MagicMock(spec=ResultMessage)
            r.result = "APPROVED — code looks good"
            r.is_error = False
            r.num_turns = 1
            r.total_cost_usd = 0.0
            yield r

        agent = ReviewerAgent(tmp_path)
        with patch("claude_agent_sdk.query", side_effect=_approved_query):
            result = await agent.execute("Review the code")
        assert result.artifacts.get("approved") is True

    async def test_reviewer_approved_flag_false(self, tmp_path: Path):
        """ReviewerAgent sets approved=False when 'APPROVED' not in output."""
        async def _rejected_query(prompt: str, options: Any) -> AsyncIterator[Any]:
            from claude_agent_sdk import ResultMessage
            r = MagicMock(spec=ResultMessage)
            r.result = "Needs fixes: missing error handling"
            r.is_error = False
            r.num_turns = 1
            r.total_cost_usd = 0.0
            yield r

        agent = ReviewerAgent(tmp_path)
        with patch("claude_agent_sdk.query", side_effect=_rejected_query):
            result = await agent.execute("Review the code")
        assert result.artifacts.get("approved") is False

    async def test_engineer_artifacts(self, tmp_path: Path, mock_sdk_success: Any):
        agent = EngineerAgent(tmp_path)
        with mock_sdk_success:
            result = await agent.execute("Implement auth")
        assert "implementation" in result.artifacts

    async def test_security_has_critical_false(self, tmp_path: Path, mock_sdk_success: Any):
        agent = SecurityAgent(tmp_path)
        with mock_sdk_success:
            result = await agent.execute("Security audit")
        assert result.artifacts.get("has_critical") is False

    async def test_security_has_critical_true(self, tmp_path: Path):
        async def _critical_query(prompt: str, options: Any) -> AsyncIterator[Any]:
            from claude_agent_sdk import ResultMessage
            r = MagicMock(spec=ResultMessage)
            r.result = "CRITICAL: SQL injection found in login endpoint"
            r.is_error = False
            r.num_turns = 1
            r.total_cost_usd = 0.0
            yield r

        agent = SecurityAgent(tmp_path)
        with patch("claude_agent_sdk.query", side_effect=_critical_query):
            result = await agent.execute("Audit")
        assert result.artifacts.get("has_critical") is True

    async def test_monitor_anomaly_detected(self, tmp_path: Path):
        async def _anomaly_query(prompt: str, options: Any) -> AsyncIterator[Any]:
            from claude_agent_sdk import ResultMessage
            r = MagicMock(spec=ResultMessage)
            r.result = "ANOMALY: DB connection timeouts detected (47/h)"
            r.is_error = False
            r.num_turns = 1
            r.total_cost_usd = 0.0
            yield r

        agent = MonitorAgent(tmp_path)
        with patch("claude_agent_sdk.query", side_effect=_anomaly_query):
            result = await agent.execute("Health check")
        assert result.artifacts.get("anomaly_detected") is True

    async def test_monitor_healthy(self, tmp_path: Path, mock_sdk_success: Any):
        agent = MonitorAgent(tmp_path)
        with mock_sdk_success:
            result = await agent.execute("Health check")
        assert result.artifacts.get("anomaly_detected") is False

    async def test_investigator_requires_human(self, tmp_path: Path):
        async def _escalate_query(prompt: str, options: Any) -> AsyncIterator[Any]:
            from claude_agent_sdk import ResultMessage
            r = MagicMock(spec=ResultMessage)
            r.result = "3 attempts failed. ESCALATE to CEO."
            r.is_error = False
            r.num_turns = 3
            r.total_cost_usd = 0.0
            yield r

        agent = InvestigatorAgent(tmp_path)
        with patch("claude_agent_sdk.query", side_effect=_escalate_query):
            result = await agent.execute("Investigate production crash")
        assert result.artifacts.get("requires_human") is True


# ── Kill switch integration ───────────────────────────────────────────────────

class TestKillSwitch:
    """Kill switch prevents agent execution."""

    async def test_kill_switch_halts_agent(self, tmp_path: Path):
        # Create the KILL file
        kill_dir = tmp_path / ".pocketteam"
        kill_dir.mkdir()
        (kill_dir / "KILL").touch()

        agent = EngineerAgent(tmp_path)
        result = await agent.execute("implement something")

        # Should fail gracefully — kill switch raises KillSwitchError
        # which execute() catches and returns as AgentResult(success=False)
        assert result.success is False
        assert result.error is not None

    async def test_no_kill_switch_proceeds(self, tmp_path: Path):
        """Without KILL file the agent proceeds to SDK call."""
        agent = PlannerAgent(tmp_path)
        with patch("claude_agent_sdk.query", side_effect=_fake_query_success):
            result = await agent.execute("Create plan")
        assert result.success is True


# ── Engineer Opus upgrade ─────────────────────────────────────────────────────

class TestEngineerOpusUpgrade:
    async def test_upgrade_uses_opus_then_restores(self, tmp_path: Path):
        agent = EngineerAgent(tmp_path)
        original_model = agent._model

        recorded_models: list[str] = []

        async def _record_model(prompt: str, options: Any) -> AsyncIterator[Any]:
            from claude_agent_sdk import ResultMessage
            recorded_models.append(options.model)
            r = MagicMock(spec=ResultMessage)
            r.result = "Opus result"
            r.is_error = False
            r.num_turns = 5
            r.total_cost_usd = 0.20
            yield r

        with patch("claude_agent_sdk.query", side_effect=_record_model):
            result = await agent.upgrade_to_opus("complex refactor")

        assert result.success is True
        assert recorded_models[0] == "claude-opus-4-6"
        # Model restored after upgrade
        assert agent._model == original_model


# ── COO pipeline delegation ───────────────────────────────────────────────────

class TestCOOAgent:
    async def test_coo_run_calls_sdk(self, tmp_path: Path):
        agent = COOAgent(tmp_path)
        with patch("claude_agent_sdk.query", side_effect=_fake_query_success):
            result = await agent.execute("Orchestrate a feature")
        assert result.success is True

    async def test_coo_run_pipeline_invokes_pipeline(self, tmp_path: Path):
        """run_pipeline() creates a Pipeline and calls run()."""
        agent = COOAgent(tmp_path)

        mock_pipeline = AsyncMock()
        mock_pipeline.run = AsyncMock(return_value=True)

        with patch("pocketteam.core.pipeline.Pipeline", return_value=mock_pipeline):
            with patch("pocketteam.core.context.SharedContext"):
                result = await agent.run_pipeline("Build user auth")

        assert result is True
        mock_pipeline.run.assert_called_once()
