"""
Tests for pocketteam/safety/activity_logger.py

Coverage:
- log_activity writes a correctly shaped entry to the daily audit log
- Creates the log file (and parent dirs) when they do not exist
- Handles OSError on mkdir gracefully (never crashes)
- Handles OSError on append_jsonl gracefully (never crashes)
- input_hash format is sha256:<16-hex-chars>
- agent_id defaults to "unknown" when empty string supplied
- Non-string tool_input is JSON-serialised before hashing
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from pocketteam.safety.activity_logger import log_activity

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _audit_dir(tmp_pocketteam: Path) -> Path:
    return tmp_pocketteam / ".pocketteam" / "artifacts" / "audit"


def _log_file(tmp_pocketteam: Path) -> Path:
    date = datetime.now().strftime("%Y-%m-%d")
    return _audit_dir(tmp_pocketteam) / f"{date}.jsonl"


def _read_entries(log_path: Path) -> list[dict]:
    return [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def project_root(tmp_path: Path) -> Path:
    """A temp directory that looks like a PocketTeam project root."""
    pocketteam_dir = tmp_path / ".pocketteam"
    pocketteam_dir.mkdir()
    return tmp_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestLogActivityBasic:
    def test_creates_log_file_when_missing(self, project_root: Path) -> None:
        log_path = _log_file(project_root)
        assert not log_path.exists()

        with patch(
            "pocketteam.safety.activity_logger._find_project_root",
            return_value=project_root,
        ):
            log_activity("Read", "/some/file.py", "engineer")

        assert log_path.exists()

    def test_appends_entry_with_correct_fields(self, project_root: Path) -> None:
        with patch(
            "pocketteam.safety.activity_logger._find_project_root",
            return_value=project_root,
        ):
            log_activity("Write", "print('hello')", "engineer")

        entries = _read_entries(_log_file(project_root))
        assert len(entries) == 1
        entry = entries[0]

        assert entry["event"] == "tool_use"
        assert entry["tool"] == "Write"
        assert entry["agent"] == "engineer"
        assert "ts" in entry
        assert "input_hash" in entry

    def test_input_hash_format(self, project_root: Path) -> None:
        """input_hash must be sha256:<16-hex-chars>"""
        with patch(
            "pocketteam.safety.activity_logger._find_project_root",
            return_value=project_root,
        ):
            log_activity("Bash", "ls -la", "qa")

        entry = _read_entries(_log_file(project_root))[0]
        hash_value = entry["input_hash"]
        assert hash_value.startswith("sha256:")
        hex_part = hash_value[len("sha256:"):]
        assert len(hex_part) == 16
        assert all(c in "0123456789abcdef" for c in hex_part)

    def test_multiple_calls_append(self, project_root: Path) -> None:
        with patch(
            "pocketteam.safety.activity_logger._find_project_root",
            return_value=project_root,
        ):
            log_activity("Read", "file1.py", "engineer")
            log_activity("Bash", "pytest", "qa")

        entries = _read_entries(_log_file(project_root))
        assert len(entries) == 2
        assert entries[0]["tool"] == "Read"
        assert entries[1]["tool"] == "Bash"


class TestLogActivityAgentId:
    def test_empty_agent_id_defaults_to_coo(self, project_root: Path) -> None:
        """Main session (empty agent_id) is the COO."""
        with patch(
            "pocketteam.safety.activity_logger._find_project_root",
            return_value=project_root,
        ):
            log_activity("Read", "file.py", "")

        entry = _read_entries(_log_file(project_root))[0]
        assert entry["agent"] == "coo"

    def test_agent_id_is_preserved(self, project_root: Path) -> None:
        with patch(
            "pocketteam.safety.activity_logger._find_project_root",
            return_value=project_root,
        ):
            log_activity("Glob", "**/*.py", "planner")

        entry = _read_entries(_log_file(project_root))[0]
        assert entry["agent"] == "planner"


class TestLogActivityNonStringInput:
    def test_dict_input_is_serialised_before_hashing(self, project_root: Path) -> None:
        tool_input = {"command": "git status"}
        with patch(
            "pocketteam.safety.activity_logger._find_project_root",
            return_value=project_root,
        ):
            log_activity("Bash", tool_input, "engineer")

        entry = _read_entries(_log_file(project_root))[0]
        # Must not raise and must produce a valid hash
        assert entry["input_hash"].startswith("sha256:")

    def test_list_input_does_not_crash(self, project_root: Path) -> None:
        with patch(
            "pocketteam.safety.activity_logger._find_project_root",
            return_value=project_root,
        ):
            log_activity("Read", ["a", "b", "c"], "engineer")

        # No exception — that is the only guarantee
        assert _log_file(project_root).exists()


class TestLogActivityErrorHandling:
    def test_no_project_root_is_silent(self) -> None:
        """When no .pocketteam dir is found, log_activity must not crash."""
        with patch(
            "pocketteam.safety.activity_logger._find_project_root",
            return_value=None,
        ):
            log_activity("Read", "file.py", "engineer")  # must not raise

    def test_mkdir_oserror_is_silent(self, project_root: Path) -> None:
        """OSError during audit_dir.mkdir must not crash the system."""
        with patch(
            "pocketteam.safety.activity_logger._find_project_root",
            return_value=project_root,
        ):
            with patch("pocketteam.safety.activity_logger.Path.mkdir", side_effect=OSError("disk full")):
                log_activity("Write", "data", "engineer")  # must not raise

    def test_append_oserror_is_silent(self, project_root: Path) -> None:
        """OSError during append_jsonl must not crash the system."""
        with patch(
            "pocketteam.safety.activity_logger._find_project_root",
            return_value=project_root,
        ):
            with patch(
                "pocketteam.safety.activity_logger.append_jsonl",
                side_effect=OSError("permission denied"),
            ):
                log_activity("Bash", "rm foo", "engineer")  # must not raise
