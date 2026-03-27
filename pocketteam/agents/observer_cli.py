"""
Observer CLI — Background Entry Point (Stage 2 of 2).

Called by observer_trigger.py as a detached background subprocess.
Runs the programmatic ObserverAgent analysis and emits findings to
the event stream.

Usage:
    python -m pocketteam.agents.observer_cli <project_root>
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(1)

    project_root = Path(sys.argv[1])
    if not project_root.exists():
        sys.exit(1)

    from pocketteam.agents.observer import ObserverAgent

    observer = ObserverAgent(project_root)
    asyncio.run(observer.analyze_task())


if __name__ == "__main__":
    main()
