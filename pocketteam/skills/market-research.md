---
name: market-research
description: "Research market trends and opportunities. Use for product strategy decisions."
---

# /market-research — Market Research

Research the competitive landscape and trends for a given product area using web search.

## Research Scope

Define before starting:
- **Product area**: [what space are we researching]
- **Question to answer**: [specific decision this research informs]
- **Time budget**: [30 min / 1 hour]

## Research Checklist

### Competitors
- [ ] List 5-10 direct competitors (same problem, same audience)
- [ ] List 3-5 indirect competitors (different approach, same audience)
- [ ] Note each competitor's: pricing, target customer, key differentiator

### Market Signals
- [ ] Recent funding or acquisitions in this space (last 12 months)
- [ ] Product Hunt launches in this category
- [ ] HN threads mentioning the problem (search: `site:news.ycombinator.com [problem]`)
- [ ] Reddit threads where target users discuss the problem

### Trends
- [ ] Is this market growing, mature, or declining?
- [ ] What features are becoming table-stakes (everyone has them)?
- [ ] What features are differentiators (few have them)?

## Output Format

Save to `.pocketteam/artifacts/plans/market-research-[topic]-[date].md`:

```markdown
# Market Research: [Topic]

**Date:** YYYY-MM-DD
**Question:** [what decision this informs]

## Competitors

| Name | Pricing | Target | Differentiator |
|------|---------|--------|----------------|

## Market Signals
- [signal]: [source + date]

## Trends
- Growing: [evidence]
- Table-stakes features: [list]
- Differentiator opportunities: [list]

## Recommendation
[Based on research: what should we do / avoid / watch]
```
