"""
Tests for Computer Use feature:
- ComputerUseConfig dataclass defaults
- load_config / save_config roundtrip
- load_config without computer_use key (graceful default)
- _setup_computer_use_mcp (built-in MCP, always returns True)
- --yes flag does NOT activate Computer Use
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from pocketteam.config import ComputerUseConfig, PocketTeamConfig, load_config, save_config
from pocketteam.init import _setup_computer_use_mcp


# ─────────────────────────────────────────────────────────────────────────────
# ComputerUseConfig defaults
# ─────────────────────────────────────────────────────────────────────────────

class TestComputerUseConfigDefaults:
    """ComputerUseConfig must have safe opt-out defaults."""

    def test_enabled_defaults_false(self):
        cfg = ComputerUseConfig()
        assert cfg.enabled is False

    def test_browser_mcp_defaults_false(self):
        cfg = ComputerUseConfig()
        assert cfg.browser_mcp is False

    def test_native_macos_defaults_false(self):
        cfg = ComputerUseConfig()
        assert cfg.native_macos is False

    def test_explicit_values_stored(self):
        cfg = ComputerUseConfig(enabled=True, browser_mcp=True, native_macos=True)
        assert cfg.enabled is True
        assert cfg.browser_mcp is True
        assert cfg.native_macos is True


# ─────────────────────────────────────────────────────────────────────────────
# PocketTeamConfig.computer_use field
# ─────────────────────────────────────────────────────────────────────────────

class TestPocketTeamConfigComputerUseField:
    """PocketTeamConfig must expose computer_use with a ComputerUseConfig default."""

    def test_computer_use_field_exists(self):
        cfg = PocketTeamConfig()
        assert hasattr(cfg, "computer_use")

    def test_computer_use_field_is_computer_use_config(self):
        cfg = PocketTeamConfig()
        assert isinstance(cfg.computer_use, ComputerUseConfig)

    def test_computer_use_defaults_to_disabled(self):
        cfg = PocketTeamConfig()
        assert cfg.computer_use.enabled is False


# ─────────────────────────────────────────────────────────────────────────────
# load_config / save_config roundtrip
# ─────────────────────────────────────────────────────────────────────────────

class TestComputerUseConfigRoundtrip:
    """save_config + load_config must preserve computer_use values."""

    def test_roundtrip_enabled_true(self, tmp_path):
        cfg = PocketTeamConfig(project_root=tmp_path)
        cfg.computer_use = ComputerUseConfig(enabled=True, browser_mcp=True, native_macos=False)
        save_config(cfg)
        loaded = load_config(tmp_path)
        assert loaded.computer_use.enabled is True
        assert loaded.computer_use.browser_mcp is True
        assert loaded.computer_use.native_macos is False

    def test_roundtrip_all_flags_true(self, tmp_path):
        cfg = PocketTeamConfig(project_root=tmp_path)
        cfg.computer_use = ComputerUseConfig(enabled=True, browser_mcp=True, native_macos=True)
        save_config(cfg)
        loaded = load_config(tmp_path)
        assert loaded.computer_use.enabled is True
        assert loaded.computer_use.browser_mcp is True
        assert loaded.computer_use.native_macos is True

    def test_roundtrip_all_flags_false(self, tmp_path):
        cfg = PocketTeamConfig(project_root=tmp_path)
        cfg.computer_use = ComputerUseConfig(enabled=False, browser_mcp=False, native_macos=False)
        save_config(cfg)
        loaded = load_config(tmp_path)
        assert loaded.computer_use.enabled is False
        assert loaded.computer_use.browser_mcp is False
        assert loaded.computer_use.native_macos is False

    def test_computer_use_section_written_to_yaml(self, tmp_path):
        import yaml
        cfg = PocketTeamConfig(project_root=tmp_path)
        cfg.computer_use = ComputerUseConfig(enabled=True, browser_mcp=True)
        save_config(cfg)
        config_path = tmp_path / ".pocketteam" / "config.yaml"
        raw = yaml.safe_load(config_path.read_text())
        assert "computer_use" in raw
        assert raw["computer_use"]["enabled"] is True
        assert raw["computer_use"]["browser_mcp"] is True


# ─────────────────────────────────────────────────────────────────────────────
# load_config without computer_use key (graceful default)
# ─────────────────────────────────────────────────────────────────────────────

class TestLoadConfigWithoutComputerUse:
    """load_config must return disabled ComputerUseConfig when key is absent."""

    def test_missing_computer_use_key_returns_defaults(self, tmp_path):
        """A config.yaml without computer_use must return defaults — no KeyError."""
        pocketteam_dir = tmp_path / ".pocketteam"
        pocketteam_dir.mkdir()
        (pocketteam_dir / "config.yaml").write_text(
            "project:\n  name: testproject\n  health_url: ''\n"
        )
        cfg = load_config(tmp_path)
        assert cfg.computer_use.enabled is False
        assert cfg.computer_use.browser_mcp is False
        assert cfg.computer_use.native_macos is False

    def test_partial_computer_use_key_fills_defaults(self, tmp_path):
        """A partial computer_use block must not raise."""
        pocketteam_dir = tmp_path / ".pocketteam"
        pocketteam_dir.mkdir()
        (pocketteam_dir / "config.yaml").write_text(
            "project:\n  name: testproject\n  health_url: ''\n"
            "computer_use:\n  enabled: true\n"
        )
        cfg = load_config(tmp_path)
        assert cfg.computer_use.enabled is True
        assert cfg.computer_use.browser_mcp is False  # not specified → default
        assert cfg.computer_use.native_macos is False  # not specified → default


# ─────────────────────────────────────────────────────────────────────────────
# _setup_computer_use_mcp
# ─────────────────────────────────────────────────────────────────────────────

class TestSetupComputerUseMcp:
    """Tests for _setup_computer_use_mcp(project_root).

    Computer Use is a built-in Claude Code MCP server — the function
    always returns True and prints activation instructions.
    """

    def test_always_returns_true(self, tmp_path):
        with patch("pocketteam.init.console"):
            result = _setup_computer_use_mcp(tmp_path)
        assert result is True


# ─────────────────────────────────────────────────────────────────────────────
# --yes flag must NOT activate Computer Use
# ─────────────────────────────────────────────────────────────────────────────

class TestAcceptDefaultsDoesNotEnableComputerUse:
    """--yes (accept_defaults=True) must never enable Computer Use."""

    @pytest.mark.asyncio
    async def test_accept_defaults_leaves_computer_use_disabled(self, tmp_path):
        """_interview with accept_defaults=True must not enable computer_use."""
        from pocketteam.init import _interview

        # _interview calls console.print and Prompt.ask; we mock the console
        with (
            patch("pocketteam.init.console"),
            patch("pocketteam.init.Confirm.ask", return_value=False),
            patch("pocketteam.init.Prompt.ask", return_value=""),
        ):
            cfg = await _interview(tmp_path, project_name=None, accept_defaults=True)

        assert cfg.computer_use.enabled is False
