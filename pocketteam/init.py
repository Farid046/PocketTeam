"""
PocketTeam Init
Handles both new project creation and integration into existing projects.
Uses merge-not-overwrite strategy to avoid destroying existing .claude/ configs.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from .config import PocketTeamConfig, TelegramConfig, save_config
from .constants import (
    AGENTS_DIR,
    AUDIT_DIR,
    CLAUDE_DIR,
    EVENTS_FILE,
    INCIDENTS_DIR,
    INSIGHTS_DIR,
    LEARNINGS_DIR,
    PLANS_DIR,
    POCKETTEAM_DIR,
    REVIEWS_DIR,
    SESSIONS_DIR,
    SKILLS_DIR,
)

console = Console()

# Markers for CLAUDE.md merge — these must never change
POCKETTEAM_START = "<!-- POCKETTEAM START -->"
POCKETTEAM_END = "<!-- POCKETTEAM END -->"


async def run_init(
    project_name: str | None,
    accept_defaults: bool,
    no_dashboard: bool = False,
) -> None:
    """Main init flow."""
    console.print(Panel(
        "Welcome to [bold cyan]PocketTeam[/] 🚀\n"
        "Your autonomous AI IT team.",
        border_style="cyan",
    ))

    # Determine project root
    if project_name:
        project_root = Path.cwd() / project_name
        project_root.mkdir(parents=True, exist_ok=True)
        is_new = True
        console.print(f"Creating new project: [bold]{project_root}[/]")
    else:
        project_root = Path.cwd()
        is_new = not (project_root / ".git").exists() and not (project_root / POCKETTEAM_DIR).exists()

    # Detect existing setup
    has_claude_dir = (project_root / CLAUDE_DIR).exists()
    has_pocketteam = (project_root / POCKETTEAM_DIR).exists()
    has_git = (project_root / ".git").exists()

    if has_pocketteam and not accept_defaults:
        reconfigure = Confirm.ask(
            "[yellow]PocketTeam is already initialized here. Reconfigure?[/]",
            default=False,
        )
        if not reconfigure:
            console.print("Aborted.")
            return

    # Interview
    cfg = await _interview(project_root, project_name, accept_defaults)

    # Create directory structure
    _create_directories(project_root)

    # Save config
    save_config(cfg)

    # Setup .claude/ (merge if exists)
    _setup_claude_dir(project_root, cfg, is_new=not has_claude_dir)

    # Initialize git if new project
    if is_new and not has_git:
        subprocess.run(["git", "init", "-q"], cwd=project_root, check=False)
        _create_gitignore(project_root)

    # Create GitHub Actions workflow
    _create_github_actions(project_root, cfg)

    # GitHub integration: repo creation, secrets, workflow push
    if cfg.github.enabled:
        try:
            from .github_setup import run_github_setup
            gh_cfg = run_github_setup(project_root, cfg, accept_defaults)
            cfg.github = gh_cfg
            # Re-save config with updated GitHub info (repo_name, repo_owner)
            save_config(cfg)
        except Exception as e:
            console.print(f"  [yellow]⚠ GitHub setup: {e}[/]")
            console.print("  Run later: [bold]gh auth login[/] then [bold]pocketteam init[/]")

    # Create start script + ensure plugin is installed if Telegram configured
    tg_active = bool(cfg.telegram.bot_token and not cfg.telegram.bot_token.startswith("$"))
    if tg_active:
        _create_start_script(project_root, cfg)
        # Safety net: ensure plugin is installed even on re-init without reconfigure
        _setup_telegram_plugin(cfg.telegram.bot_token)

    # Telegram auto-session daemon (macOS launchd)
    if tg_active:
        try:
            from .telegram_daemon_plist import install_plist, is_macos
            if is_macos():
                daemon_ok = install_plist(project_root)
                if daemon_ok:
                    console.print("  [green]✓[/] Telegram auto-session daemon installed")
                    console.print(
                        "    [dim]Messages while Claude is offline will auto-start a session[/]"
                    )
                else:
                    console.print("  [yellow]⚠[/] Telegram daemon setup failed (check launchctl logs)")
        except Exception as e:
            console.print(f"  [yellow]⚠[/] Telegram daemon skipped: {e}")

    # MCP Starter Pack
    _setup_mcp_servers(cfg, console)

    # Setup dashboard (default ON, skip with --no-dashboard)
    if not no_dashboard:
        try:
            from .dashboard import setup_dashboard
            setup_dashboard(cfg)
        except SystemExit:
            # setup_dashboard may sys.exit() with instructions — let it propagate
            raise
        except Exception as e:
            console.print(f"  [yellow]Dashboard setup skipped: {e}[/]")
            console.print("  Run later: [bold]pocketteam dashboard install[/]")

    # Send Telegram confirmation if configured
    if tg_active and cfg.telegram.chat_id:
        try:
            from .channels.setup import TelegramChannel
            ch = TelegramChannel(project_root, config=cfg)
            tg_ok = await ch.send_message(
                f"🚀 <b>PocketTeam initialized!</b>\n\n"
                f"Project: {cfg.project_name}\n"
                f"Start Claude Code with Telegram:\n"
                f"<code>pocketteam start</code>\n\n"
                f"Or DM me after pairing."
            )
            if tg_ok:
                console.print("  [green]✅ Telegram test message sent![/]")
            else:
                console.print("  [yellow]⚠️ Could not reach Telegram bot.[/]")
        except Exception:
            pass

    # Active features summary
    features = _build_active_features_summary(cfg, tg_active)

    # Dynamic next steps
    next_steps = []
    if tg_active:
        next_steps.append("Start:")
        next_steps.append("  [bold]pocketteam start[/]")
        next_steps.append("")
        next_steps.append("[dim]Send a message to your bot on Telegram to start remote control.[/]")
    else:
        next_steps.append("Start:")
        next_steps.append("  [bold]pocketteam start[/]")

    next_steps.append("")
    next_steps.append("Then give it a task:")
    next_steps.append("  > Build user auth with OAuth2")
    next_steps.append("")
    if cfg.dashboard.enabled:
        next_steps.append("[dim]Manage: pocketteam dashboard start|stop|status|logs[/]")
    elif no_dashboard:
        next_steps.append("[dim]Dashboard skipped. Install later: pocketteam dashboard install[/]")
    next_steps.append("[dim]Commands: pocketteam start | start new | start resume | status[/]")

    console.print(Panel(
        "✅ [bold green]PocketTeam initialized![/]\n\n"
        "[bold]Active Features:[/]\n"
        + "\n".join(features)
        + "\n\n"
        + "\n".join(next_steps),
        title="Ready",
        border_style="green",
    ))


async def _interview(
    project_root: Path,
    project_name: str | None,
    accept_defaults: bool,
) -> PocketTeamConfig:
    """Interactive setup interview — guides user step-by-step."""
    from .config import load_config

    # Load existing config as defaults (so re-init preserves previous answers)
    existing = load_config(project_root)
    cfg = PocketTeamConfig(project_root=project_root)
    cfg.project_name = project_name or existing.project_name or project_root.name
    cfg.health_url = existing.health_url
    cfg.auth = existing.auth
    cfg.telegram = existing.telegram
    cfg.monitoring = existing.monitoring
    cfg.budget = existing.budget
    cfg.github = existing.github
    cfg.network = existing.network
    cfg.insights = existing.insights

    # ── Step 1: Project Name ────────────────────────────────────────────
    console.print(Panel(
        "[bold]Step 1/6: Project Name[/]\n\n"
        "This name is used in status messages and Telegram notifications.",
        title="[cyan]1[/] Project",
        border_style="cyan",
    ))
    if not accept_defaults:
        cfg.project_name = Prompt.ask(
            "  Project name",
            default=cfg.project_name,
        )

    # ── Step 2: API Key ─────────────────────────────────────────────────
    has_env_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    current_key = cfg.auth.api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    key_display = f"{current_key[:10]}...{current_key[-4:]}" if len(current_key) > 20 else ("set" if current_key else "not set")

    console.print(Panel(
        "[bold]Step 2/6: Anthropic API Key[/] [dim](optional)[/]\n\n"
        "Only needed for self-healing via Agent SDK (e.g. GitHub Actions monitoring).\n"
        "Uses Haiku model for minimal cost.\n"
        "[bold]Normal operation runs entirely on your Claude subscription[/] —\n"
        "no API key required for interactive use.\n\n"
        "Get one at: [bold cyan]https://console.anthropic.com/settings/keys[/]\n\n"
        f"Current: [{'green' if current_key else 'yellow'}]{key_display}[/]\n"
        + ("  (detected from ANTHROPIC_API_KEY env var)\n" if has_env_key else "") +
        "\n"
        "[dim]The key is stored in .pocketteam/config.yaml (gitignored).\n"
        "You can also set it as ANTHROPIC_API_KEY environment variable.[/]",
        title="[cyan]2[/] API Key",
        border_style="cyan",
    ))
    if not accept_defaults:
        if current_key:
            change_key = Confirm.ask(
                f"  API key is set ({key_display}). Change it?",
                default=False,
            )
            if change_key:
                new_key = Prompt.ask("  Paste your API key", default="")
                if new_key:
                    cfg.auth.api_key = new_key
        else:
            new_key = Prompt.ask(
                "  Paste your API key (or Enter to skip — set ANTHROPIC_API_KEY env var later)",
                default="",
            )
            if new_key:
                cfg.auth.api_key = new_key

        # Warn if key doesn't look like Anthropic format (non-blocking)
        if cfg.auth.api_key and not cfg.auth.api_key.startswith("sk-ant-"):
            console.print("[yellow]Warning: Key doesn't look like Anthropic format (sk-ant-*). Continuing anyway.[/]")

        # Auth mode is derived: if key exists, hybrid; else subscription-only
        if cfg.auth.api_key or has_env_key:
            cfg.auth.mode = "hybrid"
        else:
            cfg.auth.mode = "subscription"

    # ── Step 3: Telegram via Claude Code Channels ─────────────────────
    tg_configured = bool(cfg.telegram.bot_token
                         and not cfg.telegram.bot_token.startswith("$"))
    tg_display = f"Bot: ...{cfg.telegram.bot_token[-6:]}" if tg_configured else "not configured"

    # Check prerequisites
    has_bun = shutil.which("bun") is not None

    console.print(Panel(
        "[bold]Telegram Remote Control[/]\n\n"
        "Control PocketTeam from your phone via Telegram.\n\n"
        "[bold]How to set up:[/]\n"
        "  [bold]Bot Token:[/]\n"
        "    1. Open Telegram and search for [bold]@BotFather[/]\n"
        "    2. Send [bold]/newbot[/]\n"
        "    3. Choose a name (e.g. 'MyApp PocketTeam')\n"
        "    4. Choose a username (e.g. 'myapp_pocketteam_bot')\n"
        "    5. BotFather gives you a token like: [dim]7123456789:AAH...[/]\n\n"
        "  [bold]Chat ID:[/]\n"
        "    1. Open Telegram and search for [bold]@userinfobot[/]\n"
        "    2. Send any message to it\n"
        "    3. It replies with your Chat ID (a number like [dim]123456789[/])\n\n"
        "[yellow]Important:[/] Create a project-specific bot!\n"
        "  You need a separate bot for each PocketTeam project.\n\n"
        f"Current: [{'green' if tg_configured else 'yellow'}]{tg_display}[/]\n"
        f"Bun (required): [{'green' if has_bun else 'red'}]{'installed' if has_bun else 'NOT installed'}[/]",
        title="Step 3/6: Telegram (optional)",
        border_style="cyan",
    ))

    if not accept_defaults:
        if tg_configured:
            change_tg = Confirm.ask(
                "  Telegram is configured. Reconfigure?",
                default=False,
            )
            if not change_tg:
                pass  # Keep existing
            else:
                tg_configured = False

        if not tg_configured:
            setup_telegram = Confirm.ask(
                "  Set up Telegram?",
                default=True,
            )
            if setup_telegram:
                # Check Bun prerequisite
                # Check common bun locations if not in PATH
                if not has_bun:
                    bun_paths = [
                        Path.home() / ".bun/bin/bun",
                        Path("/usr/local/bin/bun"),
                    ]
                    for bp in bun_paths:
                        if bp.exists():
                            has_bun = True
                            # Add to PATH for this session + pocketteam start
                            os.environ["PATH"] = f"{bp.parent}:{os.environ.get('PATH', '')}"
                            console.print(f"  [green]Bun found at {bp}[/]")
                            break

                if not has_bun:
                    console.print()
                    console.print("  [yellow]Bun is required for Claude Code Channels.[/]")
                    console.print()
                    install_bun = Confirm.ask("  Install Bun now?", default=True)
                    if install_bun:
                        console.print("  Installing Bun...")
                        result = subprocess.run(
                            ["bash", "-c", "curl -fsSL https://bun.sh/install | bash"],
                            capture_output=True, text=True,
                        )
                        if result.returncode == 0:
                            # Bun installs to ~/.bun/bin/ — add to PATH immediately
                            bun_dir = Path.home() / ".bun/bin"
                            if bun_dir.exists():
                                os.environ["PATH"] = f"{bun_dir}:{os.environ.get('PATH', '')}"
                                has_bun = True
                            console.print("  [green]Bun installed![/]")
                        else:
                            console.print("  [red]Install failed.[/]")
                            console.print("  Run manually: [bold]curl -fsSL https://bun.sh/install | bash[/]")
                            console.print("  Then: [bold]source ~/.zshrc && pocketteam init[/]")

                console.print()
                console.print("  [bold]Step 3a:[/] Create your Telegram bot")
                console.print("  1. Open Telegram and search for [bold cyan]@BotFather[/]")
                console.print("  2. Send [bold]/newbot[/]")
                console.print("  3. Choose a name (e.g. \"PocketTeam\")")
                console.print("  4. Choose a username (e.g. \"myapp_pocketteam_bot\")")
                console.print("  5. BotFather gives you a token like: [dim]7123456789:AAH...[/]")
                console.print()
                console.print("  [bold yellow]Important:[/bold yellow] Create a [bold]project-specific[/bold] bot!")
                console.print("  Name it after your project, e.g. 'MyApp PocketTeam'")
                console.print("  Username e.g. 'myapp_pocketteam_bot'")
                console.print("  [dim]You need a separate bot for each PocketTeam project.[/dim]")
                console.print()

                bot_token = Prompt.ask(
                    "  Paste your bot token (or Enter to skip)",
                    default=cfg.telegram.bot_token if tg_configured else "",
                )

                if bot_token:
                    cfg.telegram = TelegramConfig(
                        bot_token=bot_token,
                        chat_id=cfg.telegram.chat_id or "",
                    )

                    console.print()
                    console.print("  [green]Token saved![/]")

                    # Auto-setup: install plugin + write config
                    console.print()
                    console.print("  Setting up Telegram plugin automatically...")
                    plugin_ok = _setup_telegram_plugin(bot_token)

                    if plugin_ok:
                        console.print("  [green]✅ Telegram plugin installed and configured![/]")
                        console.print()
                    else:
                        console.print("  [yellow]⚠️ Auto-setup failed. Follow these manual steps after init:[/]")
                        console.print()
                        console.print("  [bold cyan]1.[/] Install the Telegram plugin:")
                        console.print("     [bold]/plugin install telegram@claude-plugins-official[/]")
                        console.print()
                        console.print("  [bold cyan]2.[/] Configure with your token:")
                        console.print(f"     [bold]/telegram:configure {bot_token}[/]")
                        console.print()
                        console.print("  [bold cyan]3.[/] Restart Claude Code with channels:")
                        console.print("     [bold]pocketteam start[/]")
                        console.print()

                    # Chat ID is required for Telegram to work
                    chat_id = Prompt.ask(
                        "  Paste your Chat ID (get it from @userinfobot on Telegram)",
                        default=cfg.telegram.chat_id or "",
                    )
                    if chat_id:
                        cfg.telegram.chat_id = chat_id
                    else:
                        console.print("  [yellow]⚠ Without a Chat ID, Telegram won't work.[/]")
                        console.print("  [yellow]  Get your Chat ID from @userinfobot on Telegram.[/]")

                    console.print("  [green]Telegram setup saved![/]")
                else:
                    console.print("  [dim]Skipped. Run pocketteam init again anytime.[/]")

    # ── Step 4: Health Monitoring ───────────────────────────────────────
    console.print(Panel(
        "[bold]Step 4/6: Production Health URL[/] (optional)\n\n"
        "If your app has a health endpoint, PocketTeam can monitor it\n"
        "24/7 and auto-fix issues.\n\n"
        f"Current: [{'green' if cfg.health_url else 'dim'}]{cfg.health_url or 'none'}[/]",
        title="[cyan]4[/] Health Monitoring",
        border_style="cyan",
    ))
    if not accept_defaults:
        health_url = Prompt.ask(
            "  Health URL (e.g. https://myapp.com/health)",
            default=cfg.health_url or "",
        )
        cfg.health_url = health_url
        cfg.monitoring.health_url = health_url

    # ── Step 5: GitHub Integration ────────────────────────────────────────
    gh_status = "configured" if cfg.github.repo_name else "not configured"
    console.print(Panel(
        "[bold]Step 5/6: GitHub Integration[/]\n\n"
        "Creates a GitHub repo, sets secrets, and adds a monitoring workflow.\n"
        "PocketTeam wakes up automatically when your health check fails.\n\n"
        f"Current: [{'green' if cfg.github.enabled else 'dim'}]{gh_status}[/]",
        title="[cyan]5[/] GitHub",
        border_style="cyan",
    ))
    if not accept_defaults:
        setup_gh = Confirm.ask(
            "  Enable GitHub integration?",
            default=cfg.github.enabled or bool(cfg.health_url),
        )
        cfg.github.enabled = setup_gh
    # Actual repo creation happens in run_init() after config is saved

    # ── Step 6: Insights Schedule ────────────────────────────────────────
    console.print()
    console.print(Panel(
        "[bold]Auto-Insights: Continuous Self-Improvement[/bold]\n\n"
        "PocketTeam can analyze its own performance daily and suggest\n"
        "improvements. You'll receive a Telegram summary with proposed\n"
        "changes — nothing is applied without your approval.\n\n"
        "[dim]Recommended: Yes (daily at 22:00 UTC)[/dim]",
        title="[cyan]6[/] Insights Schedule",
        border_style="cyan",
    ))

    if accept_defaults:
        enable_insights = False  # Never auto-enable, require explicit opt-in
        console.print("[dim]Skipped in --yes mode (opt-in only)[/dim]")
    else:
        enable_insights = Confirm.ask(
            "Enable daily insights schedule?",
            default=True,
        )

    if enable_insights:
        cfg.insights.enabled = True
        default_schedule = cfg.insights.schedule or "0 22 * * *"
        from pocketteam.cli import _cron_to_time, _parse_schedule_input
        default_display = _cron_to_time(default_schedule)
        custom = Prompt.ask(
            "Daily schedule time [dim](e.g. 14:00 or cron: 0 14 * * *)[/dim]",
            default=default_display,
        )
        cfg.insights.schedule = _parse_schedule_input(custom)
        cfg.insights.telegram_notify = bool(cfg.telegram.chat_id)
        console.print(f"[green]✓[/green] Insights scheduled: {cfg.insights.schedule}")
    else:
        cfg.insights.enabled = False
        console.print("[dim]Insights schedule not enabled. Enable later with: pocketteam insights on[/dim]")

    # ── Summary ─────────────────────────────────────────────────────────
    tg_final = bool(cfg.telegram.bot_token and cfg.telegram.chat_id
                     and not cfg.telegram.bot_token.startswith("$"))
    api_final = bool(cfg.auth.api_key or os.environ.get("ANTHROPIC_API_KEY"))

    console.print()
    table = Table(title="Configuration Summary", show_header=True, border_style="green")
    table.add_column("Setting", style="cyan")
    table.add_column("Value")
    table.add_column("Status")

    table.add_row("Project", cfg.project_name, "")
    table.add_row("API Key", cfg.auth.mode, "[green]ready[/]" if api_final else "[dim]optional (GitHub Actions only)[/]")
    table.add_row("Telegram", "configured" if tg_final else "not configured", "[green]ready[/]" if tg_final else "[dim]optional[/]")
    table.add_row("Health URL", cfg.health_url or "none", "[dim]optional[/]")
    gh_summary = f"{cfg.github.repo_owner}/{cfg.github.repo_name}" if cfg.github.repo_name else "will be created"
    table.add_row("GitHub", gh_summary if cfg.github.enabled else "disabled", "")
    if cfg.insights.enabled:
        insights_schedule_display = cfg.insights.schedule or "0 22 * * *"
        table.add_row("Insights", f"Daily ({insights_schedule_display})", "[green]active[/]")
    else:
        table.add_row("Insights", "disabled", "[dim]optional[/]")

    console.print(table)

    if not api_final:
        console.print()
        console.print("  [dim]No API key set — that's fine for normal use (Claude Code subscription).[/]")
        console.print("  [dim]Only needed for self-healing via GitHub Actions.[/]")

    if not accept_defaults:
        proceed = Confirm.ask("\n  Looks good? Save configuration", default=True)
        if not proceed:
            console.print("  Aborted. Run [bold]pocketteam init[/] again anytime.")
            import sys
            sys.exit(0)

    return cfg


def _create_directories(project_root: Path) -> None:
    """Create all required PocketTeam directories."""
    dirs = [
        POCKETTEAM_DIR,
        PLANS_DIR,
        REVIEWS_DIR,
        AUDIT_DIR,
        INCIDENTS_DIR,
        INSIGHTS_DIR,
        SESSIONS_DIR,
        LEARNINGS_DIR,
        ".pocketteam/events",
        AGENTS_DIR,
        SKILLS_DIR,
        ".claude/agents",
        ".github/workflows",
    ]
    for d in dirs:
        (project_root / d).mkdir(parents=True, exist_ok=True)

    # Touch the events stream file
    events_path = project_root / EVENTS_FILE
    if not events_path.exists():
        events_path.touch()


def _setup_claude_dir(project_root: Path, cfg: PocketTeamConfig, is_new: bool) -> None:
    """Set up or merge .claude/ configuration."""
    _setup_claude_md(project_root, cfg, is_new)
    _setup_settings_json(project_root, is_new)
    _setup_agent_definitions(project_root)
    _setup_statusline(project_root)
    _setup_ptbrowse()
    _setup_optimal_defaults(project_root)


def _setup_statusline(project_root: Path) -> None:
    """Register PocketTeam statusline plugin in .claude/settings.json.

    The statusline script pipes Claude Code session data (context window %,
    rate limits) to .pocketteam/session-status.json for the dashboard.
    """
    settings_path = project_root / CLAUDE_DIR / "settings.json"
    if not settings_path.exists():
        return

    # Find the statusline script
    statusline_script = Path(__file__).parent / "statusline" / "index.js"
    if not statusline_script.exists():
        return

    try:
        existing = json.loads(settings_path.read_text())
    except (json.JSONDecodeError, OSError):
        return

    # Always set the correct absolute path (fixes stale relative paths from older versions)
    node_bin = shutil.which("node") or "node"
    correct_command = f"{node_bin} {statusline_script}"
    current = existing.get("statusLine", {}).get("command", "")
    if current != correct_command:
        existing["statusLine"] = {
            "type": "command",
            "command": correct_command,
        }
        settings_path.write_text(json.dumps(existing, indent=2))
        console.print("  [green]PocketTeam HUD configured[/]")
    else:
        console.print("  [dim]PocketTeam HUD already configured[/]")


def _setup_ptbrowse() -> None:
    """Create a ptbrowse shell wrapper at ~/.local/bin/ptbrowse (or ~/.bun/bin/ptbrowse).

    The wrapper invokes pocketteam/browse/index.ts via bun so agents can call
    `ptbrowse <command>` from any working directory.
    """
    # Resolve the absolute path to browse/index.ts inside the installed package
    browse_index = Path(__file__).parent / "browse" / "index.ts"
    if not browse_index.exists():
        console.print("  [yellow]⚠[/] ptbrowse: browse/index.ts not found, skipping wrapper")
        return

    # Prefer ~/.bun/bin (already in PATH after bun install), fall back to ~/.local/bin
    bun_bin = Path.home() / ".bun" / "bin"
    local_bin = Path.home() / ".local" / "bin"

    if bun_bin.exists():
        wrapper_dir = bun_bin
    else:
        wrapper_dir = local_bin
        wrapper_dir.mkdir(parents=True, exist_ok=True)

    wrapper_path = wrapper_dir / "ptbrowse"

    wrapper_content = f"""#!/bin/bash
exec bun run "{browse_index.resolve()}" "$@"
"""

    try:
        wrapper_path.write_text(wrapper_content)
        wrapper_path.chmod(0o755)
        console.print(f"  [green]✓[/] ptbrowse installed at [dim]{wrapper_path}[/]")
    except OSError as e:
        console.print(f"  [yellow]⚠[/] ptbrowse wrapper: {e}")

    # Install browse dependencies (node_modules) so playwright-core etc. are available
    browse_dir = Path(__file__).parent / "browse"
    if browse_dir.exists() and (browse_dir / "package.json").exists():
        bun_path = shutil.which("bun")
        if bun_path:
            subprocess.run(
                [bun_path, "install"],
                cwd=str(browse_dir),
                capture_output=True,
                timeout=60,
            )


def _build_active_features_summary(cfg: "PocketTeamConfig", tg_active: bool) -> list[str]:
    """Build the active-features list shown at the end of init.

    Returns a list of Rich-formatted strings, one per feature line.
    """
    features: list[str] = []
    features.append("  [green]✓[/] Effort: [bold]medium[/] (balanced reasoning quality)")
    features.append("  [green]✓[/] Remote Control: [bold]active[/] (claude.ai/code + Mobile)")
    features.append("  [green]✓[/] Auto Memory: [bold]active[/]")
    features.append("  [green]✓[/] Auto Dream: [bold]active[/]")
    features.append("  [green]✓[/] PocketTeam HUD: [bold]configured[/]")
    features.append("  [green]✓[/] Safety Hooks: [bold]9-Layer Guardian[/]")
    if tg_active:
        features.append("  [green]✓[/] Telegram: [bold]configured[/]")
    if cfg.github.enabled and cfg.github.repo_name:
        features.append(f"  [green]✓[/] GitHub: [bold]{cfg.github.repo_owner}/{cfg.github.repo_name}[/]")
    if cfg.dashboard.enabled:
        features.append(f"  [green]✓[/] Dashboard: [bold cyan]http://localhost:{cfg.dashboard.port}[/]")
    if cfg.insights.enabled:
        features.append(f"  [green]✓[/] Auto-Insights: [bold]{cfg.insights.schedule or '0 22 * * *'}[/]")
    return features


def _setup_optimal_defaults(project_root: Path) -> None:
    """Set optimal Claude Code defaults for PocketTeam.

    - effortLevel: medium (COO is a dispatcher, Planner gets Opus for deep thinking)
    - autoDreamEnabled: true (long-running background memory consolidation)
    - remoteControlAtStartup: true (in ~/.claude.json)
    """
    # ── Project settings: effortLevel + autoDreamEnabled ─────────────────
    settings_path = project_root / CLAUDE_DIR / "settings.json"
    if settings_path.exists():
        try:
            existing = json.loads(settings_path.read_text())
            changed = False
            if "effortLevel" not in existing:
                existing["effortLevel"] = "medium"
                changed = True
            if "autoDreamEnabled" not in existing:
                existing["autoDreamEnabled"] = True
                changed = True
            if changed:
                settings_path.write_text(json.dumps(existing, indent=2))
        except (json.JSONDecodeError, OSError):
            pass

    # ── Global: remoteControlAtStartup ───────────────────────────────────
    global_config = Path.home() / ".claude.json"
    try:
        if global_config.exists():
            config = json.loads(global_config.read_text())
        else:
            config = {}
        if not config.get("remoteControlAtStartup"):
            config["remoteControlAtStartup"] = True
            global_config.write_text(json.dumps(config, indent=2))
    except (json.JSONDecodeError, OSError):
        pass


def _setup_claude_md(project_root: Path, cfg: PocketTeamConfig, is_new: bool) -> None:
    """Create or merge CLAUDE.md with PocketTeam section."""
    claude_md_path = project_root / CLAUDE_DIR / "CLAUDE.md"

    pocketteam_section = _get_pocketteam_claude_md_section(cfg)

    if not claude_md_path.exists() or is_new:
        claude_md_path.parent.mkdir(parents=True, exist_ok=True)
        claude_md_path.write_text(pocketteam_section)
        return

    # Merge: replace existing PocketTeam section or append
    existing = claude_md_path.read_text()

    # Backup
    backup_path = claude_md_path.with_suffix(".md.backup")
    backup_path.write_text(existing)

    if POCKETTEAM_START in existing and POCKETTEAM_END in existing:
        # Replace existing section
        start_idx = existing.index(POCKETTEAM_START)
        end_idx = existing.index(POCKETTEAM_END) + len(POCKETTEAM_END)
        new_content = existing[:start_idx] + pocketteam_section + existing[end_idx:]
    else:
        # Append section
        new_content = existing.rstrip() + "\n\n" + pocketteam_section

    claude_md_path.write_text(new_content)


def _get_pocketteam_claude_md_section(cfg: PocketTeamConfig) -> str:
    return f"""{POCKETTEAM_START}
# PocketTeam - Autonomous AI IT Team

You are the **COO** of {cfg.project_name}. PocketTeam is active.

## Your Role
- You are the orchestrator. You NEVER implement code yourself.
- You delegate ALL work to specialized agents using Claude Code's built-in Agent tool.
- You coordinate the pipeline, enforce human gates, and keep the CEO informed.

## How to Delegate (CRITICAL — use the Agent tool)

Use Claude Code's built-in **Agent tool** to spawn specialized agents.
Each agent is defined in `.claude/agents/pocketteam/` with its own prompt, model, and tool permissions.

| When you need to... | Use this agent |
|---|---|
| Validate demand for a new feature | **product** agent |
| Create an implementation plan | **planner** agent |
| Review a plan or code | **reviewer** agent |
| Implement code from an approved plan | **engineer** agent |
| Run tests and verify quality | **qa** agent |
| Audit security (OWASP, CVEs) | **security** agent |
| Deploy to staging or production | **devops** agent |
| Debug a production issue | **investigator** agent |
| Update documentation | **documentation** agent |
| Check production health | **monitor** agent |
| Analyze team performance after a task | **observer** agent |

Example delegation:
> "Use the **planner** agent to create an implementation plan for: [task description]"

## Pipeline (ALWAYS follow this order)

### For NEW features:
1. (Optional) Use **product** agent → validate demand
1.5 (Optional) Use **discuss** skill → clarify gray areas before planning
2. Use **planner** agent → create detailed plan, ask ALL questions upfront
3. Use **reviewer** agent → review plan (up to 3 iterations)
4. **HUMAN GATE**: Ask CEO to approve the plan before any code is written
5. Use **engineer** agent → implement on feature branch
5.5 Use **/simplify** → review changed code for complexity and quality (autopilot only)
   - Note: /simplify is provided by the installed code-simplifier plugin, not a PocketTeam skill
6. Use **reviewer** agent → code review (two-stage: spec compliance + code quality)
7. Use **qa** agent → run all tests
8. Use **security** agent → OWASP audit + dependency scan
9. Use **documentation** agent → update docs
10. **HUMAN GATE**: Ask CEO to approve production deploy
11. Use **devops** agent → deploy staging first, then production
12. Use **monitor** agent → watch for 15 min post-deploy
13. Use **observer** agent → analyze task, cost report, update learnings

### For BUGS / urgent fixes:
1. Use **investigator** agent → root cause analysis
2. Use **engineer** agent → minimal fix
3. Use **qa** agent → test the fix
4. **HUMAN GATE**: CEO approves deploy
5. Use **devops** agent → staging first, then production

## Workflow Modes (Magic Keywords)

The CEO can activate special modes by starting their message with a keyword:

| Keyword | Mode | What happens |
|---|---|---|
| `autopilot: <task>` | Full autonomous pipeline | Plan → Review → Implement → Test → Review → Security → Docs. No stops unless failure. |
| `ralph: <task>` | Persistent until done | Implement → Test → Fix loop. Keeps going until ALL tests pass (max 5 iterations). |
| `quick: <task>` | Speed mode | Skip planning/review, implement directly, quick test. |
| `deep-dive: <topic>` | Research mode | Spawn 3 parallel Explore agents for thorough research. |

These keywords are detected by a UserPromptSubmit hook and inject workflow instructions automatically.

## Human Gate Protocol

At human gates, present a clear summary and ask for approval:
- "Plan ready: [N] files to change. Risks: [list]. Approve? (y/n)"
- "Tests passed. Security clean. Deploy to production? (y/n)"

If CEO says no → ask what to change. Never proceed without approval.
**Exception:** autopilot and ralph modes skip human gates (CEO pre-approved by using the keyword).

## Safety Rules (ABSOLUTE — enforced by hooks, not prompts)
- Safety hooks in `.claude/settings.json` run on EVERY tool call automatically
- You cannot bypass them — they are runtime hooks, not conversation instructions
- Never write to .env, .ssh, .aws, *.pem, *.key files
- Never run: rm -rf /, DROP DATABASE, TRUNCATE, fork bombs
- Always staging-first for production fixes

## Communication Style
- Keep CEO informed concisely
- Batch all questions before starting work (never ask one at a time)
- Status format: "📋 Plan ready" | "🔨 Working on X" | "✅ Done" | "⚠️ Problem"
- If blocked after 3 attempts → escalate to CEO immediately

## Artifact Locations
- Plans: `.pocketteam/artifacts/plans/`
- Reviews: `.pocketteam/artifacts/reviews/`
- Audit logs: `.pocketteam/artifacts/audit/`
- Agent learnings: `.pocketteam/learnings/`
- Event stream: `.pocketteam/events/stream.jsonl`
{POCKETTEAM_END}
"""


def _setup_settings_json(project_root: Path, is_new: bool) -> None:
    """Merge PocketTeam safety hooks into .claude/settings.json."""
    settings_path = project_root / CLAUDE_DIR / "settings.json"

    # Use sys.executable so hooks work with pipx/venv installations on any OS
    _py = sys.executable
    hook_prefix = f"{_py} -m pocketteam.safety"
    hooks_prefix = f"{_py} -m pocketteam.hooks"

    pocketteam_hooks = {
        "PreToolUse": [
            {
                "matcher": "Bash|Write|Edit|Read|Glob|Grep|mcp__.*",
                "hooks": [
                    {
                        "type": "command",
                        "command": f"{hook_prefix} pre",
                    }
                ],
            },
            {
                "matcher": "Agent",
                "hooks": [
                    {
                        "type": "command",
                        "command": f"{hooks_prefix} delegation",
                    }
                ],
            },
        ],
        "PostToolUse": [
            {
                "matcher": "Bash|Write|Edit",
                "hooks": [
                    {
                        "type": "command",
                        "command": f"{hook_prefix} post",
                    }
                ],
            },
            {
                "matcher": "Agent|Task",
                "hooks": [
                    {
                        "type": "command",
                        "command": f"{hooks_prefix} context_warning",
                    }
                ],
            },
        ],
        "UserPromptSubmit": [
            {
                "matcher": "",
                "hooks": [
                    {
                        "type": "command",
                        "command": f"{hooks_prefix} keyword",
                    },
                    {
                        "type": "command",
                        "command": f"{hooks_prefix} telegram_save",
                    },
                ],
            }
        ],
        "SessionStart": [
            {
                "matcher": "",
                "hooks": [
                    {
                        "type": "command",
                        "command": f"{hooks_prefix} session_start",
                    }
                ],
            }
        ],
        "PreCompact": [
            {
                "matcher": "",
                "hooks": [
                    {
                        "type": "command",
                        "command": f"{hooks_prefix} pre_compact",
                    }
                ],
            }
        ],
        "SubagentStart": [
            {
                "matcher": "",
                "hooks": [
                    {
                        "type": "command",
                        "command": f"{hooks_prefix} agent_start",
                    }
                ],
            }
        ],
        "SubagentStop": [
            {
                "matcher": "",
                "hooks": [
                    {
                        "type": "command",
                        "command": f"{hooks_prefix} agent_stop",
                    },
                    {
                        "type": "command",
                        "command": f"{hooks_prefix} observer_analyze",
                    },
                ],
            }
        ],
        "Stop": [
            {
                "matcher": "",
                "hooks": [
                    {
                        "type": "command",
                        "command": f"{hooks_prefix} session_stop",
                    }
                ],
            }
        ],
    }

    if not settings_path.exists() or is_new:
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(json.dumps({
            "agent": "pocketteam/coo",
            "hooks": pocketteam_hooks,
        }, indent=2))
        return

    # Merge: add our hooks without removing existing ones
    try:
        existing = json.loads(settings_path.read_text())
    except (json.JSONDecodeError, OSError):
        existing = {}

    # Backup
    backup_path = settings_path.with_suffix(".json.backup")
    backup_path.write_text(settings_path.read_text())

    existing_hooks = existing.get("hooks", {})

    for event_type, hook_list in pocketteam_hooks.items():
        if event_type not in existing_hooks:
            existing_hooks[event_type] = hook_list
        else:
            # Replace existing hooks with matching matchers (updates stale commands)
            existing_matchers = {
                h.get("matcher"): i for i, h in enumerate(existing_hooks[event_type])
            }
            for hook in hook_list:
                matcher = hook.get("matcher")
                if matcher in existing_matchers:
                    # Update in place — fixes stale python/PYTHONPATH commands
                    existing_hooks[event_type][existing_matchers[matcher]] = hook
                else:
                    existing_hooks[event_type].append(hook)

    existing["agent"] = "pocketteam/coo"
    existing["hooks"] = existing_hooks
    settings_path.write_text(json.dumps(existing, indent=2))


def _copy_skills(skills_source: Path, skills_target: Path, console: Console) -> None:
    """Copy package skills to project, respecting MANIFEST.json.

    Only skills listed in MANIFEST.json are written (or overwritten).
    User-created skills not in the manifest are left untouched.
    If MANIFEST.json is missing or corrupt, no skills are overwritten.
    """
    manifest_path = skills_source / "MANIFEST.json"
    try:
        manifest = json.loads(manifest_path.read_text())
        package_skills = set(manifest.get("package_skills", []))
    except FileNotFoundError:
        console.print("  [yellow]Warning: skills/MANIFEST.json not found — skipping skills install[/]")
        return
    except json.JSONDecodeError as e:
        console.print(f"  [yellow]Warning: skills/MANIFEST.json is corrupt: {e} — skipping skills install[/]")
        return

    if not package_skills:
        return

    skills_target.mkdir(parents=True, exist_ok=True)
    copied = 0
    for md_file in skills_source.glob("*.md"):
        skill_name = md_file.stem
        if skill_name in package_skills:
            shutil.copy2(md_file, skills_target / md_file.name)
            copied += 1

    if copied:
        console.print(f"  [green]✅ {copied} skills installed[/]")


def _setup_agent_definitions(project_root: Path) -> None:
    """Copy agent .md definitions and skills to .claude/ directories."""
    # Agent prompts → .claude/agents/pocketteam/
    templates_dir = Path(__file__).parent / "agents" / "prompts"
    target_dir = project_root / AGENTS_DIR

    if templates_dir.exists():
        target_dir.mkdir(parents=True, exist_ok=True)
        for md_file in templates_dir.glob("*.md"):
            target = target_dir / md_file.name
            # Always overwrite — agent prompts may have been updated
            shutil.copy2(md_file, target)

    # Skills → .claude/skills/pocketteam/
    skills_dir = Path(__file__).parent / "skills"
    skills_target = project_root / SKILLS_DIR

    if skills_dir.exists():
        _copy_skills(skills_dir, skills_target, console)


def _setup_telegram_plugin(bot_token: str) -> bool:
    """Install the official Telegram channel plugin.

    The plugin handles both sending and receiving via --channels flag.
    """
    try:
        if not shutil.which("claude"):
            return False

        # Write bot token to channel config location
        channel_dir = Path.home() / ".claude" / "channels" / "telegram"
        channel_dir.mkdir(parents=True, exist_ok=True)
        env_path = channel_dir / ".env"
        env_path.write_text(f"TELEGRAM_BOT_TOKEN={bot_token}\n")
        os.chmod(env_path, 0o600)

        # Remove old MCP proxy if exists (replaced by channel plugin)
        subprocess.run(
            ["claude", "mcp", "remove", "telegram-proxy", "--scope", "user"],
            capture_output=True, timeout=15,
        )

        # Install official Telegram channel plugin
        result = subprocess.run(
            ["claude", "plugin", "install", "telegram@claude-plugins-official"],
            capture_output=True, text=True, timeout=60,
        )
        combined = (result.stdout + result.stderr).lower()
        if result.returncode == 0 or "already installed" in combined:
            console.print("  [green]✓[/] Telegram channel plugin installed")
            return True
        return False

    except Exception:
        return False


def _setup_mcp_servers(config: PocketTeamConfig, console: Console) -> None:  # noqa: ARG001
    """Install recommended MCP servers (Tier 1 automatic, Tier 2 optional)."""
    try:
        console.print("\n[bold]MCP Server Setup[/bold]")

        # ── Tier 1: Context7 (no API key required) ──────────────────────────
        console.print("  Installing Context7 (library docs)...")
        try:
            result = subprocess.run(
                [
                    "claude", "mcp", "add", "--scope", "project",
                    "context7", "--", "npx", "-y", "@upstash/context7-mcp",
                ],
                capture_output=True, text=True, timeout=60,
            )
            if result.returncode == 0:
                console.print("  [green]Context7 installed[/]")
            else:
                console.print(
                    "  [yellow]Context7 installation failed "
                    "(install manually: claude mcp add context7 -- npx -y @upstash/context7-mcp)[/]"
                )
        except Exception as e:
            console.print(f"  [yellow]Context7 skipped: {e}[/]")

        # ── Tier 2: Tavily (needs API key) ──────────────────────────────────
        console.print("\n  [bold]Optional: Tavily Web Search[/bold]")
        console.print("  Free tier: 1000 searches/month at https://tavily.com")
        try:
            tavily_key = Prompt.ask("  Tavily API Key (Enter to skip)", default="")
        except (EOFError, KeyboardInterrupt):
            tavily_key = ""
        if tavily_key:
            try:
                result = subprocess.run(
                    [
                        "claude", "mcp", "add", "--scope", "local",
                        "-e", f"TAVILY_API_KEY={tavily_key}",
                        "tavily-mcp", "--", "npx", "-y", "tavily-mcp",
                    ],
                    capture_output=True, text=True, timeout=60,
                )
                if result.returncode == 0:
                    console.print("  [green]Tavily installed[/]")
                else:
                    console.print("  [yellow]Tavily installation failed[/]")
            except Exception as e:
                console.print(f"  [yellow]Tavily skipped: {e}[/]")
        else:
            console.print(
                "  [dim]Skipped. Add later: claude mcp add tavily-mcp -- npx -y tavily-mcp[/]"
            )

        # ── Tier 2: Supabase (needs access token + project ref) ─────────────
        console.print("\n  [bold]Optional: Supabase Database[/bold]")
        console.print("  Free tier at https://supabase.com")
        try:
            supabase_token = Prompt.ask("  Supabase Access Token (Enter to skip)", default="")
        except (EOFError, KeyboardInterrupt):
            supabase_token = ""
        if supabase_token:
            try:
                supabase_ref = Prompt.ask("  Supabase Project Ref")
            except (EOFError, KeyboardInterrupt):
                supabase_ref = ""
            if supabase_ref:
                try:
                    result = subprocess.run(
                        [
                            "claude", "mcp", "add", "--scope", "local",
                            "-e", f"SUPABASE_ACCESS_TOKEN={supabase_token}",
                            "supabase", "--", "npx", "-y",
                            "@supabase/mcp-server-supabase@latest",
                            f"--project-ref={supabase_ref}",
                        ],
                        capture_output=True, text=True, timeout=60,
                    )
                    if result.returncode == 0:
                        console.print("  [green]Supabase installed[/]")
                    else:
                        console.print("  [yellow]Supabase installation failed[/]")
                except Exception as e:
                    console.print(f"  [yellow]Supabase skipped: {e}[/]")
            else:
                console.print("  [dim]Supabase ref not provided — skipped.[/]")
        else:
            console.print(
                "  [dim]Skipped. Add later: "
                "claude mcp add supabase -- npx -y @supabase/mcp-server-supabase@latest[/]"
            )
    except Exception as e:
        # MCP setup must never abort the init process
        console.print(f"  [yellow]MCP setup skipped unexpectedly: {e}[/]")


def _create_start_script(project_root: Path, cfg: PocketTeamConfig) -> None:
    """Create a start script that launches Claude Code with Telegram channel."""
    # The token is needed for the channel plugin
    bot_token = cfg.telegram.bot_token

    # Store token in .pocketteam/telegram.env (gitignored)
    env_path = project_root / ".pocketteam/telegram.env"
    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text(f"TELEGRAM_BOT_TOKEN={bot_token}\n")


def _create_github_actions(project_root: Path, cfg: PocketTeamConfig) -> None:
    """Create .github/workflows/pocketteam-monitor.yml."""
    if not cfg.github.enabled or not cfg.github.actions_enabled:
        return

    workflow_path = project_root / ".github/workflows/pocketteam-monitor.yml"
    if cfg.health_url:
        health_url = cfg.health_url
    else:
        health_url = "https://your-app.com/health"
        console.print(
            "  [yellow]⚠[/] GitHub Actions: no health_url configured — "
            "edit pocketteam-monitor.yml and replace the placeholder URL."
        )
    schedule = cfg.github.schedule

    workflow = f"""name: PocketTeam Monitor

on:
  schedule:
    - cron: '{schedule}'
  workflow_dispatch:  # Allow manual trigger

jobs:
  health-check:
    runs-on: ubuntu-latest
    timeout-minutes: 10

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Health Check
        id: health
        run: |
          HTTP_STATUS=$(curl -s -o /dev/null -w "%{{http_code}}" --max-time 10 "{health_url}" || echo "000")
          echo "status=$HTTP_STATUS" >> $GITHUB_OUTPUT
          if [ "$HTTP_STATUS" != "200" ]; then
            echo "HEALTH_FAILED=true" >> $GITHUB_ENV
          fi

      - name: Check Recent Logs
        id: logs
        if: always()
        run: |
          # Check for error patterns in the last hour of logs
          # Customize this for your logging setup
          echo "Log check placeholder - customize for your stack"

      - name: Set up Python
        if: env.HEALTH_FAILED == 'true'
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Wake PocketTeam Agent (on failure)
        if: env.HEALTH_FAILED == 'true'
        env:
          ANTHROPIC_API_KEY: ${{{{ secrets.ANTHROPIC_API_KEY }}}}
          TELEGRAM_BOT_TOKEN: ${{{{ secrets.TELEGRAM_BOT_TOKEN }}}}
          TELEGRAM_CHAT_ID: ${{{{ secrets.TELEGRAM_CHAT_ID }}}}
          GH_PAT: ${{{{ secrets.GH_PAT }}}}
        run: |
          # Install PocketTeam (private repo needs GH_PAT for access)
          if [ -n "$GH_PAT" ]; then
            pip install "pocketteam @ git+https://${{GH_PAT}}@github.com/Farid046/PocketTeam.git" --quiet
          elif [ -f requirements.txt ]; then
            pip install -r requirements.txt --quiet
          else
            pip install pocketteam --quiet
          fi
          python -c "
          import asyncio
          from pocketteam.monitoring.healer import handle_health_failure
          asyncio.run(handle_health_failure(
              health_url='{health_url}',
              http_status='${{{{ steps.health.outputs.status }}}}',
          ))
          "
"""

    workflow_path.write_text(workflow)


def _create_gitignore(project_root: Path) -> None:
    """Create a sensible .gitignore."""
    gitignore = """# Python
__pycache__/
*.py[cod]
*.egg-info/
dist/
.venv/
venv/
.env
.env.*
!.env.example

# PocketTeam - exclude entire directory (sessions, events, credentials)
.pocketteam/

# macOS
.DS_Store

# VS Code
.vscode/
!.vscode/extensions.json

# Node
node_modules/
"""
    (project_root / ".gitignore").write_text(gitignore)


async def run_uninstall(keep_artifacts: bool) -> None:
    """Remove PocketTeam from project without destroying existing config."""
    project_root = Path.cwd()

    console.print("[yellow]Uninstalling PocketTeam...[/]")

    # 1. Remove PocketTeam section from CLAUDE.md
    claude_md = project_root / CLAUDE_DIR / "CLAUDE.md"
    if claude_md.exists():
        content = claude_md.read_text()
        if POCKETTEAM_START in content and POCKETTEAM_END in content:
            start_idx = content.index(POCKETTEAM_START)
            end_idx = content.index(POCKETTEAM_END) + len(POCKETTEAM_END)
            new_content = content[:start_idx].rstrip() + content[end_idx:]
            claude_md.write_text(new_content)
            console.print("  ✅ Removed PocketTeam section from CLAUDE.md")

    # 2. Remove PocketTeam hooks from settings.json
    settings_path = project_root / CLAUDE_DIR / "settings.json"
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text())
            hooks = settings.get("hooks", {})
            for event_type in list(hooks.keys()):
                hooks[event_type] = [
                    h for h in hooks[event_type]
                    if "pocketteam" not in str(h)
                ]
                if not hooks[event_type]:
                    del hooks[event_type]
            settings["hooks"] = hooks
            settings_path.write_text(json.dumps(settings, indent=2))
            console.print("  ✅ Removed PocketTeam hooks from settings.json")
        except Exception:
            pass

    # 3. Remove agent definitions
    agents_dir = project_root / AGENTS_DIR
    if agents_dir.exists():
        shutil.rmtree(agents_dir)
        console.print("  ✅ Removed .claude/agents/pocketteam/")

    # 4. Remove skills
    skills_dir = project_root / SKILLS_DIR
    if skills_dir.exists():
        shutil.rmtree(skills_dir)
        console.print("  ✅ Removed .claude/skills/pocketteam/")

    # 5. Remove GitHub Actions workflow
    workflow = project_root / ".github/workflows/pocketteam-monitor.yml"
    if workflow.exists():
        workflow.unlink()
        console.print("  ✅ Removed GitHub Actions workflow")

    # 6. Stop and remove dashboard container (must happen BEFORE .pocketteam/ is deleted)
    try:
        from .config import load_config
        cfg = load_config(project_root)
        if cfg.dashboard.enabled and cfg.dashboard.container_name:
            remove_dashboard = Confirm.ask(
                "Stop and remove dashboard container?", default=True
            )
            if remove_dashboard:
                cname = cfg.dashboard.container_name
                stopped = False
                if cfg.dashboard.compose_dir:
                    compose_dir_path = Path(cfg.dashboard.compose_dir)
                    for compose_file in compose_dir_path.rglob("docker-compose.yml"):
                        try:
                            subprocess.run(
                                ["docker", "compose", "-f", str(compose_file), "down"],
                                capture_output=True,
                                timeout=30,
                                check=False,
                            )
                            stopped = True
                        except Exception as exc:  # noqa: BLE001
                            console.print(
                                f"  [yellow]Warning: could not run compose down for {compose_file}: {exc}[/]"
                            )
                if stopped:
                    console.print(f"  ✅ Dashboard container stopped: {cname}")
                    if cfg.dashboard.compose_dir:
                        compose_dir_path = Path(cfg.dashboard.compose_dir)
                        if compose_dir_path.exists():
                            shutil.rmtree(compose_dir_path)
                            console.print(f"  ✅ Removed compose directory: {compose_dir_path}")
    except Exception as exc:  # noqa: BLE001
        console.print(f"  [yellow]Warning: could not stop dashboard container: {exc}[/]")

    # 7. Remove .pocketteam/ (optionally keep artifacts)
    pt_dir = project_root / POCKETTEAM_DIR
    if pt_dir.exists():
        if keep_artifacts:
            console.print("  [dim]Keeping .pocketteam/ artifacts (--keep-artifacts)[/]")
        else:
            confirmed = Confirm.ask(
                f"Delete [bold]{pt_dir}[/] (contains plans, audits, learnings)?",
                default=False,
            )
            if confirmed:
                shutil.rmtree(pt_dir)
                console.print("  ✅ Removed .pocketteam/")

    # Remove Telegram auto-session daemon if installed
    try:
        from .telegram_daemon_plist import uninstall_plist
        if uninstall_plist():
            console.print("  Removed Telegram auto-session daemon")
    except Exception:
        pass

    console.print("\n✅ [green]PocketTeam uninstalled.[/] Your project files are untouched.")
