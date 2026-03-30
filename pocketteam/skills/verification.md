---
name: verification
description: "Verify completion claims with evidence. Run the check before claiming done."
---

# Verification Before Completion

## Iron Law

> **You may not claim completion unless you ran the verification IN THIS MESSAGE.**

If the test/build/check was run in a previous message, a previous session, or by
a different agent — it does not count. Run it again. Show the output. Then claim done.

This law applies to ALL completion-claiming agents:
engineer, qa, reviewer, security, investigator, devops, and COO.

---

## Forbidden Phrases

Never say these without fresh proof in the same message:

| Forbidden | Use instead |
|-----------|-------------|
| "should work" | Run it. Show exit code 0. |
| "probably fixed" | Reproduce the original symptom. Show it's gone. |
| "seems to pass" | Run the test suite. Show the output. |
| "I'm confident it works" | Confidence is not evidence. Run it. |
| "tests should be green" | They either are or they aren't. Check now. |
| "looks correct to me" | Looking is not running. Execute and verify. |
| "this ought to fix it" | Fix it, then prove it. |

---

## Verification Requirements by Type

### Tests (pytest, jest, mocha, rspec, etc.)
```
REQUIRED: Run the test command and show the full output.

Minimum acceptable evidence:
  pytest tests/ -v
  → ... 42 passed, 0 failed in 3.21s ✓

NOT acceptable:
  "I wrote the tests, they should pass"
  "I tested it manually"
```

### Builds (docker build, npm run build, go build, etc.)
```
REQUIRED: Run the build command and show exit code 0.

Minimum acceptable evidence:
  docker build . -t myapp
  → Successfully built abc123
  → exit code: 0 ✓

NOT acceptable:
  "The build should work, I fixed the import"
```

### Bug Fixes
```
REQUIRED: Reproduce the original symptom BEFORE the fix, then show it's gone AFTER.

Minimum acceptable evidence:
  1. [Show the original error / failing test / wrong output]
  2. [Apply the fix]
  3. [Run the same scenario — show it now works]

NOT acceptable:
  "The root cause was obvious, the fix is correct"
```

### Deployments
```
REQUIRED: Show health check passing after deploy.

Minimum acceptable evidence:
  curl https://staging.myapp.com/health
  → {"status": "ok", "version": "1.2.3"} ✓

NOT acceptable:
  "Deploy completed successfully" (from CI output alone)
```

### Security Audits
```
REQUIRED: Show scanner output with zero critical/high findings.

Minimum acceptable evidence:
  pip-audit output OR npm audit output OR bandit -r . output
  → 0 vulnerabilities found ✓

NOT acceptable:
  "I reviewed the code and it looks secure"
```

---

## Rationalization Table

When you feel the urge to skip verification, you will encounter one of these rationalizations.
Recognize them and reject them.

| # | Rationalization | Why It's Wrong |
|---|----------------|----------------|
| 1 | "The change was tiny — one line fix" | Tiny changes break things. One wrong character causes a crash. Run it. |
| 2 | "I already ran it 10 minutes ago" | 10 minutes ago is not now. You may have changed something since. Run it again. |
| 3 | "The test suite is slow" | Speed is not an excuse for claiming done without proof. Run the relevant subset. |
| 4 | "I'm confident I didn't break anything" | Confidence is not evidence. The compiler/test runner is the authority, not your confidence. |
| 5 | "The reviewer will catch it if it's wrong" | The reviewer's job is to review, not to be your safety net for skipped verification. |
| 6 | "I can't run it in this environment" | Then say: "I cannot verify this in my current environment — here is what needs to be verified manually: [steps]." Never silently claim done. |

---

## When You Cannot Run Verification

If verification is genuinely impossible (no test runner available, production-only scenario,
requires CEO credentials), you MUST:

1. State explicitly: "I cannot run this verification in my environment."
2. Describe exactly what needs to be verified: "Run `pytest tests/test_auth.py` and confirm all pass."
3. Mark the task as: `STATUS: DONE_WITH_CONCERNS — manual verification required`

Never silently omit the verification step. Either run it, or document why you can't and
hand the verification obligation to the CEO explicitly.

---

## COO Rule: Trust but Verify Agent Reports

When an agent reports "done" or "all tests pass":
- If the agent showed test output in its response: accept the report.
- If the agent claimed done without showing output: ask for proof before marking the task complete.

The COO is the last line of defense before informing the CEO.
