---
name: log-analysis
description: "Analyze system logs for errors and patterns. Use when debugging production behavior."
---

# /log-analysis — Log Analysis

Parse PocketTeam event stream and Docker logs to spot errors, anomalies, and unusual patterns.

## Event Stream Analysis

```bash
BASE=.pocketteam

# Error rate in last N events
tail -500 $BASE/events/stream.jsonl | python3 -c "
import sys, json, collections
events = []
for line in sys.stdin:
    try: events.append(json.loads(line.strip()))
    except: pass
total = len(events)
errors = [e for e in events if e.get('type') == 'error' or 'error' in str(e.get('message','')).lower()]
by_agent = collections.Counter(e.get('agent','unknown') for e in errors)
print(f'Total events: {total}')
print(f'Errors: {len(errors)} ({100*len(errors)//max(total,1)}%)')
print(f'Errors by agent: {dict(by_agent)}')
"

# Agent activity summary
tail -200 $BASE/events/stream.jsonl | python3 -c "
import sys, json, collections
events = [json.loads(l) for l in sys.stdin if l.strip()]
by_type = collections.Counter(e.get('type') for e in events)
by_agent = collections.Counter(e.get('agent') for e in events)
print('Event types:', dict(by_type))
print('Agent activity:', dict(by_agent))
"
```

## Docker Log Analysis

```bash
# Error/warning count per service
docker compose logs --since=1h 2>&1 | python3 -c "
import sys, re, collections
lines = sys.stdin.readlines()
errors = [l.strip() for l in lines if re.search(r'error|fatal|exception|panic', l, re.I)]
print(f'Error lines: {len(errors)}')
for e in errors[:10]: print(f'  {e[:120]}')
"

# Restart detection
docker compose logs --since=1h 2>&1 | grep -i "started\|restart\|exit" | head -20
```

## Anomaly Detection

Look for:
- Error rate > 5% of events → investigate
- Same error repeating > 3 times → likely a loop or persistent bug
- Agent spawning rate spike → possible runaway automation
- Container restart within 1h of deploy → deploy regression

## Report Format

```markdown
## Log Analysis: [time range]

### Event Stream
- Total events: N
- Error rate: N%
- Top errors: [list with counts]

### Docker Logs
- Error lines: N
- Restarts: N
- Notable: [any unusual patterns]

### Anomalies Detected
- [anomaly]: [evidence] → Severity: HIGH/MED/LOW

### Action Required
- [what monitor should do next]
```
