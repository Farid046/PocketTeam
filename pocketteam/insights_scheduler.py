"""
Cross-platform OS scheduler for PocketTeam Auto-Insights.

Public API:
  install_scheduler(project_root, cron) -> bool
  uninstall_scheduler() -> bool
  scheduler_status() -> dict[str, ...]
"""

from __future__ import annotations

import platform
import subprocess
from pathlib import Path

# Label used across all platforms to identify PocketTeam's scheduler entry.
_PLIST_LABEL = "com.pocketteam.insights"
_PLIST_FILENAME = f"{_PLIST_LABEL}.plist"
_CRONTAB_MARKER = "# pocketteam-insights"
_SCHTASKS_TASK_NAME = "PocketTeam-Insights"

# The command the scheduler will run.
_INSIGHTS_CMD = 'claude --continue -p "Run /self-improve for this project"'


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def install_scheduler(project_root: Path, cron: str) -> bool:
    """Register the insights schedule with the OS scheduler.

    Args:
        project_root: Absolute path to the project directory.
        cron: Standard 5-field cron expression (e.g. "0 22 * * *").

    Returns:
        True on success, False on failure (never raises).
    """
    try:
        system = platform.system()
        if system == "Darwin":
            return _install_launchd(project_root, cron)
        elif system == "Linux":
            return _install_crontab(project_root, cron)
        elif system == "Windows":
            return _install_schtasks(project_root, cron)
        else:
            # Unknown platform — best effort via crontab
            return _install_crontab(project_root, cron)
    except Exception:
        return False


def uninstall_scheduler() -> bool:
    """Remove the PocketTeam insights schedule from the OS scheduler.

    Returns:
        True if something was removed, False if nothing was installed (never raises).
    """
    try:
        system = platform.system()
        if system == "Darwin":
            return _uninstall_launchd()
        elif system == "Linux":
            return _uninstall_crontab()
        elif system == "Windows":
            return _uninstall_schtasks()
        else:
            return _uninstall_crontab()
    except Exception:
        return False


def scheduler_status() -> dict[str, object]:
    """Return current scheduler registration status.

    Returns:
        dict with keys:
          - platform (str): human-readable OS name
          - registered (bool): whether the schedule is currently active
          - detail (str): short description of the current state
    """
    try:
        system = platform.system()
        if system == "Darwin":
            return _status_launchd()
        elif system == "Linux":
            return _status_crontab()
        elif system == "Windows":
            return _status_schtasks()
        else:
            return _status_crontab()
    except Exception:
        return {"platform": platform.system() or "unknown", "registered": False, "detail": "status check failed"}


# ---------------------------------------------------------------------------
# macOS: launchd
# ---------------------------------------------------------------------------

def _plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / _PLIST_FILENAME


def _cron_to_launchd_interval(cron: str) -> tuple[int, int]:
    """Parse 'minute hour * * *' cron into (minute, hour)."""
    fields = cron.strip().split()
    if len(fields) != 5:
        raise ValueError(f"Expected 5 cron fields, got {len(fields)}: {cron!r}")
    minute = int(fields[0])
    hour = int(fields[1])
    return minute, hour


def _build_plist(project_root: Path, minute: int, hour: int) -> str:
    """Build a launchd plist XML string."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{_PLIST_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/sh</string>
        <string>-c</string>
        <string>cd {project_root} &amp;&amp; {_INSIGHTS_CMD}</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>{hour}</integer>
        <key>Minute</key>
        <integer>{minute}</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>{Path.home()}/.pocketteam-insights.log</string>
    <key>StandardErrorPath</key>
    <string>{Path.home()}/.pocketteam-insights.err</string>
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
"""


def _install_launchd(project_root: Path, cron: str) -> bool:
    minute, hour = _cron_to_launchd_interval(cron)
    plist = _plist_path()
    plist.parent.mkdir(parents=True, exist_ok=True)
    plist.write_text(_build_plist(project_root, minute, hour))

    # Unload old entry silently (ignore errors), then load fresh
    subprocess.run(
        ["launchctl", "unload", str(plist)],
        capture_output=True,
    )
    subprocess.run(
        ["launchctl", "load", str(plist)],
        check=False,
    )
    return True


def _uninstall_launchd() -> bool:
    plist = _plist_path()
    if not plist.exists():
        return False
    subprocess.run(
        ["launchctl", "unload", str(plist)],
        capture_output=True,
    )
    plist.unlink(missing_ok=True)
    return True


def _status_launchd() -> dict[str, object]:
    plist = _plist_path()
    registered = plist.exists()
    detail = str(plist) if registered else "launchd plist not installed"
    return {"platform": "macOS", "registered": registered, "detail": detail}


# ---------------------------------------------------------------------------
# Linux / unknown: crontab
# ---------------------------------------------------------------------------

def _read_crontab() -> str:
    result = subprocess.run(
        ["crontab", "-l"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return ""
    return result.stdout or ""


def _write_crontab(content: str) -> None:
    subprocess.run(
        ["crontab", "-"],
        input=content,
        text=True,
        check=False,
    )


def _install_crontab(project_root: Path, cron: str) -> bool:
    existing = _read_crontab()
    # Remove any previous PocketTeam entry first
    lines = [
        line for line in existing.splitlines()
        if _CRONTAB_MARKER not in line and "pocketteam" not in line.lower()
    ]
    new_entry = (
        f"{_CRONTAB_MARKER}\n"
        f"{cron} cd {project_root} && {_INSIGHTS_CMD}\n"
    )
    updated = "\n".join(lines).rstrip("\n") + "\n" + new_entry
    _write_crontab(updated)
    return True


def _uninstall_crontab() -> bool:
    existing = _read_crontab()
    if _CRONTAB_MARKER not in existing:
        return False
    lines = []
    skip_next = False
    for line in existing.splitlines():
        if _CRONTAB_MARKER in line:
            skip_next = True
            continue
        if skip_next and "pocketteam" in line.lower():
            skip_next = False
            continue
        skip_next = False
        lines.append(line)
    _write_crontab("\n".join(lines) + "\n")
    return True


def _status_crontab() -> dict[str, object]:
    try:
        existing = _read_crontab()
        registered = _CRONTAB_MARKER in existing
        detail = "crontab entry installed" if registered else "no crontab entry"
        return {"platform": "Linux", "registered": registered, "detail": detail}
    except Exception:
        return {"platform": "Linux", "registered": False, "detail": "crontab check failed"}


# ---------------------------------------------------------------------------
# Windows: schtasks
# ---------------------------------------------------------------------------

_SCHTASKS_TRIGGER_TIME_FORMAT = "{hour:02d}:{minute:02d}"


def _install_schtasks(project_root: Path, cron: str) -> bool:
    minute, hour = _cron_to_launchd_interval(cron)
    trigger_time = _SCHTASKS_TRIGGER_TIME_FORMAT.format(hour=hour, minute=minute)
    cmd = (
        f'cd /d "{project_root}" && {_INSIGHTS_CMD}'
    )
    subprocess.run(
        [
            "schtasks", "/Create", "/F",
            "/TN", _SCHTASKS_TASK_NAME,
            "/TR", f'cmd /c "{cmd}"',
            "/SC", "DAILY",
            "/ST", trigger_time,
        ],
        check=False,
        capture_output=True,
    )
    return True


def _uninstall_schtasks() -> bool:
    subprocess.run(
        [
            "schtasks", "/Delete", "/F",
            "/TN", _SCHTASKS_TASK_NAME,
        ],
        check=False,
        capture_output=True,
    )
    return True


def _status_schtasks() -> dict[str, object]:
    result = subprocess.run(
        ["schtasks", "/Query", "/TN", _SCHTASKS_TASK_NAME],
        capture_output=True,
        text=True,
    )
    registered = result.returncode == 0
    detail = "schtasks task installed" if registered else "schtasks task not found"
    return {"platform": "Windows", "registered": registered, "detail": detail}
