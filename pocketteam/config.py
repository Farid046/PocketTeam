"""
PocketTeam Configuration
Reads/writes .pocketteam/config.yaml for each project.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

import yaml

from .constants import (
    CONFIG_FILE,
    DASHBOARD_IMAGE,
    DASHBOARD_PORT,
    DASHBOARD_VERSION,
    DEFAULT_BUDGET_USD,
    MAX_AUTO_FIX_ATTEMPTS,
    MONITOR_INTERVAL_STEADY,
)


@dataclass
class TelegramConfig:
    bot_token: str = ""
    chat_id: str = ""
    persistent_sessions: bool = True
    auto_resume: bool = True


@dataclass
class MonitoringConfig:
    enabled: bool = True
    auto_fix: bool = True
    staging_first: bool = True
    max_fix_attempts: int = MAX_AUTO_FIX_ATTEMPTS
    interval_steady: int = MONITOR_INTERVAL_STEADY
    health_url: str = ""


@dataclass
class BudgetConfig:
    max_per_task: float = DEFAULT_BUDGET_USD
    prefer_subscription: bool = True
    warn_api_costs: bool = True


@dataclass
class AuthConfig:
    mode: Literal["subscription", "api_key", "hybrid"] = "subscription"
    api_key: str = ""            # Only used in api_key / hybrid mode


@dataclass
class DashboardConfig:
    enabled: bool = False
    port: int = DASHBOARD_PORT
    image: str = DASHBOARD_IMAGE
    image_version: str = DASHBOARD_VERSION
    domain: str = ""
    compose_dir: str = ""
    docker_context: str = "default"
    claude_version_at_init: str = ""
    compose_checksum: str = ""
    project_root: str = ""
    claude_project_hash: str = ""
    compose_command: str = "docker compose"  # "docker compose" (v2) or "docker-compose" (v1)
    container_name: str = "pocketteam-dashboard"  # Derived from project_name at init


@dataclass
class ComputerUseConfig:
    enabled: bool = False
    browser_mcp: bool = False
    native_macos: bool = False


@dataclass
class InsightsConfig:
    """Auto-Insights self-improvement configuration."""
    enabled: bool = False
    schedule: str = "0 22 * * *"
    last_run: Optional[str] = None
    telegram_notify: bool = True
    auto_apply: bool = False


@dataclass
class GitHubConfig:
    """GitHub integration — repo management + Actions monitoring."""
    enabled: bool = True
    repo_name: str = ""          # e.g. "my-project" (created via gh CLI)
    repo_owner: str = ""         # GitHub user or org (auto-detected from gh auth)
    repo_private: bool = True
    actions_enabled: bool = True
    api_key: str = ""            # Stored as GitHub Secret ANTHROPIC_API_KEY
    model: str = "claude-haiku-4-5-20251001"
    schedule: str = "0 * * * *"  # Every hour


# Backwards compat alias
GitHubActionsConfig = GitHubConfig


@dataclass
class NetworkConfig:
    approved_domains: list[str] = field(default_factory=lambda: [
        "github.com",
        "api.github.com",
        "api.supabase.com",
        "registry.npmjs.org",
        "pypi.org",
        "docs.anthropic.com",
    ])


@dataclass
class PocketTeamConfig:
    project_name: str = ""
    health_url: str = ""

    auth: AuthConfig = field(default_factory=AuthConfig)
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    budget: BudgetConfig = field(default_factory=BudgetConfig)
    github: GitHubConfig = field(default_factory=GitHubConfig)

    @property
    def github_actions(self) -> GitHubConfig:
        """Backwards compat: cfg.github_actions → cfg.github."""
        return self.github

    @github_actions.setter
    def github_actions(self, value: GitHubConfig) -> None:
        self.github = value
    network: NetworkConfig = field(default_factory=NetworkConfig)
    dashboard: DashboardConfig = field(default_factory=DashboardConfig)
    computer_use: ComputerUseConfig = field(default_factory=ComputerUseConfig)
    insights: InsightsConfig = field(default_factory=InsightsConfig)

    # Absolute path to project root (set at runtime, not stored)
    project_root: Path = field(default_factory=Path.cwd, repr=False)


def load_config(project_root: Path | None = None) -> PocketTeamConfig:
    """Load config from .pocketteam/config.yaml in the given project root."""
    root = project_root or Path.cwd()
    config_path = root / CONFIG_FILE

    # Load .env before resolving config (secrets live in .env, not config.yaml)
    _load_dotenv(root)

    if not config_path.exists():
        cfg = PocketTeamConfig(project_name=root.name)
        cfg.project_root = root
        return cfg

    with open(config_path) as f:
        raw = yaml.safe_load(f) or {}

    cfg = PocketTeamConfig(project_root=root)
    project = raw.get("project", {})
    cfg.project_name = project.get("name", root.name)
    cfg.health_url = project.get("health_url", "")

    if auth_raw := raw.get("auth"):
        cfg.auth = AuthConfig(
            mode=auth_raw.get("mode", "subscription"),
            api_key=_resolve_env(auth_raw.get("api_key", "")),
        )

    if tg := raw.get("telegram"):
        cfg.telegram = TelegramConfig(
            bot_token=_resolve_env(tg.get("bot_token", "")),
            chat_id=_resolve_env(tg.get("chat_id", "")),
            persistent_sessions=tg.get("persistent_sessions", True),
            auto_resume=tg.get("auto_resume", True),
        )

    if mon := raw.get("monitoring"):
        cfg.monitoring = MonitoringConfig(
            enabled=mon.get("enabled", True),
            auto_fix=mon.get("auto_fix", True),
            staging_first=mon.get("staging_first", True),
            max_fix_attempts=mon.get("max_fix_attempts", MAX_AUTO_FIX_ATTEMPTS),
            interval_steady=mon.get("interval_steady", MONITOR_INTERVAL_STEADY),
            health_url=mon.get("health_url", cfg.health_url),
        )

    if bud := raw.get("budget"):
        cfg.budget = BudgetConfig(
            max_per_task=bud.get("max_per_task", DEFAULT_BUDGET_USD),
            prefer_subscription=bud.get("prefer_subscription", True),
        )

    # Load from "github" key first, fall back to legacy "github_actions"
    ga = raw.get("github") or raw.get("github_actions")
    if ga:
        cfg.github = GitHubConfig(
            enabled=ga.get("enabled", True),
            repo_name=ga.get("repo_name", ""),
            repo_owner=ga.get("repo_owner", ""),
            repo_private=ga.get("repo_private", True),
            actions_enabled=ga.get("actions_enabled", ga.get("enabled", True)),
            api_key=_resolve_env(ga.get("api_key", "")),
            model=ga.get("model", "claude-haiku-4-5-20251001"),
            schedule=ga.get("schedule", "0 * * * *"),
        )

    if net := raw.get("network"):
        extra_domains = net.get("approved_domains", [])
        cfg.network = NetworkConfig(
            approved_domains=NetworkConfig().approved_domains + extra_domains
        )

    if dash := raw.get("dashboard"):
        cfg.dashboard = DashboardConfig(
            enabled=dash.get("enabled", False),
            port=dash.get("port", DASHBOARD_PORT),
            image=dash.get("image", DASHBOARD_IMAGE),
            image_version=dash.get("image_version", DASHBOARD_VERSION),
            domain=dash.get("domain", ""),
            compose_dir=dash.get("compose_dir", ""),
            docker_context=dash.get("docker_context", "default"),
            claude_version_at_init=dash.get("claude_version_at_init", ""),
            compose_checksum=dash.get("compose_checksum", ""),
            project_root=dash.get("project_root", ""),
            claude_project_hash=dash.get("claude_project_hash", ""),
            compose_command=dash.get("compose_command", "docker compose"),
            container_name=dash.get("container_name", "pocketteam-dashboard"),
        )

    if cu := raw.get("computer_use"):
        cfg.computer_use = ComputerUseConfig(
            enabled=cu.get("enabled", False),
            browser_mcp=cu.get("browser_mcp", False),
            native_macos=cu.get("native_macos", False),
        )

    if ins := raw.get("insights"):
        cfg.insights = InsightsConfig(
            enabled=ins.get("enabled", False),
            schedule=ins.get("schedule", "0 22 * * *"),
            last_run=ins.get("last_run"),
            telegram_notify=ins.get("telegram_notify", True),
            auto_apply=False,  # NEVER auto-apply, always require CEO approval
        )

    return cfg


def save_config(cfg: PocketTeamConfig) -> None:
    """Persist config to .pocketteam/config.yaml."""
    config_path = cfg.project_root / CONFIG_FILE
    config_path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "project": {
            "name": cfg.project_name,
            "health_url": cfg.health_url,
        },
        "auth": {
            "mode": cfg.auth.mode,
            # Write a placeholder reference, never the literal secret value.
            # The actual key lives in .pocketteam/.env (gitignored).
            "api_key": "$ANTHROPIC_API_KEY",
        },
        "telegram": {
            # Write a placeholder reference, never the literal secret value.
            # The actual token lives in .pocketteam/telegram.env (gitignored).
            "bot_token": "$TELEGRAM_BOT_TOKEN",
            "chat_id": cfg.telegram.chat_id or "",
            "persistent_sessions": cfg.telegram.persistent_sessions,
            "auto_resume": cfg.telegram.auto_resume,
        },
        "monitoring": {
            "enabled": cfg.monitoring.enabled,
            "auto_fix": cfg.monitoring.auto_fix,
            "staging_first": cfg.monitoring.staging_first,
            "max_fix_attempts": cfg.monitoring.max_fix_attempts,
            "interval_steady": cfg.monitoring.interval_steady,
        },
        "budget": {
            "max_per_task": cfg.budget.max_per_task,
            "prefer_subscription": cfg.budget.prefer_subscription,
        },
        "github": {
            "enabled": cfg.github.enabled,
            "repo_name": cfg.github.repo_name,
            "repo_owner": cfg.github.repo_owner,
            "repo_private": cfg.github.repo_private,
            "actions_enabled": cfg.github.actions_enabled,
            # Stored as GitHub Secret ANTHROPIC_API_KEY — never write the literal value.
            "api_key": "$ANTHROPIC_API_KEY",
            "model": cfg.github.model,
            "schedule": cfg.github.schedule,
        },
        "network": {
            "approved_domains": [],  # Extra domains beyond defaults
        },
        "dashboard": {
            "enabled": cfg.dashboard.enabled,
            "port": cfg.dashboard.port,
            "image": cfg.dashboard.image,
            "image_version": cfg.dashboard.image_version,
            "domain": cfg.dashboard.domain,
            "compose_dir": cfg.dashboard.compose_dir,
            "docker_context": cfg.dashboard.docker_context,
            "claude_version_at_init": cfg.dashboard.claude_version_at_init,
            "compose_checksum": cfg.dashboard.compose_checksum,
            "project_root": cfg.dashboard.project_root,
            "claude_project_hash": cfg.dashboard.claude_project_hash,
            "compose_command": cfg.dashboard.compose_command,
            "container_name": cfg.dashboard.container_name,
        },
        "computer_use": {
            "enabled": cfg.computer_use.enabled,
            "browser_mcp": cfg.computer_use.browser_mcp,
            "native_macos": cfg.computer_use.native_macos,
        },
        "insights": {
            "enabled": cfg.insights.enabled,
            "schedule": cfg.insights.schedule,
            "last_run": cfg.insights.last_run,
            "telegram_notify": cfg.insights.telegram_notify,
            "auto_apply": False,  # NEVER persisted as True
        },
    }

    with open(config_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)

    # Errata E1: config.yaml contains project paths and checksums — protect it
    os.chmod(config_path, 0o600)


def _load_dotenv(project_root: Path) -> None:
    """Load .pocketteam/.env if it exists (secrets stay out of config.yaml)."""
    env_file = project_root / ".pocketteam" / ".env"
    if not env_file.exists():
        return
    try:
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                # Don't overwrite existing env vars (system takes precedence)
                if key and key not in os.environ:
                    os.environ[key] = value
    except OSError:
        pass


def _resolve_env(value: str) -> str:
    """Resolve ${ENV_VAR} and $ENV_VAR references in config values."""
    if value.startswith("${") and value.endswith("}"):
        env_var = value[2:-1]
        return os.environ.get(env_var, "")
    elif value.startswith("$") and not value.startswith("${"):
        env_var = value[1:]
        return os.environ.get(env_var, "")
    return value
