"""
GitHub Setup — automated repo creation, secrets, and workflow push via gh CLI.

Called during `pocketteam init` Step 5 when user enables GitHub integration.
Requires `gh` CLI installed and authenticated.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from rich.console import Console
from rich.prompt import Confirm, Prompt

from .config import GitHubConfig, PocketTeamConfig

console = Console()


class GitHubSetupError(Exception):
    pass


def check_gh_installed() -> bool:
    """Check if the gh CLI is available."""
    return shutil.which("gh") is not None


def check_gh_authenticated() -> bool:
    """Check if the user is logged in to GitHub."""
    result = subprocess.run(
        ["gh", "auth", "status"],
        capture_output=True, text=True, timeout=10,
    )
    return result.returncode == 0


def get_gh_username() -> str:
    """Get the authenticated GitHub username."""
    result = subprocess.run(
        ["gh", "api", "user", "--jq", ".login"],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode != 0:
        raise GitHubSetupError(f"Failed to get GitHub username: {result.stderr.strip()}")
    return result.stdout.strip()


def gh_auth_login() -> bool:
    """Run `gh auth login` interactively. Returns True on success."""
    console.print("  [yellow]Opening GitHub login...[/]")
    result = subprocess.run(
        ["gh", "auth", "login", "--web"],
        timeout=120,
    )
    return result.returncode == 0


def repo_exists(owner: str, name: str) -> bool:
    """Check if a GitHub repo already exists."""
    result = subprocess.run(
        ["gh", "repo", "view", f"{owner}/{name}", "--json", "name"],
        capture_output=True, text=True, timeout=10,
    )
    return result.returncode == 0


def _has_remote(name: str = "origin", cwd: Path | None = None) -> bool:
    """Check if a git remote exists."""
    result = subprocess.run(
        ["git", "remote", "get-url", name],
        capture_output=True, text=True, cwd=cwd,
    )
    return result.returncode == 0


def create_repo(name: str, private: bool = True, cwd: Path | None = None) -> str:
    """
    Create a GitHub repo via gh CLI.
    Handles existing 'origin' remote gracefully.
    Returns the full repo name (owner/name).
    """
    visibility = "--private" if private else "--public"
    owner = get_gh_username()
    full_repo = f"{owner}/{name}"
    repo_url = f"https://github.com/{full_repo}.git"

    if _has_remote("origin", cwd=cwd):
        # Origin already exists — create repo without --source, then update remote
        result = subprocess.run(
            ["gh", "repo", "create", name, visibility],
            capture_output=True, text=True, timeout=60, cwd=cwd,
        )
        if result.returncode != 0:
            raise GitHubSetupError(f"Failed to create repo: {result.stderr.strip()}")

        # Update existing remote to point to new repo
        subprocess.run(
            ["git", "remote", "set-url", "origin", repo_url],
            capture_output=True, cwd=cwd,
        )
    else:
        # No origin — use --source=. for full setup
        # Before --push, check if commits exist
        has_commits = subprocess.run(
            ["git", "log", "--oneline", "-1"],
            capture_output=True, cwd=cwd,
        ).returncode == 0

        flags = [visibility, "--source=."]
        if has_commits:
            flags.append("--push")

        result = subprocess.run(
            ["gh", "repo", "create", name] + flags,
            capture_output=True, text=True, timeout=60, cwd=cwd,
        )
        if result.returncode != 0:
            raise GitHubSetupError(f"Failed to create repo: {result.stderr.strip()}")

        if not has_commits:
            console.print("  [dim]Repo created on GitHub. Push after your first commit: git push -u origin main[/]")

    return full_repo


def set_repo_secret(repo: str, name: str, value: str) -> bool:
    """Set a GitHub Actions secret on the repo."""
    if not value:
        return False

    result = subprocess.run(
        ["gh", "secret", "set", name, "--repo", repo, "--body", value],
        capture_output=True, text=True, timeout=15,
    )
    return result.returncode == 0


def set_repo_secrets(repo: str, cfg: PocketTeamConfig) -> dict[str, bool]:
    """Set all required GitHub Actions secrets."""
    import os
    secrets = {}

    # ANTHROPIC_API_KEY
    api_key = cfg.auth.api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    if api_key:
        secrets["ANTHROPIC_API_KEY"] = set_repo_secret(repo, "ANTHROPIC_API_KEY", api_key)

    # Telegram secrets (optional)
    if cfg.telegram.bot_token and not cfg.telegram.bot_token.startswith("$"):
        secrets["TELEGRAM_BOT_TOKEN"] = set_repo_secret(
            repo, "TELEGRAM_BOT_TOKEN", cfg.telegram.bot_token
        )
    if cfg.telegram.chat_id:
        secrets["TELEGRAM_CHAT_ID"] = set_repo_secret(
            repo, "TELEGRAM_CHAT_ID", cfg.telegram.chat_id
        )

    return secrets


def push_workflow(project_root: Path) -> bool:
    """Commit and push the GitHub Actions workflow.

    Uses -f to override .gitignore — the workflow MUST be committed
    for GitHub Actions to work, even if .gitignore excludes it.
    """
    workflow_path = project_root / ".github" / "workflows" / "pocketteam-monitor.yml"
    if not workflow_path.exists():
        return False

    # Stage with -f to override .gitignore (workflow must be in repo for Actions)
    subprocess.run(
        ["git", "add", "-f", str(workflow_path)], cwd=project_root, check=False
    )
    result = subprocess.run(
        ["git", "commit", "-m", "ci: add PocketTeam monitoring workflow"],
        capture_output=True, text=True, cwd=project_root,
    )
    if result.returncode != 0 and "nothing to commit" not in result.stdout:
        return False

    push_result = subprocess.run(
        ["git", "push", "-u", "origin", "HEAD"],
        capture_output=True, text=True, cwd=project_root, timeout=30,
    )
    return push_result.returncode == 0


def trigger_workflow(repo: str, workflow: str = "pocketteam-monitor.yml") -> bool:
    """Trigger a manual workflow run."""
    result = subprocess.run(
        ["gh", "workflow", "run", workflow, "--repo", repo],
        capture_output=True, text=True, timeout=15,
    )
    return result.returncode == 0


def run_github_setup(
    project_root: Path,
    cfg: PocketTeamConfig,
    accept_defaults: bool = False,
) -> GitHubConfig:
    """
    Full GitHub setup flow for pocketteam init.

    1. Check/install gh CLI
    2. Authenticate if needed
    3. Create repo from project name
    4. Set secrets
    5. Push workflow
    6. Trigger first run

    Returns updated GitHubConfig.
    """
    gh_cfg = cfg.github

    # Step 1: Check gh CLI
    if not check_gh_installed():
        console.print("  [yellow]⚠ gh CLI not found.[/]")
        console.print("    Install: [bold]brew install gh[/] or https://cli.github.com")
        gh_cfg.enabled = False
        return gh_cfg

    # Step 2: Check authentication
    if not check_gh_authenticated():
        console.print("  [dim]GitHub CLI not authenticated.[/]")
        if accept_defaults:
            console.print("  [yellow]Skipping GitHub (--yes mode, no auth)[/]")
            gh_cfg.enabled = False
            return gh_cfg

        do_login = Confirm.ask("  Log in to GitHub now?", default=True)
        if not do_login or not gh_auth_login():
            console.print("  [yellow]GitHub setup skipped.[/]")
            gh_cfg.enabled = False
            return gh_cfg

    # Get username for repo owner
    try:
        owner = get_gh_username()
        gh_cfg.repo_owner = owner
        console.print(f"  [green]✓[/] Authenticated as [bold]{owner}[/]")
    except GitHubSetupError as e:
        console.print(f"  [red]✗[/] {e}")
        gh_cfg.enabled = False
        return gh_cfg

    # Step 3: Repo name (default: project name)
    default_name = cfg.project_name.lower().replace(" ", "-")
    if not accept_defaults:
        repo_name = Prompt.ask(
            "  Repository name",
            default=gh_cfg.repo_name or default_name,
        )
    else:
        repo_name = gh_cfg.repo_name or default_name
    gh_cfg.repo_name = repo_name

    full_repo = f"{owner}/{repo_name}"

    # Check if repo already exists
    if repo_exists(owner, repo_name):
        console.print(f"  [green]✓[/] Repo [bold]{full_repo}[/] already exists")

        # Ensure remote points to this repo
        repo_url = f"https://github.com/{full_repo}.git"
        if _has_remote("origin", cwd=project_root):
            subprocess.run(
                ["git", "remote", "set-url", "origin", repo_url],
                capture_output=True, cwd=project_root,
            )
        else:
            subprocess.run(
                ["git", "remote", "add", "origin", repo_url],
                capture_output=True, cwd=project_root,
            )
    else:
        # Visibility
        if not accept_defaults:
            private = Confirm.ask("  Private repository?", default=True)
        else:
            private = gh_cfg.repo_private
        gh_cfg.repo_private = private

        console.print(f"  Creating [bold]{full_repo}[/] ({'private' if private else 'public'})...")
        try:
            full_repo = create_repo(repo_name, private=private, cwd=project_root)
            console.print(f"  [green]✓[/] Repo created: [bold]{full_repo}[/]")
        except GitHubSetupError as e:
            console.print(f"  [red]✗[/] {e}")
            gh_cfg.enabled = True  # Still enabled, just no repo yet
            return gh_cfg

    # Step 4: Set secrets
    console.print("  Setting GitHub Actions secrets...")
    secrets = set_repo_secrets(full_repo, cfg)
    for name, ok in secrets.items():
        status = "[green]✓[/]" if ok else "[yellow]⚠ skipped[/]"
        console.print(f"    {status} {name}")

    # Step 5: Ensure workflow exists and push
    gh_cfg.actions_enabled = True
    if (project_root / ".github" / "workflows" / "pocketteam-monitor.yml").exists():
        console.print("  Pushing workflow...")
        if push_workflow(project_root):
            console.print("  [green]✓[/] Workflow pushed")
        else:
            console.print("  [dim]Workflow will be pushed on next commit[/]")

    # Step 6: Trigger first run (optional)
    if not accept_defaults:
        console.print()
        console.print(
            "  [dim]This runs the monitoring workflow once on GitHub Actions to verify\n"
            "  that the health check, secrets, and Agent SDK connection work.\n"
            "  It does NOT deploy anything — it just checks your health URL\n"
            "  and wakes PocketTeam if it fails.[/]"
        )
        do_trigger = Confirm.ask(
            "  Run a test monitoring check on GitHub Actions now?", default=False
        )
    else:
        do_trigger = False

    if do_trigger:
        if trigger_workflow(full_repo):
            console.print(
                f"  [green]✓[/] Workflow triggered!\n"
                f"    Check results: [bold]https://github.com/{full_repo}/actions[/]"
            )
        else:
            console.print(
                "  [yellow]⚠[/] Trigger failed — workflow may not be pushed yet.\n"
                f"    Push first, then: [bold]gh workflow run pocketteam-monitor.yml --repo {full_repo}[/]"
            )

    return gh_cfg
