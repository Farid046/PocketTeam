"""
Tests for _launch_claude() command construction.

Verifies that:
- --agent pocketteam/coo is included in the command
- --agent appears before --continue / --resume session flags
- existing session flags (continue, pick, id) still work
- when resume="continue" and no session exists, falls back to a new session (no --continue)
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from pocketteam.cli import _launch_claude, _has_existing_session


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
        # Need an existing session so --continue is not suppressed
        project_key = str(tmp_path).replace("/", "-").lstrip("-")
        session_dir = tmp_path / ".claude_home" / "projects" / project_key
        session_dir.mkdir(parents=True)
        (session_dir / "fake-session.jsonl").write_text("{}\n")
        monkeypatch.setenv("HOME", str(tmp_path / ".claude_home" / ".."))

        # Patch _has_existing_session to return True so --continue is added
        with patch("pocketteam.cli._has_existing_session", return_value=True):
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


# ─────────────────────────────────────────────────────────────────────────────
# Session existence detection
# ─────────────────────────────────────────────────────────────────────────────


class TestHasExistingSession:
    def test_returns_false_when_no_project_dir(self, tmp_path):
        """_has_existing_session returns False when project dir does not exist."""
        assert _has_existing_session(tmp_path) is False

    def test_returns_false_when_project_dir_empty(self, tmp_path, monkeypatch):
        """_has_existing_session returns False when project dir has no .jsonl files."""
        home = tmp_path / "home"
        project_key = str(tmp_path).replace("/", "-").lstrip("-")
        session_dir = home / ".claude" / "projects" / project_key
        session_dir.mkdir(parents=True)
        monkeypatch.setenv("HOME", str(home))
        assert _has_existing_session(tmp_path) is False

    def test_returns_true_when_jsonl_exists(self, tmp_path, monkeypatch):
        """_has_existing_session returns True when at least one .jsonl file exists."""
        home = tmp_path / "home"
        project_key = str(tmp_path).replace("/", "-").lstrip("-")
        session_dir = home / ".claude" / "projects" / project_key
        session_dir.mkdir(parents=True)
        (session_dir / "abc123.jsonl").write_text("{}\n")
        monkeypatch.setenv("HOME", str(home))
        assert _has_existing_session(tmp_path) is True


# ─────────────────────────────────────────────────────────────────────────────
# Fallback: no session exists → start new instead of --continue
# ─────────────────────────────────────────────────────────────────────────────


class TestContinueFallback:
    def test_no_continue_when_no_session(self, tmp_path, monkeypatch):
        """When resume='continue' and no session exists, --continue must NOT be in cmd."""
        with patch("pocketteam.cli._has_existing_session", return_value=False):
            cmd = _capture_cmd(tmp_path, monkeypatch, resume="continue", no_telegram=True)
        assert "--continue" not in cmd

    def test_new_session_started_when_no_session(self, tmp_path, monkeypatch):
        """When resume='continue' and no session exists, cmd must still contain core flags."""
        with patch("pocketteam.cli._has_existing_session", return_value=False):
            cmd = _capture_cmd(tmp_path, monkeypatch, resume="continue", no_telegram=True)
        assert "claude" in cmd[0]
        assert "--dangerously-skip-permissions" in cmd

    def test_continue_present_when_session_exists(self, tmp_path, monkeypatch):
        """When resume='continue' and a session exists, --continue must be in cmd."""
        with patch("pocketteam.cli._has_existing_session", return_value=True):
            cmd = _capture_cmd(tmp_path, monkeypatch, resume="continue", no_telegram=True)
        assert "--continue" in cmd
