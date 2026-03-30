---
name: dashboard-deploy
description: "Deploy PocketTeam dashboard. Use when updating the monitoring dashboard."
---

# /dashboard-deploy — PocketTeam Dashboard Deploy

Primary deploy job for the PocketTeam dashboard. Always staging first, then production.

## Pre-Deploy Checklist

- [ ] Tests passed (QA signed off)
- [ ] Security scan clean (Security signed off)
- [ ] CEO approved deploy (human gate confirmed)
- [ ] Current git status clean (`git status` → no uncommitted changes)

## Build

```bash
cd /Users/farid/Documents/entwicklung/PocketTeam/dashboard

# Build production image
docker build -t pocketteam-dashboard:$(git rev-parse --short HEAD) -t pocketteam-dashboard:latest .

# Verify build
docker images pocketteam-dashboard --format "table {{.Tag}}\t{{.Size}}\t{{.CreatedAt}}"
```

## Staging Deploy

```bash
# Start staging (port 3849)
docker compose -f docker-compose.staging.yml up -d --force-recreate

# Wait for startup
sleep 5

# Smoke test staging
curl -sf http://localhost:3849/api/health && echo "Staging OK" || echo "Staging FAILED"
bun run pocketteam/browse/index.ts goto http://localhost:3849
bun run pocketteam/browse/index.ts assert text "PocketTeam"
```

## Production Deploy (only after staging passes)

```bash
# Swap production (port 3848)
docker compose up -d --force-recreate dashboard

# Wait for startup
sleep 5

# Smoke test production
curl -sf http://localhost:3848/api/health && echo "Production OK" || echo "Production FAILED — ROLLBACK NOW"
```

## Post-Deploy

```bash
# Confirm running container
docker compose ps dashboard

# Tail logs for 60 seconds watching for errors
docker compose logs -f dashboard --since=1m 2>&1 | timeout 60 grep -i "error\|fatal\|exception" && echo "ERRORS FOUND" || echo "Logs clean"
```

## Rollback

If production smoke test fails → run `/rollback` skill immediately.

## Report

```
Dashboard Deploy: [git short SHA]
Staging: PASS / FAIL
Production: PASS / FAIL
Duration: [time]
```
