---
name: risk-assessment
description: "Identify and assess project risks. Use during planning or before major decisions."
---

# /risk-assessment — Risk Analysis

Produce a structured risk assessment for a plan before implementation begins.

## Risk Categories to Check

- **Data loss** — migrations, deletes, overwrites
- **Breaking changes** — API contracts, DB schema, file formats
- **Security regression** — new attack surface, auth bypass, exposed secrets
- **Performance degradation** — N+1 queries, unbounded loops, large payloads
- **Dependency risk** — new packages, version conflicts, license issues
- **Rollback difficulty** — irreversible actions (data migrations, external API calls)

## Risk Matrix

For each risk found, score it:

| Risk | Likelihood (1-3) | Impact (1-3) | Score | Mitigation |
|------|-----------------|--------------|-------|------------|
| [risk] | 2 | 3 | 6 | [action] |

Score = Likelihood × Impact. Prioritize by score descending.

## Thresholds

- Score 7-9 → **BLOCKER**: Must mitigate before proceeding
- Score 4-6 → **HIGH**: Mitigation required, document in plan
- Score 1-3 → **LOW**: Document, monitor, no blocker

## Output Format

```markdown
## Risk Assessment: [Plan Name]

### BLOCKERS (score 7-9)
1. [Risk]: [Why] → Mitigation: [specific action]

### HIGH (score 4-6)
1. [Risk]: [Why] → Mitigation: [specific action]

### LOW (score 1-3)
1. [Risk]: Accepted — monitoring plan: [how]

### Recommendation
- PROCEED / PROCEED WITH CONDITIONS / DO NOT PROCEED
- Conditions: [list if applicable]
```
