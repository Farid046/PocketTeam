"""
PocketTeam CLI
Entry point for: pocketteam init | status | kill | retro | logs
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

console = Console()


@click.group()
@click.version_option(package_name="pocketteam")
def main() -> None:
    """PocketTeam - Your autonomous AI IT team."""


# ─────────────────────────────────────────────────────────────────────────────
# pocketteam init
# ─────────────────────────────────────────────────────────────────────────────

@main.command()
@click.option("--new", "project_name", default=None, metavar="NAME",
              help="Create a new project directory with the given name.")
@click.option("--yes", "-y", is_flag=True, help="Accept defaults without prompting.")
def init(project_name: str | None, yes: bool) -> None:
    """Set up PocketTeam in the current project (or create a new one)."""
    asyncio.run(_init(project_name, yes))


async def _init(project_name: str | None, yes: bool) -> None:
    from .init import run_init
    await run_init(project_name=project_name, accept_defaults=yes)


# ─────────────────────────────────────────────────────────────────────────────
# pocketteam status
# ─────────────────────────────────────────────────────────────────────────────

@main.command()
@click.option("--all", "show_all", is_flag=True, help="Show all configured projects.")
def status(show_all: bool) -> None:
    """Show PocketTeam status for the current project."""
    asyncio.run(_status(show_all))


async def _status(show_all: bool) -> None:
    from .config import load_config
    from .constants import KILL_SWITCH_FILE, EVENTS_FILE
    import json
    from datetime import datetime

    project_root = Path.cwd()
    config_path = project_root / ".pocketteam/config.yaml"

    if not config_path.exists():
        console.print("[red]No PocketTeam config found.[/] Run [bold]pocketteam init[/] first.")
        sys.exit(1)

    cfg = load_config(project_root)
    kill_active = (project_root / KILL_SWITCH_FILE).exists()

    table = Table(title=f"PocketTeam: {cfg.project_name}", show_header=True)
    table.add_column("Setting", style="cyan")
    table.add_column("Value")

    table.add_row("Project", cfg.project_name)
    table.add_row("Health URL", cfg.health_url or "[dim]not configured[/]")
    table.add_row("Auth Mode", cfg.auth.mode)
    table.add_row("Telegram", "✅ configured" if cfg.telegram.bot_token else "❌ not configured")
    table.add_row("Monitoring", "✅ enabled" if cfg.monitoring.enabled else "❌ disabled")
    table.add_row("GitHub Actions", "✅ enabled" if cfg.github_actions.enabled else "❌ disabled")
    table.add_row("Kill Switch", "[red]🔴 ACTIVE[/]" if kill_active else "🟢 inactive")

    # Show last event if stream exists
    events_path = project_root / EVENTS_FILE
    if events_path.exists():
        try:
            lines = events_path.read_text().strip().splitlines()
            if lines:
                last = json.loads(lines[-1])
                ts = last.get("ts", "")
                agent = last.get("agent", "?")
                action = last.get("action", "")
                table.add_row("Last Activity", f"{agent}: {action} ({ts[:19]})")
        except Exception:
            pass

    console.print(table)


# ─────────────────────────────────────────────────────────────────────────────
# pocketteam kill
# ─────────────────────────────────────────────────────────────────────────────

@main.command()
@click.option("--force", is_flag=True, help="Skip confirmation prompt.")
def kill(force: bool) -> None:
    """Activate the kill switch — stop all running agents immediately."""
    from .constants import KILL_SWITCH_FILE

    kill_path = Path.cwd() / KILL_SWITCH_FILE
    kill_path.parent.mkdir(parents=True, exist_ok=True)

    if not force:
        confirmed = Confirm.ask(
            "[bold red]This will stop ALL running PocketTeam agents. Continue?[/]",
            default=False,
        )
        if not confirmed:
            console.print("Aborted.")
            return

    kill_path.touch()
    console.print(Panel(
        "🔴 [bold red]KILL SWITCH ACTIVATED[/]\n"
        "All agents will stop within 1 second.\n"
        f"Signal file: {kill_path}\n\n"
        "To resume: [bold]rm .pocketteam/KILL[/] then restart your task.",
        title="Kill Switch",
        border_style="red",
    ))


# ─────────────────────────────────────────────────────────────────────────────
# pocketteam resume (reset kill switch)
# ─────────────────────────────────────────────────────────────────────────────

@main.command()
def resume() -> None:
    """Remove the kill switch to allow agents to run again."""
    from .constants import KILL_SWITCH_FILE

    kill_path = Path.cwd() / KILL_SWITCH_FILE
    if kill_path.exists():
        kill_path.unlink()
        console.print("✅ Kill switch removed. Agents can now run.")
    else:
        console.print("[dim]Kill switch was not active.[/]")


# ─────────────────────────────────────────────────────────────────────────────
# pocketteam retro
# ─────────────────────────────────────────────────────────────────────────────

@main.command()
@click.option("--days", default=7, help="Number of days to analyze (default: 7).")
def retro(days: int) -> None:
    """Run a retrospective: analyze recent activity, patterns, learnings."""
    asyncio.run(_retro(days))


async def _retro(days: int) -> None:
    from .core.orchestrator import run_retro
    await run_retro(days=days)


# ─────────────────────────────────────────────────────────────────────────────
# pocketteam logs
# ─────────────────────────────────────────────────────────────────────────────

@main.command()
@click.option("--follow", "-f", is_flag=True, help="Follow log output (like tail -f).")
@click.option("--lines", "-n", default=50, help="Number of lines to show (default: 50).")
@click.option("--agent", default=None, help="Filter by agent name.")
def logs(follow: bool, lines: int, agent: str | None) -> None:
    """Show PocketTeam event log."""
    asyncio.run(_logs(follow=follow, lines=lines, agent_filter=agent))


async def _logs(follow: bool, lines: int, agent_filter: str | None) -> None:
    import json
    import asyncio
    from .constants import EVENTS_FILE
    from datetime import datetime

    events_path = Path.cwd() / EVENTS_FILE
    if not events_path.exists():
        console.print("[dim]No events logged yet.[/]")
        return

    def print_event(line: str) -> None:
        try:
            e = json.loads(line)
            ts = e.get("ts", "")[:19]
            ag = e.get("agent", "?")
            action = e.get("action", "")
            etype = e.get("type", "")
            status = e.get("status", "")

            if agent_filter and ag != agent_filter:
                return

            color = {
                "coo": "yellow",
                "engineer": "blue",
                "reviewer": "cyan",
                "qa": "green",
                "security": "red",
                "devops": "magenta",
                "planner": "bright_blue",
                "monitor": "bright_green",
                "observer": "bright_yellow",
            }.get(ag, "white")

            console.print(f"[dim]{ts}[/] [[{color}]{ag:12}[/]] {action or etype or status}")
        except Exception:
            console.print(line)

    # Show last N lines
    all_lines = events_path.read_text().splitlines()
    for line in all_lines[-lines:]:
        if line.strip():
            print_event(line)

    if follow:
        console.print("[dim]Following... (Ctrl+C to stop)[/]")
        import aiofiles
        try:
            async with aiofiles.open(events_path) as f:
                await f.seek(0, 2)  # Seek to end
                while True:
                    line = await f.readline()
                    if line:
                        print_event(line.strip())
                    else:
                        await asyncio.sleep(0.5)
        except KeyboardInterrupt:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# pocketteam run-headless (for CI/GitHub Actions — NOT the normal flow)
# ─────────────────────────────────────────────────────────────────────────────

@main.command("run-headless")
@click.argument("task")
@click.option("--skip-product", is_flag=True, default=True,
              help="Skip product validation (default: True).")
@click.option("--no-telegram", is_flag=True, help="Disable Telegram notifications.")
def run_headless(task: str, skip_product: bool, no_telegram: bool) -> None:
    """Headless pipeline via Agent SDK (for CI/GitHub Actions). Requires ANTHROPIC_API_KEY.

    For normal use, open Claude Code instead: claude
    """
    asyncio.run(_run(task, skip_product, no_telegram))


async def _run(task: str, skip_product: bool, no_telegram: bool) -> None:
    from .config import load_config
    from .core.orchestrator import run_task
    from .channels.setup import TelegramChannel

    root = Path.cwd()
    cfg = load_config(root)

    telegram: TelegramChannel | None = None
    if not no_telegram:
        telegram = TelegramChannel(root, config=cfg)
        if telegram.is_configured:
            await telegram.send_message(
                f"<b>New task</b>: {task[:200]}\nPipeline starting..."
            )

    async def on_status(message: str) -> None:
        console.print(f"  {message}")
        if telegram and telegram.is_configured:
            await telegram.send_message(message)

    async def on_approval(prompt: str) -> bool:
        if telegram and telegram.is_configured:
            import uuid
            request_id = f"gate-{uuid.uuid4().hex[:8]}"
            return await telegram.send_approval_request(prompt, request_id)
        # Fallback: CLI prompt
        return Confirm.ask(f"\n{prompt}", default=False)

    console.print(Panel(
        f"[bold]Task:[/] {task}\n"
        f"[dim]Telegram: {'✅' if telegram and telegram.is_configured else '❌'}[/]",
        title="PocketTeam Pipeline",
        border_style="cyan",
    ))

    success = await run_task(
        task_description=task,
        project_root=root,
        skip_product=skip_product,
        on_status=on_status,
        on_approval=on_approval,
    )

    if success:
        console.print(Panel("✅ [bold green]Pipeline completed successfully![/]", border_style="green"))
        if telegram and telegram.is_configured:
            await telegram.send_message("✅ Pipeline completed successfully!")
    else:
        console.print(Panel("❌ [bold red]Pipeline failed.[/]", border_style="red"))
        if telegram and telegram.is_configured:
            await telegram.send_message("❌ Pipeline failed. Check logs.")
        sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# pocketteam sessions
# ─────────────────────────────────────────────────────────────────────────────

@main.command()
@click.option("--cleanup", is_flag=True, help="Remove sessions older than 30 days.")
def sessions(cleanup: bool) -> None:
    """List or manage pipeline sessions."""
    from .channels.setup import SessionManager

    root = Path.cwd()
    sm = SessionManager(root)

    if cleanup:
        removed = sm.cleanup_old_sessions()
        console.print(f"Removed {removed} old session(s).")
        return

    session_list = sm.list_sessions()
    if not session_list:
        console.print("[dim]No sessions found.[/]")
        return

    table = Table(title="Pipeline Sessions")
    table.add_column("Task ID", style="cyan")
    table.add_column("Description")
    table.add_column("Phase")
    table.add_column("Modified")

    for s in session_list[:20]:
        table.add_row(
            s["task_id"],
            s.get("task_description", "")[:50],
            s.get("phase", "?"),
            s.get("modified", ""),
        )

    console.print(table)


# ─────────────────────────────────────────────────────────────────────────────
# pocketteam uninstall
# ─────────────────────────────────────────────────────────────────────────────

@main.command()
@click.option("--keep-artifacts", is_flag=True, help="Keep .pocketteam/ artifacts.")
def uninstall(keep_artifacts: bool) -> None:
    """Remove PocketTeam from the current project (non-destructive)."""
    asyncio.run(_uninstall(keep_artifacts))


async def _uninstall(keep_artifacts: bool) -> None:
    from .init import run_uninstall
    await run_uninstall(keep_artifacts=keep_artifacts)


if __name__ == "__main__":
    main()
