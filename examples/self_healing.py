"""
Self-healing example: Monitor a production endpoint and auto-fix issues.

Usage:
    python examples/self_healing.py --url https://myapp.com/health
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path


async def main():
    from pocketteam.monitoring.watcher import Watcher
    from pocketteam.config import PocketTeamConfig, MonitoringConfig

    url = "http://localhost:3000/health"
    for i, arg in enumerate(sys.argv):
        if arg == "--url" and i + 1 < len(sys.argv):
            url = sys.argv[i + 1]

    project_root = Path.cwd()
    config = PocketTeamConfig(
        project_root=project_root,
        health_url=url,
        monitoring=MonitoringConfig(health_url=url),
    )

    print(f"Monitoring: {url}")
    print("Press Ctrl+C to stop\n")

    async def on_status(message: str) -> None:
        print(f"  [{message}]")

    async def on_health_failure(health_result) -> None:
        print(f"  HEALTH FAILURE: {health_result.error}")
        print("  Investigator would wake up here...")

    watcher = Watcher(
        project_root,
        config=config,
        on_status=on_status,
        on_health_failure=on_health_failure,
    )

    try:
        await watcher.start()
    except KeyboardInterrupt:
        watcher.stop()
        print("\nStopped.")


if __name__ == "__main__":
    asyncio.run(main())
