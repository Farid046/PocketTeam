---
name: hotfix
description: "Minimal production fix workflow. Use for urgent bugs in production."
---

# /hotfix — Minimal Production Fix

For urgent bugs where speed matters. Minimal change, no scope creep, fast path.

## Rules

- Touch ONLY the files necessary to fix the specific bug
- No refactoring. No cleanup. No "while I'm here" changes.
- Branch name: `fix/[ticket-or-short-description]`

## Steps

```bash
# 1. Branch from main (not from an existing feature branch)
git checkout main && git pull
git checkout -b fix/[description]

# 2. Read the failing behavior first
# Understand WHAT is broken before touching code

# 3. Apply the minimal fix

# 4. Run targeted tests
pytest tests/test_affected.py -xvs   # or equivalent

# 5. Commit with clear message
git add [specific files only]
git commit -m "fix: [what] — [why it was broken]"
```

## What "Minimal" Means

- If fix needs 1 line → change 1 line
- If fix needs 3 lines → change 3 lines
- If you find unrelated issues → note them in a comment or separate ticket, do NOT fix them now

## Fast-Path Pipeline

1. Engineer implements fix
2. QA runs smoke test (not full suite)
3. Security scans only the changed files
4. CEO approves → DevOps deploys

## Report Format

```
Hotfix: [branch name]
Root cause: [one sentence]
Change: [file:line — what changed]
Test: [command run + result]
Ready for review: yes
```
