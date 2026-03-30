---
name: cost-report
description: "Generate per-agent cost report from token usage data. Use after task completion."
---

# Skill: Cost Report

Generate a cost report from `.pocketteam/costs/*.jsonl` and write the summary to `.pocketteam/artifacts/costs/`.

## When to Use

- After a completed task when cost data is available
- When the CEO asks "how much did this cost?"
- As part of the Observer post-task analysis

## Steps

### 1. Find Cost Files

```bash
ls .pocketteam/costs/*.jsonl
```

### 2. Read and Parse Records

Each `.jsonl` file is named `YYYY-MM-DD.jsonl`. Each line is a JSON record:

```json
{"ts": "2026-03-29T14:32:11.123456+00:00", "agent": "engineer", "cost_usd": 0.043, "input_tokens": 12400, "output_tokens": 890, "cache_read_tokens": 0}
```

### 3. Aggregate by Agent

Group all records by `agent` field. For each agent compute:
- `total_cost_usd` — sum of all `cost_usd` values
- `total_input_tokens` — sum of all `input_tokens`
- `total_output_tokens` — sum of all `output_tokens`
- `total_cache_read_tokens` — sum of all `cache_read_tokens`
- `call_count` — number of records

### 4. Apply Thresholds

| Check | Threshold | Flag |
|---|---|---|
| Task total | > $1.00 | HIGH COST |
| Any single agent | > $0.50 | FLAG FOR HAIKU DOWNGRADE |
| Any single agent | > $0.20 | NOTE AS EXPENSIVE |

### 5. Write Report

Write to `.pocketteam/artifacts/costs/YYYY-MM-DD-cost-report.md`:

```markdown
# Cost Report — YYYY-MM-DD

**Total Task Cost:** $X.XX

## Per-Agent Breakdown

| Agent | Calls | Cost (USD) | Input Tokens | Output Tokens | Cache Read |
|---|---|---|---|---|---|
| engineer | 3 | $0.087 | 24800 | 1780 | 0 |
| reviewer | 1 | $0.012 | 3200 | 410 | 0 |
| qa | 2 | $0.031 | 8900 | 620 | 0 |

## Flags

- [HIGH COST] Total exceeded $1.00 — review agent model tiers
- [HAIKU CANDIDATE] engineer ($0.087) — consider downgrade for simple tasks

## Notes

Cost data sourced from `.pocketteam/costs/YYYY-MM-DD.jsonl`.
Missing or zero-cost records indicate subscription mode (no API billing).
```

### 6. Ensure Output Directory Exists

Create `.pocketteam/artifacts/costs/` if it does not exist before writing.

## Edge Cases

- **No cost files found:** Log "No cost data available for this date." Do not fail.
- **All cost_usd = 0.0:** Normal in subscription mode. Report tokens only, note "Subscription mode — no API billing."
- **Multiple days:** If reporting across a date range, merge all `.jsonl` files and note the date range in the report header.
