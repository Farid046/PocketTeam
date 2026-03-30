---
name: setup-schedules
description: "Configure recurring automated tasks. Use to set up nightly tests or weekly digests."
---

# Skill: PocketTeam Scheduled Tasks Setup

Use when setting up or managing recurring automated tasks for a PocketTeam project.

## Available Schedules

### 1. Nightly Test Suite
- **Cron:** 0 0 * * * (2am Berlin / midnight UTC)
- **Prompt:** "Run the full test suite with pytest. If any tests fail, create a GitHub issue with the test name, error message, and suggested fix."
- **Value:** Catches regressions overnight before the team starts working.

### 2. Weekly Security Scan
- **Cron:** 0 7 * * 1 (Monday 9am Berlin / 7am UTC)
- **Prompt:** "Run a security audit: check for known CVEs in dependencies (pip audit, npm audit), scan for hardcoded secrets, review OWASP Top 10 compliance. Create a GitHub issue for any findings."
- **Value:** Proactive security without manual effort.

### 3. Weekly Digest
- **Cron:** 0 6 * * 5 (Friday 8am Berlin / 6am UTC)
- **Prompt:** "Create a weekly summary: list all commits this week (git log --since='7 days ago'), all PRs opened/merged/closed, any new issues. Write the digest to .pocketteam/artifacts/digests/YYYY-MM-DD.md."
- **Value:** CEO gets a project overview every Friday morning.

## How to Set Up

Use the /schedule skill in Claude Code:
```
/schedule
```

Then follow the interactive prompts to create each trigger.

## Limitations
- Remote agents run in Anthropic's cloud — no access to local services (Docker, databases)
- Minimum interval: 1 hour
- Git repo is cloned fresh each run
- Telegram notifications require MCP connector setup at https://claude.ai/settings/connectors

## Managing Schedules
- View: https://claude.ai/code/scheduled
- Run manually: /schedule run <trigger_id>
- Delete: via the web UI at https://claude.ai/code/scheduled
