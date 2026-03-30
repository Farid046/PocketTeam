---
name: competitive-analysis
description: "Analyze market competitors. Use when evaluating product positioning."
---

# /competitive-analysis — Competitive Analysis

Deep comparison of PocketTeam against specific competitors. Output includes a comparison table suitable for README.

## Setup

Define before starting:
- **Competitors to compare**: [list 3-5]
- **Features to compare**: [list 5-10 key capabilities]

## Feature Scoring

For each feature, score PocketTeam and each competitor:
- `+` = fully supported
- `~` = partial / limited
- `-` = not supported
- `?` = unknown (needs research)

## Comparison Table Template

```markdown
| Feature | PocketTeam | [Competitor A] | [Competitor B] | [Competitor C] |
|---------|-----------|----------------|----------------|----------------|
| Multi-agent orchestration | + | ~ | - | + |
| Safety hooks | + | - | - | - |
| Browser automation | + | - | + | - |
| Open source | + | - | + | + |
| Self-hosted | + | - | + | - |
| Real-time dashboard | + | - | - | ~ |
| Telegram integration | + | - | - | - |
```

## Analysis Sections

```markdown
## Where PocketTeam Leads
- [feature]: [why we're ahead] — opportunity to highlight in marketing

## Where Competitors Lead
- [feature]: [what they do better] — gap to close or consciously ignore

## Unique to PocketTeam (no competitor has)
- [feature] — strong differentiator, emphasize

## Commodity Features (everyone has)
- [feature] — table-stakes, don't over-invest here
```

## README Integration

When analysis is complete, propose updating the README comparison table:
1. Write updated table to proposal
2. Use `/propose-improvements` to submit for COO review
3. COO approves → Documentation agent updates README

## Save To

`.pocketteam/artifacts/plans/competitive-analysis-[date].md`
