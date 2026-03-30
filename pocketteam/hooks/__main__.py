"""
Entry point for PocketTeam hooks: python -m pocketteam.hooks <hook_type>

Hook types:
  delegation        — PreToolUse on Agent calls: auto-inject model tier
  keyword           — UserPromptSubmit: detect autopilot/ralph/quick keywords
  telegram_save     — UserPromptSubmit: persist Telegram messages to disk
  agent_start       — SubagentStart: log spawn event
  agent_stop        — SubagentStop: log completion event
  observer_analyze  — SubagentStop: trigger background observer analysis
  session_start     — SessionStart: load unread Telegram messages
  session_stop      — Stop: delete session.lock on Claude exit
  pre_compact       — PreCompact: preserve context before compression
  context_warning   — PostToolUse on Agent|Task: warn when context is high
"""

import json
import sys

hook_type = sys.argv[1] if len(sys.argv) > 1 else ""

try:
    hook_input = json.loads(sys.stdin.read())
except (json.JSONDecodeError, EOFError):
    hook_input = {}

if hook_type == "delegation":
    from .delegation_enforcer import handle
    result = handle(hook_input)
    print(json.dumps(result))

elif hook_type == "keyword":
    from .keyword_detector import handle
    result = handle(hook_input)
    print(json.dumps(result))

elif hook_type == "telegram_save":
    from .telegram_inbox import handle
    result = handle(hook_input)
    print(json.dumps(result))

elif hook_type == "agent_start":
    from .agent_lifecycle import handle_start
    handle_start(hook_input)
    print(json.dumps({}))

elif hook_type == "agent_stop":
    from .agent_lifecycle import handle_stop
    handle_stop(hook_input)
    print(json.dumps({}))

elif hook_type == "observer_analyze":
    from .observer_trigger import handle
    result = handle(hook_input)
    print(json.dumps(result))

elif hook_type == "session_start":
    from .session_start import handle
    result = handle(hook_input)
    print(json.dumps(result))

elif hook_type == "pre_compact":
    from .pre_compact import handle
    result = handle(hook_input)
    print(json.dumps(result))

elif hook_type == "session_stop":
    from .session_stop import handle
    result = handle(hook_input)
    print(json.dumps(result))

elif hook_type == "context_warning":
    from .context_warning import handle
    result = handle(hook_input)
    print(json.dumps(result))

else:
    print(json.dumps({}))
