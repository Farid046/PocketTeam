---
name: investigate
description: "Deep investigation with hypothesis-driven methodology. Use for complex production issues."
---

# Investigation

You are diagnosing a production issue. Follow this methodology strictly.

## 3-Strike Rule
You have 3 fix attempts before escalating to the CEO. Use them wisely.

## Step 1: Gather Evidence (READ-ONLY)

Never change anything until you understand the problem:

```bash
# Recent errors
git log --oneline --since="24h ago"
# Check logs if available
tail -n 500 /var/log/app/error.log 2>/dev/null || echo "No log file"
```

Read the failing code. Read related tests. Check recent changes.

## Step 2: Form Hypotheses

List ALL possible causes, ranked by likelihood:
```
Hypothesis 1 (70%): [cause] — evidence: [what supports this]
Hypothesis 2 (20%): [cause] — evidence: [what supports this]
Hypothesis 3 (10%): [cause] — evidence: [what supports this]
```

## Step 3: Test Each Hypothesis

Start with the most likely. Test BEFORE fixing.
Use read-only commands to verify.

## Step 4: Scope Lock

Once root cause found: create a MINIMAL fix.
Do NOT refactor while fixing. Scope lock prevents regression.

## Step 5: Report

```markdown
## Investigation Report

### Root Cause
[Precise description]

### Evidence
- [log excerpt / metric / commit]

### Fix
[Minimal targeted change]

### Prevention
[How to prevent this class of issue]
```

## Escalation

After 3 failed fixes:
> "3 fix attempts failed. Root cause: [best guess]. Options: [A] [B] [C]. What do you prefer?"
