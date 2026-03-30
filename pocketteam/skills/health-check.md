---
name: health-check
description: "Verify production service health. Use after deploys or when monitoring alerts."
---

# /health-check — Service Health Check

Comprehensive health check combining API probes and visual verification. Run after deploys and on a schedule.

## API Checks (curl)

```bash
# HTTP health endpoint
curl -sf http://localhost:3848/api/health | python3 -c "
import sys, json
d = json.loads(sys.stdin.read())
status = d.get('status', 'unknown')
print(f'Health: {status}')
sys.exit(0 if status == 'ok' else 1)
" && echo "API: OK" || echo "API: FAIL"

# Agents endpoint returning data
curl -sf http://localhost:3848/api/agents | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f'Agents endpoint: {len(d)} agents returned')
" || echo "Agents endpoint: FAIL"

# Sessions endpoint
curl -sf http://localhost:3848/api/sessions | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f'Sessions endpoint: {len(d)} sessions')
" || echo "Sessions endpoint: FAIL"
```

## WebSocket Check

```bash
# Confirm WS upgrades (101 response)
curl -sf --include \
  -H "Upgrade: websocket" -H "Connection: Upgrade" \
  -H "Sec-WebSocket-Key: dGVzdA==" -H "Sec-WebSocket-Version: 13" \
  http://localhost:3848/ws 2>&1 | head -5
# Expect: HTTP/1.1 101 Switching Protocols
```

## Visual Check (ptbrowse)

```bash
# Dashboard loads
bun run pocketteam/browse/index.ts goto http://localhost:3848
bun run pocketteam/browse/index.ts wait text "PocketTeam" 5000
bun run pocketteam/browse/index.ts assert text "PocketTeam"
bun run pocketteam/browse/index.ts assert no-text "Error"
bun run pocketteam/browse/index.ts assert no-text "Cannot connect"
bun run pocketteam/browse/index.ts screenshot
```

## Container Health

```bash
docker compose ps
# Confirm: dashboard shows "Up" not "Restarting" or "Exit"

docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}"
# Alert if CPU > 80% or memory near limit
```

## Report Format

```
Health Check: [timestamp]
API health:    PASS / FAIL
Agents API:    PASS / FAIL ([N] agents)
WebSocket:     PASS / FAIL
Visual load:   PASS / FAIL
Container:     UP / DOWN / RESTARTING
CPU/Memory:    [stats]

Overall: HEALTHY / DEGRADED / DOWN
```
