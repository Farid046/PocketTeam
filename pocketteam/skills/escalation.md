---
name: escalation
description: "Escalate blocked issues to CEO with context. Use when 3+ fix attempts fail."
---

# /escalation — Escalation Protocol

When a health check or log analysis finds a problem, follow this protocol. Do NOT notify CEO for every minor issue.

## Severity Classification

| Severity | Criteria | Action |
|----------|----------|--------|
| P1 — Critical | Service down, data loss, security breach | Escalate immediately + attempt auto-heal |
| P2 — High | Core feature broken, error rate > 10% | Escalate within 5 min, attempt auto-heal |
| P3 — Medium | Degraded performance, minor feature broken | Log it, monitor, escalate if persists > 15 min |
| P4 — Low | Cosmetic, log noise, non-critical | Log only, no escalation |

## Auto-Heal Attempts (before escalating P1/P2)

```bash
# Attempt 1: Container restart
docker compose restart dashboard
sleep 5
curl -sf http://localhost:3848/api/health && echo "Healed" && exit 0

# Attempt 2: Full recreate
docker compose up -d --force-recreate dashboard
sleep 10
curl -sf http://localhost:3848/api/health && echo "Healed" && exit 0

# If both fail: escalate to CEO
```

## CEO Notification via Event Stream

NEVER send direct messages to CEO. Write to the event stream — the dashboard and Telegram hook will surface it.

```bash
SEVERITY=P1
MESSAGE="[what is broken and what was tried]"
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)

echo "{\"type\": \"escalation\", \"severity\": \"$SEVERITY\", \"message\": \"$MESSAGE\", \"auto_heal_attempted\": true, \"timestamp\": \"$TIMESTAMP\", \"agent\": \"monitor\"}" >> .pocketteam/events/stream.jsonl
```

## Escalation Message Format

```
[P1/P2/P3] [Service]: [What is wrong]
Since: [timestamp]
Auto-heal: [tried / not applicable]
Evidence: [log line or error]
Recommended action: [what COO/CEO should do]
```

## Do NOT Escalate For

- Single failed health check that passes on retry (transient)
- Log lines that are INFO or WARN only
- Issues that are already being fixed (ticket exists)
- P4 issues

## After Escalation

Monitor continues checking every 2 minutes. If resolved:

```bash
echo "{\"type\": \"resolved\", \"severity\": \"$SEVERITY\", \"message\": \"Issue resolved\", \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\", \"agent\": \"monitor\"}" >> .pocketteam/events/stream.jsonl
```
