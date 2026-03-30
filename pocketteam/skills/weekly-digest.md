---
name: weekly-digest
description: "Generate weekly project summary. Use for team status updates."
---

# /weekly-digest — Weekly Team Digest

Produce a weekly summary of PocketTeam activity. Run at end of week (or on demand).

## Data Collection

```bash
BASE=$(git rev-parse --show-toplevel)

# Events from last 7 days
python3 - << 'EOF'
import json, collections, datetime, subprocess

base = subprocess.check_output(["git", "rev-parse", "--show-toplevel"]).decode().strip() + "/.pocketteam/events/stream.jsonl"
cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=7)

events = []
with open(base) as f:
    for line in f:
        try:
            e = json.loads(line.strip())
            ts = e.get("timestamp", "")
            if ts >= cutoff.strftime("%Y-%m-%d"):
                events.append(e)
        except:
            pass

by_type = collections.Counter(e.get("type") for e in events)
by_agent = collections.Counter(e.get("agent") for e in events if e.get("agent"))
denials = [e for e in events if e.get("type") == "denial"]
errors = [e for e in events if e.get("type") == "error"]

print(f"Total events: {len(events)}")
print(f"By type: {dict(by_type.most_common(10))}")
print(f"By agent: {dict(by_agent.most_common(10))}")
print(f"Denials: {len(denials)}")
print(f"Errors: {len(errors)}")
print(f"Top denied agents: {dict(collections.Counter(e.get('agent') for e in denials).most_common(5))}")
EOF
```

## Git Activity

```bash
git log --since="7 days ago" --oneline --format="%ci %h %s"
git log --since="7 days ago" --oneline | wc -l
```

## Digest Template

Save to `.pocketteam/learnings/digest-YYYY-WNN.md`:

```markdown
# Weekly Digest — Week [N], [Year]

## Activity
- Events: N total
- Commits: N
- Tasks completed: N

## Agent Activity (top 5)
| Agent | Events | Errors | Denial Rate |
|-------|--------|--------|-------------|

## Highlights
- [notable task or achievement]

## Issues
- [recurring errors or patterns]
- [agents with high denial rates]

## Trend
vs. last week: [more/less active, error rate up/down]
```
