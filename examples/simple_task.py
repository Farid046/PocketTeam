"""
Simple example: Run a task through the PocketTeam pipeline.

Usage:
    python examples/simple_task.py "Build user authentication with OAuth2"
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path


async def main():
    from pocketteam.core.orchestrator import run_task

    if len(sys.argv) < 2:
        print("Usage: python examples/simple_task.py <task>")
        sys.exit(1)

    task = sys.argv[1]
    project_root = Path.cwd()

    print(f"Running task: {task}")
    print(f"Project: {project_root}")
    print()

    async def on_status(message: str) -> None:
        print(f"  [{message}]")

    async def on_approval(prompt: str) -> bool:
        print(f"\n  APPROVAL NEEDED: {prompt}")
        response = input("  Approve? (y/n): ").strip().lower()
        return response in ("y", "yes")

    success = await run_task(
        task_description=task,
        project_root=project_root,
        on_status=on_status,
        on_approval=on_approval,
    )

    if success:
        print("\nPipeline completed successfully!")
    else:
        print("\nPipeline failed.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
