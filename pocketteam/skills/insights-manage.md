---
name: insights-manage
description: View, configure, and act on insights reports and schedule
---

# Insights Management

Help the CEO manage the Auto-Insights system. Respond to these intents:

## "Show latest insights" / "Letzte Insights zeigen"
1. Find the most recent `.md` file in `.pocketteam/artifacts/insights/`
2. Read and summarize it
3. Highlight the proposed improvements

## "Change insights frequency" / "Insights Frequenz ändern"
1. Ask for new cron expression or use natural language (e.g., "twice a day" → `0 8,20 * * *`)
2. Update `.pocketteam/config.yaml` → `insights.schedule`
3. Remind CEO to update the Remote Agent trigger:
   - "Update your schedule at: https://claude.ai/code/scheduled"
   - Or run: `claude /schedule`

## "Disable insights" / "Insights ausschalten"
1. Set `.pocketteam/config.yaml` → `insights.enabled = false`
2. Remind CEO to remove the Remote Agent trigger at https://claude.ai/code/scheduled
3. Confirm: "Insights disabled. Re-enable anytime with: pocketteam insights on"

## "Apply proposal" / "Vorschlag umsetzen"
1. Read the latest insights report from `.pocketteam/artifacts/insights/`
2. Extract the "Proposed Improvements" section
3. For EACH proposed improvement, delegate to the COO pipeline:
   - COO creates a plan
   - Reviewer reviews the plan
   - CEO approves (HUMAN GATE)
   - Engineer implements
   - QA tests
4. NEVER skip the pipeline — each improvement goes through the full process

## "Compare insights" / "Insights vergleichen"
1. Read the two most recent reports
2. Show delta: what improved, what worsened, new patterns

## Constraints
- Always read config from `.pocketteam/config.yaml` for current state
- Never auto-apply changes
- Keep responses concise
