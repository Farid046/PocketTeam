---
name: service-deploy
description: "Deploy microservice to staging then production. Use when shipping features."
---

# /service-deploy — Generic Service Deploy

For deploying any service in the PocketTeam stack that is not the dashboard. Always staging-first.

## Identify the Service

```bash
# List all services in compose
docker compose config --services

# Check current state
docker compose ps
```

## Pre-Deploy Checklist

- [ ] Service name confirmed: `[service]`
- [ ] Image tagged: `[image]:[sha]`
- [ ] Tests passed for this service
- [ ] CEO approval confirmed

## Staging Deploy

```bash
SERVICE=[service-name]

# Pull or build
docker compose -f docker-compose.staging.yml build $SERVICE

# Restart service in staging
docker compose -f docker-compose.staging.yml up -d --force-recreate $SERVICE

# Health check (adjust URL to service)
sleep 3
docker compose -f docker-compose.staging.yml ps $SERVICE
docker compose -f docker-compose.staging.yml logs $SERVICE --tail=20
```

## Verify Staging

Run the appropriate health check for the service:
- HTTP service: `curl -sf http://[staging-host]:[port]/health`
- Worker/daemon: `docker compose -f docker-compose.staging.yml ps $SERVICE | grep "Up"`
- Confirm no ERROR in logs

## Production Deploy

Only proceed if staging is confirmed healthy.

```bash
# Production deploy
docker compose up -d --force-recreate $SERVICE

# Verify
sleep 3
docker compose ps $SERVICE
docker compose logs $SERVICE --tail=20 | grep -i "error\|fatal" && echo "ERRORS — ROLLBACK" || echo "Clean"
```

## Environment Variables

Never hardcode env vars. Verify they are set:

```bash
docker compose config | grep -A5 $SERVICE | grep -i "env\|secret\|key"
# Confirm all required vars present, none have placeholder values
```

## Report

```
Service Deploy: [service] @ [sha]
Staging: PASS / FAIL
Production: PASS / FAIL
Env vars: verified
```
