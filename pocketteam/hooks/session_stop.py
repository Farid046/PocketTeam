"""Hook: SessionStop — clean up session.lock when Claude exits."""
import json
import sys
from pathlib import Path

from ._utils import _find_pocketteam_dir


def handle(hook_input: dict) -> dict:
    """Remove session.lock so the Telegram daemon knows the session has ended."""
    pt_dir = _find_pocketteam_dir()
    if not pt_dir:
        return {}

    lock_file = pt_dir / "session.lock"
    try:
        lock_file.unlink(missing_ok=True)
    except OSError:
        pass

    return {}


if __name__ == "__main__":
    try:
        hook_input = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, EOFError):
        hook_input = {}
    result = handle(hook_input)
    print(json.dumps(result))
