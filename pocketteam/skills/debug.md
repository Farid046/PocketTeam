---
name: debug
description: "Systematic debugging with root-cause analysis. Use when code has runtime errors."
---

# /debug — Systematic Debugging

When a test fails or something behaves wrong, follow this process. Do NOT guess. Do NOT make random changes.

## Step 1: Reproduce

```bash
# Run only the failing test (not the full suite — faster feedback)
pytest tests/test_foo.py::test_bar -xvs        # Python
bun test src/foo.test.ts -- --reporter=verbose  # TypeScript
```

Confirm you can reproduce it 100% before touching any code.

## Step 2: Read the Error

- Read the full stack trace, not just the last line
- Identify: the exact file + line number where it breaks
- Identify: what value was expected vs. what arrived

## Step 3: Narrow the Scope

```bash
# Add a temporary print/log just before the failing line
# Run again — confirm your hypothesis about the wrong value
# Remove the debug print before committing
```

Do NOT add multiple debug prints at once — one at a time, top-down.

## Step 4: Identify Root Cause Category

- **Wrong input** — caller passes bad data → fix the caller
- **Wrong assumption** — code assumes X but reality is Y → fix the logic
- **Wrong dependency** — library/module behaves unexpectedly → check version, docs
- **State leak** — test ordering issue → add setup/teardown, reset state

## Step 5: Apply Minimal Fix

- Change the smallest amount of code that fixes the root cause
- Do NOT refactor unrelated code while fixing
- Re-run the failing test first, then the full suite

## Step 6: Report

```
Bug: [what was wrong]
Root cause: [why it happened]
Fix: [what changed, file:line]
Tests: [N pass, 0 fail]
```
