"""
PocketTeam CLI
Entry point for: pocketteam init | start | status | health | dashboard | insights | logs | retro | sessions | run-headless | uninstall | help
"""

from __future__ import annotations

import asyncio
import logging
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table

logger = logging.getLogger(__name__)

console = Console()


def _parse_schedule_input(user_input: str) -> str:
    """Convert HH:MM to cron string, or pass through if already cron."""
    match = re.match(r'^(\d{1,2}):(\d{2})$', user_input.strip())
    if match:
        hour, minute = match.groups()
        return f"{int(minute)} {int(hour)} * * *"
    # Already cron format or custom — pass through
    return user_input


def _cron_to_time(cron: str) -> str:
    """Convert simple daily cron to HH:MM for display."""
    match = re.match(r'^(\d+)\s+(\d+)\s+\*\s+\*\s+\*$', cron.strip())
    if match:
        minute, hour = match.groups()
        return f"{int(hour):02d}:{int(minute):02d}"
    return cron  # Complex cron, show as-is

# Rich color names for each agent role used in log output
AGENT_COLORS: dict[str, str] = {
    "coo": "yellow",
    "engineer": "blue",
    "reviewer": "cyan",
    "qa": "green",
    "security": "red",
    "devops": "magenta",
    "planner": "bright_blue",
    "monitor": "bright_green",
    "observer": "bright_yellow",
}


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
@click.option("--no-dashboard", is_flag=True, help="Skip dashboard setup.")
def init(project_name: str | None, yes: bool, no_dashboard: bool) -> None:
    """Set up PocketTeam in the current project (or create a new one)."""
    asyncio.run(_init(project_name, yes, no_dashboard))


async def _init(project_name: str | None, yes: bool, no_dashboard: bool) -> None:
    from .init import run_init
    await run_init(project_name=project_name, accept_defaults=yes, no_dashboard=no_dashboard)


# ─────────────────────────────────────────────────────────────────────────────
# pocketteam start — launch Claude Code (auto mode → fallback skip-permissions)
# ─────────────────────────────────────────────────────────────────────────────

@main.group(invoke_without_command=True)
@click.option("--no-telegram", is_flag=True, help="Start without Telegram channel.")
@click.pass_context
def start(ctx: click.Context, no_telegram: bool) -> None:
    """Resume last session (or start new if none exists).

    Uses --dangerously-skip-permissions with PocketTeam's 9-layer safety hooks.

    Default (no subcommand): resumes the last session.
    Use 'pocketteam start new' to start a fresh session.
    Use 'pocketteam start resume' to pick a session interactively.
    """
    ctx.ensure_object(dict)
    ctx.obj["no_telegram"] = no_telegram
    if ctx.invoked_subcommand is None:
        # Default: continue last session (avoids orphan sessions)
        _launch_claude(no_telegram=no_telegram, resume="continue", session_id=None)


@start.command("new")
@click.pass_context
def start_new(ctx: click.Context) -> None:
    """Start a fresh new session."""
    no_telegram = ctx.parent.obj.get("no_telegram", False) if ctx.parent else False
    _launch_claude(no_telegram=no_telegram, resume="new", session_id=None)


@start.command("resume")
@click.argument("session_id", required=False, default=None)
@click.pass_context
def start_resume(ctx: click.Context, session_id: str | None) -> None:
    """Resume a specific session by ID, or open session picker if no ID given."""
    no_telegram = ctx.parent.obj.get("no_telegram", False) if ctx.parent else False
    _launch_claude(no_telegram=no_telegram, resume="pick" if not session_id else "id", session_id=session_id)


def _launch_claude(
    *,
    no_telegram: bool,
    resume: str,  # "continue" | "pick" | "id" | "new"
    session_id: str | None,
) -> None:
    """Launch Claude Code with --dangerously-skip-permissions.

    PocketTeam's 9-layer safety hooks run on every tool call regardless.
    Auto mode (--permission-mode auto) will be added when available on Max plan.

    resume modes:
      "continue" - auto-resume last session (--continue)
      "pick"     - open interactive session picker (--resume)
      "id"       - resume specific session (--resume <id>)
      "new"      - start fresh (no resume flag)
    """
    import os

    from .config import load_config

    root = Path.cwd()
    cfg = load_config(root)

    # Ensure bun is in PATH (installed to ~/.bun/bin/ by pocketteam init)
    bun_dir = Path.home() / ".bun/bin"
    if bun_dir.exists() and str(bun_dir) not in os.environ.get("PATH", ""):
        os.environ["PATH"] = f"{bun_dir}:{os.environ['PATH']}"

    tg_active = bool(
        cfg.telegram.bot_token
        and not cfg.telegram.bot_token.startswith("$")
        and not no_telegram
    )

    # Load Telegram env
    if tg_active:
        env_file = root / ".pocketteam/telegram.env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if "=" in line and not line.startswith("#"):
                    key, val = line.split("=", 1)
                    os.environ[key.strip()] = val.strip()

    # Build command: skip-permissions + medium effort for COO (Planner gets Opus for deep thinking)
    cmd = ["claude", "--dangerously-skip-permissions", "--effort", "medium", "--agent", "pocketteam/coo"]

    # Session handling
    if resume == "continue":
        cmd.append("--continue")
        console.print("[dim]Continuing last session...[/]")
    elif resume == "pick":
        cmd.append("--resume")
        console.print("[dim]Opening session picker...[/]")
    elif resume == "id" and session_id:
        cmd.extend(["--resume", session_id])
        console.print(f"Resuming session [cyan]{session_id}[/]")
    else:
        console.print("[dim]Starting new session...[/]")

    # Telegram channel
    if tg_active:
        cmd.extend(["--channels", "plugin:telegram@claude-plugins-official"])
        console.print(f"[cyan]Telegram channel[/] active for [bold]{cfg.project_name}[/]")
    else:
        console.print(f"Starting Claude Code for [bold]{cfg.project_name}[/]")

    console.print("[green]PocketTeam[/] — 9-layer safety hooks active")
    console.print()
    os.execvp(cmd[0], cmd)


# ─────────────────────────────────────────────────────────────────────────────
# pocketteam status
# ─────────────────────────────────────────────────────────────────────────────

@main.command()
@click.option("--all", "show_all", is_flag=True, help="Show all configured projects.")
def status(show_all: bool) -> None:
    """Show PocketTeam status for the current project."""
    asyncio.run(_status(show_all))


async def _status(show_all: bool) -> None:
    import json

    from .config import load_config
    from .constants import EVENTS_FILE

    project_root = Path.cwd()
    config_path = project_root / ".pocketteam/config.yaml"

    if not config_path.exists():
        console.print("[red]No PocketTeam config found.[/] Run [bold]pocketteam init[/] first.")
        sys.exit(1)

    cfg = load_config(project_root)

    table = Table(title=f"PocketTeam: {cfg.project_name}", show_header=True)
    table.add_column("Setting", style="cyan")
    table.add_column("Value")

    table.add_row("Project", cfg.project_name)
    table.add_row("Health URL", cfg.health_url or "[dim]not configured[/]")
    table.add_row("Auth Mode", cfg.auth.mode)
    table.add_row("Telegram", "✅ configured" if cfg.telegram.bot_token else "❌ not configured")
    table.add_row("Monitoring", "✅ enabled" if cfg.monitoring.enabled else "❌ disabled")
    table.add_row("GitHub Actions", "✅ enabled" if cfg.github_actions.enabled else "❌ disabled")

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
            logger.debug("Failed to read last event", exc_info=True)

    console.print(table)


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
# pocketteam health
# ─────────────────────────────────────────────────────────────────────────────

HEALTH_CHECK_TIMEOUT = 5  # seconds for HTTP health endpoint requests


@main.command()
def health() -> None:
    """Show system health: project, config, last event, dashboard."""
    asyncio.run(_health())


async def _health() -> None:
    import json

    from .config import load_config
    from .constants import CONFIG_FILE, EVENTS_FILE, POCKETTEAM_DIR

    project_root = Path.cwd()
    ok = "[bold green]OK[/]"
    warn = "[bold yellow]WARN[/]"
    fail = "[bold red]FAIL[/]"

    console.print()
    console.print("[bold]PocketTeam Health Check[/]")
    console.print()

    # ── 1. Project directory ──────────────────────────────────────────────────
    pocketteam_dir = project_root / POCKETTEAM_DIR
    if pocketteam_dir.is_dir():
        console.print(f"  Project:      {ok} (.pocketteam/ found)")
    else:
        console.print(f"  Project:      {fail} (.pocketteam/ not found — run pocketteam init)")
        # Further checks are meaningless without the directory
        console.print()
        return

    # ── 2. Config validity ────────────────────────────────────────────────────
    config_path = project_root / CONFIG_FILE
    if not config_path.exists():
        console.print(f"  Config:       {warn} (config.yaml missing)")
        cfg = None
    else:
        try:
            cfg = load_config(project_root)
            console.print(f"  Config:       {ok} (config.yaml valid)")
        except Exception as exc:
            console.print(f"  Config:       {fail} (config.yaml parse error: {exc})")
            cfg = None

    # ── 3. Last event ─────────────────────────────────────────────────────────
    events_path = project_root / EVENTS_FILE
    if not events_path.exists():
        console.print(f"  Last Event:   {warn} (no events yet)")
    else:
        try:
            lines = [line for line in events_path.read_text().splitlines() if line.strip()]
            if not lines:
                console.print(f"  Last Event:   {warn} (stream empty)")
            else:
                last = json.loads(lines[-1])
                ts_raw = last.get("ts", "")
                agent = last.get("agent", "?")
                action = last.get("action", last.get("type", ""))
                # Compute human-readable age
                age_str = ""
                if ts_raw:
                    try:
                        ts_dt = datetime.fromisoformat(ts_raw.rstrip("Z")).replace(
                            tzinfo=UTC
                        )
                        delta = datetime.now(tz=UTC) - ts_dt
                        total_secs = int(delta.total_seconds())
                        if total_secs < 60:
                            age_str = f"{total_secs}s ago"
                        elif total_secs < 3600:
                            age_str = f"{total_secs // 60}m ago"
                        elif total_secs < 86400:
                            age_str = f"{total_secs // 3600}h ago"
                        else:
                            age_str = f"{total_secs // 86400}d ago"
                    except ValueError:
                        age_str = ts_raw[:19]
                detail = f"{agent}: {action}" if action else agent
                console.print(
                    f"  Last Event:   {ok} ({age_str} — {detail})"
                    if age_str
                    else f"  Last Event:   {ok} ({detail})"
                )
        except Exception as exc:
            console.print(f"  Last Event:   {warn} (could not read stream: {exc})")

    # ── 5. Dashboard reachability ─────────────────────────────────────────────
    health_url: str = ""
    if cfg:
        health_url = cfg.health_url or ""
        if not health_url and cfg.dashboard.enabled and cfg.dashboard.port:
            health_url = f"http://localhost:{cfg.dashboard.port}/api/health"

    if not health_url:
        console.print(f"  Dashboard:    {warn} (not configured)")
    else:
        try:
            import urllib.error
            import urllib.request
            req = urllib.request.Request(health_url, method="GET")
            with urllib.request.urlopen(req, timeout=HEALTH_CHECK_TIMEOUT) as resp:
                status_code = resp.getcode()
            if status_code < 400:
                console.print(f"  Dashboard:    {ok} ({health_url} → HTTP {status_code})")
            else:
                console.print(
                    f"  Dashboard:    {warn} ({health_url} → HTTP {status_code})"
                )
        except Exception as exc:
            short = str(exc)[:80]
            console.print(f"  Dashboard:    {warn} ({health_url} unreachable — {short})")

    console.print()


# ─────────────────────────────────────────────────────────────────────────────
# pocketteam logs
# ─────────────────────────────────────────────────────────────────────────────

@main.command()
@click.option("--follow", "-f", is_flag=True, help="Follow log output (like tail -f).")
@click.option("--lines", "-n", default=50, help="Number of lines to show (default: 50).")
@click.option("--agent", default=None, help="Filter by agent name.")
@click.option("--since", default=None, help="Show logs since (e.g., 1h, 30m, 2d).")
def logs(follow: bool, lines: int, agent: str | None, since: str | None) -> None:
    """Show PocketTeam event log."""
    asyncio.run(_logs(follow=follow, lines=lines, agent_filter=agent, since=since))


def _parse_since(since: str) -> datetime | None:
    """Parse a duration string like '1h', '30m', '2d' into a cutoff datetime (UTC).

    Returns None if the string is invalid.
    """
    match = re.fullmatch(r"(\d+)(h|m|d)", since.strip())
    if not match:
        return None
    value, unit = int(match.group(1)), match.group(2)
    delta = {
        "m": timedelta(minutes=value),
        "h": timedelta(hours=value),
        "d": timedelta(days=value),
    }[unit]
    return datetime.now(tz=UTC) - delta


async def _logs(
    follow: bool, lines: int, agent_filter: str | None, since: str | None
) -> None:
    import asyncio
    import json

    from .constants import EVENTS_FILE

    events_path = Path.cwd() / EVENTS_FILE
    if not events_path.exists():
        console.print("[dim]No events logged yet.[/]")
        return

    # Parse --since into a cutoff timestamp
    since_cutoff: datetime | None = None
    if since:
        since_cutoff = _parse_since(since)
        if since_cutoff is None:
            console.print(
                f"[red]Invalid --since value:[/] '{since}'. "
                "Use format like 1h, 30m, 2d."
            )
            sys.exit(1)

    def _event_passes_since(e: dict) -> bool:
        """Return True if the event timestamp is at or after since_cutoff."""
        if since_cutoff is None:
            return True
        ts_raw = e.get("ts", "")
        if not ts_raw:
            return True
        try:
            # Accept ISO-8601 timestamps: "2024-01-15T10:30:00Z" or without Z
            ts_raw_clean = ts_raw.rstrip("Z")
            ts_dt = datetime.fromisoformat(ts_raw_clean).replace(tzinfo=UTC)
            return ts_dt >= since_cutoff
        except ValueError:
            return True

    def print_event(line: str) -> None:
        try:
            e = json.loads(line)
            if not _event_passes_since(e):
                return

            ts = e.get("ts", "")[:19]
            ag = e.get("agent", "?")
            action = e.get("action", "")
            etype = e.get("type", "")
            status = e.get("status", "")

            if agent_filter and ag != agent_filter:
                return

            color = AGENT_COLORS.get(ag, "white")

            console.print(f"[dim]{ts}[/] [[{color}]{ag:12}[/]] {action or etype or status}")
        except Exception:
            console.print(line)

    # When --since is set, scan all lines; otherwise show last N
    all_lines = events_path.read_text().splitlines()
    source_lines = all_lines if since_cutoff is not None else all_lines[-lines:]
    for line in source_lines:
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

    For normal interactive use, start Claude Code instead: pocketteam start
    """
    asyncio.run(_run(task, skip_product, no_telegram))


async def _run(task: str, skip_product: bool, no_telegram: bool) -> None:
    from .channels.setup import TelegramChannel
    from .config import load_config
    from .core.orchestrator import run_task

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


# ─────────────────────────────────────────────────────────────────────────────
# pocketteam dashboard
# ─────────────────────────────────────────────────────────────────────────────


@main.group(invoke_without_command=True)  # Errata E8: invoke_without_command=True
@click.pass_context
def dashboard(ctx: click.Context) -> None:
    """Manage the PocketTeam dashboard."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(dashboard_start)


@dashboard.command("start")
def dashboard_start() -> None:
    """Start the dashboard container."""
    from .dashboard import dashboard_start_cmd
    dashboard_start_cmd(Path.cwd())


@dashboard.command("stop")
def dashboard_stop() -> None:
    """Stop the dashboard container."""
    from .dashboard import dashboard_stop_cmd
    dashboard_stop_cmd(Path.cwd())


@dashboard.command("status")
def dashboard_status() -> None:
    """Show dashboard status, URL, and volume health."""
    from .dashboard import dashboard_status_cmd
    dashboard_status_cmd(Path.cwd())


@dashboard.command("logs")
def dashboard_logs() -> None:
    """Follow dashboard container logs."""
    from .dashboard import dashboard_logs_cmd
    dashboard_logs_cmd(Path.cwd())


@dashboard.command("update")
def dashboard_update() -> None:
    """Pull latest digest-pinned image, update compose, and restart."""
    from .dashboard import dashboard_update_cmd
    dashboard_update_cmd(Path.cwd())


@dashboard.command("configure")
@click.option("--port", default=None, type=int, help="Change the external port.")
@click.option("--domain", default=None, help="Set domain (generates Caddyfile with basicauth).")
@click.option("--project-root", "project_root_override", default=None,
              help="Switch project root (must be under your home directory).")
@click.option("--reset", is_flag=True, help="Regenerate compose from config (warns if hand-edited).")
def dashboard_configure(
    port: int | None,
    domain: str | None,
    project_root_override: str | None,
    reset: bool,
) -> None:
    """Change dashboard settings post-setup."""
    from .dashboard import dashboard_configure_cmd
    dashboard_configure_cmd(
        project_root=Path.cwd(),
        port=port,
        domain=domain,
        project_root_override=project_root_override,
        reset=reset,
    )


@dashboard.command("install")
def dashboard_install() -> None:
    """Install the dashboard (for users who ran pocketteam init --no-dashboard)."""
    from .dashboard import dashboard_install_cmd
    dashboard_install_cmd(Path.cwd())


# ─────────────────────────────────────────────────────────────────────────────
# pocketteam insights
# ─────────────────────────────────────────────────────────────────────────────

@main.group()
def insights() -> None:
    """Auto-Insights: self-improvement schedule management."""


@insights.command("on")
@click.option("--cron", default=None, help="Custom cron schedule or HH:MM time (e.g. '14:00' or '0 8 * * *')")
def insights_on(cron: str | None) -> None:
    """Enable the daily insights schedule."""
    from .config import load_config, save_config

    cfg = load_config(Path.cwd())
    cfg.insights.enabled = True
    if cron:
        converted = _parse_schedule_input(cron)
        # Validate: must be 5 space-separated fields after conversion
        if not re.match(r"^(\S+\s+){4}\S+$", converted.strip()):
            click.echo("Error: Invalid schedule. Use HH:MM (e.g. '14:00') or cron (e.g. '0 22 * * *').")
            raise SystemExit(1)
        cfg.insights.schedule = converted
    cfg.insights.telegram_notify = bool(cfg.telegram.chat_id)
    save_config(cfg)

    console.print(f"[green]✓[/] Insights enabled (schedule: {cfg.insights.schedule})")
    console.print()
    console.print("To create the Remote Agent trigger, run:")
    console.print(f'  claude /schedule create --cron "{cfg.insights.schedule}" --prompt "Run /self-improve for this project"')
    console.print()
    console.print("Or use: pocketteam insights run")


@insights.command("off")
def insights_off() -> None:
    """Disable the insights schedule."""
    from .config import load_config, save_config

    cfg = load_config(Path.cwd())
    cfg.insights.enabled = False
    save_config(cfg)

    console.print("[green]✓[/] Insights disabled.")
    console.print()
    console.print("Remember to also remove the Remote Agent trigger at:")
    console.print("  https://claude.ai/code/scheduled")


@insights.command("status")
def insights_status() -> None:
    """Show insights schedule status and recent reports."""
    from .config import load_config
    from .constants import INSIGHTS_DIR

    cfg = load_config(Path.cwd())

    console.print(f"Enabled:    {'Yes' if cfg.insights.enabled else 'No'}")
    console.print(f"Schedule:   {cfg.insights.schedule}")
    console.print(f"Last run:   {cfg.insights.last_run or 'Never'}")
    console.print(f"Telegram:   {'Yes' if cfg.insights.telegram_notify else 'No'}")
    console.print("Auto-apply: No (always requires CEO approval)")
    console.print()

    # List recent reports
    insights_dir = Path.cwd() / INSIGHTS_DIR
    if insights_dir.exists():
        reports = sorted(insights_dir.glob("*.md"), reverse=True)[:5]
        if reports:
            console.print("Recent reports:")
            for r in reports:
                console.print(f"  - {r.name}")
        else:
            console.print("No reports yet.")
    else:
        console.print("No reports yet.")


def _send_insights_telegram(project_root: Path, content: str) -> None:
    """Send an insights report via Telegram Bot API.

    Reads bot token from ~/.claude/channels/telegram/.env and chat_id from
    ~/.claude/channels/telegram/access.json (first allowFrom entry).
    Truncates content to 4000 characters to stay within Telegram's 4096-char limit.
    Silent (no exception) when Telegram is not configured.
    """
    try:
        import json as _json
        import urllib.parse
        import urllib.request

        env_file = Path.home() / ".claude" / "channels" / "telegram" / ".env"
        access_file = Path.home() / ".claude" / "channels" / "telegram" / "access.json"

        if not env_file.exists() or not access_file.exists():
            return

        bot_token = ""
        for line in env_file.read_text().splitlines():
            if line.startswith("TELEGRAM_BOT_TOKEN="):
                bot_token = line.split("=", 1)[1].strip()
                break

        if not bot_token:
            return

        access_data = _json.loads(access_file.read_text())
        allowed = access_data.get("allowFrom", [])
        if not allowed:
            return

        chat_id = allowed[0]

        # Truncate to Telegram's practical limit (leaving room for header)
        MAX_LENGTH = 4000
        text = content if len(content) <= MAX_LENGTH else content[:MAX_LENGTH]

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": text,
        }).encode()

        req = urllib.request.Request(url, data=data, method="POST")
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass  # Telegram notification is best-effort — never block insights run


@insights.command("run")
def insights_run() -> None:
    """Run insights analysis now (outside of schedule)."""
    import shutil
    import subprocess

    from .constants import INSIGHTS_DIR

    claude_path = shutil.which("claude")
    if not claude_path:
        console.print("[red]Claude CLI not found in PATH[/]")
        raise SystemExit(1)

    project_root = Path.cwd()
    console.print("[cyan]Running self-improve analysis...[/]")

    result = subprocess.run(
        [claude_path, "--continue", "-p", "Run /self-improve for this project"],
        cwd=str(project_root),
    )

    if result.returncode == 0:
        console.print("[green]Insights analysis complete.[/]")
        # Find and send latest insights report via Telegram
        artifacts_dir = project_root / INSIGHTS_DIR
        if artifacts_dir.exists():
            reports = sorted(artifacts_dir.glob("*.md"), reverse=True)
            if reports:
                report_content = reports[0].read_text()
                _send_insights_telegram(project_root, report_content)
    else:
        console.print(f"[red]Insights analysis failed (exit code {result.returncode})[/]")
        raise SystemExit(result.returncode)


# ─────────────────────────────────────────────────────────────────────────────
# pocketteam help
# ─────────────────────────────────────────────────────────────────────────────

# Command groups displayed in the help output, in order.
_HELP_GROUPS: list[tuple[str, list[tuple[str, str]]]] = [
    (
        "Getting Started",
        [
            ("init", "Set up PocketTeam in your project"),
            ("start", "Resume last session (or start new if none exists)"),
            ("start new", "Start a fresh session"),
            ("start resume", "Pick a session to resume"),
            ("status", "Show project status"),
        ],
    ),
    (
        "Monitoring",
        [
            ("health", "System health check"),
            ("logs", "Show event log"),
            ("sessions", "List or manage pipeline sessions"),
        ],
    ),
    (
        "Dashboard",
        [
            ("dashboard", "Dashboard management (start/stop/status/logs/install/update/configure)"),
        ],
    ),
    (
        "Automation",
        [
            ("insights", "Self-improvement schedule (on/off/status/run)"),
            ("retro", "Run a retrospective"),
            ("run-headless", "CI/GitHub Actions pipeline"),
        ],
    ),
    (
        "Maintenance",
        [
            ("uninstall", "Remove PocketTeam from project"),
            ("help", "Show this help message"),
        ],
    ),
]


@main.command(name="help")
def help_command() -> None:
    """Show a grouped overview of all available commands."""
    try:
        from importlib.metadata import version as pkg_version
        ver = pkg_version("pocketteam")
    except Exception:
        ver = "?"

    console.print()
    console.print(f"[bold cyan]PocketTeam v{ver}[/] — Autonomous AI IT Team")
    console.print()

    for group_name, commands in _HELP_GROUPS:
        table = Table(
            show_header=False,
            box=None,
            padding=(0, 2),
            show_edge=False,
        )
        table.add_column("Command", style="bold green", no_wrap=True, min_width=22)
        table.add_column("Description", style="")

        for cmd_name, description in commands:
            table.add_row(f"pocketteam {cmd_name}", description)

        console.print(f"[bold]{group_name}:[/]")
        console.print(table)
        console.print()

    console.print("[dim]Tip: Use [bold]pocketteam <command> --help[/bold] for details on any command.[/]")
    console.print()


if __name__ == "__main__":
    main()
