"""systemd user-unit management for Telegram daemon. Linux only."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from pocketteam.telegram_daemon import _slugify

_SERVICE_NAME_PREFIX = "pocketteam-telegram"


def is_linux() -> bool:
    return sys.platform == "linux"


def is_systemd_available() -> tuple[bool, str]:
    """Check whether systemd user instance is available.

    Returns (True, "") on success.
    Returns (False, reason) with a user-readable explanation on failure.
    Accepts returncode 0 or 1 — systemd --user status exits 1 when degraded
    (common on Hetzner cloud-init images), but the bus is still usable.
    """
    systemctl = _find_systemctl()
    if not systemctl:
        return False, "systemctl not found — systemd is not installed"

    try:
        result = subprocess.run(
            [systemctl, "--user", "is-system-running"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        # rc 0 = running, rc 1 = degraded — both usable
        if result.returncode in (0, 1):
            # Distinguish genuine D-Bus failures (bus unavailable, not just degraded)
            if "Failed to connect" in result.stderr or "bus" in result.stderr.lower():
                return False, f"systemd user bus unavailable: {result.stderr.strip()}"
            return True, ""
        # rc 3 = not running / offline
        return False, f"systemd --user not running (rc={result.returncode}): {result.stdout.strip()}"
    except FileNotFoundError:
        return False, "systemctl not found"
    except subprocess.TimeoutExpired:
        return False, "systemctl timed out — systemd may not be running"
    except Exception as exc:
        return False, f"systemd check failed: {exc}"


def _find_systemctl() -> str | None:
    import shutil
    for candidate in ["/usr/bin/systemctl", "/bin/systemctl"]:
        if os.path.isfile(candidate):
            return candidate
    return shutil.which("systemctl")


def _service_name(project_root: Path) -> str:
    return f"{_SERVICE_NAME_PREFIX}-{_slugify(project_root.name)}"


def _service_path(project_root: Path) -> Path:
    return Path.home() / ".config" / "systemd" / "user" / f"{_service_name(project_root)}.service"


def generate_unit(project_root: Path) -> str:
    """Generate a systemd user unit INI string for the given project root."""
    home = str(Path.home())
    log_dir = project_root / ".pocketteam" / "logs"
    python = sys.executable
    name = _service_name(project_root)

    return (
        "[Unit]\n"
        f"Description=PocketTeam Telegram Auto-Session Daemon ({project_root.name})\n"
        "After=network-online.target\n"
        "Wants=network-online.target\n"
        "\n"
        "[Service]\n"
        f"ExecStart={python} -m pocketteam.telegram_daemon --project-root {project_root}\n"
        f"WorkingDirectory={project_root}\n"
        "Restart=on-failure\n"
        "RestartSec=10\n"
        f"Environment=HOME={home}\n"
        f"Environment=PATH={home}/.bun/bin:{home}/.local/bin:{home}/.claude:/usr/local/bin:/usr/bin:/bin\n"
        f"StandardOutput=append:{log_dir}/telegram-daemon.stdout.log\n"
        f"StandardError=append:{log_dir}/telegram-daemon.stderr.log\n"
        "\n"
        "[Install]\n"
        f"WantedBy=default.target\n"
    )


def install_systemd_service(project_root: Path) -> tuple[bool, str]:
    """Install and enable the systemd user unit. Idempotent — safe on re-init.

    Returns (True, message) on success, (False, reason) on failure.
    """
    if not is_linux():
        return False, "systemd units are only supported on Linux"

    available, reason = is_systemd_available()
    if not available:
        return False, reason

    # Reject paths with spaces — systemd ExecStart is unreliable with them
    if " " in str(project_root):
        return False, f"project path contains spaces: {project_root!r} — move to a path without spaces"

    # Ensure log directory exists before systemd tries to open it
    log_dir = project_root / ".pocketteam" / "logs"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        return False, f"could not create log directory {log_dir}: {exc}"

    service_path = _service_path(project_root)
    name = _service_name(project_root)
    systemctl = _find_systemctl()

    # Stop any previously installed version (idempotent — ignore errors)
    if service_path.exists():
        subprocess.run(
            [systemctl, "--user", "stop", name],
            capture_output=True,
        )

    # Write service file
    service_path.parent.mkdir(parents=True, exist_ok=True)
    service_path.write_text(generate_unit(project_root))
    service_path.chmod(0o600)

    # Reload systemd manager configuration
    subprocess.run([systemctl, "--user", "daemon-reload"], capture_output=True)

    # Enable and start the service
    enable_result = subprocess.run(
        [systemctl, "--user", "enable", "--now", name],
        capture_output=True,
        text=True,
    )
    if enable_result.returncode != 0:
        return False, f"systemctl enable failed: {enable_result.stderr.strip()}"

    # Attempt to enable linger so the daemon survives user logout
    linger_enabled = _enable_linger()

    if linger_enabled:
        return True, f"Telegram daemon installed (linger enabled — daemon persists after logout)"
    else:
        return True, (
            f"Telegram daemon installed (warning: linger not enabled — "
            f"daemon stops at logout; run: loginctl enable-linger $USER)"
        )


def _enable_linger() -> bool:
    """Enable systemd linger for current user. Returns True if linger is active."""
    username = os.environ.get("USER") or os.environ.get("LOGNAME") or ""
    if username:
        try:
            subprocess.run(
                ["loginctl", "enable-linger", username],
                capture_output=True,
                timeout=10,
            )
        except Exception:
            pass

    # Verify linger is actually set
    try:
        verify = subprocess.run(
            ["loginctl", "show-user", "-p", "Linger"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if verify.returncode == 0 and "Linger=yes" in verify.stdout:
            return True
    except Exception:
        pass

    return False


def uninstall_systemd_service(project_root: Path) -> bool:
    """Disable and remove the systemd user unit. Returns True if something was removed."""
    if not is_linux():
        return False

    service_path = _service_path(project_root)
    if not service_path.exists():
        return False

    name = _service_name(project_root)
    systemctl = _find_systemctl()

    subprocess.run(
        [systemctl, "--user", "disable", "--now", name],
        capture_output=True,
    )
    service_path.unlink(missing_ok=True)
    subprocess.run([systemctl, "--user", "daemon-reload"], capture_output=True)
    return True
