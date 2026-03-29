"""
PreCompact Hook — preserves critical context before compression.

Saves a timestamp so that after compression, the SessionStart hook
knows which Telegram messages were already in context vs. lost.
Also saves a brief context snapshot to .pocketteam/context-preservation.md
that includes the current task, active plan, and active agents so that
the new context window has orientation after compaction.
"""

import json
import time
from pathlib import Path

from ._utils import _find_pocketteam_dir


def _read_last_event_task(events_path: Path) -> str | None:
    """Return the most recent task description found in the event stream."""
    if not events_path.exists():
        return None
    try:
        # Read last 16 KB — enough for recent events without loading the whole file
        stat = events_path.stat()
        read_size = min(stat.st_size, 16384)
        with events_path.open("rb") as fh:
            fh.seek(max(0, stat.st_size - read_size))
            tail = fh.read().decode("utf-8", errors="replace")
        task = None
        for line in tail.split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
                if ev.get("task"):
                    task = ev["task"]
            except json.JSONDecodeError:
                continue
        return task
    except OSError:
        return None


def _find_active_plan(plans_dir: Path) -> str | None:
    """Return the filename of the most recently modified plan file."""
    if not plans_dir.exists():
        return None
    try:
        plan_files = sorted(
            plans_dir.glob("*.md"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return plan_files[0].name if plan_files else None
    except OSError:
        return None


def _list_active_agents(events_path: Path) -> list[str]:
    """Return a list of agent names that have a start but no subsequent stop."""
    if not events_path.exists():
        return []
    try:
        stat = events_path.stat()
        read_size = min(stat.st_size, 16384)
        with events_path.open("rb") as fh:
            fh.seek(max(0, stat.st_size - read_size))
            tail = fh.read().decode("utf-8", errors="replace")
        agents: dict[str, str] = {}
        for line in tail.split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
                name = ev.get("agent")
                ev_type = ev.get("type")
                if name and ev_type in ("agent_start", "agent_stop"):
                    agents[name] = ev_type
            except json.JSONDecodeError:
                continue
        return [name for name, status in agents.items() if status == "agent_start"]
    except OSError:
        return []


def handle(hook_input: dict) -> dict:
    """Save compact timestamp + mark unprocessed messages + write context snapshot."""
    pt_dir = _find_pocketteam_dir()
    if not pt_dir:
        return {}

    # Save timestamp
    ts_file = pt_dir / ".last-compact-ts"
    try:
        ts_file.write_text(str(int(time.time())))
    except OSError:
        pass

    # Re-mark any "presented" messages as "received" so they get
    # re-presented after compression (the context that saw them is gone)
    inbox_path = pt_dir / "telegram-inbox.jsonl"
    if inbox_path.exists():
        try:
            lines = inbox_path.read_text().strip().split("\n")
        except OSError:
            lines = []

        updated = []
        for line in lines:
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                updated.append(line)
                continue

            # Messages that were "presented" in the now-compressed context
            # need to be re-presented in the new context
            if entry.get("status") == "presented":
                entry["status"] = "received"
                entry["requeued_reason"] = "pre_compact"

            updated.append(json.dumps(entry, default=str))

        try:
            inbox_path.write_text("\n".join(updated) + "\n")
        except OSError:
            pass

    # ── Context snapshot ──────────────────────────────────────────────────────
    # Gather task, plan, and agent info so the new context has orientation.
    events_path = pt_dir / "events" / "stream.jsonl"
    plans_dir = pt_dir / "artifacts" / "plans"

    current_task = _read_last_event_task(events_path)
    active_plan = _find_active_plan(plans_dir)
    active_agents = _list_active_agents(events_path)

    snapshot_lines = [
        "# PocketTeam Context Preservation Snapshot",
        f"Compacted at: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}",
        "",
        "## Current Task",
        current_task or "(no task recorded in event stream)",
        "",
        "## Active Plan",
        active_plan or "(no plan files found)",
        "",
        "## Active Agents",
    ]
    if active_agents:
        for agent in active_agents:
            snapshot_lines.append(f"- {agent}")
    else:
        snapshot_lines.append("(no active agents)")

    snapshot_path = pt_dir / "context-preservation.md"
    try:
        snapshot_path.write_text("\n".join(snapshot_lines) + "\n")
    except OSError:
        pass

    return {}
