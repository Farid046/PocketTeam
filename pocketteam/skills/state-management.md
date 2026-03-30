---
name: state-management
description: "Track project state in STATE.md. Use to persist decisions, blockers, and progress."
---

# Structured Project State

Maintains `.pocketteam/STATE.md` as a living document that captures the authoritative
current state of the project. Any agent or session can restore full context by reading
this file — no need to replay conversation history.

## When to Update STATE.md

- **Task completed:** Record what was done, what changed, what comes next.
- **Blocker encountered:** Record the blocker so the CEO can resolve it without context.
- **Decision made:** Major decisions (architecture, API contracts) belong here AND in CONTEXT.md.
- **Phase transition:** Moving from planning → implementation → review → deploy.
- **Session start (read-only):** Agents read STATE.md to understand where the project is.

## STATE.md Structure

Create or overwrite `.pocketteam/STATE.md` with this template:

```markdown
# Project State
_Last updated: [YYYY-MM-DD HH:MM] by [agent-name]_

## Current Phase
[planning | implementation | review | testing | deployment | maintenance]

### Active Sprint / Goal
[One sentence describing the current main objective]

## Active Tasks
| Task | Status | Owner | Notes |
|------|--------|-------|-------|
| [task name] | [in-progress / blocked / done] | [agent] | [brief note] |

## Decisions Made
| Decision | Choice | Date | Rationale |
|----------|--------|------|-----------|
| [decision] | [choice] | [date] | [why] |

## Blockers
| Blocker | Impact | Needs From | Since |
|---------|--------|------------|-------|
| [description] | [high/med/low] | [CEO/agent] | [date] |

## Recent Changes
_Last 5 significant changes:_
- [YYYY-MM-DD] [agent]: [what was done] ([files changed])
- ...

## Next Steps
1. [Next action with owner]
2. [Next action with owner]

## Context Pointers
- Plan: `.pocketteam/artifacts/plans/[plan-file].md`
- Decisions: `.pocketteam/CONTEXT.md`
- Event log: `.pocketteam/events/stream.jsonl`
```

## Update Protocol

### At Task Completion
1. Read current STATE.md (if exists).
2. Move completed tasks to "Recent Changes".
3. Update "Active Tasks" with remaining/new tasks.
4. Update "Current Phase" if it changed.
5. Update "Next Steps".
6. Write the file with updated timestamp and agent name.

### At Session Start (COO)
1. Read STATE.md if it exists.
2. Summarize current state to the CEO in one paragraph.
3. Ask: "Shall we continue with [next steps]?" — do not assume.

### When a Blocker Is Added
1. Add row to the Blockers table.
2. Set task status to "blocked".
3. Notify CEO via Telegram (if daemon is running).

## Fallback: STATE.md Does Not Exist

If STATE.md does not exist (fresh project or first use):
- Do not error. Create it fresh.
- Set "Current Phase" to "planning".
- Set "Active Tasks" and all tables to empty.
- This is normal for session 1.

## What NOT to Put in STATE.md

- Full file contents or diffs (use git diff for that)
- Conversation logs (use event stream)
- Sensitive data (tokens, passwords, keys)
- Speculative future plans beyond "Next Steps"

STATE.md is a snapshot, not an audit trail. Keep it current and scannable.
