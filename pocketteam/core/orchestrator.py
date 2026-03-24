"""
Orchestrator — the main entry point for running PocketTeam.
Connects the pipeline to Telegram channels, loads config, starts monitoring.
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any, Callable, Optional

from ..config import PocketTeamConfig, load_config
from ..constants import EVENTS_FILE
from .context import SharedContext
from .pipeline import Pipeline


async def run_task(
    task_description: str,
    project_root: Optional[Path] = None,
    skip_product: bool = True,
    on_status: Optional[Callable] = None,
    on_approval: Optional[Callable] = None,
) -> bool:
    """
    Run a task through the full pipeline.

    Args:
        task_description: What to build/fix
        project_root: Project directory (default: cwd)
        skip_product: Skip product validation (default for bug fixes)
        on_status: Callback for status messages (e.g. Telegram send)
        on_approval: Callback for human gate approvals (e.g. Telegram prompt)

    Returns:
        True if pipeline completed successfully
    """
    root = project_root or Path.cwd()
    cfg = load_config(root)

    context = SharedContext.create_new(
        task_description=task_description,
        project_root=root,
    )

    # Log task start
    _log_event(root, "coo", "pipeline_start", f"New task: {task_description[:100]}")

    pipeline = Pipeline(
        context=context,
        on_human_gate=on_approval,
        on_status_update=on_status,
    )

    success = await pipeline.run(skip_product=skip_product)

    _log_event(
        root, "coo",
        "pipeline_done" if success else "pipeline_failed",
        f"Task {'completed' if success else 'failed'}: {task_description[:100]}",
    )

    return success


async def run_retro(days: int = 7, project_root: Optional[Path] = None) -> None:
    """
    Run a retrospective: analyze activity, agent learnings, bottlenecks.
    """
    from rich.console import Console
    from rich.table import Table
    import json

    console = Console()
    root = project_root or Path.cwd()

    console.print(f"\n[bold cyan]PocketTeam Retrospective[/] (last {days} days)\n")

    # Agent learnings
    learnings_dir = root / ".pocketteam/learnings"
    if learnings_dir.exists():
        table = Table(title="Agent Learnings")
        table.add_column("Agent")
        table.add_column("Pattern")
        table.add_column("Count")

        for yaml_file in learnings_dir.glob("*.yaml"):
            try:
                import yaml
                data = yaml.safe_load(yaml_file.read_text())
                for p in (data or {}).get("patterns", []):
                    table.add_row(
                        yaml_file.stem,
                        p.get("pattern", "")[:60],
                        str(p.get("count", 0)),
                    )
            except Exception:
                pass
        console.print(table)

    # Audit stats
    audit_dir = root / ".pocketteam/artifacts/audit"
    if audit_dir.exists():
        from ..safety.audit_log import AuditLog
        audit = AuditLog(root)
        stats = audit.get_stats()
        console.print(f"\n[bold]Safety Stats (today)[/]")
        console.print(f"  Total checks: {stats['total']}")
        console.print(f"  Allowed: {stats['allowed']}")
        console.print(f"  Denied: {stats['denied']}")
        console.print(f"  Layer 1 blocks: {stats['layer1_blocks']}")
        console.print(f"  MCP blocks: {stats['mcp_blocks']}")
        console.print(f"  Network blocks: {stats['network_blocks']}")

    # Event stream summary
    events_path = root / EVENTS_FILE
    if events_path.exists():
        lines = events_path.read_text().splitlines()
        agent_activity: dict[str, int] = {}
        for line in lines:
            try:
                e = json.loads(line)
                ag = e.get("agent", "unknown")
                if e.get("status") == "awake":
                    agent_activity[ag] = agent_activity.get(ag, 0) + 1
            except Exception:
                pass

        if agent_activity:
            console.print(f"\n[bold]Agent Activity[/]")
            for agent, count in sorted(agent_activity.items(), key=lambda x: -x[1]):
                console.print(f"  {agent:15} {count} tasks")


def _log_event(
    project_root: Path,
    agent: str,
    event_type: str,
    action: str,
) -> None:
    """Log an orchestrator event to the event stream."""
    try:
        events_path = project_root / EVENTS_FILE
        events_path.parent.mkdir(parents=True, exist_ok=True)
        event = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "agent": agent,
            "type": event_type,
            "status": "working",
            "action": action,
        }
        with open(events_path, "a") as f:
            f.write(json.dumps(event) + "\n")
    except Exception:
        pass
