---
name: breaking-change-plan
description: "Plan breaking API or schema changes safely. Use when backwards compatibility is affected."
---

# /breaking-change-plan — Breaking Change Strategy

Use when a change involves DB schema changes, API contract changes, or anything that can't be rolled back trivially.

## Classify the Change

**Type A — DB Schema Change**
- Additive only (new nullable columns, new tables): safe, deploy any order
- Column rename/remove or type change: requires migration strategy (see below)
- Index changes: can lock table in production, plan maintenance window

**Type B — API Contract Change**
- New optional fields: backwards compatible, safe
- Renamed/removed fields or changed types: breaking, requires versioning
- New required fields: breaking for existing clients

**Type C — File/Config Format Change**
- Requires migration of existing files before old code is removed

## Zero-Downtime Migration Pattern (Expand/Contract)

```
Phase 1 — EXPAND: Add new structure, keep old structure
  Deploy → verify both work

Phase 2 — MIGRATE: Write migration script, run on staging first
  Script: [specific commands]
  Rollback: [specific undo commands]

Phase 3 — CONTRACT: Remove old structure once all clients updated
  Deploy → verify old structure absent
```

## Plan Template

```markdown
## Breaking Change Plan: [What]

### Change Type: [A/B/C]
### Zero-Downtime: [yes/no — reason if no]

### Phase 1 (Expand)
- Files: [list]
- Deploys: [sequence]

### Phase 2 (Migrate)
- Migration script: [path]
- Test on staging: [command]
- Production run: [command]
- Rollback: [command]

### Phase 3 (Contract)
- Remove: [files/columns/endpoints]
- Deploy after: [date/condition]

### Communication Plan
- Notify: [who] before Phase 1
- Deprecation notice: [when]
```
