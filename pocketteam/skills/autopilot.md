---
name: autopilot
description: "Full autonomous pipeline without human gates. Activated by autopilot: keyword."
---

# /autopilot — Full Autonomous Pipeline

CEO has pre-approved continuous execution by using the `autopilot:` keyword. Skip all human gates. Proceed without stopping for approval.

## Pipeline (Execute in Order)

1. **Planner** — Create detailed implementation plan
2. **Reviewer** — Review plan for completeness and risks
3. **Engineer** — Implement on feature branch
4. **Reviewer** — Code review of implementation
5. **QA** — Run all tests
6. **Security** — OWASP audit + dependency scan
7. **Documentation** — Update docs

## Rules

- Do NOT pause for approval at any step unless a step FAILS
- If any step fails → stop immediately, report failure to CEO, wait for instruction
- Report progress after each step: "Step N/7 complete: [what was done]"
- On success, deliver final summary: branch name, files changed, test results, security findings

## Failure Protocol

If a step fails after 2 retries:
1. Stop the pipeline
2. Report: "Autopilot halted at Step N: [reason]"
3. List what was completed and what remains
4. Wait for CEO instruction

## Final Report Format

```
Autopilot complete for: [task]
Branch: feature/[name]
Files changed: N
Steps: Plan ✓ | Review ✓ | Implement ✓ | QA ✓ | Security ✓ | Docs ✓
Ready to merge: [y/n — with reason if no]
```
