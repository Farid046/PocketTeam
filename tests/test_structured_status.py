"""
Tests for structured agent status reporting (Feature 4).

Verifies that _parse_agent_status correctly extracts the STATUS token
from the last non-empty line of an agent's output message.
"""

from pocketteam.hooks.agent_lifecycle import _parse_agent_status


class TestParseAgentStatus:
    """Unit tests for _parse_agent_status."""

    def test_parse_done(self):
        """Plain DONE token returns ("DONE", "")."""
        result = _parse_agent_status("STATUS: DONE")
        assert result == ("DONE", "")

    def test_parse_done_with_concerns(self):
        """DONE_WITH_CONCERNS token returns status and reason."""
        result = _parse_agent_status("STATUS: DONE_WITH_CONCERNS — low coverage")
        assert result == ("DONE_WITH_CONCERNS", "low coverage")

    def test_parse_needs_context(self):
        """NEEDS_CONTEXT token returns status and reason."""
        result = _parse_agent_status("STATUS: NEEDS_CONTEXT — missing DB schema")
        assert result == ("NEEDS_CONTEXT", "missing DB schema")

    def test_parse_blocked(self):
        """BLOCKED token returns status and reason."""
        result = _parse_agent_status("STATUS: BLOCKED — staging is down")
        assert result == ("BLOCKED", "staging is down")

    def test_parse_multiline_status_on_last_line(self):
        """STATUS token on last line of multiline text is found correctly."""
        message = (
            "All tests passed with 92% coverage.\n"
            "Integration tests required minor mocking adjustments.\n"
            "\n"
            "STATUS: DONE_WITH_CONCERNS — coverage below 95% threshold"
        )
        result = _parse_agent_status(message)
        assert result == ("DONE_WITH_CONCERNS", "coverage below 95% threshold")

    def test_parse_no_status_token_defaults_to_done(self):
        """Message without a STATUS token defaults to ("DONE", "")."""
        result = _parse_agent_status("Everything looks good, no issues found.")
        assert result == ("DONE", "")

    def test_parse_empty_string_defaults_to_done(self):
        """Empty string defaults to ("DONE", "")."""
        result = _parse_agent_status("")
        assert result == ("DONE", "")
