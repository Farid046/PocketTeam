---
name: clarify
description: "Iterative intent clarification with CEO before planning. COO asks questions in cycles until CEO says stop or 10 cycles reached."
---

# /clarify — Deep Intent Clarification

The CEO used the `clarify:` keyword. Before ANY planning or delegation, the COO must fully understand the CEO's intent through iterative questioning.

## Purpose

Unlike `discuss` (which resolves technical gray areas in one batch), `clarify` is a multi-round dialogue to deeply understand WHAT the CEO wants and WHY — before the task even reaches the planner.

## Protocol

### Rules

1. **Minimum 1 cycle, maximum 10 cycles** of questions
2. Each cycle: ask 2–4 focused questions (never more)
3. **Stop conditions** (whichever comes first):
   - CEO says "stop", "enough", "go", "reicht", "los", "passt", "start", "genug", or similar
   - 10 question cycles have been completed
4. Questions must build on previous answers — never repeat or ask what was already answered
5. Start broad (goals, constraints, users), then narrow (edge cases, priorities, trade-offs)

### Cycle Structure

Each cycle follows this format:

```
## Clarify — Cycle [N]/10

Based on what I understand so far:
> [1-2 sentence summary of current understanding]

Questions:
1. [Question about intent/scope/priority]
2. [Question about constraints/users/context]
3. [Question about edge cases/trade-offs] (optional)

Reply with answers, or say "go" to proceed with what I have.
```

### Question Progression

| Cycles | Focus Area |
|--------|-----------|
| 1–2 | **Goal & Scope** — What exactly should change? Who is this for? What does success look like? |
| 3–4 | **Constraints** — What must NOT change? Time/budget limits? Dependencies? |
| 5–6 | **Edge Cases** — What happens when X? What if Y fails? Priority order? |
| 7–8 | **Trade-offs** — Speed vs quality? Minimal vs complete? Backwards compatibility? |
| 9–10 | **Validation** — Summarize full understanding, ask for final corrections |

Do NOT rigidly follow this table — adapt based on the CEO's answers. If scope is clear after cycle 2, skip to constraints. If edge cases emerge early, explore them.

### After Clarification Ends

1. Write a **Clarification Summary** to `.pocketteam/artifacts/clarifications/[task-slug].md`:

```markdown
# Clarification: [Task Name]
Date: [YYYY-MM-DD]
Cycles: [N]

## CEO Intent
[2-3 sentences capturing the core intent]

## Key Decisions
- [Decision 1]
- [Decision 2]
- ...

## Constraints
- [Constraint 1]
- [Constraint 2]

## Out of Scope
- [Explicitly excluded item 1]
- [Explicitly excluded item 2]

## Open Questions (if any)
- [Question that CEO deferred or left ambiguous]
```

2. Pass the clarification summary to the **Planner** agent as input context
3. The planner MUST reference this summary — no assumptions that contradict it

## What NOT to Ask

- Implementation details (that's the planner's job)
- Technology choices (unless the CEO has a strong preference)
- Questions with obvious answers derivable from the codebase
- The same question twice, rephrased

## Anti-Patterns

- Asking 10+ questions in one cycle (overwhelming)
- Purely yes/no questions (low information density)
- Leading questions that assume the answer
- Continuing to ask after the CEO signals "go"
