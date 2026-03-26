"""
Tests for PocketTeam hooks: keyword_detector and __main__ dispatch.
"""

import json
import subprocess
import sys

import pytest
from pocketteam.hooks.keyword_detector import handle


class TestKeywordDetector:
    """Unit tests for the keyword detector hook handler."""

    def test_keyword_hook_detects_autopilot(self):
        result = handle({"input": "autopilot: build the login feature"})
        assert "additionalContext" in result
        assert "AUTOPILOT" in result["additionalContext"]
        assert "build the login feature" in result["additionalContext"]

    def test_keyword_hook_detects_ralph(self):
        result = handle({"input": "ralph: fix all failing tests"})
        assert "additionalContext" in result
        assert "RALPH" in result["additionalContext"]
        assert "fix all failing tests" in result["additionalContext"]

    def test_keyword_hook_detects_quick(self):
        result = handle({"input": "quick: rename variable foo to bar"})
        assert "additionalContext" in result
        assert "QUICK" in result["additionalContext"]
        assert "rename variable foo to bar" in result["additionalContext"]

    def test_keyword_hook_detects_deep_dive(self):
        result = handle({"input": "deep-dive: WebSocket performance"})
        assert "additionalContext" in result
        assert "DEEP DIVE" in result["additionalContext"]

    def test_keyword_hook_case_insensitive(self):
        result = handle({"input": "AUTOPILOT: build dashboard"})
        assert "additionalContext" in result
        assert "AUTOPILOT" in result["additionalContext"]

    def test_keyword_hook_ralph_mixed_case(self):
        result = handle({"input": "Ralph: implement tests"})
        assert "additionalContext" in result

    def test_keyword_hook_quick_uppercase(self):
        result = handle({"input": "QUICK: hotfix typo"})
        assert "additionalContext" in result

    def test_keyword_hook_no_match(self):
        result = handle({"input": "Please implement the dashboard feature"})
        assert result == {}

    def test_keyword_hook_empty_input(self):
        result = handle({"input": ""})
        assert result == {}

    def test_keyword_hook_no_input_key(self):
        result = handle({})
        assert result == {}

    def test_keyword_hook_non_string_input(self):
        result = handle({"input": 42})
        assert result == {}

    def test_keyword_hook_content_key_fallback(self):
        """Supports 'content' key as alternative to 'input'."""
        result = handle({"content": "autopilot: deploy to staging"})
        assert "additionalContext" in result

    def test_keyword_hook_message_key_fallback(self):
        """Supports 'message' key as alternative to 'input'."""
        result = handle({"message": "ralph: keep retrying until green"})
        assert "additionalContext" in result

    def test_keyword_hook_task_extracted_correctly(self):
        """Task portion after the keyword should be preserved intact."""
        result = handle({"input": "autopilot: refactor auth module and add tests"})
        context = result["additionalContext"]
        assert "refactor auth module and add tests" in context

    def test_keyword_hook_whitespace_trimmed(self):
        """Leading/trailing whitespace around input is handled."""
        result = handle({"input": "  autopilot:  build feature  "})
        assert "additionalContext" in result

    def test_keyword_hook_normal_text_no_colon(self):
        result = handle({"input": "autopilot without colon"})
        assert result == {}


class TestHookDispatch:
    """Integration tests for __main__ dispatch via subprocess."""

    def _run_hook(self, hook_type: str, hook_input: dict) -> dict:
        """Run a hook via subprocess and return parsed output."""
        proc = subprocess.run(
            [sys.executable, "-m", "pocketteam.hooks", hook_type],
            input=json.dumps(hook_input),
            capture_output=True,
            text=True,
        )
        return json.loads(proc.stdout)

    def test_keyword_dispatch_autopilot(self):
        result = self._run_hook("keyword", {"input": "autopilot: build it"})
        assert "additionalContext" in result

    def test_keyword_dispatch_no_match(self):
        result = self._run_hook("keyword", {"input": "just a normal message"})
        assert result == {}

    def test_unknown_hook_returns_empty(self):
        result = self._run_hook("nonexistent_hook_type", {"input": "autopilot: test"})
        assert result == {}

    def test_unknown_hook_does_not_crash(self):
        """Unknown hook type must exit cleanly with empty JSON output."""
        proc = subprocess.run(
            [sys.executable, "-m", "pocketteam.hooks", "totally_unknown"],
            input=json.dumps({"input": "test"}),
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0
        assert json.loads(proc.stdout) == {}

    def test_malformed_json_input_returns_empty(self):
        """Malformed JSON on stdin must not crash the hook — returns empty dict."""
        proc = subprocess.run(
            [sys.executable, "-m", "pocketteam.hooks", "keyword"],
            input="not valid json {{{",
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0
        assert json.loads(proc.stdout) == {}
