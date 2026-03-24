"""
Tests for Safety Layer 10: Kill Switch
Out-of-band stop mechanism — completely independent of agent context.
"""

import time
import threading
import pytest
from pathlib import Path
from pocketteam.safety.kill_switch import KillSwitch, KillSwitchGuard, KillSwitchError


@pytest.fixture
def tmp_project(tmp_path):
    (tmp_path / ".pocketteam").mkdir()
    return tmp_path


class TestKillSwitch:
    """Layer 10: Kill switch tests."""

    def test_not_active_by_default(self, tmp_project):
        ks = KillSwitch(tmp_project)
        assert not ks.is_active

    def test_activate_creates_file(self, tmp_project):
        ks = KillSwitch(tmp_project)
        ks.activate("test")
        assert (tmp_project / ".pocketteam/KILL").exists()
        assert ks.is_active

    def test_deactivate_removes_file(self, tmp_project):
        ks = KillSwitch(tmp_project)
        ks.activate("test")
        ks.deactivate()
        assert not ks.is_active

    def test_activate_returns_event(self, tmp_project):
        ks = KillSwitch(tmp_project)
        event = ks.activate("cli")
        assert event.trigger_source == "cli"
        assert event.triggered_at > 0

    def test_on_kill_callback_invoked(self, tmp_project):
        events = []
        ks = KillSwitch(tmp_project, on_kill=lambda e: events.append(e))
        ks.activate("test")
        assert len(events) == 1
        assert events[0].trigger_source == "test"

    def test_file_watch_detects_external_kill(self, tmp_project):
        """Simulate external kill (e.g., `touch .pocketteam/KILL` from terminal)."""
        detected = threading.Event()
        ks = KillSwitch(
            tmp_project,
            on_kill=lambda e: detected.set(),
        )
        ks.arm()

        # External process touches the kill file
        kill_file = tmp_project / ".pocketteam/KILL"
        kill_file.touch()

        # Should be detected within ~2 seconds
        assert detected.wait(timeout=3), "Kill switch was not detected"
        ks.disarm()

    def test_telegram_kill_source(self, tmp_project):
        ks = KillSwitch(tmp_project)
        event = ks.activate("telegram")
        assert event.trigger_source == "telegram"

    def test_invalidates_dsac_tokens_on_kill(self, tmp_project):
        """Kill switch must invalidate all pending D-SAC tokens."""
        from pocketteam.safety.dsac import DSACGuard

        guard = DSACGuard(tmp_project)
        preview = guard.create_dry_run_preview("Bash", "rm file.txt", ["file.txt"])
        guard.issue_approval_token(preview, "devops", "task-001")

        ks = KillSwitch(tmp_project)
        event = ks.activate("test")
        assert event.tokens_invalidated == 1

        # Token should now be invalid
        tokens = guard._load_tokens()
        assert all(t["used"] for t in tokens.values())


class TestKillSwitchGuard:
    """Context manager and guard behavior."""

    def test_raises_when_kill_active(self, tmp_project):
        ks = KillSwitch(tmp_project)
        ks.activate("test")

        guard = KillSwitchGuard(ks)
        with pytest.raises(KillSwitchError):
            guard.check()

    def test_context_manager_raises(self, tmp_project):
        ks = KillSwitch(tmp_project)
        ks.activate("test")

        with pytest.raises(KillSwitchError):
            with KillSwitchGuard(ks):
                pass  # Should raise before this line

    def test_no_raise_when_not_active(self, tmp_project):
        ks = KillSwitch(tmp_project)
        guard = KillSwitchGuard(ks)

        # Should not raise
        guard.check()
        with KillSwitchGuard(ks):
            pass

    def test_stops_within_1_second(self, tmp_project):
        """Kill switch must be detected within 1 second (SLA)."""
        detected_at = [None]
        activated_at = [None]

        def on_kill(event):
            detected_at[0] = time.time()

        ks = KillSwitch(tmp_project, on_kill=on_kill)
        ks.arm()

        activated_at[0] = time.time()
        (tmp_project / ".pocketteam/KILL").touch()

        time.sleep(2)  # Wait for detection
        ks.disarm()

        assert detected_at[0] is not None, "Kill switch not detected"
        detection_time = detected_at[0] - activated_at[0]
        assert detection_time < 2, f"Kill switch took {detection_time:.2f}s (must be < 2s)"
