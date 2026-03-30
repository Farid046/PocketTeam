"""
Shared fixtures for SDK integration tests.

Provides:
- fake_app: Starts/stops the fake HTTP server as a subprocess
- fake_app_url: Base URL of the running fake app
- chaos: Helper to toggle chaos modes
- project_root: Temporary project directory with PocketTeam config
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Generator

import pytest
import yaml


@pytest.fixture(scope="session")
def fake_app() -> Generator[tuple[subprocess.Popen, int], None, None]:
    """Start the fake app as a subprocess, yield (process, port), then kill it."""
    proc = subprocess.Popen(
        [sys.executable, "-m", "tests.sdk_integration.fake_app", "--port", "0"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=str(Path(__file__).resolve().parents[2]),  # project root
    )

    # Wait for READY:<port> signal
    port = 0
    deadline = time.time() + 10
    while time.time() < deadline:
        line = proc.stdout.readline().strip()
        if line.startswith("READY:"):
            port = int(line.split(":")[1])
            break
        if proc.poll() is not None:
            stderr = proc.stderr.read()
            raise RuntimeError(f"Fake app died on startup: {stderr}")

    if port == 0:
        proc.kill()
        raise RuntimeError("Fake app did not signal READY within 10s")

    yield proc, port

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture(scope="session")
def fake_app_url(fake_app: tuple[subprocess.Popen, int]) -> str:
    """Base URL of the running fake app."""
    _, port = fake_app
    return f"http://127.0.0.1:{port}"


class ChaosClient:
    """Helper to interact with the fake app's chaos endpoints."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url

    def set(self, **kwargs) -> dict:
        """Update chaos state. E.g. chaos.set(health_status=500, log_errors=3)"""
        data = json.dumps(kwargs).encode()
        req = urllib.request.Request(
            f"{self.base_url}/chaos",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read())

    def reset(self) -> dict:
        """Reset to healthy state."""
        req = urllib.request.Request(
            f"{self.base_url}/reset",
            data=b"",
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read())

    def get(self) -> dict:
        """Get current chaos state."""
        with urllib.request.urlopen(f"{self.base_url}/chaos", timeout=5) as resp:
            return json.loads(resp.read())


@pytest.fixture()
def chaos(fake_app_url: str) -> Generator[ChaosClient, None, None]:
    """Chaos client — resets after each test."""
    client = ChaosClient(fake_app_url)
    client.reset()
    yield client
    client.reset()


@pytest.fixture()
def project_root(tmp_path: Path, fake_app_url: str) -> Path:
    """
    Temporary project directory with minimal PocketTeam config.
    Points health_url at the fake app.
    """
    pt_dir = tmp_path / ".pocketteam"
    pt_dir.mkdir()
    (pt_dir / "artifacts" / "incidents").mkdir(parents=True)
    (pt_dir / "events").mkdir()

    config = {
        "project": {
            "name": "sdk-test-project",
            "health_url": f"{fake_app_url}/health",
        },
        "auth": {"mode": "api_key", "api_key": "$ANTHROPIC_API_KEY"},
        "telegram": {
            "bot_token": "",
            "chat_id": "",
        },
        "monitoring": {
            "enabled": True,
            "auto_fix": True,
            "staging_first": True,
            "max_fix_attempts": 3,
        },
        "github_actions": {
            "enabled": True,
            "schedule": "0 * * * *",
        },
        "budget": {"max_per_task": 5.0},
    }

    (pt_dir / "config.yaml").write_text(yaml.dump(config))

    # Minimal git init so agents can work
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=False)

    return tmp_path
