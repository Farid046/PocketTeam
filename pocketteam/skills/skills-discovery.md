---
name: skills-discovery
description: "List all available PocketTeam skills with categories. Use when asking what skills exist."
---

# PocketTeam Skills Discovery

Use when the CEO wants to know what capabilities are available. This skill discovers
all installed skills dynamically — no hardcoded list, so it always reflects the
current installation.

## When to Invoke

- User asks: "welche Skills gibt es?", "what skills do you have?", "help", "/skills"
- User asks for capabilities in a specific domain: "what deployment skills do you have?"
- After a fresh `pocketteam init` — orienting a new user
- Any time the skill list may have changed (after install or update)

## Discovery Procedure

### Step 1 — Find All Skills

Run a Glob on `.claude/skills/pocketteam/` to find all skill files:
- Flat files: `.claude/skills/pocketteam/*.md`

Read each file's YAML frontmatter to extract `name` and `description`.
If a file has no frontmatter or is missing `name`/`description`, use the filename
as the name and mark description as "(no description)".

### Step 2 — Categorize

Assign each skill to a category based on keywords in its description:

| Category | Keywords to look for |
|----------|---------------------|
| **Workflow** | autopilot, ralph, quick, pause, resume, state, discuss, wave |
| **Development** | tdd, test, debug, scaffold, review, verification, commit, browse |
| **Architecture** | architecture, design, codebase, map, breaking-change, threat |
| **Operations** | deploy, rollback, hotfix, health, log, diagnostic, monitor |
| **Documentation** | readme, doc, handoff, retro, weekly, product-brief |
| **Security** | security, owasp, dependency, audit, scan |
| **Research** | market, competitive, propose, investigate, timeline |
| **Meta** | skills, discovery, cost, schedule |

If no keyword matches, put the skill in **Other**.

### Step 3 — Present Formatted Table

Output grouped by category:

```
## PocketTeam Skills

### Workflow
| Skill | Description |
|-------|-------------|
| /autopilot | Full autonomous pipeline — plan to deploy |
| /ralph | Persistent implement-test-fix loop until all tests pass |
| ... | ... |

### Development
| Skill | Description |
|-------|-------------|
| /review | Comprehensive code review with checklist |
| /debug | Systematic root-cause debugging |
| ... | ... |

[... other categories ...]

Total: [N] skills installed
```

Truncate descriptions to ~80 characters if needed. Use the `/skillname` format
to signal they are invocable commands.

### Step 4 — Domain Filter (Optional)

If the user asked for skills in a specific domain (e.g. "deployment skills"),
show only the matching category and add:
"Showing [N] skills in Operations. Say '/skills' for the full list."

### Step 5 — Recommend (Optional)

If the user described a task (not just asked for a list), recommend 1–3 skills
that fit:

```
Based on what you described, these skills may help:
- **/debug** — systematic root-cause tracing
- **/investigate** — production incident analysis
```

## Skill Count Discrepancy

If the discovered count differs significantly from the expected count in MANIFEST.json,
note it:
"Note: MANIFEST.json lists [N] skills but only [M] files found in `.claude/skills/pocketteam/`.
Some skills may not have been installed. Run `pocketteam init` to reinstall."
