"""launchd plist generation and management for Telegram daemon. macOS only."""

from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path

_PLIST_LABEL_BASE = "com.pocketteam.telegram-daemon"


def _plist_label(project_root: Path) -> str:
    """Return a launchd label unique to this project."""
    project_name = project_root.name.lower().replace(" ", "-")
    return f"{_PLIST_LABEL_BASE}.{project_name}"


def _plist_path(project_root: Path) -> Path:
    """Return the plist file path for this project."""
    label = _plist_label(project_root)
    return Path.home() / "Library" / "LaunchAgents" / f"{label}.plist"


def is_macos() -> bool:
    return platform.system() == "Darwin"


def generate_plist(project_root: Path) -> str:
    """Generate a launchd plist XML string for the given project root."""
    home = str(Path.home())
    log_dir = project_root / ".pocketteam" / "logs"
    python = sys.executable
    label = _plist_label(project_root)

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>{label}</string>
  <key>ProgramArguments</key>
  <array>
    <string>{python}</string>
    <string>-m</string>
    <string>pocketteam.telegram_daemon</string>
    <string>--project-root</string>
    <string>{project_root}</string>
  </array>
  <key>WorkingDirectory</key>
  <string>{project_root}</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>{log_dir}/telegram-daemon.stdout.log</string>
  <key>StandardErrorPath</key>
  <string>{log_dir}/telegram-daemon.stderr.log</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/usr/local/bin:/usr/bin:/bin:{home}/.bun/bin:{home}/.local/bin</string>
    <key>HOME</key>
    <string>{home}</string>
  </dict>
  <key>ThrottleInterval</key>
  <integer>10</integer>
</dict>
</plist>"""


def install_plist(project_root: Path) -> bool:
    """Install and load the launchd plist. Idempotent — safe to call on re-init."""
    if not is_macos():
        return False

    plist_path = _plist_path(project_root)

    # Ensure log directory exists before launchd tries to open it
    log_dir = project_root / ".pocketteam" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    # Unload any previously installed version first
    if plist_path.exists():
        subprocess.run(
            ["launchctl", "unload", str(plist_path)],
            capture_output=True,
        )

    # Write updated plist
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    plist_path.write_text(generate_plist(project_root))

    # Load into launchd
    result = subprocess.run(
        ["launchctl", "load", str(plist_path)],
        capture_output=True,
    )
    return result.returncode == 0


def uninstall_plist(project_root: Path) -> bool:
    """Unload and remove the launchd plist. Returns True if something was removed."""
    plist_path = _plist_path(project_root)
    if not is_macos() or not plist_path.exists():
        return False

    subprocess.run(
        ["launchctl", "unload", str(plist_path)],
        capture_output=True,
    )
    plist_path.unlink(missing_ok=True)
    return True
