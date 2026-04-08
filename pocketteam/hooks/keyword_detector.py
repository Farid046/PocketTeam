"""
Keyword Detector — UserPromptSubmit hook.

Detects magic keywords at the start of user input and injects
workflow instructions into the prompt:

  autopilot: <task>  → Full autonomous pipeline (plan → review → implement → test → deploy)
  ralph: <task>      → Persistent mode: verify/fix loops until ALL tests pass
  quick: <task>      → Skip reviews, go straight to implementation
  deep-dive: <topic> → Spawn 3 parallel Explore agents for thorough research
  clarify: <task>    → Iterative intent clarification (up to 10 cycles) before planning
"""

KEYWORDS = {
    "autopilot:": "autopilot",
    "ralph:": "ralph",
    "quick:": "quick",
    "deep-dive:": "deep_dive",
    "deepdive:": "deep_dive",
    "clarify:": "clarify",
}

WORKFLOW_INSTRUCTIONS = {
    "autopilot": "AUTOPILOT: Full pipeline without human gates. Planner→Reviewer→Engineer→QA→Reviewer→Security→Docs. Stop only on failure, retry up to 3x.",
    "ralph": "RALPH: Implement→Test→Fix loop. Keep going until ALL tests pass (max 5 iterations). Not done until QA reports 100%.",
    "quick": "QUICK: Skip planning/review. Engineer implements directly, QA quick test, report results.",
    "deep_dive": "DEEP DIVE: Spawn 3 parallel Explore agents (codebase, external docs, edge cases). Synthesize findings.",
    "clarify": "CLARIFY: Iterative intent clarification mode. Ask 2-4 focused questions per cycle. Max 10 cycles. Stop when CEO says 'stop'/'enough'/'go'/'reicht'/'los'/'passt'/'start'/'genug' or after 10 cycles. Write summary to .pocketteam/artifacts/clarifications/, then pass to Planner.",
}


def handle(hook_input: dict) -> dict:
    """Process a UserPromptSubmit hook — detect keywords and inject instructions."""
    user_input = hook_input.get("input", hook_input.get("content", hook_input.get("message", "")))

    if not isinstance(user_input, str):
        return {}

    stripped = user_input.strip().lower()

    for keyword, mode in KEYWORDS.items():
        if stripped.startswith(keyword):
            # Extract the actual task (everything after the keyword)
            task = user_input.strip()[len(keyword):].strip()
            instructions = WORKFLOW_INSTRUCTIONS[mode]

            # Return workflow instructions as advisory context
            return {
                "additionalContext": f"{instructions}\n\nTASK: {task}",
            }

    return {}
