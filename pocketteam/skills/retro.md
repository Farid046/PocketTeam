---
name: retro
description: "Post-task retrospective. Use after completing a feature or fixing a bug."
---

# /retro — Task Retrospective

After a task completes, run a retrospective to capture learning while it's fresh. Output goes to `.pocketteam/learnings/`.

## Data to Collect

```bash
BASE=$(git rev-parse --show-toplevel)

# Task duration (time between first and last event for this task)
# Agent spawn count
# Denial rate (how many tool calls were blocked by guardian)
# Retry count (how many times engineer had to re-attempt)
tail -200 $BASE/.pocketteam/events/stream.jsonl | python3 -c "
import sys, json
events = [json.loads(l) for l in sys.stdin if l.strip()]
agents_used = set(e.get('agent') for e in events if e.get('agent'))
denials = [e for e in events if e.get('type') == 'denial']
errors = [e for e in events if e.get('type') == 'error']
print(f'Agents involved: {agents_used}')
print(f'Denials: {len(denials)}')
print(f'Errors: {len(errors)}')
"
```

## Retro Questions

Answer each honestly:

1. **What went well?** (specific, not generic)
2. **What was slower than expected?** (and why)
3. **What caused the most back-and-forth?** (unclear spec? wrong agent?)
4. **Did any agent fail or need retrying?** (which one, why)
5. **What would you do differently?** (concrete change, not vague)
6. **What should become a skill or pattern?** (repeatable process found)

## Output Format

Save to `.pocketteam/learnings/retro-[task-slug]-[date].md`:

```markdown
# Retro: [Task Name] — [Date]

## Stats
- Duration: [time]
- Agents used: [list]
- Denials: N | Errors: N

## What Went Well
- [specific item]

## What Was Slow
- [item]: [root cause]

## Improvement Actions
1. [specific change] → Owner: [COO/engineer/planner/etc]

## New Pattern Found
[If a new reusable approach was discovered, describe it here — candidate for a skill]
```

## After Writing

If the retro surfaces a new skill idea → write it to `.pocketteam/learnings/proposed/` using `/propose-improvements` skill.
