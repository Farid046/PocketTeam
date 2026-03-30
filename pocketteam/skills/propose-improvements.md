---
name: propose-improvements
description: "Suggest system improvements based on analysis. Use during retrospectives."
---

# /propose-improvements — Propose Team Improvements

When a retro, digest, or observation surfaces an improvement, document it as a proposal. Do NOT directly edit agent prompts or skill files.

## Rule: Propose, Do Not Apply

Observer writes proposals to `.pocketteam/learnings/proposed/`. Only COO (with CEO approval) applies them to actual agent files.

## Proposal File

Save to `.pocketteam/learnings/proposed/[slug]-[date].md`:

```markdown
# Proposal: [Title]

**Date:** YYYY-MM-DD
**Observed by:** observer
**Source:** retro/weekly-digest/monitoring

## Problem
[What specific behavior or outcome is suboptimal? Be concrete.]
[Example: "Engineer agent is not including test files in commits, requiring a second commit 60% of the time"]

## Proposed Change
**Target:** [agent name or skill name]
**Type:** agent-prompt / skill / workflow / CLAUDE.md

[Exact text to add/change/remove. Not vague direction — actual content.]

## Expected Outcome
[How will this change behavior? What metric improves?]

## Evidence
- Observed N times across last [time period]
- Specific examples: [task name or event ID]

## Risk
- Could cause: [unintended side effect]
- Mitigated by: [how]

## Priority
- HIGH: Causing repeated failures or wasted cycles
- MEDIUM: Reducing efficiency noticeably
- LOW: Minor improvement, do when convenient
```

## Process After Writing

1. Write the proposal file
2. Report to COO: "Proposal written: [title] at [path]"
3. COO reviews and batches proposals for CEO approval
4. CEO approves → COO delegates to Engineer to apply
5. Observer verifies improvement was applied correctly

## What Qualifies for a Proposal

- The same issue appeared 3+ times in event stream
- A step consistently takes longer than expected
- An agent consistently makes the same type of mistake
- A new pattern was discovered that should be a skill

## What Does Not Qualify

- One-off events (single occurrence)
- Issues that are already tracked
- Changes that require architectural decisions (escalate to CEO directly)
