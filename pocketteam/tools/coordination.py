"""
Coordination Tool — In-process message bus for agent-to-agent communication.

Wraps SharedContext with higher-level communication patterns:
- Request/response: Agent A asks a question, waits for Agent B's answer
- Broadcast: COO notifies all agents of a pipeline event
- Pub/Sub: Agents subscribe to named channels
- Handoff: Pass work + artifacts from one agent to the next

All coordination events are written to stream.jsonl so the dashboard
can show which agents are talking to each other.

No IPC, no network — all in-process via SharedContext.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..constants import EVENTS_FILE
from ..jsonl import append_jsonl

# ─────────────────────────────────────────────────────────────────────────────
# Data structures
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Message:
    """A message from one agent to another (or broadcast)."""
    from_agent: str
    to_agent: str          # "*" for broadcast
    channel: str           # Named channel, e.g. "plan_ready", "review_done"
    content: Any
    reply_to: str | None = None   # message_id this replies to
    message_id: str = field(default_factory=lambda: f"msg-{uuid.uuid4().hex[:12]}")
    ts: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%S"))


@dataclass
class HandoffPackage:
    """
    Structured handoff between pipeline phases.
    Carries the output of one agent as the input for the next.
    """
    from_agent: str
    to_agent: str
    task: str
    artifacts: dict[str, Any] = field(default_factory=dict)
    context_summary: str = ""
    requires_action: bool = True


# ─────────────────────────────────────────────────────────────────────────────
# CoordinationHub
# ─────────────────────────────────────────────────────────────────────────────

class CoordinationHub:
    """
    Central coordinator for agent communication.

    One hub per pipeline run, backed by the SharedContext for persistence.
    Agents interact via:
    - send()         → fire-and-forget message
    - request()      → send message and await a reply (with timeout)
    - broadcast()    → send to all agents (shows in dashboard)
    - handoff()      → structured work transfer between agents
    - subscribe()    → register a callback for a channel
    """

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self._known_agents: set[str] = set()              # all agents ever seen
        self._mailboxes: dict[str, list[Message]] = {}   # agent_id → messages
        self._channels: dict[str, list[Message]] = {}    # channel → messages
        self._subscribers: dict[str, list[Callable]] = {}  # channel → callbacks
        self._reply_futures: dict[str, asyncio.Future] = {}  # message_id → future
        self._lock = asyncio.Lock()

    # ── Send / Receive ────────────────────────────────────────────────────────

    async def send(
        self,
        from_agent: str,
        to_agent: str,
        channel: str,
        content: Any,
        reply_to: str | None = None,
    ) -> Message:
        """Send a message to a specific agent or broadcast (to_agent='*')."""
        msg = Message(
            from_agent=from_agent,
            to_agent=to_agent,
            channel=channel,
            content=content,
            reply_to=reply_to,
        )

        async with self._lock:
            # Register agents we know about
            self._known_agents.add(from_agent)
            if to_agent != "*":
                self._known_agents.add(to_agent)

            # Deliver to mailbox
            if to_agent == "*":
                # Broadcast: deliver to every known agent
                for agent_id in self._known_agents:
                    if agent_id not in self._mailboxes:
                        self._mailboxes[agent_id] = []
                    self._mailboxes[agent_id].append(msg)
            else:
                if to_agent not in self._mailboxes:
                    self._mailboxes[to_agent] = []
                self._mailboxes[to_agent].append(msg)

            # Store in channel log
            if channel not in self._channels:
                self._channels[channel] = []
            self._channels[channel].append(msg)

            # Resolve any pending request() future
            if reply_to and reply_to in self._reply_futures:
                fut = self._reply_futures.pop(reply_to)
                if not fut.done():
                    fut.set_result(msg)

        # Notify channel subscribers (outside lock to avoid deadlocks)
        await self._notify_subscribers(channel, msg)

        # Log to event stream
        await self._log_coordination_event(msg)

        return msg

    async def broadcast(
        self,
        from_agent: str,
        channel: str,
        content: Any,
    ) -> Message:
        """Broadcast a message to all agents (shown prominently in dashboard)."""
        return await self.send(from_agent, "*", channel, content)

    async def request(
        self,
        from_agent: str,
        to_agent: str,
        channel: str,
        content: Any,
        timeout: float = 30.0,
    ) -> Message | None:
        """
        Send a message and wait for a reply.
        Returns the reply message, or None on timeout.

        The responder must call reply() with the original message_id.
        """
        msg = await self.send(from_agent, to_agent, channel, content)

        # Create a future that will be resolved when a reply arrives
        loop = asyncio.get_event_loop()
        fut: asyncio.Future = loop.create_future()

        async with self._lock:
            self._reply_futures[msg.message_id] = fut

        try:
            return await asyncio.wait_for(fut, timeout=timeout)
        except TimeoutError:
            async with self._lock:
                self._reply_futures.pop(msg.message_id, None)
            return None

    async def reply(
        self,
        from_agent: str,
        original_message: Message,
        content: Any,
    ) -> Message:
        """Reply to a request() call."""
        return await self.send(
            from_agent=from_agent,
            to_agent=original_message.from_agent,
            channel=f"{original_message.channel}.reply",
            content=content,
            reply_to=original_message.message_id,
        )

    # ── Mailbox ───────────────────────────────────────────────────────────────

    def get_mail(self, agent_id: str) -> list[Message]:
        """Get all pending messages for an agent (clears mailbox, keeps agent registered)."""
        messages = self._mailboxes.pop(agent_id, [])
        # Keep agent registered for future broadcasts even after clearing mailbox
        self._known_agents.add(agent_id)
        return messages

    def peek_mail(self, agent_id: str) -> list[Message]:
        """Read messages without clearing the mailbox."""
        return list(self._mailboxes.get(agent_id, []))

    def get_channel_history(self, channel: str) -> list[Message]:
        """Get all messages ever sent on a channel."""
        return list(self._channels.get(channel, []))

    # ── Handoff ───────────────────────────────────────────────────────────────

    async def handoff(self, package: HandoffPackage) -> None:
        """
        Structured work handoff between agents.
        Sends a 'handoff' channel message with the full package.
        """
        await self.send(
            from_agent=package.from_agent,
            to_agent=package.to_agent,
            channel="handoff",
            content={
                "task": package.task,
                "artifacts": package.artifacts,
                "context_summary": package.context_summary,
                "requires_action": package.requires_action,
            },
        )

    def get_pending_handoff(self, agent_id: str) -> HandoffPackage | None:
        """Check if there's a pending handoff for this agent."""
        for msg in self.peek_mail(agent_id):
            if msg.channel == "handoff":
                data = msg.content
                return HandoffPackage(
                    from_agent=msg.from_agent,
                    to_agent=agent_id,
                    task=data.get("task", ""),
                    artifacts=data.get("artifacts", {}),
                    context_summary=data.get("context_summary", ""),
                    requires_action=data.get("requires_action", True),
                )
        return None

    # ── Pub/Sub ───────────────────────────────────────────────────────────────

    def subscribe(self, channel: str, callback: Callable[[Message], None]) -> None:
        """Subscribe to a channel. Callback is called when a message arrives."""
        if channel not in self._subscribers:
            self._subscribers[channel] = []
        self._subscribers[channel].append(callback)

    def unsubscribe(self, channel: str, callback: Callable) -> None:
        """Remove a subscription."""
        if channel in self._subscribers:
            self._subscribers[channel] = [
                cb for cb in self._subscribers[channel] if cb != callback
            ]

    async def _notify_subscribers(self, channel: str, msg: Message) -> None:
        """Notify all subscribers for a channel."""
        for callback in self._subscribers.get(channel, []):
            try:
                result = callback(msg)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                pass  # Subscriber errors must never crash the hub

    # ── Event Logging ─────────────────────────────────────────────────────────

    async def _log_coordination_event(self, msg: Message) -> None:
        """Write coordination event to stream.jsonl for the dashboard."""
        try:
            events_path = self.project_root / EVENTS_FILE
            events_path.parent.mkdir(parents=True, exist_ok=True)

            event = {
                "ts": msg.ts,
                "type": "agent_communicate",
                "from": msg.from_agent,
                "to": msg.to_agent,
                "channel": msg.channel,
                "message_id": msg.message_id,
                # Don't log full content — may be large or contain sensitive data
                "content_preview": str(msg.content)[:100] if msg.content else "",
            }
            append_jsonl(events_path, event)
        except Exception:
            pass  # Logging must never crash coordination


# ─────────────────────────────────────────────────────────────────────────────
# Standard channel names (convention, not enforced)
# ─────────────────────────────────────────────────────────────────────────────

class Channel:
    """Standard channel names used by the pipeline."""
    # Planning phase
    PLAN_READY = "plan_ready"
    PLAN_APPROVED = "plan_approved"
    PLAN_REJECTED = "plan_rejected"

    # Implementation phase
    IMPLEMENTATION_READY = "implementation_ready"
    REVIEW_REQUEST = "review_request"
    REVIEW_DONE = "review_done"
    QA_DONE = "qa_done"
    SECURITY_DONE = "security_done"

    # Deploy phase
    STAGING_READY = "staging_ready"
    STAGING_OK = "staging_ok"
    STAGING_FAILED = "staging_failed"
    PRODUCTION_DEPLOYED = "production_deployed"

    # Monitoring
    HEALTH_ALERT = "health_alert"
    INCIDENT_DETECTED = "incident_detected"
    INCIDENT_RESOLVED = "incident_resolved"

    # CEO / Human gates
    HUMAN_GATE = "human_gate"
    CEO_APPROVED = "ceo_approved"
    CEO_REJECTED = "ceo_rejected"

    # System
    PIPELINE_DONE = "pipeline_done"
    PIPELINE_FAILED = "pipeline_failed"


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline-level helpers
# ─────────────────────────────────────────────────────────────────────────────

async def announce_phase_complete(
    hub: CoordinationHub,
    from_agent: str,
    phase: str,
    summary: str,
    artifacts: dict[str, Any] | None = None,
) -> None:
    """Convenience: agent announces its phase is complete to the COO."""
    await hub.send(
        from_agent=from_agent,
        to_agent="coo",
        channel=f"{phase}_complete",
        content={
            "phase": phase,
            "summary": summary,
            "artifacts": artifacts or {},
        },
    )


async def request_ceo_approval(
    hub: CoordinationHub,
    from_agent: str,
    prompt: str,
    timeout: float = 300.0,  # 5 min default
) -> bool:
    """
    Ask the COO to relay an approval request to the CEO.
    Returns True if approved, False if rejected or timed out.
    """
    reply = await hub.request(
        from_agent=from_agent,
        to_agent="coo",
        channel=Channel.HUMAN_GATE,
        content={"prompt": prompt},
        timeout=timeout,
    )
    if reply is None:
        return False  # Timeout = not approved
    content = reply.content
    if isinstance(content, dict):
        return content.get("approved", False)
    return bool(content)
