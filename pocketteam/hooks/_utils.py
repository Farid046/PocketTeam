"""
Shared utilities for PocketTeam hooks.
"""

from pathlib import Path


def _find_pocketteam_dir() -> Path | None:
    """Walk up from cwd to find the .pocketteam/ directory."""
    d = Path.cwd()
    for _ in range(20):
        candidate = d / ".pocketteam"
        if candidate.exists():
            return candidate
        parent = d.parent
        if parent == d:
            break
        d = parent
    return None
