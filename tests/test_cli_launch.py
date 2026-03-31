"""
Tests for _launch_claude() command construction.

Verifies that:
- --agent pocketteam/coo is included in the command
- --agent appears before --continue / --resume session flags
- existing session flags (continue, pick, id) still work
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from pocketteam.cli import _launch_claude


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _capture_cmd(tmp_path, monkeypatch, session_id: str | None = None, **launch_kwargs) -> list[str]:
    """Call _launch_claude() and return the cmd list that would be exec'd.

    Monkeypatches os.execvp to capture the command instead of replacing the
    process, and chdir to tmp_path so config loading finds no .pocketteam/.
    """
    captured: list[list[str]] = []

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(os, "execvp", lambda prog, argv: captured.append(list(argv)))

    # _launch_claude reads config; provide a minimal .pocketteam/config.yaml
    pt_dir = tmp_path / ".pocketteam"
    pt_dir.mkdir(exist_ok=True)
    (pt_dir / "config.yaml").write_text(
        "project:\n  name: test-project\n  health_url: ''\n"
    )

    _launch_claude(session_id=session_id, **launch_kwargs)

    assert len(captured) == 1, "os.execvp was not called exactly once"
    return captured[0]


# ─────────────────────────────────────────────────────────────────────────────
# --agent flag presence tests
# ─────────────────────────────────────────────────────────────────────────────


class TestAgentFlag:
    def test_agent_flag_present(self, tmp_path, monkeypatch):
        """--agent must appear in the command."""
        cmd = _capture_cmd(tmp_path, monkeypatch, resume="new", no_telegram=True)
        assert "--agent" in cmd

    def test_agent_value_is_pocketteam_coo(self, tmp_path, monkeypatch):
        """The value after --agent must be 'pocketteam/coo'."""
        cmd = _capture_cmd(tmp_path, monkeypatch, resume="new", no_telegram=True)
        idx = cmd.index("--agent")
        assert cmd[idx + 1] == "pocketteam/coo"

    def test_agent_flag_present_on_continue(self, tmp_path, monkeypatch):
        """--agent is included even when --continue is added."""
        cmd = _capture_cmd(tmp_path, monkeypatch, resume="continue", no_telegram=True)
        assert "--agent" in cmd
        idx = cmd.index("--agent")
        assert cmd[idx + 1] == "pocketteam/coo"

    def test_agent_flag_present_on_resume_pick(self, tmp_path, monkeypatch):
        """--agent is included even when --resume (picker) is added."""
        cmd = _capture_cmd(tmp_path, monkeypatch, resume="pick", no_telegram=True)
        assert "--agent" in cmd
        idx = cmd.index("--agent")
        assert cmd[idx + 1] == "pocketteam/coo"

    def test_agent_flag_present_on_resume_id(self, tmp_path, monkeypatch):
        """--agent is included even when --resume <id> is added."""
        cmd = _capture_cmd(
            tmp_path, monkeypatch, resume="id", session_id="abc123", no_telegram=True
        )
        assert "--agent" in cmd
        idx = cmd.index("--agent")
        assert cmd[idx + 1] == "pocketteam/coo"


# ─────────────────────────────────────────────────────────────────────────────
# Ordering tests: --agent must precede session flags
# ─────────────────────────────────────────────────────────────────────────────


class TestAgentFlagOrdering:
    def test_agent_before_continue(self, tmp_path, monkeypatch):
        """--agent must appear before --continue in the command list."""
        cmd = _capture_cmd(tmp_path, monkeypatch, resume="continue", no_telegram=True)
        assert "--agent" in cmd
        assert "--continue" in cmd
        assert cmd.index("--agent") < cmd.index("--continue")

    def test_agent_before_resume_picker(self, tmp_path, monkeypatch):
        """--agent must appear before --resume (session picker) in the command list."""
        cmd = _capture_cmd(tmp_path, monkeypatch, resume="pick", no_telegram=True)
        assert "--agent" in cmd
        assert "--resume" in cmd
        assert cmd.index("--agent") < cmd.index("--resume")

    def test_agent_before_resume_id(self, tmp_path, monkeypatch):
        """--agent must appear before --resume <id> in the command list."""
        cmd = _capture_cmd(
            tmp_path, monkeypatch, resume="id", session_id="abc123", no_telegram=True
        )
        assert "--agent" in cmd
        assert "--resume" in cmd
        assert cmd.index("--agent") < cmd.index("--resume")
