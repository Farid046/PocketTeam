"""
Entry point for: python -m pocketteam.safety [pre|post]

Called by Claude Code hooks in .claude/settings.json.
- pre:  Reads hook input from stdin, checks safety layers, returns allow/deny.
- post: Logs tool usage to audit trail, always allows.
"""

import json
import os
import sys

mode = sys.argv[1] if len(sys.argv) > 1 else "pre"

try:
    hook_input = json.loads(sys.stdin.read())
except (json.JSONDecodeError, EOFError):
    print(
        json.dumps({
            "allow": False,
            "reason": "Malformed hook input -- cannot verify safety",
        }),
        file=sys.stderr,
    )
    sys.exit(1)

tool_name = hook_input.get("tool_name", hook_input.get("name", ""))
tool_input = hook_input.get("tool_input", hook_input.get("input", {}))
agent_id = hook_input.get("agent_id", "")

# B3: Extract session_id from hook_input, env var as fallback.
# PreToolUse hooks may or may not include session_id.
# SubagentStop hooks provide it. The env var is a secondary source.
session_id = hook_input.get("session_id", "")
if not session_id:
    session_id = os.environ.get("CLAUDE_SESSION_ID", "")

if mode == "pre":
    from .guardian import pre_tool_hook

    result = pre_tool_hook(
        tool_name, tool_input, agent_id, session_id=session_id
    )
    print(json.dumps(result))
    sys.exit(0 if result.get("allow") else 1)

elif mode == "post":
    from .activity_logger import log_activity

    input_str = (
        json.dumps(tool_input, default=str)
        if not isinstance(tool_input, str)
        else tool_input
    )
    log_activity(tool_name, input_str, agent_id)
    print(json.dumps({"allow": True}))
    sys.exit(0)
