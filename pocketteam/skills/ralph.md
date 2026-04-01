---
name: ralph
description: "Implement-test-fix loop until all tests pass. Activated by ralph: keyword."
---

# /ralph — Persistent Until Done

CEO has pre-approved a fix loop by using the `ralph:` keyword. Keep iterating until ALL tests pass. Maximum 5 iterations.

## Loop Protocol

```
Iteration 1: Implement → Run tests → Check results
Iteration 2: Fix failures → Run tests → Check results
...
Iteration 5: Final fix attempt
```

## Per Iteration

1. **Implement** (or fix failures from previous iteration)
2. **Run full test suite** — capture output, count failures
3. **Evaluate** — if all pass, stop and report success
4. **Diagnose** — for each failing test: read the error, locate the code, identify the fix
5. **Loop** — apply targeted fixes, do not refactor unrelated code

## Iteration Tracking

After each run, log:
```
Iteration N/5
Tests: [X passed, Y failed]
Failures:
  - [test name]: [error summary]
  - [test name]: [error summary]
Fix plan: [what will be changed]
```

## Mandatory Review

After EVERY engineer fix iteration, run a reviewer pass before re-testing. Never skip the review step — even in ralph mode.

## Stopping Conditions

- ALL tests pass → report success, stop
- 5 iterations reached → report remaining failures, stop, escalate to CEO
- Same test fails 3 iterations in a row with no progress → escalate immediately, stop loop

## Final Report

```
Ralph complete after N iterations
Tests: all passing / N still failing (list them)
Files modified: [list]
```
