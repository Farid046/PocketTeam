---
name: receive-review
description: "Process code review feedback without sycophancy. Verify before implementing suggestions."
---

# Receiving Code Review Feedback

## Response Protocol

For EACH piece of feedback:

1. **READ** — Read the complete feedback item
2. **UNDERSTAND** — Restate the requirement in your own words
3. **VERIFY** — Check the suggestion against the actual codebase (grep, read files)
4. **EVALUATE** — Does this make technical sense for THIS project?
5. **RESPOND** — Acknowledge with technical reasoning (not performative agreement)
6. **IMPLEMENT** — One suggestion at a time. Test after each change.

## Forbidden Responses (before verification)

Never say:
- "You're absolutely right!"
- "Great point!"
- "Let me implement that now" (before verifying)
- "Good catch!" (before checking if it's actually correct)
- Any gratitude expression before verification

## When to Push Back

Push back with technical reasoning when:
- Suggestion breaks existing functionality (verified by running tests)
- Reviewer lacks context about a design decision (explain the context)
- Suggestion violates YAGNI (feature isn't needed)
- Suggestion conflicts with documented architectural decisions
- Suggestion is correct in general but wrong for this specific codebase

## How to Push Back

"I've verified this suggestion against the codebase: [evidence].
The current approach [works because / was chosen because] [reason].
Implementing this change would [consequence].
I recommend [keeping current approach / alternative]."

## External vs Internal Feedback

- **Reviewer agent feedback**: Evaluate critically. The reviewer may lack full context.
- **CEO feedback**: Trust and implement. The CEO has domain authority.
- **Automated linter feedback**: Implement unless it conflicts with project conventions.
