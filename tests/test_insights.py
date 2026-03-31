"""Tests for InsightsConfig and insights integration (Wave 3a — Auto-Insights Self-Healing)."""

from __future__ import annotations

import yaml
import pytest
from pathlib import Path

from pocketteam.config import InsightsConfig, PocketTeamConfig, load_config, save_config


# ---------------------------------------------------------------------------
# InsightsConfig dataclass defaults
# ---------------------------------------------------------------------------

class TestInsightsConfig:
    """Tests for the InsightsConfig dataclass."""

    def test_defaults(self):
        """InsightsConfig has safe defaults."""
        cfg = InsightsConfig()
        assert cfg.enabled is False
        assert cfg.schedule == "0 22 * * *"
        assert cfg.last_run is None
        assert cfg.telegram_notify is True
        assert cfg.auto_apply is False

    def test_auto_apply_dataclass_allows_true(self):
        """Direct dataclass construction allows auto_apply=True (guard is in load_config)."""
        cfg = InsightsConfig(auto_apply=True)
        assert cfg.auto_apply is True


# ---------------------------------------------------------------------------
# InsightsConfig persistence (save/load round-trip)
# ---------------------------------------------------------------------------

class TestInsightsConfigPersistence:
    """Tests for save/load round-trip of InsightsConfig."""

    def test_save_load_roundtrip(self, tmp_path):
        """InsightsConfig survives a save/load cycle via project_root."""
        cfg = PocketTeamConfig(project_root=tmp_path)
        cfg.insights = InsightsConfig(
            enabled=True,
            schedule="0 8 * * *",
            last_run="2026-03-31",
            telegram_notify=False,
            auto_apply=False,
        )
        save_config(cfg)

        loaded = load_config(tmp_path)
        assert loaded.insights.enabled is True
        assert loaded.insights.schedule == "0 8 * * *"
        assert loaded.insights.last_run == "2026-03-31"
        assert loaded.insights.telegram_notify is False
        assert loaded.insights.auto_apply is False

    def test_auto_apply_forced_false_on_load(self, tmp_path):
        """load_config forces auto_apply=False even if YAML contains auto_apply: true."""
        pt_dir = tmp_path / ".pocketteam"
        pt_dir.mkdir(parents=True)
        config_data = {
            "insights": {
                "enabled": True,
                "schedule": "0 22 * * *",
                "auto_apply": True,  # Attempting to sneak this in
            }
        }
        (pt_dir / "config.yaml").write_text(yaml.dump(config_data))
        (pt_dir / "config.yaml").chmod(0o600)

        loaded = load_config(tmp_path)
        assert loaded.insights.auto_apply is False  # MUST always be False

    def test_missing_insights_section_uses_defaults(self, tmp_path):
        """Config without an insights section returns safe InsightsConfig defaults."""
        pt_dir = tmp_path / ".pocketteam"
        pt_dir.mkdir(parents=True)
        config_file = pt_dir / "config.yaml"
        config_file.write_text(yaml.dump({"project": {"name": "test"}}))
        config_file.chmod(0o600)

        loaded = load_config(tmp_path)
        assert loaded.insights.enabled is False
        assert loaded.insights.auto_apply is False
        assert loaded.insights.schedule == "0 22 * * *"

    def test_save_writes_insights_section(self, tmp_path):
        """save_config writes an insights section to config.yaml."""
        cfg = PocketTeamConfig(project_root=tmp_path)
        cfg.insights = InsightsConfig(enabled=True, schedule="0 9 * * 1")
        save_config(cfg)

        raw = yaml.safe_load((tmp_path / ".pocketteam" / "config.yaml").read_text())
        assert "insights" in raw
        assert raw["insights"]["enabled"] is True
        assert raw["insights"]["schedule"] == "0 9 * * 1"

    def test_save_never_persists_auto_apply_true(self, tmp_path):
        """save_config always writes auto_apply: false regardless of the in-memory value."""
        cfg = PocketTeamConfig(project_root=tmp_path)
        # Directly set to True on the dataclass (bypassing load_config guard)
        cfg.insights = InsightsConfig(auto_apply=True)
        save_config(cfg)

        raw = yaml.safe_load((tmp_path / ".pocketteam" / "config.yaml").read_text())
        assert raw["insights"]["auto_apply"] is False


# ---------------------------------------------------------------------------
# InsightsConfig constants
# ---------------------------------------------------------------------------

class TestInsightsConstants:
    """Tests for insights-related constants."""

    def test_insights_dir_defined(self):
        """INSIGHTS_DIR constant exists and points to the correct path."""
        from pocketteam.constants import INSIGHTS_DIR
        assert INSIGHTS_DIR == ".pocketteam/artifacts/insights"

    def test_insights_dir_under_artifacts(self):
        """INSIGHTS_DIR is nested under the artifacts directory."""
        from pocketteam.constants import INSIGHTS_DIR
        assert "artifacts" in INSIGHTS_DIR


# ---------------------------------------------------------------------------
# init.py integration
# ---------------------------------------------------------------------------

class TestInsightsInit:
    """Tests for insights integration in init.py."""

    def test_create_directories_includes_insights(self):
        """_create_directories references INSIGHTS_DIR so the directory is created at init."""
        import inspect
        from pocketteam import init as init_module
        source = inspect.getsource(init_module)
        assert "INSIGHTS_DIR" in source
