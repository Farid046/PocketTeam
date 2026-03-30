---
name: architecture-review
description: "Review system architecture for scalability and security. Use before major changes."
---

# /architecture-review — Architecture Review

Review a design or implementation for architectural soundness. Goes beyond code style to system structure.

## What to Read First

- Existing files in the same layer/module (understand established patterns)
- Any ADRs in `ARCHITECTURE.md` or `.pocketteam/docs/`
- The plan that was approved (compare intent vs. implementation)

## Checklist

### Pattern Compliance
- [ ] Follows existing layer separation (server/client/shared — no mixing)
- [ ] New abstractions match existing naming and structure conventions
- [ ] No new design patterns introduced without justification

### Coupling & Cohesion
- [ ] Modules have single responsibility (does one thing well)
- [ ] Dependencies point in the right direction (no circular imports)
- [ ] External dependencies isolated behind interfaces (easy to swap)

### Maintainability
- [ ] Code can be understood without the author present
- [ ] Complex logic has inline comments explaining WHY, not WHAT
- [ ] No hardcoded values that belong in config

### Scalability
- [ ] No O(n²) loops hidden in utility functions
- [ ] No synchronous operations that should be async
- [ ] State management is predictable and traceable

### Testability
- [ ] Business logic is separated from I/O (pure functions where possible)
- [ ] No untestable global state mutations
- [ ] Dependencies are injectable (not hard-imported at module level)

## Output Format

```markdown
## Architecture Review: [Feature]

### Compliant ✓
- [what is well-structured]

### Violations ✗ (must fix)
1. [Pattern/principle]: [File:line] — [issue] — [recommended fix]

### Debt Introduced (acceptable but document)
- [what] — why acceptable — [where to track]

### Verdict: APPROVED / CHANGES REQUESTED
```
