---
name: review
description: "Code review checklist for correctness and security. Use before merging changes."
---

# Code Review

You are performing a comprehensive code review. Follow this checklist systematically.

## Step 1: Understand the Changes

```bash
git diff --stat
git diff
git log --oneline -5
```

Read ALL changed files completely before commenting.

## Step 2: Review Checklist

### Correctness
- Logic implements what was intended (no silent scope creep)
- Edge cases handled (nulls, empty, large inputs, concurrent access)
- Error handling: specific exceptions, not bare `except`
- Async/await used correctly (no forgotten awaits)

### Security (CRITICAL)
- No SQL injection (parameterized queries)
- No XSS (input sanitized before rendering)
- No hardcoded secrets in code
- Input validation at API boundaries
- LLM Trust Boundary: never pass unsanitized LLM output to dangerous functions

### Completeness
- All planned items implemented
- Tests cover happy path + error cases
- Documentation updated if needed

### Code Quality
- No dead code, unused imports
- Consistent naming with codebase
- No over-engineering or premature abstraction

## Step 3: Output Format

```markdown
## Code Review

### What's Good
- [specific praise]

### Must Fix (blocking)
1. **[File:Line]**: [Issue] — [Why] — [Fix]

### Suggestions (non-blocking)
1. **[File:Line]**: [Better approach]

### Verdict
- [ ] APPROVED
- [ ] CHANGES REQUESTED
```
