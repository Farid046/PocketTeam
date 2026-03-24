"""
Full pipeline example with Telegram integration.

Usage:
    export TELEGRAM_BOT_TOKEN=...
    export TELEGRAM_CHAT_ID=...
    python examples/full_pipeline.py "Create a REST API with CRUD endpoints"
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path


async def main():
    from pocketteam.channels.setup import TelegramChannel
    from pocketteam.config import load_config
    from pocketteam.core.orchestrator import run_task

    if len(sys.argv) < 2:
        print("Usage: python examples/full_pipeline.py <task>")
        sys.exit(1)

    task = sys.argv[1]
    project_root = Path.cwd()
    config = load_config(project_root)

    # Setup Telegram channel
    telegram = TelegramChannel(project_root, config=config)

    async def on_status(message: str) -> None:
        print(f"  [{message}]")
        if telegram.is_configured:
            await telegram.send_message(message)

    async def on_approval(prompt: str) -> bool:
        if telegram.is_configured:
            import uuid
            request_id = f"gate-{uuid.uuid4().hex[:8]}"
            return await telegram.send_approval_request(prompt, request_id)
        # Fallback to CLI
        print(f"\n  APPROVAL NEEDED: {prompt}")
        response = input("  Approve? (y/n): ").strip().lower()
        return response in ("y", "yes")

    print(f"Task: {task}")
    print(f"Project: {project_root}")
    print(f"Telegram: {'configured' if telegram.is_configured else 'not configured'}")
    print()

    success = await run_task(
        task_description=task,
        project_root=project_root,
        skip_product=False,  # Full pipeline includes product validation
        on_status=on_status,
        on_approval=on_approval,
    )

    if success:
        print("\nPipeline completed successfully!")
        if telegram.is_configured:
            await telegram.send_message("Pipeline completed!")
    else:
        print("\nPipeline failed.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
