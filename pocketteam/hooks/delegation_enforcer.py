"""
Delegation Enforcer — PreToolUse hook for Agent/Task tool calls.

Model routing is handled by the agent .md frontmatter (model: opus/sonnet/haiku).
Hooks CANNOT override the model — this was confirmed in testing.
This hook now returns {} to save ~50 tokens per agent spawn.
"""


def handle(hook_input: dict) -> dict:
    """No-op — model is set in agent .md frontmatter, not hooks."""
    return {}
