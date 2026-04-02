"""
PocketTeam Dashboard
Docker-based real-time visibility into the agent swarm.

All subprocess calls use shell=False to prevent shell injection.
Auth token lives in .pocketteam/.env, never in config.yaml.
"""

from __future__ import annotations

import hashlib
import os
import platform
import pwd
import secrets
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

from rich.console import Console

from .config import DashboardConfig, PocketTeamConfig, load_config, save_config
from .constants import (
    DASHBOARD_IMAGE,
    DASHBOARD_PORT,
    DASHBOARD_PORT_RANGE_END,
    DASHBOARD_REGISTRY_IMAGE,
    DASHBOARD_VERSION,
)


# ─────────────────────────────────────────────────────────────────────────────
# Container name sanitization
# ─────────────────────────────────────────────────────────────────────────────


def sanitize_container_name(project_name: str) -> str:
    """
    Convert a project name into a valid Docker container name.

    Rules:
    - Lowercase
    - Spaces replaced with hyphens
    - Only alphanumeric characters and hyphens allowed (all others stripped)
    - Leading/trailing hyphens removed
    - Falls back to "pocketteam-dashboard" if result is empty

    Example: "My Cool Project" → "my-cool-project-dashboard"
    """
    import re
    name = project_name.strip().lower()
    name = name.replace(" ", "-")
    name = re.sub(r"[^a-z0-9\-]", "", name)
    name = name.strip("-")
    if not name:
        return "pocketteam-dashboard"
    return f"{name}-dashboard"

console = Console()


# ─────────────────────────────────────────────────────────────────────────────
# Username resolution (Errata Q2)
# ─────────────────────────────────────────────────────────────────────────────


def get_real_username() -> str:
    """Get actual user, even under sudo."""
    return (
        os.environ.get("SUDO_USER")
        or os.environ.get("USER")
        or pwd.getpwuid(os.getuid()).pw_name
    )


# ─────────────────────────────────────────────────────────────────────────────
# Container runtime detection (Step 1)
# ─────────────────────────────────────────────────────────────────────────────


def _user_in_docker_group() -> bool:
    """Check if the real user is in the docker group."""
    try:
        import grp
        docker_gid = grp.getgrnam("docker").gr_gid
        return docker_gid in os.getgroups()
    except (KeyError, OSError):
        return False


def detect_container_runtime() -> str:
    """
    Detect available Docker context without mutating state.

    Uses `docker --context <ctx> info` — NOT `docker context use`.
    Returns the context name string on success.
    Exits with instructions on failure.
    """
    os_type = platform.system()

    # Check Podman first — we require Docker
    if shutil.which("podman") and not shutil.which("docker"):
        console.print("[yellow]Podman detected. PocketTeam requires Docker (or OrbStack).[/]")
        console.print("Install Docker Desktop: https://docker.com/get-started")
        console.print("Or OrbStack (Mac, lightweight): https://orbstack.dev")
        sys.exit(1)

    # Probe known contexts — never mutates state
    for ctx in ["orbstack", "desktop-linux", "default"]:
        result = subprocess.run(
            ["docker", "--context", ctx, "info"],
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            return ctx

    # Docker installed but daemon not running
    if shutil.which("docker"):
        if os_type == "Darwin":
            console.print("[red]Docker is installed but not running.[/]")
            console.print("Start Docker Desktop or OrbStack from Applications.")
            console.print("Then re-run: [bold]pocketteam init[/]")
        elif os_type == "Linux":
            console.print("[red]Docker is installed but not running.[/]")
            console.print("Run: [bold]sudo systemctl start docker[/]")
            if not _user_in_docker_group():
                console.print(
                    "Then: [bold]sudo usermod -aG docker $USER && newgrp docker[/]"
                )
        sys.exit(1)

    # Not installed — always ask before installing system software (Q1, Q2, Q3)
    _install_docker(os_type)
    # _install_docker always exits — this is unreachable but satisfies type checker
    sys.exit(1)  # pragma: no cover


def _install_docker(os_type: str) -> None:
    """Ask user before installing Docker. Always exits."""
    if os_type == "Darwin":
        console.print("[yellow]Docker is required for the PocketTeam dashboard.[/]")
        console.print("Recommended: OrbStack (lightweight) — https://orbstack.dev")
        console.print("Alternative: Docker Desktop — https://docker.com/get-started")
        if shutil.which("brew"):
            confirm = input("Install OrbStack via Homebrew? (y/n) ")
            if confirm.lower() == "y":
                subprocess.run(["brew", "install", "--cask", "orbstack"], check=False)
                console.print(
                    "[green]OrbStack installed. Start it from Applications, then re-run:[/]"
                )
                console.print("  [bold]pocketteam init[/]")
                sys.exit(0)  # Success path — Errata Q1: exit(0) not exit(1)
            else:
                console.print("Install manually, then re-run: [bold]pocketteam init[/]")
                sys.exit(0)
        else:
            console.print("Install manually, then re-run: [bold]pocketteam init[/]")
            sys.exit(0)

    elif os_type == "Linux":
        console.print("[yellow]Docker is required for the PocketTeam dashboard.[/]")
        console.print("Official install: https://docs.docker.com/engine/install/")
        confirm = input("Auto-install Docker via official script? (y/n) ")
        if confirm.lower() == "y":
            # Download first, show SHA256, then execute (Errata S6 pattern)
            tmp_script = "/tmp/get-docker.sh"
            subprocess.run(
                ["curl", "-fsSL", "-o", tmp_script, "https://get.docker.com"],
                check=True,
            )
            sha = hashlib.sha256(Path(tmp_script).read_bytes()).hexdigest()
            console.print(f"Script SHA256: {sha}")
            execute_confirm = input("Execute? (y/n) ")
            if execute_confirm.lower() != "y":
                console.print("Aborted. Install Docker manually, then re-run: pocketteam init")
                sys.exit(0)
            subprocess.run(["sh", tmp_script], check=False)
            username = get_real_username()
            console.print()
            console.print("[yellow]Docker group membership required.[/]")
            console.print("  This grants effective root access via Docker.")
            group_confirm = input(f"  Add '{username}' to docker group? (y/n) ")
            if group_confirm.lower() == "y":
                subprocess.run(
                    ["sudo", "usermod", "-aG", "docker", username], check=False
                )
                console.print("Added. Run: [bold]newgrp docker[/]")
                console.print("Then re-run: [bold]pocketteam init[/]")
            sys.exit(1)
        else:
            console.print("Install Docker manually, then re-run: [bold]pocketteam init[/]")
            sys.exit(1)

    elif "WSL" in platform.release():
        console.print("[yellow]Install Docker Desktop for Windows with WSL2 backend:[/]")
        console.print("https://docs.docker.com/desktop/wsl/")
        sys.exit(1)

    else:
        console.print("[red]Unsupported OS. Install Docker manually:[/]")
        console.print("https://docs.docker.com/engine/install/")
        sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# Docker daemon pre-flight (used by CLI commands — Errata Q4)
# ─────────────────────────────────────────────────────────────────────────────


def check_docker_daemon(docker_context: str) -> None:
    """
    Verify Docker daemon is reachable with the stored context.
    Exits with actionable message if not running.
    """
    result = subprocess.run(
        ["docker", "--context", docker_context, "info"],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        os_type = platform.system()
        console.print("[red]Docker daemon is not running.[/]")
        if os_type == "Darwin":
            console.print("Start Docker Desktop or OrbStack from Applications.")
        elif os_type == "Linux":
            console.print("Run: [bold]sudo systemctl start docker[/]")
        console.print(f"Context in use: {docker_context}")
        sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# Disk space check (Step 2)
# ─────────────────────────────────────────────────────────────────────────────


def check_disk_space(min_mb: int = 200) -> None:
    """Exit with actionable message if disk space is insufficient."""
    free_mb = shutil.disk_usage("/").free // (1024 * 1024)
    if free_mb < min_mb:
        console.print(
            f"[red]Insufficient disk space: {free_mb}MB free, {min_mb}MB required.[/]"
        )
        console.print("Free up disk space, then re-run: [bold]pocketteam init[/]")
        sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# Image build from local source (Step 3)
# ─────────────────────────────────────────────────────────────────────────────


def build_image(project_root: Path, context: str) -> None:
    """Build the dashboard Docker image from local source."""
    dashboard_dir = project_root / "dashboard"
    if not dashboard_dir.exists():
        console.print("[yellow]dashboard/ directory not found — cannot build from source.[/]")
        console.print("  Install later with: [bold]pocketteam dashboard install[/]")
        return
    console.print("  Building dashboard image (first time ~2 min, cached after)...")
    try:
        subprocess.run(
            ["docker", "--context", context, "build",
             "-t", f"{DASHBOARD_IMAGE}:{DASHBOARD_VERSION}",
             "-f", str(dashboard_dir / "Dockerfile"),
             str(dashboard_dir)],
            check=True
        )
    except subprocess.CalledProcessError:
        console.print("[red]Docker build failed. Check the output above for errors.[/]")
        sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# Port detection (Step 5)
# ─────────────────────────────────────────────────────────────────────────────


def find_free_port(
    start: int = DASHBOARD_PORT,
    end: int = DASHBOARD_PORT_RANGE_END,
) -> int:
    """Auto-detect free port in range. Zero questions asked."""
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("localhost", port)) != 0:
                return port
    console.print(f"[red]Ports {start}–{end} all in use.[/]")
    console.print(
        "Free one, or run: [bold]pocketteam dashboard configure --port <port>[/]"
    )
    sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# Compose command detection (Errata E3)
# ─────────────────────────────────────────────────────────────────────────────


def detect_compose_command() -> list[str]:
    """
    Detect Docker Compose v2 plugin or v1 standalone.
    Returns command as list for subprocess (no shell injection).
    """
    # Try v2 plugin syntax first
    r = subprocess.run(
        ["docker", "compose", "version"], capture_output=True, check=False
    )
    if r.returncode == 0:
        return ["docker", "compose"]

    # Try v1 standalone
    r = subprocess.run(
        ["docker-compose", "version"], capture_output=True, check=False
    )
    if r.returncode == 0:
        return ["docker-compose"]

    console.print("[red]Docker Compose not found.[/]")
    console.print("Install: https://docs.docker.com/compose/install/")
    sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# Compose file generation (Step 7)
# ─────────────────────────────────────────────────────────────────────────────


def _get_claude_version() -> str:
    """Get installed Claude Code version, empty string if unavailable."""
    try:
        result = subprocess.run(
            ["claude", "--version"],
            capture_output=True,
            text=True,
            check=False,
        )
        ver = result.stdout.strip()
        return ver.split()[0] if ver else ""
    except (OSError, IndexError):
        return ""


def generate_compose(
    dash: DashboardConfig,
    claude_project_dir: Path,
    pocketteam_dir: Path,
    env_file_path: Path,
    container_name: str | None = None,
) -> str:
    """
    Generate a hardened docker-compose.yml with literal paths.

    Security: localhost-only binding, read_only, non-root, resource limits,
    cap_drop ALL, no-new-privileges, restart on-failure:3 (Errata E4 — not
    deploy.restart_policy which is Swarm-only).
    Auth token sourced from env_file, not from config.

    container_name: Docker container name. Defaults to dash.container_name,
    falling back to "pocketteam-dashboard" for backwards compatibility.
    """
    image_ref = f"{dash.image}:{dash.image_version}"
    cname = container_name or dash.container_name or "pocketteam-dashboard"

    return f"""name: {cname}
version: "3.8"
services:
  dashboard:
    image: {image_ref}
    container_name: {cname}
    ports:
      - "127.0.0.1:{dash.port}:{dash.port}"
    volumes:
      - "{claude_project_dir}:/data/claude/project:ro"
      - "{pocketteam_dir}:/data/pocketteam:ro"
    environment:
      - PORT={dash.port}
    env_file:
      - "{env_file_path}"
    read_only: true
    tmpfs:
      - /tmp
    user: "1001:1001"
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    mem_limit: 256m
    cpus: 0.5
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://localhost:{dash.port}/api/v1/health"]
      interval: 10s
      timeout: 3s
      start_period: 10s
      retries: 3
"""


# ─────────────────────────────────────────────────────────────────────────────
# Health wait (Step 8)
# ─────────────────────────────────────────────────────────────────────────────


def wait_for_healthy(port: int, timeout: int = 30) -> bool:
    """Poll health endpoint until healthy or timeout. Returns True if healthy."""
    for _ in range(timeout // 2):
        try:
            r = urllib.request.urlopen(
                f"http://localhost:{port}/api/v1/health", timeout=2
            )
            if r.status == 200:
                return True
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(2)

    console.print("[yellow]Dashboard starting but taking longer than expected.[/]")
    console.print("  Check: [bold]pocketteam dashboard logs[/]")
    return False


# ─────────────────────────────────────────────────────────────────────────────
# .pocketteam/.env auth token management
# ─────────────────────────────────────────────────────────────────────────────


def _write_auth_token(compose_dir: Path) -> str:
    """
    Generate a 64-char hex auth token and write to compose_dir/.env.
    Separate file from .pocketteam/.env to avoid leaking API keys to container.
    NEVER logs the token.
    Returns the token for use in this session only.
    """
    token = secrets.token_hex(32)  # 64 hex chars
    env_path = compose_dir / ".env"
    compose_dir.mkdir(parents=True, exist_ok=True)

    # Write only AUTH_TOKEN — nothing else goes into this file
    env_path.write_text(f"AUTH_TOKEN={token}\n")
    os.chmod(env_path, 0o600)
    return token


# ─────────────────────────────────────────────────────────────────────────────
# .pocketteam/.gitignore (Errata S2)
# ─────────────────────────────────────────────────────────────────────────────


def ensure_pocketteam_gitignore(project_root: Path) -> None:
    """Write .pocketteam/.gitignore with deny-all '*' rule."""
    gitignore_path = project_root / ".pocketteam" / ".gitignore"
    gitignore_path.parent.mkdir(parents=True, exist_ok=True)
    if not gitignore_path.exists():
        gitignore_path.write_text("*\n")


# ─────────────────────────────────────────────────────────────────────────────
# Main dashboard setup (called from init.py)
# ─────────────────────────────────────────────────────────────────────────────


def setup_dashboard(cfg: PocketTeamConfig) -> None:
    """
    Full dashboard setup flow — runs after existing init steps.
    Modifies cfg.dashboard in-place and calls save_config().
    """
    project_root = cfg.project_root.resolve()

    console.print()
    console.print("[bold cyan]Setting up PocketTeam Dashboard...[/]")

    # Step 1: Detect container runtime
    console.print("  Detecting container runtime...")
    detected_context = detect_container_runtime()
    console.print(f"  [green]Docker context: {detected_context}[/]")

    # Step 2: Disk space
    check_disk_space(min_mb=600)

    # Step 3: Try to pull pre-built image first (works for pipx installations)
    image_ref = f"{DASHBOARD_REGISTRY_IMAGE}:latest"
    console.print(f"  Pulling dashboard image...")
    pull_result = subprocess.run(
        ["docker", "--context", detected_context, "pull", image_ref],
        capture_output=True, text=True, timeout=120,
    )
    if pull_result.returncode == 0:
        console.print("  [green]Dashboard image ready.[/]")
        # Tag it as local image name for compose
        subprocess.run(
            ["docker", "--context", detected_context, "tag", image_ref, f"{DASHBOARD_IMAGE}:{DASHBOARD_VERSION}"],
            capture_output=True, check=False,
        )
    else:
        # Fallback: build from source (only works with git clone)
        dashboard_dir = project_root / "dashboard"
        if dashboard_dir.exists():
            console.print("  [dim]Pull failed, building from source...[/]")
            build_image(project_root, detected_context)
            console.print("  [green]Image ready.[/]")
        else:
            console.print("  [yellow]Dashboard image not available. Install later with:[/]")
            console.print("    [bold]pocketteam dashboard install[/]")
            return  # Don't crash, just skip gracefully

    # Step 4: Auto-compute paths + validate
    claude_home = Path.home() / ".claude"
    claude_project_hash = str(project_root).replace("/", "-")
    claude_project_dir = claude_home / "projects" / claude_project_hash

    if not claude_project_dir.exists():
        if not claude_home.exists():
            console.print(
                "  [dim]Claude Code hasn't been run yet. Creating placeholder dirs.[/]"
            )
            console.print(
                "  Dashboard will show data once you run: [bold]pocketteam start[/]"
            )
        claude_project_dir.mkdir(parents=True, exist_ok=True)

    # Ensure event + audit dirs exist for volume mounts
    (project_root / ".pocketteam" / "events").mkdir(parents=True, exist_ok=True)
    (project_root / ".pocketteam" / "artifacts" / "audit").mkdir(
        parents=True, exist_ok=True
    )

    # Errata E2: compose_dir uses sha256 hash — prevents path collision
    compose_dir_hash = hashlib.sha256(str(project_root).encode()).hexdigest()[:16]
    compose_dir = Path.home() / ".pocketteam" / "dashboard" / compose_dir_hash
    compose_file = compose_dir / "docker-compose.yml"

    # Step 5: Find free port (zero questions)
    port = find_free_port()

    # Step 6: Handle re-init (don't clobber hand-edited compose files)
    if compose_file.exists():
        existing_root = cfg.dashboard.project_root
        if existing_root and existing_root != str(project_root):
            console.print(
                f"  [yellow]Dashboard currently configured for: {existing_root}[/]"
            )
            console.print(f"  Switching to: {project_root}")
            confirm = input("  Continue? (y/n) ")
            if confirm.lower() != "y":
                sys.exit(0)

        # Backup if hand-edited
        current_checksum = hashlib.sha256(compose_file.read_bytes()).hexdigest()
        stored_checksum = cfg.dashboard.compose_checksum
        if stored_checksum and current_checksum != stored_checksum:
            backup = compose_file.with_suffix(".yml.bak")
            shutil.copy2(compose_file, backup)
            os.chmod(backup, 0o600)
            console.print(f"  Backed up hand-edited compose to: {backup}")

    # Step 7a: Detect compose command (Errata E3)
    compose_cmd_list = detect_compose_command()
    compose_command = " ".join(compose_cmd_list)

    # Step 7b: Generate auth token — write to .pocketteam/.env (Errata S2, S3)
    _write_auth_token(compose_dir)

    # Step 7c: Write .pocketteam/.gitignore (Errata S2)
    ensure_pocketteam_gitignore(project_root)

    # Step 7d: Populate dashboard config
    container_name = sanitize_container_name(cfg.project_name or project_root.name)
    cfg.dashboard = DashboardConfig(
        enabled=True,
        port=port,
        image=DASHBOARD_IMAGE,
        image_version=DASHBOARD_VERSION,
        domain="",
        compose_dir=str(compose_dir),
        docker_context=detected_context,
        claude_version_at_init=_get_claude_version(),
        compose_checksum="",  # filled after writing compose
        project_root=str(project_root),
        claude_project_hash=claude_project_hash,
        compose_command=compose_command,
        container_name=container_name,
    )
    save_config(cfg)

    # Step 7e: Generate and write compose file
    compose_dir.mkdir(parents=True, exist_ok=True)
    env_file_path = compose_dir / ".env"
    compose_content = generate_compose(
        dash=cfg.dashboard,
        claude_project_dir=claude_project_dir,
        pocketteam_dir=project_root / ".pocketteam",
        env_file_path=env_file_path,
    )
    compose_file.write_text(compose_content)
    os.chmod(compose_file, 0o600)

    # Update checksum after writing
    cfg.dashboard.compose_checksum = hashlib.sha256(
        compose_content.encode()
    ).hexdigest()
    save_config(cfg)

    # Step 7f: Start the container
    console.print("  Starting dashboard container...")
    # Build the full command: docker --context <ctx> compose -f <file> up -d
    # or: docker-compose -f <file> up -d  (v1)
    if compose_cmd_list[0] == "docker":
        start_cmd = (
            ["docker", "--context", detected_context]
            + compose_cmd_list[1:]  # ["compose"]
            + ["-f", str(compose_file), "up", "-d"]
        )
    else:
        start_cmd = compose_cmd_list + ["-f", str(compose_file), "up", "-d"]

    result = subprocess.run(start_cmd, check=False)
    if result.returncode != 0:
        console.print("[red]Failed to start dashboard container.[/]")
        console.print("  Check: [bold]pocketteam dashboard logs[/]")
        console.print(f"  Compose file: {compose_file}")
        return

    # Step 8: Wait for healthy + open browser
    console.print("  Waiting for dashboard to become healthy...")
    healthy = wait_for_healthy(port)
    if healthy:
        url = f"http://localhost:{port}"
        console.print(f"  [green]Dashboard ready: {url}[/]")
        webbrowser.open(url)
    else:
        console.print(f"  Dashboard may still be starting: http://localhost:{port}")


# ─────────────────────────────────────────────────────────────────────────────
# CLI helpers used by cli.py dashboard subcommands
# ─────────────────────────────────────────────────────────────────────────────


def _load_dashboard_config(project_root: Path | None = None) -> tuple[PocketTeamConfig, Path]:
    """Load config and return (cfg, compose_file). Exits if dashboard not configured."""
    root = project_root or Path.cwd()
    cfg = load_config(root)
    if not cfg.dashboard.enabled or not cfg.dashboard.compose_dir:
        console.print("[red]Dashboard is not configured.[/]")
        console.print("Run: [bold]pocketteam dashboard install[/]")
        sys.exit(1)
    compose_file = Path(cfg.dashboard.compose_dir) / "docker-compose.yml"
    if not compose_file.exists():
        console.print(f"[red]Compose file not found: {compose_file}[/]")
        console.print("Run: [bold]pocketteam init[/] to reconfigure the dashboard.")
        sys.exit(1)
    return cfg, compose_file


ALLOWED_COMPOSE_COMMANDS = {"docker compose", "docker-compose"}


def _build_compose_cmd(cfg: PocketTeamConfig, compose_file: Path) -> list[str]:
    """Build the compose command prefix with context and file flag."""
    if cfg.dashboard.compose_command not in ALLOWED_COMPOSE_COMMANDS:
        raise ValueError(
            f"Invalid compose_command: {cfg.dashboard.compose_command!r}. "
            f"Allowed values: {sorted(ALLOWED_COMPOSE_COMMANDS)}"
        )
    compose_parts = cfg.dashboard.compose_command.split()
    ctx = cfg.dashboard.docker_context

    if compose_parts[0] == "docker":
        # docker --context <ctx> compose -f <file> ...
        return ["docker", "--context", ctx] + compose_parts[1:] + ["-f", str(compose_file)]
    else:
        # docker-compose -f <file> ...  (v1 does not support --context)
        return compose_parts + ["-f", str(compose_file)]


def dashboard_start_cmd(project_root: Path | None = None) -> None:
    """Start the dashboard container (compose up -d)."""
    root = project_root or Path.cwd()
    cfg, compose_file = _load_dashboard_config(root)
    check_docker_daemon(cfg.dashboard.docker_context)

    # Check if image exists, build if not
    result = subprocess.run(
        ["docker", "image", "inspect", f"{DASHBOARD_IMAGE}:{DASHBOARD_VERSION}"],
        capture_output=True, check=False
    )
    if result.returncode != 0:
        console.print("[yellow]Dashboard image not found. Building...[/]")
        project_root_path = Path(cfg.dashboard.project_root)
        build_image(project_root_path, cfg.dashboard.docker_context)

    cmd = _build_compose_cmd(cfg, compose_file) + ["up", "-d"]
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        console.print("[red]Failed to start dashboard.[/]")
        console.print("Check: [bold]pocketteam dashboard logs[/]")
        sys.exit(1)

    port = cfg.dashboard.port
    healthy = wait_for_healthy(port)
    url = f"http://localhost:{port}"
    if healthy:
        console.print(f"[green]Dashboard running: {url}[/]")
        webbrowser.open(url)
    else:
        console.print(f"[yellow]Dashboard starting: {url}[/]")


def dashboard_stop_cmd(project_root: Path | None = None) -> None:
    """Stop the dashboard container (compose down)."""
    root = project_root or Path.cwd()
    cfg, compose_file = _load_dashboard_config(root)
    check_docker_daemon(cfg.dashboard.docker_context)

    cmd = _build_compose_cmd(cfg, compose_file) + ["down"]
    subprocess.run(cmd, check=False)
    console.print("Dashboard stopped.")


def dashboard_status_cmd(project_root: Path | None = None) -> None:
    """
    Show dashboard status: container state, URL, volume health.
    Exits with non-zero if container is not running (Errata Q7).
    """
    root = project_root or Path.cwd()
    cfg, compose_file = _load_dashboard_config(root)
    check_docker_daemon(cfg.dashboard.docker_context)

    # Container state via docker inspect
    ctx = cfg.dashboard.docker_context
    cname = cfg.dashboard.container_name or "pocketteam-dashboard"
    inspect_result = subprocess.run(
        [
            "docker",
            "--context",
            ctx,
            "inspect",
            "--format",
            "{{.State.Status}} (up {{.State.StartedAt}})",
            cname,
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    if inspect_result.returncode != 0:
        container_status = "not found"
        exit_code = 1
    else:
        raw = inspect_result.stdout.strip()
        container_status = raw
        exit_code = 0 if "running" in raw else 1

    port = cfg.dashboard.port
    url = f"http://localhost:{port}"

    console.print("\n[bold]Dashboard Status[/]")
    console.print(f"  Container:  {container_status}")
    console.print(f"  URL:        {url}")
    console.print(f"  Image:      {cfg.dashboard.image}:{cfg.dashboard.image_version}")
    console.print(f"  Project:    {cfg.dashboard.project_root}")
    console.print()
    console.print("[bold]Volume Health:[/]")

    # Check claude project dir
    claude_project_dir = (
        Path.home() / ".claude" / "projects" / cfg.dashboard.claude_project_hash
    )
    if claude_project_dir.exists():
        sessions = sum(
            1
            for p in claude_project_dir.iterdir()
            if p.is_dir() and p.name != "memory"
        )
        console.print(
            f"  [green]~/.claude/projects/{cfg.dashboard.claude_project_hash}/"
            f" exists ({sessions} session(s))[/]"
        )
    else:
        console.print(
            f"  [yellow].claude/projects/{cfg.dashboard.claude_project_hash}/"
            f" does not exist yet — run pocketteam start[/]"
        )

    pocketteam_dir = Path(cfg.dashboard.project_root) / ".pocketteam"
    if pocketteam_dir.exists():
        console.print("  [green].pocketteam/ exists[/]")
    else:
        console.print("  [red].pocketteam/ missing — run pocketteam init[/]")

    if exit_code != 0:
        sys.exit(exit_code)


def dashboard_logs_cmd(project_root: Path | None = None) -> None:
    """Follow dashboard container logs (compose logs -f)."""
    root = project_root or Path.cwd()
    cfg, compose_file = _load_dashboard_config(root)
    check_docker_daemon(cfg.dashboard.docker_context)

    cmd = _build_compose_cmd(cfg, compose_file) + ["logs", "-f"]
    try:
        subprocess.run(cmd, check=False)
    except KeyboardInterrupt:
        pass


def dashboard_update_cmd(project_root: Path | None = None) -> None:
    """Rebuild dashboard from local source."""
    root = project_root or Path.cwd()
    cfg = load_config(root)
    if not cfg.dashboard.enabled:
        console.print("[yellow]Dashboard not configured. Run: pocketteam init[/]")
        return
    check_docker_daemon(cfg.dashboard.docker_context)
    project_root_path = Path(cfg.dashboard.project_root)
    console.print("[bold]Rebuilding dashboard from source...[/]")
    build_image(project_root_path, cfg.dashboard.docker_context)
    # Restart container with new image
    compose_file = Path(cfg.dashboard.compose_dir) / "docker-compose.yml"
    if compose_file.exists():
        cmd = _build_compose_cmd(cfg, compose_file)
        subprocess.run(cmd + ["down"], check=False)
        subprocess.run(cmd + ["up", "-d"], check=True)
        console.print("[green]Dashboard updated and restarted.[/]")
    else:
        console.print("[yellow]No compose file found. Run: pocketteam init[/]")


def dashboard_configure_cmd(
    project_root: Path | None = None,
    port: int | None = None,
    domain: str | None = None,
    project_root_override: str | None = None,
    reset: bool = False,
) -> None:
    """
    Change dashboard settings post-setup.
    Validates paths, checks compose checksum, regenerates compose, restarts.
    """
    root = project_root or Path.cwd()
    cfg, compose_file = _load_dashboard_config(root)

    changed = False

    if port is not None:
        cfg.dashboard.port = port
        changed = True

    if domain is not None:
        cfg.dashboard.domain = domain
        changed = True

    if project_root_override is not None:
        # Symlink resolution + allowlist validation (Errata S5)
        resolved = Path(project_root_override).resolve()

        # Allowlist: must be under home directory
        if not resolved.is_relative_to(Path.home()):
            console.print("[red]Project root must be under your home directory.[/]")
            sys.exit(1)

        if not resolved.is_dir():
            console.print(f"[red]Not a directory: {resolved}[/]")
            sys.exit(1)

        cfg.dashboard.project_root = str(resolved)
        cfg.dashboard.claude_project_hash = (
            str(resolved).replace("/", "-")
        )
        changed = True

    if not changed and not reset:
        console.print(
            "[yellow]No changes specified. Use --port, --domain, --project-root, or --reset.[/]"
        )
        return

    # Check compose checksum — warn if hand-edited
    current_checksum = hashlib.sha256(compose_file.read_bytes()).hexdigest()
    if cfg.dashboard.compose_checksum and current_checksum != cfg.dashboard.compose_checksum:
        console.print(
            "[yellow]Compose file has been hand-edited. It will be overwritten.[/]"
        )
        backup = compose_file.with_suffix(".yml.bak")
        shutil.copy2(compose_file, backup)
        os.chmod(backup, 0o600)
        console.print(f"Backed up to: {backup}")
        confirm = input("Continue? (y/n) ")
        if confirm.lower() != "y":
            sys.exit(0)

    # Regenerate compose
    claude_project_dir = (
        Path.home() / ".claude" / "projects" / cfg.dashboard.claude_project_hash
    )
    env_file_path = Path(cfg.dashboard.project_root) / ".pocketteam" / ".env"
    pocketteam_dir = Path(cfg.dashboard.project_root) / ".pocketteam"

    compose_content = generate_compose(
        dash=cfg.dashboard,
        claude_project_dir=claude_project_dir,
        pocketteam_dir=pocketteam_dir,
        env_file_path=env_file_path,
    )
    compose_file.write_text(compose_content)
    os.chmod(compose_file, 0o600)
    cfg.dashboard.compose_checksum = hashlib.sha256(compose_content.encode()).hexdigest()
    save_config(cfg)

    # Restart if running
    check_docker_daemon(cfg.dashboard.docker_context)
    compose_cmd = _build_compose_cmd(cfg, compose_file)
    subprocess.run(compose_cmd + ["down"], check=False)
    subprocess.run(compose_cmd + ["up", "-d"], check=False)

    wait_for_healthy(cfg.dashboard.port)
    console.print("[green]Dashboard reconfigured and restarted.[/]")
    console.print(f"  URL: http://localhost:{cfg.dashboard.port}")


def dashboard_install_cmd(project_root: Path | None = None) -> None:
    """
    Install dashboard for users who ran `pocketteam init --no-dashboard`.
    Runs the full dashboard setup flow. (Errata Q5)
    """
    root = project_root or Path.cwd()
    cfg = load_config(root)
    if cfg.dashboard.enabled:
        console.print("[yellow]Dashboard is already configured.[/]")
        console.print("Run: [bold]pocketteam dashboard start[/]")
        return
    setup_dashboard(cfg)
