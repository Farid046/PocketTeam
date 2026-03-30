---
name: task-breakdown
description: "Break epic into parallelizable tasks. Use when planning large implementations."
---

# /task-breakdown — Task Decomposition

Break a large task into smaller units that can be worked on in parallel or sequenced without blocking.

## Process

### Step 1: Identify Boundaries
- List all files that need to change
- Group changes by: backend / frontend / config / tests / docs
- Mark hard dependencies (A must finish before B)

### Step 2: Decompose into Units

Each unit must be:
- **Independent** — no circular dependencies between units
- **Testable** — can be verified in isolation
- **Deliverable** — merged alone without breaking main

### Step 3: Parallelism Map

```
[Unit A] ─┐
[Unit B] ─┼─→ [Integration Unit] → [Tests] → [Docs]
[Unit C] ─┘
```

Mark which units can run in parallel vs. must sequence.

### Step 4: Output Format

```markdown
## Task: [Name]

### Units

| # | Unit | Files | Depends On | Can Parallelize With |
|---|------|-------|------------|----------------------|
| 1 | [name] | [files] | none | 2, 3 |
| 2 | [name] | [files] | none | 1, 3 |
| 3 | [name] | [files] | 1, 2 | none |

### Estimated Complexity
- Total files: N
- Parallel opportunities: N units
- Suggested agent assignments: [list]
```

## Anti-Patterns to Avoid
- Units larger than 5 files (split further)
- Units with no clear test criterion
- Circular dependencies (redesign the split)
