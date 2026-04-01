"""
Tests for pocketteam help command.
"""

from __future__ import annotations

from click.testing import CliRunner

from pocketteam.cli import main


class TestHelpCommand:
    def test_help_exits_zero(self):
        runner = CliRunner()
        result = runner.invoke(main, ["help"])
        assert result.exit_code == 0

    def test_help_shows_version(self):
        runner = CliRunner()
        result = runner.invoke(main, ["help"])
        assert "1.0.0" in result.output

    def test_help_shows_all_commands(self):
        runner = CliRunner()
        result = runner.invoke(main, ["help"])
        expected_commands = [
            "init",
            "start",
            "status",
            "health",
            "logs",
            "sessions",
            "dashboard",
            "insights",
            "retro",
            "run-headless",
            "uninstall",
            "help",
        ]
        for cmd in expected_commands:
            assert cmd in result.output, f"Expected command '{cmd}' not found in help output"

    def test_help_shows_categories(self):
        runner = CliRunner()
        result = runner.invoke(main, ["help"])
        # Check that category headers are present
        assert "Getting Started" in result.output
        assert "Monitoring" in result.output
        assert "Automation" in result.output
        assert "Maintenance" in result.output

    def test_help_shows_tip(self):
        runner = CliRunner()
        result = runner.invoke(main, ["help"])
        assert "--help" in result.output

    def test_main_help_flag_still_works(self):
        """pocketteam --help should still show the Click-generated help."""
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "PocketTeam" in result.output
