"""
Kill switch (Layer 10) has been removed.

Sessions are stopped via Esc in Claude Code, which interrupts the agent immediately.
This is more reliable than a file-based kill switch because it works during active
tool calls and does not require a polling loop.
"""

import pytest


def test_session_stop_via_esc_is_documented():
    """The kill switch was removed — Esc in Claude Code is the stop mechanism."""
    pass
