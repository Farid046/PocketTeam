---
name: atomic-commits
description: "Conventional commit format reference. Use when committing implementation tasks."
---

# Skill: Atomic Commits

Reference for conventional commit format used across PocketTeam.

## Format

```
{type}({scope}): {description}
```

- `{type}` — one of the types below
- `{scope}` — module, agent, or component being changed
- `{description}` — present tense, imperative mood, ≤72 chars total line length

## Commit Types

| Type | When to use | Example scope |
|---|---|---|
| `feat` | New feature or capability | `planner`, `auth`, `dashboard` |
| `fix` | Bug fix | `hooks`, `telegram`, `session` |
| `refactor` | Code restructuring, no behavior change | `agent-lifecycle`, `cost-tracker` |
| `test` | Adding or updating tests | `context-warning`, `structured-status` |
| `docs` | Documentation, README, inline comments | `readme`, `api-docs` |
| `chore` | Config, tooling, dependencies, CI | `settings`, `constants`, `deps` |

## PocketTeam-Typical Examples

```bash
# Feature additions
git commit -m "feat(planner): add batch question table format"
git commit -m "feat(reviewer): add two-stage spec compliance check"
git commit -m "feat(engineer): enforce atomic commit format per task"

# Bug fixes
git commit -m "fix(hooks): handle missing session-status.json gracefully"
git commit -m "fix(telegram): prevent duplicate session on daemon restart"
git commit -m "fix(session-start): read correct TELEGRAM_BOT_TOKEN env key"

# Refactors
git commit -m "refactor(agent-lifecycle): extract status parser into own function"
git commit -m "refactor(cost-tracker): move JSONL append logic to helper"

# Tests
git commit -m "test(context-awareness): add 7 unit tests including stale file case"
git commit -m "test(cost-tracker): cover zero-cost and missing usage dict edge cases"

# Docs
git commit -m "docs(skills): add atomic-commits reference skill"
git commit -m "docs(mcp): document per-task MCP activation strategy"

# Chore
git commit -m "chore(constants): add CONTEXT_WARNING thresholds and COSTS_DIR"
git commit -m "chore(settings): register context_warning PostToolUse hook"
```

## Rules

1. **One task = one commit.** Never bundle multiple logical changes.
2. **Commit outcomes, not process.** Do not commit PLAN.md, WIP states, or review notes.
3. **Stage specific files.** Never `git add .` or `git add -A` — accidentally stages secrets.
4. **No fixup commits.** Get it right the first time. If you need to correct, amend only if not yet pushed.
5. **Scope is required** for PocketTeam agents — it makes the log scannable.

## Anti-Patterns to Avoid

```bash
# Too broad — what was done?
git commit -m "updates"

# Bundles unrelated changes
git commit -m "feat: planner + engineer + reviewer changes"

# Process commit — noise in log
git commit -m "add PLAN.md"
git commit -m "WIP"

# Past tense — use imperative
git commit -m "fixed the bug"   # wrong
git commit -m "fix(hooks): ..."  # correct
```
