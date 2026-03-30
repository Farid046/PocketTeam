---
name: rollback
description: "Safe rollback procedure. Use when a deploy causes production issues."
---

# /rollback — Immediate Rollback

Run this when a deploy breaks production. Speed is critical. Do not investigate first — restore service, then investigate.

## Step 1: Stop the Bleeding

```bash
# Identify the broken service
docker compose ps

# Roll back to previous image (Docker keeps previous layers)
SERVICE=[service-name]

# Find the previous image tag
docker images pocketteam-dashboard --format "{{.Tag}}\t{{.CreatedAt}}" | head -5
# Identify the tag BEFORE the broken one
```

## Step 2: Rollback

```bash
# Option A: Previous tag is known
docker compose stop $SERVICE
docker tag pocketteam-dashboard:[previous-sha] pocketteam-dashboard:latest
docker compose up -d $SERVICE

# Option B: Use docker rollback via compose override
docker compose -f docker-compose.yml -f docker-compose.rollback.yml up -d $SERVICE
```

## Step 3: Verify Restoration

```bash
# Must pass within 60 seconds
curl -sf http://localhost:3848/api/health && echo "RESTORED" || echo "STILL DOWN"

# Check logs — confirm old version running
docker compose logs $SERVICE --tail=10
```

## Step 4: Notify CEO

Write to event stream:

```bash
echo "{\"type\": \"rollback\", \"service\": \"$SERVICE\", \"reason\": \"[reason]\", \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\", \"status\": \"complete\"}" >> .pocketteam/events/stream.jsonl
```

## Step 5: Lock Deploys Until Fixed

```bash
# Create a deploy lock
touch .pocketteam/DEPLOY_LOCK
echo "Rollback at $(date). Reason: [reason]. Fix required before next deploy." > .pocketteam/DEPLOY_LOCK
```

## Post-Rollback

1. Service restored → notify CEO via event stream
2. Hand off to Investigator agent for root cause analysis
3. Do NOT deploy again until root cause is found and fixed
4. Remove DEPLOY_LOCK only after CEO approval

## Report

```
Rollback: [service]
Previous version: [sha]
Restored: yes / no
Time to restore: [seconds]
CEO notified: yes (event stream)
```
