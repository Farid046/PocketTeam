---
name: wave-execute
description: "Execute plan tasks in parallel waves. Use when plan has independent implementation steps."
---

# Skill: Wave Execution Protocol

**Trigger:** A plan contains `<!-- wave:N ... -->` annotations on 4 or more tasks.

---

## Overview

Wave execution parallelizes independent tasks within the same wave while preserving
dependency ordering between waves. The COO reads wave annotations, resolves conflicts,
then spawns sub-agents per wave — at most 3 at a time.

---

## Annotation Format

Each annotated task block looks like:

```markdown
<!-- wave:1 provides:auth-models files:models.py,migrations.py -->
1. Create database models
```

| Attribute | Required | Description |
|---|---|---|
| `wave:N` | Yes | Wave number (integer, starts at 1) |
| `provides:X` | No | Logical artifact this task exports (used by `requires:`) |
| `requires:X,Y` | No | Comma-separated list of `provides` tokens this task needs |
| `files:A,B` | Yes* | Comma-separated list of files this task writes or modifies |

*`files:` is required for conflict detection. Tasks without `files:` are treated as file-conflict-free.

---

## Wave Execution Procedure

### Step 1 — Parse

Read every `<!-- wave:N ... -->` annotation in the plan. Build a list of tasks with:
- wave number
- task description
- provides token (if any)
- requires list (if any)
- files list (if any)

### Step 2 — Group by Wave Number

Collect tasks into wave buckets: `{1: [...], 2: [...], 3: [...]}`.

### Step 3 — Conflict Check (per wave)

For each wave bucket:
1. Flatten all `files:` values across tasks in the wave into a single list.
2. Compare `len(all_files_list)` vs `len(set(all_files_list))`.
3. If they differ, there is at least one file claimed by two or more tasks → conflict.

**Conflict resolution:**
- Split conflicting tasks into sequential sub-waves.
- Ordering: task with **more files** goes first (it likely lays the foundation).
- Log the conflict to the event stream as event type `wave_conflict_resolved`:
  ```json
  {"event": "wave_conflict_resolved", "wave": 2, "conflicting_file": "api.py", "resolution": "sequential_sub_waves"}
  ```

### Step 4 — Execute Waves in Order

For each wave (and sub-wave):
1. Spawn sub-agents in parallel — **hard limit: max 3 tasks simultaneously**.
2. If a wave has > 3 tasks, batch into groups of 3 and execute sequentially within the wave.
3. Wait for all sub-agents in the current wave to finish.

### Step 5 — Evaluate Results

After each wave completes, check every sub-agent's status token (last non-empty line):

| Status | Action |
|---|---|
| `STATUS: DONE` | Continue to next wave |
| `STATUS: DONE_WITH_CONCERNS — reason` | COO records concern, may surface to CEO, continues |
| `STATUS: NEEDS_CONTEXT — what` | COO provides missing context, re-runs the task before proceeding |
| `STATUS: BLOCKED — reason` | **Stop the wave chain.** Escalate to CEO before continuing. |

If any task is `BLOCKED`, do not start the next wave until the blockage is resolved.

---

## File-Conflict Detection — Quick Reference

```
wave_tasks = [t1, t2, t3]  # tasks in same wave
all_files  = [f for t in wave_tasks for f in t.files]
conflict   = len(all_files) != len(set(all_files))
```

When conflict is detected, find the duplicate files:
```
from collections import Counter
dupes = [f for f, count in Counter(all_files).items() if count > 1]
```

Split: task(s) writing the duplicate file first (more-files task first), remaining tasks second.

---

## Hard Limit: Max 3 Parallel Tasks

Never spawn more than 3 sub-agent tasks in parallel in a single wave batch.
If a wave has 5 tasks, execute as: batch-of-3 → then batch-of-2.

This limit exists to:
- Prevent context exhaustion
- Keep error attribution clear
- Stay within sub-agent concurrency constraints

---

## When NOT to Use Waves

Do not use wave execution when:

1. **Fewer than 4 tasks** — sequential execution is just as fast and simpler.
2. **Shared files without clear ownership** — if tasks write to the same config file and the split is ambiguous, sequential is safer.
3. **Plan lacks `<!-- wave:N -->` annotations** — never infer waves from task order alone.
4. **All tasks depend on each other** — a single long dependency chain has no parallelism benefit.
5. **Tasks involve database migrations** — migration order must be strictly sequential.

---

## Example: 3-Wave Plan

```markdown
<!-- wave:1 provides:db-models files:models/user.py,models/base.py -->
1. Create User and Base database models

<!-- wave:1 provides:db-migrations files:migrations/0001_initial.py -->
2. Generate initial migration

<!-- wave:2 requires:db-models provides:user-service files:services/user_service.py -->
3. Implement UserService business logic

<!-- wave:2 requires:db-models provides:user-serializer files:serializers/user.py -->
4. Write User serializer

<!-- wave:3 requires:user-service,user-serializer provides:user-api files:api/views.py,api/urls.py -->
5. Wire up API views and URL routing
```

Execution order:
- Wave 1: Tasks 1 and 2 run in parallel (no file overlap).
- Wave 2: Tasks 3 and 4 run in parallel (different files, both require `db-models` which wave 1 provided).
- Wave 3: Task 5 runs after wave 2 is fully complete.

Total wall time: 3 waves instead of 5 sequential steps.
