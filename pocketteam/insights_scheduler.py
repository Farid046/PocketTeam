"""
Cross-platform OS scheduler for PocketTeam Auto-Insights.

Public API:
  install_scheduler(project_root, cron) -> bool
  uninstall_scheduler(project_root) -> bool
  scheduler_status(project_root) -> dict[str, ...]
"""

from __future__ import annotations

import platform
import subprocess
from pathlib import Path

# The command the scheduler will run.
_INSIGHTS_CMD = 'claude --continue -p "Run /self-improve for this project"'


# ---------------------------------------------------------------------------
# Project-specific naming helpers
# ---------------------------------------------------------------------------

def _plist_label(project_root: Path) -> str:
    """Return a launchd label unique to this project.

    Format: com.pocketteam.insights.<project-name>
    """
    name = project_root.name.lower().replace(" ", "-")
    return f"com.pocketteam.insights.{name}"


def _plist_path(project_root: Path) -> Path:
    """Return the plist file path for this project."""
    label = _plist_label(project_root)
    return Path.home() / "Library" / "LaunchAgents" / f"{label}.plist"


def _cron_marker(project_root: Path) -> str:
    """Return the crontab comment marker unique to this project."""
    return f"# pocketteam-insights-{project_root.name}"


def _schtasks_name(project_root: Path) -> str:
    """Return the Windows Scheduled Task name unique to this project."""
    return f"PocketTeamInsights-{project_root.name}"


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


def uninstall_scheduler(project_root: Path) -> bool:
    """Remove the PocketTeam insights schedule from the OS scheduler.

    Args:
        project_root: Absolute path to the project directory.

    Returns:
        True if something was removed, False if nothing was installed (never raises).
    """
    try:
        system = platform.system()
        if system == "Darwin":
            return _uninstall_launchd(project_root)
        elif system == "Linux":
            return _uninstall_crontab(project_root)
        elif system == "Windows":
            return _uninstall_schtasks(project_root)
        else:
            return _uninstall_crontab(project_root)
    except Exception:
        return False


def scheduler_status(project_root: Path) -> dict[str, object]:
    """Return current scheduler registration status.

    Args:
        project_root: Absolute path to the project directory.

    Returns:
        dict with keys:
          - platform (str): human-readable OS name
          - registered (bool): whether the schedule is currently active
          - detail (str): short description of the current state
    """
    try:
        system = platform.system()
        if system == "Darwin":
            return _status_launchd(project_root)
        elif system == "Linux":
            return _status_crontab(project_root)
        elif system == "Windows":
            return _status_schtasks(project_root)
        else:
            return _status_crontab(project_root)
    except Exception:
        return {"platform": platform.system() or "unknown", "registered": False, "detail": "status check failed"}


# ---------------------------------------------------------------------------
# macOS: launchd
# ---------------------------------------------------------------------------

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
    plist = _plist_path(project_root)
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


def _uninstall_launchd(project_root: Path) -> bool:
    plist = _plist_path(project_root)
    if not plist.exists():
        return False
    subprocess.run(
        ["launchctl", "unload", str(plist)],
        capture_output=True,
    )
    plist.unlink(missing_ok=True)
    return True


def _status_launchd(project_root: Path) -> dict[str, object]:
    plist = _plist_path(project_root)
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
    marker = _cron_marker(project_root)
    existing = _read_crontab()
    # Remove any previous entry for this project first
    lines = [
        line for line in existing.splitlines()
        if marker not in line and not (
            "pocketteam" in line.lower() and project_root.name.lower() in line.lower()
        )
    ]
    new_entry = (
        f"{marker}\n"
        f"{cron} cd {project_root} && {_INSIGHTS_CMD}\n"
    )
    updated = "\n".join(lines).rstrip("\n") + "\n" + new_entry
    _write_crontab(updated)
    return True


def _uninstall_crontab(project_root: Path) -> bool:
    marker = _cron_marker(project_root)
    existing = _read_crontab()
    if marker not in existing:
        return False
    lines = []
    skip_next = False
    for line in existing.splitlines():
        if marker in line:
            skip_next = True
            continue
        if skip_next and "pocketteam" in line.lower():
            skip_next = False
            continue
        skip_next = False
        lines.append(line)
    _write_crontab("\n".join(lines) + "\n")
    return True


def _status_crontab(project_root: Path) -> dict[str, object]:
    try:
        marker = _cron_marker(project_root)
        existing = _read_crontab()
        registered = marker in existing
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
    task_name = _schtasks_name(project_root)
    cmd = (
        f'cd /d "{project_root}" && {_INSIGHTS_CMD}'
    )
    subprocess.run(
        [
            "schtasks", "/Create", "/F",
            "/TN", task_name,
            "/TR", f'cmd /c "{cmd}"',
            "/SC", "DAILY",
            "/ST", trigger_time,
        ],
        check=False,
        capture_output=True,
    )
    return True


def _uninstall_schtasks(project_root: Path) -> bool:
    task_name = _schtasks_name(project_root)
    subprocess.run(
        [
            "schtasks", "/Delete", "/F",
            "/TN", task_name,
        ],
        check=False,
        capture_output=True,
    )
    return True


def _status_schtasks(project_root: Path) -> dict[str, object]:
    task_name = _schtasks_name(project_root)
    result = subprocess.run(
        ["schtasks", "/Query", "/TN", task_name],
        capture_output=True,
        text=True,
    )
    registered = result.returncode == 0
    detail = "schtasks task installed" if registered else "schtasks task not found"
    return {"platform": "Windows", "registered": registered, "detail": detail}
