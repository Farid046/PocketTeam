---
name: timeline-reconstruction
description: "Reconstruct incident timeline from logs and commits. Use for post-mortems."
---

# /timeline-reconstruction — Timeline Reconstruction

Build a unified timeline from multiple sources to identify when and why something broke.

## Data Sources

```bash
BASE=$(git rev-parse --show-toplevel)

# 1. Git history (last 20 commits with times)
git -C $BASE log --oneline --format="%ci %h %s" -20

# 2. PocketTeam event stream
tail -100 $BASE/.pocketteam/events/stream.jsonl | python3 -c "
import sys, json
for line in sys.stdin:
    try:
        e = json.loads(line.strip())
        print(f\"{e.get('timestamp','?')} [{e.get('type','?')}] {e.get('agent','?')}: {e.get('message','')[:80]}\")
    except: pass
"

# 3. Docker logs with timestamps
docker compose logs --timestamps --since=2h dashboard 2>&1 | tail -200

# 4. System logs (macOS)
log show --last 2h --predicate 'process == "docker"' 2>/dev/null | tail -50
```

## Correlation Method

1. Note the exact time of the first user report or alert
2. Look 30 minutes before that time in all sources
3. Find the earliest anomaly (error log, unusual event, deploy)
4. That's your "time of introduction" — now find the commit/event that caused it

## Timeline Template

```markdown
## Incident Timeline: [Issue Name]

| Time (UTC) | Source | Event | Significance |
|------------|--------|-------|--------------|
| 14:23:00 | git | feat: new parser | Introduced |
| 14:31:00 | docker logs | ERROR: parse failed | First symptom |
| 14:45:00 | event stream | agent:engineer tool=Write | Possible trigger |
| 15:02:00 | CEO report | "dashboard broken" | Detected |

### Root Cause Window: 14:23–14:31

### Most Likely Cause: [commit sha or event]
### Evidence: [what in the logs confirms it]
```

## Handoff

After completing timeline → use `/handoff-spec` skill to format findings for the Engineer.
