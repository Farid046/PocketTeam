"""launchd plist generation and management for Telegram daemon. macOS only."""

from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path

PLIST_LABEL = "com.pocketteam.telegram-daemon"
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{PLIST_LABEL}.plist"


def is_macos() -> bool:
    return platform.system() == "Darwin"


def generate_plist(project_root: Path) -> str:
    """Generate a launchd plist XML string for the given project root."""
    home = str(Path.home())
    log_dir = project_root / ".pocketteam" / "logs"
    python = sys.executable

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>{PLIST_LABEL}</string>
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

    # Ensure log directory exists before launchd tries to open it
    log_dir = project_root / ".pocketteam" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    # Unload any previously installed version first
    if PLIST_PATH.exists():
        subprocess.run(
            ["launchctl", "unload", str(PLIST_PATH)],
            capture_output=True,
        )

    # Write updated plist
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    PLIST_PATH.write_text(generate_plist(project_root))

    # Load into launchd
    result = subprocess.run(
        ["launchctl", "load", str(PLIST_PATH)],
        capture_output=True,
    )
    return result.returncode == 0


def uninstall_plist() -> bool:
    """Unload and remove the launchd plist. Returns True if something was removed."""
    if not is_macos() or not PLIST_PATH.exists():
        return False

    subprocess.run(
        ["launchctl", "unload", str(PLIST_PATH)],
        capture_output=True,
    )
    PLIST_PATH.unlink(missing_ok=True)
    return True
