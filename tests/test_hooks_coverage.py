"""
Unit tests for 5 previously-untested hook files:
  session_start, session_stop, pre_compact, telegram_inbox, delegation_enforcer
"""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_find(tmp_path: Path):
    """Return a patcher that makes _find_pocketteam_dir() return tmp_path."""
    return patch(
        "pocketteam.hooks._utils._find_pocketteam_dir",
        return_value=tmp_path,
    )


# ---------------------------------------------------------------------------
# session_start
# ---------------------------------------------------------------------------

class TestSessionStart:
    """Tests for pocketteam.hooks.session_start.handle()."""

    def _handle(self, tmp_path: Path, hook_input: dict | None = None):
        from pocketteam.hooks import session_start
        with patch.object(session_start, "_find_pocketteam_dir", return_value=tmp_path):
            # Suppress the _notify_telegram network call
            with patch.object(session_start, "_notify_telegram"):
                return session_start.handle(hook_input or {})

    def test_no_inbox_file_returns_empty(self, tmp_path):
        result = self._handle(tmp_path)
        assert result == {}

    def test_inbox_with_received_messages_returns_context(self, tmp_path):
        inbox = tmp_path / "telegram-inbox.jsonl"
        entry = {
            "ts": "2026-03-30T10:00:00+00:00",
            "from": "farid",
            "text": "Hello PocketTeam",
            "status": "received",
            "session_id": "abc",
        }
        inbox.write_text(json.dumps(entry) + "\n")

        result = self._handle(tmp_path)

        assert "additionalContext" in result
        assert "Hello PocketTeam" in result["additionalContext"]

    def test_inbox_messages_marked_as_presented(self, tmp_path):
        inbox = tmp_path / "telegram-inbox.jsonl"
        entry = {
            "ts": "2026-03-30T10:00:00+00:00",
            "from": "farid",
            "text": "Mark me",
            "status": "received",
            "session_id": "abc",
        }
        inbox.write_text(json.dumps(entry) + "\n")

        self._handle(tmp_path)

        updated = [json.loads(l) for l in inbox.read_text().splitlines() if l.strip()]
        assert updated[0]["status"] == "presented"

    def test_already_presented_messages_not_returned(self, tmp_path):
        inbox = tmp_path / "telegram-inbox.jsonl"
        entry = {
            "ts": "2026-03-30T10:00:00+00:00",
            "from": "farid",
            "text": "Already seen",
            "status": "presented",
            "session_id": "abc",
        }
        inbox.write_text(json.dumps(entry) + "\n")

        result = self._handle(tmp_path)
        # No unread messages → empty dict
        assert result == {}

    def test_session_lock_created_with_pid(self, tmp_path):
        self._handle(tmp_path)

        lock_file = tmp_path / "session.lock"
        assert lock_file.exists()
        assert lock_file.read_text() == str(os.getpid())

    def test_no_pocketteam_dir_returns_empty(self):
        from pocketteam.hooks import session_start
        with patch.object(session_start, "_find_pocketteam_dir", return_value=None):
            result = session_start.handle({})
        assert result == {}

    def test_multiple_messages_summary_count(self, tmp_path):
        inbox = tmp_path / "telegram-inbox.jsonl"
        entries = [
            {"ts": "2026-03-30T10:00:00+00:00", "from": "f", "text": f"msg{i}",
             "status": "received", "session_id": "s"}
            for i in range(3)
        ]
        inbox.write_text("\n".join(json.dumps(e) for e in entries) + "\n")

        result = self._handle(tmp_path)

        assert "3" in result["additionalContext"]

    def test_auto_trigger_marker_consumed_and_no_notify(self, tmp_path):
        """auto-triggered marker suppresses notification and is deleted."""
        marker = tmp_path / "auto-triggered"
        marker.touch()

        from pocketteam.hooks import session_start
        notify_calls = []
        with patch.object(session_start, "_find_pocketteam_dir", return_value=tmp_path):
            with patch.object(session_start, "_notify_telegram",
                              side_effect=lambda *a, **kw: notify_calls.append(a)):
                session_start.handle({})

        assert not marker.exists(), "marker file should be consumed"
        assert notify_calls == [], "notification should not fire for auto-triggered sessions"

    def test_malformed_jsonl_lines_skipped(self, tmp_path):
        inbox = tmp_path / "telegram-inbox.jsonl"
        inbox.write_text("not-json\n" + json.dumps({
            "ts": "2026-03-30T10:00:00+00:00", "from": "f",
            "text": "real", "status": "received", "session_id": "s",
        }) + "\n")

        result = self._handle(tmp_path)
        # The valid received message should be shown
        assert "real" in result["additionalContext"]


# ---------------------------------------------------------------------------
# session_stop
# ---------------------------------------------------------------------------

class TestSessionStop:
    """Tests for pocketteam.hooks.session_stop.handle()."""

    def _handle(self, tmp_path: Path, hook_input: dict | None = None):
        from pocketteam.hooks import session_stop
        with patch.object(session_stop, "_find_pocketteam_dir", return_value=tmp_path):
            return session_stop.handle(hook_input or {})

    def test_lock_file_deleted_when_present(self, tmp_path):
        lock = tmp_path / "session.lock"
        lock.write_text("12345")

        result = self._handle(tmp_path)

        assert not lock.exists()
        assert result == {}

    def test_no_error_when_lock_missing(self, tmp_path):
        result = self._handle(tmp_path)
        assert result == {}

    def test_no_pocketteam_dir_returns_empty(self):
        from pocketteam.hooks import session_stop
        with patch.object(session_stop, "_find_pocketteam_dir", return_value=None):
            result = session_stop.handle({})
        assert result == {}

    def test_always_returns_empty_dict(self, tmp_path):
        lock = tmp_path / "session.lock"
        lock.write_text("99")
        result = self._handle(tmp_path)
        assert result == {}


# ---------------------------------------------------------------------------
# pre_compact
# ---------------------------------------------------------------------------

class TestPreCompact:
    """Tests for pocketteam.hooks.pre_compact.handle()."""

    def _handle(self, tmp_path: Path, hook_input: dict | None = None):
        from pocketteam.hooks import pre_compact
        with patch.object(pre_compact, "_find_pocketteam_dir", return_value=tmp_path):
            return pre_compact.handle(hook_input or {})

    def test_writes_context_preservation_md(self, tmp_path):
        result = self._handle(tmp_path)

        snapshot = tmp_path / "context-preservation.md"
        assert snapshot.exists()
        content = snapshot.read_text()
        assert "PocketTeam Context Preservation Snapshot" in content
        assert result == {}

    def test_snapshot_contains_compacted_at(self, tmp_path):
        self._handle(tmp_path)
        content = (tmp_path / "context-preservation.md").read_text()
        assert "Compacted at:" in content

    def test_snapshot_no_task_when_no_events(self, tmp_path):
        self._handle(tmp_path)
        content = (tmp_path / "context-preservation.md").read_text()
        assert "no task recorded" in content

    def test_snapshot_records_task_from_events(self, tmp_path):
        events_dir = tmp_path / "events"
        events_dir.mkdir()
        event = {"type": "task_start", "task": "Build the auth module"}
        (events_dir / "stream.jsonl").write_text(json.dumps(event) + "\n")

        self._handle(tmp_path)
        content = (tmp_path / "context-preservation.md").read_text()
        assert "Build the auth module" in content

    def test_snapshot_no_plan_when_plans_dir_absent(self, tmp_path):
        self._handle(tmp_path)
        content = (tmp_path / "context-preservation.md").read_text()
        assert "no plan files found" in content

    def test_snapshot_records_most_recent_plan(self, tmp_path):
        plans = tmp_path / "artifacts" / "plans"
        plans.mkdir(parents=True)
        (plans / "plan-auth.md").write_text("# auth plan")

        self._handle(tmp_path)
        content = (tmp_path / "context-preservation.md").read_text()
        assert "plan-auth.md" in content

    def test_presented_messages_reset_to_received(self, tmp_path):
        inbox = tmp_path / "telegram-inbox.jsonl"
        entry = {
            "ts": "2026-03-30T10:00:00+00:00",
            "from": "f",
            "text": "requeue me",
            "status": "presented",
            "session_id": "s",
        }
        inbox.write_text(json.dumps(entry) + "\n")

        self._handle(tmp_path)

        lines = [json.loads(l) for l in inbox.read_text().splitlines() if l.strip()]
        assert lines[0]["status"] == "received"
        assert lines[0]["requeued_reason"] == "pre_compact"

    def test_already_received_messages_unchanged(self, tmp_path):
        inbox = tmp_path / "telegram-inbox.jsonl"
        entry = {
            "ts": "2026-03-30T10:00:00+00:00",
            "from": "f",
            "text": "keep me",
            "status": "received",
            "session_id": "s",
        }
        inbox.write_text(json.dumps(entry) + "\n")

        self._handle(tmp_path)

        lines = [json.loads(l) for l in inbox.read_text().splitlines() if l.strip()]
        assert lines[0]["status"] == "received"
        assert "requeued_reason" not in lines[0]

    def test_writes_last_compact_ts(self, tmp_path):
        self._handle(tmp_path)
        ts_file = tmp_path / ".last-compact-ts"
        assert ts_file.exists()
        assert ts_file.read_text().strip().isdigit()

    def test_no_pocketteam_dir_returns_empty(self):
        from pocketteam.hooks import pre_compact
        with patch.object(pre_compact, "_find_pocketteam_dir", return_value=None):
            result = pre_compact.handle({})
        assert result == {}

    def test_no_active_agents_says_none(self, tmp_path):
        self._handle(tmp_path)
        content = (tmp_path / "context-preservation.md").read_text()
        assert "no active agents" in content

    def test_active_agents_listed(self, tmp_path):
        events_dir = tmp_path / "events"
        events_dir.mkdir()
        events = [
            {"type": "agent_start", "agent": "engineer"},
            {"type": "agent_start", "agent": "planner"},
        ]
        (events_dir / "stream.jsonl").write_text(
            "\n".join(json.dumps(e) for e in events) + "\n"
        )

        self._handle(tmp_path)
        content = (tmp_path / "context-preservation.md").read_text()
        assert "- engineer" in content
        assert "- planner" in content

    def test_stopped_agent_not_listed(self, tmp_path):
        events_dir = tmp_path / "events"
        events_dir.mkdir()
        events = [
            {"type": "agent_start", "agent": "engineer"},
            {"type": "agent_stop", "agent": "engineer"},
        ]
        (events_dir / "stream.jsonl").write_text(
            "\n".join(json.dumps(e) for e in events) + "\n"
        )

        self._handle(tmp_path)
        content = (tmp_path / "context-preservation.md").read_text()
        assert "- engineer" not in content


# ---------------------------------------------------------------------------
# telegram_inbox
# ---------------------------------------------------------------------------

class TestTelegramInbox:
    """Tests for pocketteam.hooks.telegram_inbox.handle()."""

    def _handle(self, tmp_path: Path, hook_input: dict):
        from pocketteam.hooks import telegram_inbox
        with patch.object(telegram_inbox, "_find_pocketteam_dir", return_value=tmp_path):
            return telegram_inbox.handle(hook_input)

    def test_non_telegram_message_ignored(self, tmp_path):
        result = self._handle(tmp_path, {"input": "just a normal message"})
        assert result == {}
        assert not (tmp_path / "telegram-inbox.jsonl").exists()

    def test_telegram_message_saved_to_inbox(self, tmp_path):
        hook_input = {
            "input": '<channel source="telegram" chat_id="123">Hello!</channel>',
        }
        self._handle(tmp_path, hook_input)

        inbox = tmp_path / "telegram-inbox.jsonl"
        assert inbox.exists()
        entry = json.loads(inbox.read_text().strip())
        assert entry["text"] == "Hello!"
        assert entry["status"] == "received"

    def test_channel_tag_content_extracted(self, tmp_path):
        hook_input = {
            "input": '<channel source="telegram" chat_id="42">Deploy now</channel>',
        }
        self._handle(tmp_path, hook_input)
        entry = json.loads((tmp_path / "telegram-inbox.jsonl").read_text().strip())
        assert entry["text"] == "Deploy now"

    def test_kill_command_creates_kill_file(self, tmp_path):
        hook_input = {
            "input": '<channel source="telegram" chat_id="42">/kill</channel>',
        }
        result = self._handle(tmp_path, hook_input)
        assert (tmp_path / "KILL").exists()
        assert result == {}
        # Kill command should NOT be queued in inbox
        assert not (tmp_path / "telegram-inbox.jsonl").exists()

    def test_stop_command_creates_kill_file(self, tmp_path):
        hook_input = {
            "input": '<channel source="telegram" chat_id="42">/stop</channel>',
        }
        self._handle(tmp_path, hook_input)
        assert (tmp_path / "KILL").exists()

    def test_kill_bare_word_creates_kill_file(self, tmp_path):
        """Bare 'kill' without slash also triggers kill switch."""
        hook_input = {
            "input": '<channel source="telegram" chat_id="42">kill</channel>',
        }
        self._handle(tmp_path, hook_input)
        assert (tmp_path / "KILL").exists()

    def test_plugin_telegram_marker_detected(self, tmp_path):
        hook_input = {"input": "plugin:telegram hello from bot"}
        self._handle(tmp_path, hook_input)
        inbox = tmp_path / "telegram-inbox.jsonl"
        assert inbox.exists()

    def test_telegram_metadata_in_hook_input_detected(self, tmp_path):
        """If 'channel' and 'telegram' appear anywhere in hook_input dict."""
        hook_input = {
            "input": "Hello CEO",
            "source": "channel",
            "provider": "telegram",
        }
        self._handle(tmp_path, hook_input)
        inbox = tmp_path / "telegram-inbox.jsonl"
        assert inbox.exists()

    def test_non_string_message_returns_empty(self, tmp_path):
        result = self._handle(tmp_path, {"input": 42})
        assert result == {}

    def test_message_capped_at_2000_chars(self, tmp_path):
        long_text = "x" * 3000
        hook_input = {
            "input": f'<channel source="telegram" chat_id="1">{long_text}</channel>',
        }
        self._handle(tmp_path, hook_input)
        entry = json.loads((tmp_path / "telegram-inbox.jsonl").read_text().strip())
        assert len(entry["text"]) == 2000

    def test_entry_has_required_fields(self, tmp_path):
        hook_input = {
            "input": '<channel source="telegram" chat_id="99">Hi</channel>',
            "user_id": "farid",
            "session_id": "sess-1",
        }
        self._handle(tmp_path, hook_input)
        entry = json.loads((tmp_path / "telegram-inbox.jsonl").read_text().strip())
        assert "ts" in entry
        assert entry["from"] == "farid"
        assert entry["session_id"] == "sess-1"

    def test_multiple_messages_appended(self, tmp_path):
        hook_input = {"input": '<channel source="telegram" chat_id="1">First</channel>'}
        self._handle(tmp_path, hook_input)
        hook_input2 = {"input": '<channel source="telegram" chat_id="1">Second</channel>'}
        self._handle(tmp_path, hook_input2)

        lines = [
            json.loads(l) for l in
            (tmp_path / "telegram-inbox.jsonl").read_text().splitlines() if l.strip()
        ]
        assert len(lines) == 2
        assert lines[0]["text"] == "First"
        assert lines[1]["text"] == "Second"

    def test_no_pocketteam_dir_returns_empty(self):
        from pocketteam.hooks import telegram_inbox
        with patch.object(telegram_inbox, "_find_pocketteam_dir", return_value=None):
            result = telegram_inbox.handle({
                "input": '<channel source="telegram">msg</channel>',
            })
        assert result == {}


# ---------------------------------------------------------------------------
# delegation_enforcer
# ---------------------------------------------------------------------------

class TestDelegationEnforcer:
    """Tests for pocketteam.hooks.delegation_enforcer.handle()."""

    def _handle(self, hook_input: dict):
        from pocketteam.hooks.delegation_enforcer import handle
        return handle(hook_input)

    def test_returns_empty_dict_for_non_agent_tool(self):
        result = self._handle({"tool": "read_file", "params": {"path": "/tmp/x"}})
        assert result == {}

    def test_returns_empty_dict_for_agent_tool(self):
        result = self._handle({"tool": "Agent", "params": {"agent": "engineer"}})
        assert result == {}

    def test_returns_empty_dict_for_empty_input(self):
        result = self._handle({})
        assert result == {}

    def test_returns_empty_dict_always(self):
        """Delegation enforcer is a no-op — always returns empty dict."""
        for hook_input in [
            {"tool": "Task", "model": "opus"},
            {"tool": "Agent", "agent": "planner", "model": "haiku"},
            {"tool": "bash", "command": "ls"},
            {},
        ]:
            assert self._handle(hook_input) == {}
