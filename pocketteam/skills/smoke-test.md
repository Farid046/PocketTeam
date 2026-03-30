---
name: smoke-test
description: "Quick sanity check on critical paths. Use after deploys for fast validation."
---

# /smoke-test — Post-Deploy Smoke Test

Run the 5 fastest checks to confirm a deploy didn't break critical paths. Target: complete in < 30 seconds.

## The 5 Checks

```bash
# 1. Service is up (HTTP 200)
curl -sf http://localhost:3848/api/health && echo "OK" || echo "FAIL: service down"

# 2. WebSocket connects
curl -sf --include \
  -H "Upgrade: websocket" \
  -H "Connection: Upgrade" \
  -H "Sec-WebSocket-Key: test" \
  -H "Sec-WebSocket-Version: 13" \
  http://localhost:3848/ws 2>&1 | grep -q "101\|upgrade" && echo "WS OK" || echo "WS FAIL"

# 3. API returns data (not empty/error)
curl -sf http://localhost:3848/api/agents | python3 -c "import sys,json; d=json.load(sys.stdin); print('AGENTS OK' if isinstance(d,list) else 'AGENTS FAIL')"

# 4. No ERROR lines in last 50 log lines
docker compose logs --tail=50 dashboard 2>&1 | grep -i "error\|fatal\|exception" && echo "ERRORS FOUND" || echo "LOGS OK"

# 5. Dashboard UI loads (browser check)
bun run pocketteam/browse/index.ts goto http://localhost:3848 && \
bun run pocketteam/browse/index.ts assert text "PocketTeam" && echo "UI OK" || echo "UI FAIL"
```

## Pass/Fail Criteria

- All 5 pass → smoke test PASSED, proceed
- Any check fails → smoke test FAILED, initiate rollback, notify CEO

## Report Format

```
Smoke Test: [service] @ [timestamp]
1. HTTP health:  PASS / FAIL
2. WebSocket:    PASS / FAIL
3. API data:     PASS / FAIL
4. Error logs:   PASS / FAIL
5. UI load:      PASS / FAIL

Result: PASSED / FAILED
Action: [proceed / rollback]
```
