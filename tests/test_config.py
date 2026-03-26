"""
Tests for pocketteam/config.py: loading, saving, env resolution, and defaults.
"""

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from pocketteam.config import (
    PocketTeamConfig,
    TelegramConfig,
    load_config,
    save_config,
    _resolve_env,
)


class TestResolveEnv:
    """Unit tests for _resolve_env helper."""

    def test_resolve_env_dollar_brace_format(self, monkeypatch):
        monkeypatch.setenv("MY_TOKEN", "secret123")
        assert _resolve_env("${MY_TOKEN}") == "secret123"

    def test_resolve_env_dollar_format(self, monkeypatch):
        monkeypatch.setenv("MY_KEY", "apikey456")
        assert _resolve_env("$MY_KEY") == "apikey456"

    def test_resolve_env_missing_var_returns_empty(self, monkeypatch):
        monkeypatch.delenv("UNDEFINED_VAR_XYZ", raising=False)
        assert _resolve_env("${UNDEFINED_VAR_XYZ}") == ""

    def test_resolve_env_missing_dollar_format_returns_empty(self, monkeypatch):
        monkeypatch.delenv("UNDEFINED_VAR_XYZ", raising=False)
        assert _resolve_env("$UNDEFINED_VAR_XYZ") == ""

    def test_resolve_env_literal_value_unchanged(self):
        assert _resolve_env("some-literal-value") == "some-literal-value"

    def test_resolve_env_empty_string(self):
        assert _resolve_env("") == ""

    def test_resolve_env_dollar_brace_takes_precedence_over_dollar(self, monkeypatch):
        monkeypatch.setenv("VAR", "value")
        # ${VAR} is the full format
        result = _resolve_env("${VAR}")
        assert result == "value"

    def test_resolve_env_does_not_expand_partial_match(self):
        """A value like 'prefix_$VAR_suffix' is NOT expanded — only exact $VAR."""
        result = _resolve_env("not_a_$VAR_reference")
        # Starts with 'n', not '$', so returned as-is
        assert result == "not_a_$VAR_reference"


class TestLoadConfigDefaults:
    """Test that load_config returns safe defaults when no file exists."""

    def test_load_config_defaults_no_file(self, tmp_path):
        cfg = load_config(tmp_path)
        assert isinstance(cfg, PocketTeamConfig)
        assert cfg.project_name == tmp_path.name
        # Default auth mode
        assert cfg.auth.mode == "subscription"
        # Monitoring enabled by default
        assert cfg.monitoring.enabled is True
        # Budget is set
        assert cfg.budget.max_per_task > 0

    def test_load_config_empty_yaml(self, tmp_path):
        """An empty config.yaml file must not raise — returns defaults."""
        pocketteam_dir = tmp_path / ".pocketteam"
        pocketteam_dir.mkdir()
        config_file = pocketteam_dir / "config.yaml"
        config_file.write_text("")
        cfg = load_config(tmp_path)
        assert isinstance(cfg, PocketTeamConfig)
        assert cfg.project_name == tmp_path.name

    def test_load_config_sets_project_root(self, tmp_path):
        cfg = load_config(tmp_path)
        assert cfg.project_root == tmp_path


class TestSaveLoadRoundtrip:
    """Test that save_config + load_config preserves values."""

    def test_save_load_roundtrip_project_name(self, tmp_path):
        cfg = PocketTeamConfig(project_name="my-test-project", project_root=tmp_path)
        save_config(cfg)
        loaded = load_config(tmp_path)
        assert loaded.project_name == "my-test-project"

    def test_save_load_roundtrip_health_url(self, tmp_path):
        cfg = PocketTeamConfig(
            project_name="proj",
            health_url="https://example.com/health",
            project_root=tmp_path,
        )
        save_config(cfg)
        loaded = load_config(tmp_path)
        assert loaded.health_url == "https://example.com/health"

    def test_save_load_roundtrip_monitoring_flags(self, tmp_path):
        from pocketteam.config import MonitoringConfig
        cfg = PocketTeamConfig(project_root=tmp_path)
        cfg.monitoring = MonitoringConfig(enabled=False, auto_fix=False, staging_first=False)
        save_config(cfg)
        loaded = load_config(tmp_path)
        assert loaded.monitoring.enabled is False
        assert loaded.monitoring.auto_fix is False
        assert loaded.monitoring.staging_first is False

    def test_save_load_roundtrip_budget(self, tmp_path):
        from pocketteam.config import BudgetConfig
        cfg = PocketTeamConfig(project_root=tmp_path)
        cfg.budget = BudgetConfig(max_per_task=99.99, prefer_subscription=False)
        save_config(cfg)
        loaded = load_config(tmp_path)
        assert loaded.budget.max_per_task == 99.99
        assert loaded.budget.prefer_subscription is False

    def test_save_creates_config_yaml(self, tmp_path):
        cfg = PocketTeamConfig(project_name="proj", project_root=tmp_path)
        save_config(cfg)
        config_path = tmp_path / ".pocketteam" / "config.yaml"
        assert config_path.exists()

    def test_save_config_sets_permissions(self, tmp_path):
        """config.yaml must be protected (mode 0o600)."""
        cfg = PocketTeamConfig(project_root=tmp_path)
        save_config(cfg)
        config_path = tmp_path / ".pocketteam" / "config.yaml"
        mode = oct(config_path.stat().st_mode)[-3:]
        assert mode == "600"

    def test_save_does_not_write_literal_api_key(self, tmp_path, monkeypatch):
        """Secrets must never be written literally into config.yaml."""
        from pocketteam.config import AuthConfig
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-real-secret")
        cfg = PocketTeamConfig(project_root=tmp_path)
        cfg.auth = AuthConfig(mode="api_key", api_key="sk-real-secret")
        save_config(cfg)
        content = (tmp_path / ".pocketteam" / "config.yaml").read_text()
        assert "sk-real-secret" not in content
        # Placeholder reference is written instead
        assert "$ANTHROPIC_API_KEY" in content

    def test_save_telegram_writes_placeholder_not_secret(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "bot:actualtoken")
        cfg = PocketTeamConfig(project_root=tmp_path)
        cfg.telegram = TelegramConfig(bot_token="bot:actualtoken")
        save_config(cfg)
        content = (tmp_path / ".pocketteam" / "config.yaml").read_text()
        assert "bot:actualtoken" not in content
        assert "$TELEGRAM_BOT_TOKEN" in content
