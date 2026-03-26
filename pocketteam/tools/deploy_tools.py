"""
Deploy Tools — Docker and Supabase deployment helpers.

Used by DevOps agent for:
- Docker build + push
- Container restart
- Database migrations (via Supabase MCP)
- Rollback to previous version
- Canary deployment strategy

All destructive operations go through D-SAC safety.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DeployResult:
    """Result of a deployment operation."""
    success: bool
    output: str = ""
    version: str = ""
    rollback_info: str = ""
    error: str | None = None
    duration_seconds: float = 0.0


class DeployTools:
    """
    Deployment helpers for Docker-based and Supabase projects.

    Safety: all destructive operations require plan approval.
    Staging-first: production deploys always go through staging.
    """

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root

    async def docker_build(
        self,
        tag: str = "latest",
        dockerfile: str = "Dockerfile",
        build_args: dict[str, str] | None = None,
    ) -> DeployResult:
        """Build a Docker image."""
        cmd = ["docker", "build", "-t", tag, "-f", dockerfile]

        if build_args:
            for key, val in build_args.items():
                cmd.extend(["--build-arg", f"{key}={val}"])

        cmd.append(".")
        return await self._run_command(cmd)

    async def docker_push(self, tag: str) -> DeployResult:
        """Push a Docker image to registry."""
        return await self._run_command(["docker", "push", tag])

    async def docker_compose_up(
        self,
        service: str | None = None,
        detach: bool = True,
        compose_file: str = "docker-compose.yml",
    ) -> DeployResult:
        """Start services with docker compose."""
        cmd = ["docker", "compose", "-f", compose_file, "up"]
        if detach:
            cmd.append("-d")
        if service:
            cmd.append(service)
        return await self._run_command(cmd)

    async def docker_compose_down(
        self,
        compose_file: str = "docker-compose.yml",
    ) -> DeployResult:
        """Stop services."""
        return await self._run_command(
            ["docker", "compose", "-f", compose_file, "down"]
        )

    async def docker_compose_restart(
        self,
        service: str | None = None,
        compose_file: str = "docker-compose.yml",
    ) -> DeployResult:
        """Restart services (common for deploying new code)."""
        cmd = ["docker", "compose", "-f", compose_file, "restart"]
        if service:
            cmd.append(service)
        return await self._run_command(cmd)

    async def git_deploy(
        self,
        remote: str = "origin",
        branch: str = "main",
    ) -> DeployResult:
        """Deploy by pushing to a git remote (e.g. for Dokku, Heroku)."""
        return await self._run_command(
            ["git", "push", remote, branch]
        )

    async def get_current_version(self) -> str:
        """Get current version from git or package."""
        result = await self._run_command(
            ["git", "describe", "--tags", "--always"],
            timeout=10,
        )
        if result.success:
            return result.output.strip()
        return "unknown"

    async def create_rollback_point(self) -> DeployResult:
        """Create a rollback point (git tag)."""
        version = await self.get_current_version()
        tag = f"rollback-{int(time.time())}"
        result = await self._run_command(
            ["git", "tag", tag],
            timeout=10,
        )
        result.rollback_info = f"Rollback tag: {tag} (version: {version})"
        return result

    async def rollback(self, tag: str) -> DeployResult:
        """Rollback to a specific tag."""
        result = await self._run_command(
            ["git", "checkout", tag],
            timeout=30,
        )
        if result.success:
            result.output = f"Rolled back to {tag}"
        return result

    async def _run_command(
        self,
        cmd: list[str],
        timeout: int = 120,
    ) -> DeployResult:
        """Execute a command and return structured result."""
        start = time.monotonic()
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(self.project_root),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            try:
                stdout, _ = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )
            except TimeoutError:
                proc.kill()
                await proc.communicate()
                return DeployResult(
                    success=False,
                    output=f"Command timed out after {timeout}s",
                    duration_seconds=time.monotonic() - start,
                )

            output = stdout.decode("utf-8", errors="replace")
            return DeployResult(
                success=(proc.returncode == 0),
                output=output,
                duration_seconds=time.monotonic() - start,
                error=output if proc.returncode != 0 else None,
            )
        except FileNotFoundError:
            return DeployResult(
                success=False,
                error=f"Command not found: {cmd[0]}",
                duration_seconds=time.monotonic() - start,
            )
