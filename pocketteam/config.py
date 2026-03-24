"""
PocketTeam Configuration
Reads/writes .pocketteam/config.yaml for each project.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

from .constants import (
    CONFIG_FILE,
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
    mode: str = "subscription"   # "subscription" | "api_key" | "hybrid"
    api_key: str = ""            # Only used in api_key / hybrid mode


@dataclass
class GitHubActionsConfig:
    enabled: bool = True
    api_key: str = ""            # Stored as GitHub Secret ANTHROPIC_API_KEY
    model: str = "claude-haiku-4-5-20251001"
    schedule: str = "0 * * * *"  # Every hour


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
    github_actions: GitHubActionsConfig = field(default_factory=GitHubActionsConfig)
    network: NetworkConfig = field(default_factory=NetworkConfig)

    # Absolute path to project root (set at runtime, not stored)
    project_root: Path = field(default_factory=Path.cwd, repr=False)


def load_config(project_root: Optional[Path] = None) -> PocketTeamConfig:
    """Load config from .pocketteam/config.yaml in the given project root."""
    root = project_root or Path.cwd()
    config_path = root / CONFIG_FILE

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

    if ga := raw.get("github_actions"):
        cfg.github_actions = GitHubActionsConfig(
            enabled=ga.get("enabled", True),
            api_key=_resolve_env(ga.get("api_key", "")),
            model=ga.get("model", "claude-haiku-4-5-20251001"),
            schedule=ga.get("schedule", "0 * * * *"),
        )

    if net := raw.get("network"):
        extra_domains = net.get("approved_domains", [])
        cfg.network = NetworkConfig(
            approved_domains=NetworkConfig().approved_domains + extra_domains
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
            "api_key": cfg.auth.api_key or "",
        },
        "telegram": {
            "bot_token": cfg.telegram.bot_token or "",
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
        "github_actions": {
            "enabled": cfg.github_actions.enabled,
            "api_key": cfg.github_actions.api_key or "",
            "model": cfg.github_actions.model,
            "schedule": cfg.github_actions.schedule,
        },
        "network": {
            "approved_domains": [],  # Extra domains beyond defaults
        },
    }

    with open(config_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)


def _resolve_env(value: str) -> str:
    """Resolve ${ENV_VAR} references in config values."""
    if value.startswith("${") and value.endswith("}"):
        env_var = value[2:-1]
        return os.environ.get(env_var, "")
    return value
