"""
PocketTeam JSONL Utilities
Shared helpers for writing newline-delimited JSON records.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any


def append_jsonl(
    path: Path | str,
    entry: Any,
    default: Callable[[Any], Any] = str,
) -> None:
    """Append a single JSON entry as a newline-delimited record to a JSONL file.

    Args:
        path:    Path to the JSONL file (created if it does not exist).
        entry:   Any JSON-serialisable object.
        default: Fallback serialiser for non-JSON-native types (default: str).
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, default=default) + "\n")
