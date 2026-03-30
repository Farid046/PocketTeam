---
name: discuss
description: "Clarify ambiguous requirements before planning. Use when task has unclear implementation choices."
---

# Discuss Phase

Use before planning when requirements have ambiguous implementation choices.
The goal is to surface ALL decisions upfront so the planner can write a complete,
unambiguous plan on the first pass.

## When to Invoke

- Requirements mention multiple possible approaches without specifying one
- The task touches architecture, external services, or data models
- There are trade-offs the CEO should own (e.g. SQL vs NoSQL, sync vs async, REST vs GraphQL)
- The COO would otherwise have to make silent assumptions in the plan

## Steps

### Step 1 — Read the Requirements

Read the full task description, any referenced files, and existing `.pocketteam/CONTEXT.md`
(if it exists) to avoid re-asking already-decided questions.

### Step 2 — Identify Gray Areas

A gray area is any decision that:
- Has two or more reasonable implementation options
- Is not already decided in CONTEXT.md or prior conversation
- Would meaningfully change the plan if the answer changed

Do NOT manufacture gray areas for trivial details. If the right choice is obvious,
make it and state it as an assumption rather than asking.

### Step 3 — Present Batch Decision Table

Present ALL gray areas in a single message using this format:

```
## Discuss: [Task Name]

Before planning, I need your input on these decisions:

| # | Gray Area | Options | Proposed Default | Confirm? |
|---|-----------|---------|-----------------|---------|
| 1 | [question] | A: ... / B: ... | A (reason) | ✓ / change |
| 2 | [question] | A: ... / B: ... | B (reason) | ✓ / change |

Reply with: "all good" or override specific rows: "2: B, 4: A"
```

Never ask one question at a time. All gray areas go in the same table.

### Step 4 — Record CEO Decisions

Once the CEO confirms or overrides:
1. Write all decisions to `.pocketteam/CONTEXT.md` under a `## Decisions` section.
2. If CONTEXT.md already exists, append a new dated block — do not overwrite existing decisions.

```markdown
## Decisions — [YYYY-MM-DD] — [Task Name]

- [Gray Area 1]: [chosen option] (CEO confirmed)
- [Gray Area 2]: [chosen option] (CEO changed from proposed default)
```

### Step 5 — Proceed to Planning

Invoke the planner with the original task description PLUS a reference to CONTEXT.md
so the decisions are baked into the plan from the start.

## What NOT to Discuss

Do not surface:
- Style preferences (follow existing code conventions)
- Technology already established in the project stack
- Decisions already in CONTEXT.md
- Trivial details with an obvious right answer

## Output Guarantee

After the discuss phase, the planner must never say "I assumed X" for anything
that was a genuine gray area. All assumptions must be explicit decisions in CONTEXT.md.
