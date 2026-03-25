"""
Entry point for: python -m pocketteam.safety.guardian [pre|post]

Called by Claude Code's PreToolUse hook in .claude/settings.json.
Reads hook input from stdin, checks safety layers, returns allow/deny.
"""
from .guardian import *

if __name__ == "__main__":
    import json
    import sys

    mode = sys.argv[1] if len(sys.argv) > 1 else "pre"

    try:
        hook_input = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, EOFError):
        print(json.dumps({"allow": True, "reason": "Could not parse hook input"}))
        sys.exit(0)

    if mode == "pre":
        tool_name = hook_input.get("tool_name", hook_input.get("name", ""))
        tool_input = hook_input.get("tool_input", hook_input.get("input", {}))
        agent_id = hook_input.get("agent_id", "")

        result = pre_tool_hook(tool_name, tool_input, agent_id)
        print(json.dumps(result))
        sys.exit(0 if result.get("allow") else 1)

    elif mode == "post":
        print(json.dumps({"allow": True}))
        sys.exit(0)
