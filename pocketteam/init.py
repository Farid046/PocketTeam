"""
PocketTeam Init
Handles both new project creation and integration into existing projects.
Uses merge-not-overwrite strategy to avoid destroying existing .claude/ configs.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from .config import PocketTeamConfig, TelegramConfig, AuthConfig, save_config
from .constants import (
    AGENTS_DIR, AUDIT_DIR, CLAUDE_DIR, CONFIG_FILE, EVENTS_FILE,
    INCIDENTS_DIR, LEARNINGS_DIR, PLANS_DIR, POCKETTEAM_DIR,
    REVIEWS_DIR, SESSIONS_DIR, SKILLS_DIR,
)

console = Console()

# Markers for CLAUDE.md merge — these must never change
POCKETTEAM_START = "<!-- POCKETTEAM START -->"
POCKETTEAM_END = "<!-- POCKETTEAM END -->"


async def run_init(project_name: str | None, accept_defaults: bool) -> None:
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

    # Create .env.example
    _create_env_example(project_root)

    console.print(Panel(
        "✅ [bold green]PocketTeam initialized![/]\n\n"
        "Next steps:\n"
        "  1. Set environment variables (see [bold].env.example[/])\n"
        "  2. Open project in VS Code: [bold]code .[/]\n"
        "  3. Claude Code will now behave as your COO\n"
        "  4. Or send a task via Telegram to your bot\n\n"
        "[dim]Safety layers: active | Kill switch: pocketteam kill[/]",
        border_style="green",
    ))


async def _interview(
    project_root: Path,
    project_name: str | None,
    accept_defaults: bool,
) -> PocketTeamConfig:
    """Interactive setup interview."""
    cfg = PocketTeamConfig(project_root=project_root)
    cfg.project_name = project_name or project_root.name

    if not accept_defaults:
        cfg.project_name = Prompt.ask(
            "Project name",
            default=cfg.project_name,
        )

    console.print("\n[bold]Authentication[/]")
    if not accept_defaults:
        auth_choice = Prompt.ask(
            "Auth mode",
            choices=["subscription", "api_key", "hybrid"],
            default="subscription",
        )
        cfg.auth = AuthConfig(mode=auth_choice)
    else:
        cfg.auth = AuthConfig(mode="subscription")

    console.print("\n[bold]Health Monitoring[/]")
    if not accept_defaults:
        health_url = Prompt.ask(
            "Production health URL (e.g. https://myapp.com/health)",
            default="",
        )
        cfg.health_url = health_url
        cfg.monitoring.health_url = health_url

    console.print("\n[bold]Telegram Bot[/]")
    if not accept_defaults:
        setup_telegram = Confirm.ask(
            "Configure Telegram bot for mobile access?",
            default=True,
        )
        if setup_telegram:
            console.print(
                "[dim]Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID as environment variables.[/]"
            )
            cfg.telegram = TelegramConfig(
                bot_token="${TELEGRAM_BOT_TOKEN}",
                chat_id="${TELEGRAM_CHAT_ID}",
            )

    console.print("\n[bold]GitHub Actions Monitoring[/]")
    if not accept_defaults:
        setup_gha = Confirm.ask(
            "Enable GitHub Actions for 24/7 production monitoring?",
            default=True,
        )
        cfg.github_actions.enabled = setup_gha

    return cfg


def _create_directories(project_root: Path) -> None:
    """Create all required PocketTeam directories."""
    dirs = [
        POCKETTEAM_DIR,
        PLANS_DIR,
        REVIEWS_DIR,
        AUDIT_DIR,
        INCIDENTS_DIR,
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
- Orchestrate the team of specialized agents
- Delegate tasks to the right agents (never do implementation yourself)
- Ensure all work follows the PocketTeam pipeline
- Communicate status to the CEO (human) via Telegram or Claude Code

## Agent Pipeline (ALWAYS follow this order)
1. **Product Advisor** → Validate demand (optional, for new features)
2. **Planner** → Create detailed plan, ask ALL questions upfront
3. **Reviewer** → Review plan for completeness, risks, architecture
4. ⛔ **HUMAN GATE**: CEO approves plan before any code is written
5. **Engineer** → Implement (feature branch, never touch main directly)
6. **Reviewer** → Code review
7. **QA** → All tests must pass
8. **Security** → OWASP audit before deploy
9. **Documentation** → Update docs
10. ⛔ **HUMAN GATE**: CEO approves production deploy
11. **DevOps** → Deploy to staging first, then production
12. **Monitor** → Watch for 15 min post-deploy

## Safety Rules (ABSOLUTE - never override)
- Safety hooks run on EVERY tool call - you cannot bypass them
- Destructive operations require D-SAC approval flow
- Kill switch in .pocketteam/KILL stops everything immediately
- Never write to .env, .ssh, .aws, *.pem, *.key files
- Never run: rm -rf /, DROP DATABASE, TRUNCATE, fork bombs, disk format
- Always staging-first for production fixes

## Communication
- Keep CEO informed with brief status updates
- Batch all questions before starting work
- Telegram updates: 📋 Plan ready | 🔨 Working | ✅ Done | ⚠️ Problem
- If blocked after 3 attempts → escalate to CEO

## Artifact Locations
- Plans: .pocketteam/artifacts/plans/
- Reviews: .pocketteam/artifacts/reviews/
- Audit logs: .pocketteam/artifacts/audit/
- Event stream: .pocketteam/events/stream.jsonl
{POCKETTEAM_END}
"""


def _setup_settings_json(project_root: Path, is_new: bool) -> None:
    """Merge PocketTeam safety hooks into .claude/settings.json."""
    settings_path = project_root / CLAUDE_DIR / "settings.json"

    pocketteam_hooks = {
        "PreToolUse": [
            {
                "matcher": "Bash|Write|Edit|mcp__.*",
                "hooks": [
                    {
                        "type": "command",
                        "command": "python .claude/skills/pocketteam/safety/guardian.py pre",
                    }
                ],
            }
        ],
        "PostToolUse": [
            {
                "matcher": ".*",
                "hooks": [
                    {
                        "type": "command",
                        "command": "python .claude/skills/pocketteam/safety/activity_logger.py",
                    }
                ],
            }
        ],
    }

    if not settings_path.exists() or is_new:
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(json.dumps({"hooks": pocketteam_hooks}, indent=2))
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
            # Append our hooks if not already present
            existing_matchers = {
                h.get("matcher") for h in existing_hooks[event_type]
            }
            for hook in hook_list:
                if hook.get("matcher") not in existing_matchers:
                    existing_hooks[event_type].append(hook)

    existing["hooks"] = existing_hooks
    settings_path.write_text(json.dumps(existing, indent=2))


def _setup_agent_definitions(project_root: Path) -> None:
    """Copy agent .md definitions to .claude/agents/pocketteam/."""
    # Agent definitions are templates in the package
    templates_dir = Path(__file__).parent / "agents" / "prompts"
    target_dir = project_root / AGENTS_DIR

    if not templates_dir.exists():
        return  # Will be populated in Phase 5

    for md_file in templates_dir.glob("*.md"):
        target = target_dir / md_file.name
        if not target.exists():
            shutil.copy2(md_file, target)


def _create_github_actions(project_root: Path, cfg: PocketTeamConfig) -> None:
    """Create .github/workflows/pocketteam-monitor.yml."""
    if not cfg.github_actions.enabled:
        return

    workflow_path = project_root / ".github/workflows/pocketteam-monitor.yml"
    health_url = cfg.health_url or "https://your-app.com/health"
    schedule = cfg.github_actions.schedule

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

      - name: Wake PocketTeam Agent (on failure)
        if: env.HEALTH_FAILED == 'true'
        env:
          ANTHROPIC_API_KEY: ${{{{ secrets.ANTHROPIC_API_KEY }}}}
          TELEGRAM_BOT_TOKEN: ${{{{ secrets.TELEGRAM_BOT_TOKEN }}}}
          TELEGRAM_CHAT_ID: ${{{{ secrets.TELEGRAM_CHAT_ID }}}}
        run: |
          pip install pocketteam --quiet
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

# PocketTeam - sensitive artifacts (keep plans/reviews in git)
.pocketteam/sessions/
.pocketteam/events/
.pocketteam/KILL

# macOS
.DS_Store

# VS Code
.vscode/
!.vscode/extensions.json

# Node
node_modules/
"""
    (project_root / ".gitignore").write_text(gitignore)


def _create_env_example(project_root: Path) -> None:
    """Create .env.example with required variables."""
    env_example = """# PocketTeam Environment Variables
# Copy to .env and fill in your values (never commit .env!)

# Claude API (only needed for GitHub Actions / headless mode)
# Interactive use via Claude Code Subscription does NOT need this
ANTHROPIC_API_KEY=sk-ant-...

# Telegram Bot (get from @BotFather)
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...   # Your personal chat ID (from @userinfobot)
"""
    env_example_path = project_root / ".env.example"
    if not env_example_path.exists():
        env_example_path.write_text(env_example)


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

    # 6. Remove .pocketteam/ (optionally keep artifacts)
    pt_dir = project_root / POCKETTEAM_DIR
    if pt_dir.exists():
        if keep_artifacts:
            console.print(f"  [dim]Keeping .pocketteam/ artifacts (--keep-artifacts)[/]")
        else:
            confirmed = Confirm.ask(
                f"Delete [bold]{pt_dir}[/] (contains plans, audits, learnings)?",
                default=False,
            )
            if confirmed:
                shutil.rmtree(pt_dir)
                console.print("  ✅ Removed .pocketteam/")

    console.print("\n✅ [green]PocketTeam uninstalled.[/] Your project files are untouched.")
