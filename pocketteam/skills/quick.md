---
name: quick
description: "Speed mode — skip planning and review. Activated by quick: keyword."
---

# /quick — Speed Mode

CEO has activated speed mode with the `quick:` keyword. Skip planning, skip review, implement directly.

## Steps

1. **Read** the relevant files (understand what exists before touching anything)
2. **Implement** the change on a feature branch — minimal, focused, no scope creep
3. **Smoke test** — run the 5 fastest checks that confirm the change works
4. **Commit** and report

## Rules

- No planner agent, no reviewer agent
- If the task requires more than 3 files changed → warn CEO but continue
- If the task touches auth, payments, or prod DB → STOP and ask for confirmation (safety override)
- Commit message: `quick: [what was done]`

## Smoke Test Checklist

After implementation, verify:
- [ ] No syntax/compile errors (`tsc --noEmit` or equivalent)
- [ ] Affected unit tests pass
- [ ] App starts without error (if applicable)
- [ ] The specific feature works as described
- [ ] No broken imports or missing files

## Report Format

```
Quick complete: [task]
Branch: feature/quick-[name]
Files changed: [list]
Smoke test: pass / fail ([details if fail])
```
