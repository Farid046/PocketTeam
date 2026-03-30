---
name: handoff-spec
description: "Write handoff documentation for team transitions. Use when passing work to others."
---

# /handoff-spec — Investigation to Engineer Handoff

After investigation is complete, format findings as a precise spec for the Engineer. Vague handoffs cause wrong fixes. Be specific.

## Handoff Template

```markdown
## Fix Specification: [Issue Title]

### What is broken
[One sentence: what fails, for whom, since when]

### Root cause
[One sentence: the exact code/config/data that causes it]

### Evidence
- File: [path] Line: [number]
- Log entry: `[exact error text]`
- Commit that introduced it: [sha] — [message]

### Files to change
| File | Line(s) | What to change |
|------|---------|----------------|
| [path] | [line] | [specific change — not "fix the bug", say what value/logic to use] |

### Expected behavior after fix
[Specific: "Calling X with Y should return Z" or "Test test_foo should pass"]

### Do NOT change
[Any files/functions that seem related but should not be touched]

### Test to verify fix
```bash
[exact command to run that should pass after fix]
```

### Time estimate
[Investigator's estimate of complexity: trivial / 1h / half-day]
```

## Rules for Handoff Quality

- Never say "fix the bug" without specifying the exact line and what value it should have
- Never hand off without a test command to verify the fix
- If the root cause is uncertain, say "most likely" and explain the uncertainty
- If multiple files need changes, list ALL of them — an incomplete spec wastes Engineer time

## Write Handoff To

```bash
echo "[handoff content]" > /Users/farid/Documents/entwicklung/PocketTeam/.pocketteam/artifacts/plans/fix-[issue-slug].md
```
