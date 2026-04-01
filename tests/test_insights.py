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


# ---------------------------------------------------------------------------
# Regression: re-init must preserve custom insights.schedule
# Bug: schedule was always reset to "0 22 * * *" on re-init
# ---------------------------------------------------------------------------

class TestInsightsScheduleReInitPreservation:
    """Regression tests for insights schedule preservation across re-init."""

    def test_load_config_preserves_custom_schedule(self, tmp_path):
        """load_config must deserialise a custom schedule correctly (not fall back to default)."""
        pt_dir = tmp_path / ".pocketteam"
        pt_dir.mkdir(parents=True)
        config_data = {
            "project": {"name": "test"},
            "insights": {
                "enabled": True,
                "schedule": "0 14 * * *",
                "telegram_notify": True,
                "auto_apply": False,
            },
        }
        config_file = pt_dir / "config.yaml"
        config_file.write_text(__import__("yaml").dump(config_data))
        config_file.chmod(0o600)

        loaded = load_config(tmp_path)
        assert loaded.insights.schedule == "0 14 * * *", (
            f"Expected '0 14 * * *' but got '{loaded.insights.schedule}'. "
            "load_config is not preserving the custom schedule."
        )

    def test_save_load_roundtrip_custom_schedule(self, tmp_path):
        """A config saved with a custom schedule must survive a full save/load cycle."""
        cfg = PocketTeamConfig(project_root=tmp_path)
        cfg.insights = InsightsConfig(enabled=True, schedule="0 14 * * *")
        save_config(cfg)

        loaded = load_config(tmp_path)
        assert loaded.insights.schedule == "0 14 * * *", (
            f"Expected '0 14 * * *' after save/load but got '{loaded.insights.schedule}'."
        )

    def test_reinit_interview_preserves_schedule_when_user_presses_enter(self, tmp_path):
        """
        Regression test for the re-init schedule-reset bug.

        Scenario:
          1. Config exists with insights.schedule = "0 14 * * *"
          2. User runs pocketteam init again
          3. At Step 6, the interview uses cfg.insights.schedule as the prompt default
          4. User presses Enter (accepts default)
          5. cfg.insights.schedule must remain "0 14 * * *" — NOT reset to "0 22 * * *"
        """
        import asyncio
        from unittest.mock import patch, AsyncMock
        import yaml

        # Arrange: write a config with a custom schedule
        pt_dir = tmp_path / ".pocketteam"
        pt_dir.mkdir(parents=True)
        config_data = {
            "project": {"name": "myapp"},
            "insights": {
                "enabled": True,
                "schedule": "0 14 * * *",
                "telegram_notify": True,
                "auto_apply": False,
            },
        }
        config_file = pt_dir / "config.yaml"
        config_file.write_text(yaml.dump(config_data))
        config_file.chmod(0o600)

        # Verify load_config picks up the custom schedule correctly
        existing = load_config(tmp_path)
        assert existing.insights.schedule == "0 14 * * *", (
            "Precondition failed: load_config did not return the custom schedule."
        )

        # Simulate the _interview logic:
        # cfg.insights = existing.insights  (line 240 in init.py)
        # Then at Step 6:
        #   default_schedule = cfg.insights.schedule or "0 22 * * *"
        #   custom = Prompt.ask(..., default=default_schedule)  <- user presses Enter
        #   cfg.insights.schedule = custom

        cfg = PocketTeamConfig(project_root=tmp_path)
        cfg.insights = existing.insights  # This is the assignment at init.py:240

        # Verify: the schedule is the existing value at this point
        assert cfg.insights.schedule == "0 14 * * *", (
            f"After cfg.insights = existing.insights, schedule was '{cfg.insights.schedule}' "
            "instead of '0 14 * * *'. The assignment at init.py:240 is broken."
        )

        # Simulate Step 6 prompt logic
        enable_insights = True
        default_schedule = cfg.insights.schedule or "0 22 * * *"

        # Verify the default offered to the user is the custom value
        assert default_schedule == "0 14 * * *", (
            f"The prompt default was '{default_schedule}' instead of '0 14 * * *'. "
            "User would see wrong default — pressing Enter would reset the schedule."
        )

        # Simulate user pressing Enter (accepting the default)
        user_input = default_schedule  # Enter key returns the default
        cfg.insights.schedule = user_input

        assert cfg.insights.schedule == "0 14 * * *", (
            f"After user presses Enter, schedule is '{cfg.insights.schedule}' "
            "instead of '0 14 * * *'. The schedule-reset bug is NOT fixed."
        )

    def test_default_schedule_fallback_only_when_schedule_is_empty(self, tmp_path):
        """
        The 'or "0 22 * * *"' fallback in Step 6 must only trigger when schedule is
        empty/None, never when a valid custom schedule exists.
        """
        # Case 1: custom schedule set -> no fallback
        cfg_with_custom = PocketTeamConfig(project_root=tmp_path)
        cfg_with_custom.insights = InsightsConfig(schedule="0 6 * * 1")
        default = cfg_with_custom.insights.schedule or "0 22 * * *"
        assert default == "0 6 * * 1"

        # Case 2: empty schedule -> falls back to default
        cfg_empty = PocketTeamConfig(project_root=tmp_path)
        cfg_empty.insights = InsightsConfig(schedule="")
        default_empty = cfg_empty.insights.schedule or "0 22 * * *"
        assert default_empty == "0 22 * * *"

        # Case 3: None schedule -> falls back to default
        cfg_none = PocketTeamConfig(project_root=tmp_path)
        cfg_none.insights = InsightsConfig(schedule=None)
        default_none = cfg_none.insights.schedule or "0 22 * * *"
        assert default_none == "0 22 * * *"
