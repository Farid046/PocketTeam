"""
Tests for Phase 7: Coordination Tool
Covers send/receive, broadcast, request/reply, handoff, pub/sub, event logging.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from pocketteam.tools.coordination import (
    Channel,
    CoordinationHub,
    HandoffPackage,
    Message,
    announce_phase_complete,
    request_ceo_approval,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    (tmp_path / ".pocketteam/events").mkdir(parents=True)
    return tmp_path


@pytest.fixture
def hub(tmp_project: Path) -> CoordinationHub:
    return CoordinationHub(tmp_project)


# ─────────────────────────────────────────────────────────────────────────────
# send / receive
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_delivers_to_mailbox(hub: CoordinationHub) -> None:
    await hub.send("planner", "reviewer", "review_request", {"plan": "step 1"})
    mail = hub.get_mail("reviewer")
    assert len(mail) == 1
    assert mail[0].from_agent == "planner"
    assert mail[0].channel == "review_request"
    assert mail[0].content == {"plan": "step 1"}


@pytest.mark.asyncio
async def test_get_mail_clears_mailbox(hub: CoordinationHub) -> None:
    await hub.send("planner", "reviewer", "review_request", "content")
    hub.get_mail("reviewer")  # first read clears
    assert hub.get_mail("reviewer") == []


@pytest.mark.asyncio
async def test_peek_mail_does_not_clear(hub: CoordinationHub) -> None:
    await hub.send("planner", "reviewer", "review_request", "content")
    hub.peek_mail("reviewer")
    assert len(hub.peek_mail("reviewer")) == 1  # still there


@pytest.mark.asyncio
async def test_message_has_unique_id(hub: CoordinationHub) -> None:
    m1 = await hub.send("a", "b", "ch", "x")
    m2 = await hub.send("a", "b", "ch", "y")
    assert m1.message_id != m2.message_id


@pytest.mark.asyncio
async def test_channel_history_accumulates(hub: CoordinationHub) -> None:
    await hub.send("planner", "reviewer", "review_request", "plan v1")
    await hub.send("engineer", "reviewer", "review_request", "plan v2")
    history = hub.get_channel_history("review_request")
    assert len(history) == 2


# ─────────────────────────────────────────────────────────────────────────────
# broadcast
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_broadcast_goes_to_all_known_agents(hub: CoordinationHub) -> None:
    # First: seed mailboxes so hub knows these agents exist
    await hub.send("coo", "planner", "init", "start")
    await hub.send("coo", "engineer", "init", "start")
    # Clear those seeded messages
    hub.get_mail("planner")
    hub.get_mail("engineer")

    # Now broadcast
    await hub.broadcast("coo", Channel.PIPELINE_DONE, "All done!")

    planner_mail = hub.get_mail("planner")
    engineer_mail = hub.get_mail("engineer")

    assert any(m.channel == Channel.PIPELINE_DONE for m in planner_mail)
    assert any(m.channel == Channel.PIPELINE_DONE for m in engineer_mail)


@pytest.mark.asyncio
async def test_broadcast_to_star(hub: CoordinationHub) -> None:
    msg = await hub.broadcast("coo", "kill_switch", "HALT")
    assert msg.to_agent == "*"


# ─────────────────────────────────────────────────────────────────────────────
# request / reply
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_request_reply_roundtrip(hub: CoordinationHub) -> None:
    async def responder() -> None:
        # Small delay to simulate work
        await asyncio.sleep(0.05)
        mail = hub.get_mail("reviewer")
        assert mail, "reviewer got no mail"
        await hub.reply("reviewer", mail[0], {"approved": True})

    task = asyncio.create_task(responder())
    reply = await hub.request("planner", "reviewer", "plan_review", {"plan": "x"}, timeout=2.0)
    await task

    assert reply is not None
    assert reply.content == {"approved": True}
    assert reply.reply_to is not None


@pytest.mark.asyncio
async def test_request_timeout_returns_none(hub: CoordinationHub) -> None:
    # Nobody responds → should timeout
    reply = await hub.request("planner", "reviewer", "plan_review", "plan", timeout=0.05)
    assert reply is None


# ─────────────────────────────────────────────────────────────────────────────
# handoff
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_handoff_delivers_package(hub: CoordinationHub) -> None:
    pkg = HandoffPackage(
        from_agent="planner",
        to_agent="engineer",
        task="Implement OAuth2 login",
        artifacts={"plan": "step 1: ..."},
        context_summary="Plan reviewed and approved",
    )
    await hub.handoff(pkg)

    received = hub.get_pending_handoff("engineer")
    assert received is not None
    assert received.task == "Implement OAuth2 login"
    assert received.artifacts == {"plan": "step 1: ..."}
    assert received.context_summary == "Plan reviewed and approved"


@pytest.mark.asyncio
async def test_get_pending_handoff_returns_none_when_empty(hub: CoordinationHub) -> None:
    assert hub.get_pending_handoff("engineer") is None


@pytest.mark.asyncio
async def test_handoff_uses_handoff_channel(hub: CoordinationHub) -> None:
    await hub.handoff(HandoffPackage("planner", "engineer", "task"))
    mail = hub.peek_mail("engineer")
    assert any(m.channel == "handoff" for m in mail)


# ─────────────────────────────────────────────────────────────────────────────
# pub/sub
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_subscribe_receives_messages(hub: CoordinationHub) -> None:
    received: list[Message] = []

    def on_plan_ready(msg: Message) -> None:
        received.append(msg)

    hub.subscribe(Channel.PLAN_READY, on_plan_ready)
    await hub.send("planner", "coo", Channel.PLAN_READY, {"plan_id": "abc"})

    assert len(received) == 1
    assert received[0].channel == Channel.PLAN_READY


@pytest.mark.asyncio
async def test_async_subscriber_works(hub: CoordinationHub) -> None:
    received: list[Message] = []

    async def on_health_alert(msg: Message) -> None:
        received.append(msg)

    hub.subscribe(Channel.HEALTH_ALERT, on_health_alert)
    await hub.broadcast("monitor", Channel.HEALTH_ALERT, "DB timeout")

    assert len(received) == 1


@pytest.mark.asyncio
async def test_unsubscribe_stops_notifications(hub: CoordinationHub) -> None:
    received: list[Message] = []

    def handler(msg: Message) -> None:
        received.append(msg)

    hub.subscribe("ch", handler)
    await hub.send("a", "b", "ch", "msg1")
    hub.unsubscribe("ch", handler)
    await hub.send("a", "b", "ch", "msg2")

    assert len(received) == 1


@pytest.mark.asyncio
async def test_subscriber_crash_does_not_propagate(hub: CoordinationHub) -> None:
    def crasher(msg: Message) -> None:
        raise RuntimeError("subscriber bug")

    hub.subscribe("ch", crasher)
    # Must not raise
    await hub.send("a", "b", "ch", "msg")


# ─────────────────────────────────────────────────────────────────────────────
# Event logging (stream.jsonl)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_events_written_to_stream(hub: CoordinationHub, tmp_project: Path) -> None:
    await hub.send("planner", "reviewer", "review_request", "plan content")

    events_path = tmp_project / ".pocketteam/events/stream.jsonl"
    assert events_path.exists()

    lines = events_path.read_text().strip().splitlines()
    assert len(lines) >= 1

    event = json.loads(lines[0])
    assert event["type"] == "agent_communicate"
    assert event["from"] == "planner"
    assert event["to"] == "reviewer"
    assert event["channel"] == "review_request"


@pytest.mark.asyncio
async def test_event_content_preview_truncated(hub: CoordinationHub, tmp_project: Path) -> None:
    long_content = "x" * 200
    await hub.send("a", "b", "ch", long_content)

    events_path = tmp_project / ".pocketteam/events/stream.jsonl"
    event = json.loads(events_path.read_text().strip())
    assert len(event["content_preview"]) <= 100


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline helpers
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_announce_phase_complete(hub: CoordinationHub) -> None:
    await announce_phase_complete(
        hub,
        from_agent="engineer",
        phase="implementation",
        summary="OAuth2 implemented, 42 files changed",
        artifacts={"diff": "git diff output"},
    )

    mail = hub.get_mail("coo")
    assert len(mail) == 1
    msg = mail[0]
    assert msg.channel == "implementation_complete"
    assert msg.content["summary"] == "OAuth2 implemented, 42 files changed"
    assert msg.content["artifacts"]["diff"] == "git diff output"


@pytest.mark.asyncio
async def test_request_ceo_approval_approved(hub: CoordinationHub) -> None:
    async def coo_responds() -> None:
        await asyncio.sleep(0.05)
        mail = hub.get_mail("coo")
        assert mail
        await hub.reply("coo", mail[0], {"approved": True})

    task = asyncio.create_task(coo_responds())
    result = await request_ceo_approval(hub, "engineer", "Deploy to production?", timeout=2.0)
    await task
    assert result is True


@pytest.mark.asyncio
async def test_request_ceo_approval_timeout_returns_false(hub: CoordinationHub) -> None:
    result = await request_ceo_approval(hub, "engineer", "Deploy?", timeout=0.05)
    assert result is False


# ─────────────────────────────────────────────────────────────────────────────
# Channel constants
# ─────────────────────────────────────────────────────────────────────────────

def test_channel_constants_are_strings() -> None:
    channels = [
        Channel.PLAN_READY, Channel.PLAN_APPROVED, Channel.PLAN_REJECTED,
        Channel.IMPLEMENTATION_READY, Channel.REVIEW_REQUEST, Channel.REVIEW_DONE,
        Channel.QA_DONE, Channel.SECURITY_DONE, Channel.STAGING_READY,
        Channel.STAGING_OK, Channel.STAGING_FAILED, Channel.PRODUCTION_DEPLOYED,
        Channel.HEALTH_ALERT, Channel.INCIDENT_DETECTED, Channel.INCIDENT_RESOLVED,
        Channel.HUMAN_GATE, Channel.CEO_APPROVED, Channel.CEO_REJECTED,
        Channel.KILL_SWITCH, Channel.PIPELINE_DONE, Channel.PIPELINE_FAILED,
    ]
    for ch in channels:
        assert isinstance(ch, str)
        assert len(ch) > 0


def test_channel_names_are_snake_case() -> None:
    """Ensure channel names are valid identifiers for use as dict keys."""
    channels = [
        Channel.PLAN_READY, Channel.HEALTH_ALERT, Channel.PIPELINE_DONE,
    ]
    for ch in channels:
        assert " " not in ch
        assert ch == ch.lower()
