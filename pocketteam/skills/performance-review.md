---
name: performance-review
description: "Analyze code performance and bottlenecks. Use when response times degrade."
---

# /performance-review — Performance Review

Review code for performance issues before they reach production. Focus on measurable impact.

## Search Patterns (run these first)

```bash
# N+1 query candidates (loop containing DB call)
grep -n "for\|forEach\|map" [file] | head -30

# Unbounded list operations
grep -n "\.all()\|SELECT \*\|findAll" [file]

# Missing indexes (look for WHERE clauses on unindexed columns in queries)
grep -rn "WHERE\|filter_by" [file]

# Synchronous blocking in async context
grep -n "time.sleep\|\.join()\|readFileSync" [file]
```

## Checklist

### Database
- [ ] No N+1 queries (queries inside loops)
- [ ] Pagination on all list endpoints (no unbounded SELECT *)
- [ ] Indexes exist for WHERE/ORDER BY columns
- [ ] Bulk operations used where applicable (`INSERT INTO ... VALUES (many)`)

### Computation
- [ ] No O(n²) or worse in hot paths (loops inside loops over large collections)
- [ ] Expensive computations cached where result is stable
- [ ] JSON serialization not happening on every request for static data

### Network & I/O
- [ ] No sequential await chains that could be `Promise.all()`
- [ ] Large payloads compressed or paginated
- [ ] No file reads on every request for static config

### Frontend
- [ ] No re-renders triggered by referentially unstable props (new objects in JSX)
- [ ] Large lists virtualized if > 100 items
- [ ] Images have explicit dimensions (prevents layout shift)

## Output Format

```markdown
## Performance Review: [Feature]

### Critical (will degrade at scale)
- [File:line]: [issue] — [expected impact] — [fix]

### Moderate (noticeable under load)
- [File:line]: [issue] — [fix]

### Acceptable / No Issues

### Verdict: APPROVED / CHANGES REQUESTED
```
