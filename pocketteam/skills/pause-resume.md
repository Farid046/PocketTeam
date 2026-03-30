---
name: pause-resume
description: "Save and restore session context. Use when switching tasks or ending a session."
---

# Session Pause and Resume

Preserves full working context across session boundaries. When you pause, everything
needed to continue is written to `.pocketteam/context-handoff.md`. When you resume,
that file is read and context is restored before any new work begins.

## /pause — Saving Context

**Triggers:** "pause", "save state", "ich muss weg", "stop for now", "brb", "taking a break"

### What to Write

Write `.pocketteam/context-handoff.md` with ALL of the following:

```markdown
# Session Handoff
_Saved: [YYYY-MM-DD HH:MM]_
_Saved by: [COO / agent-name]_

## What We Were Doing
[1–3 sentences describing the active task and where we are in it]

## Active Task Details
- **Task:** [task name / feature]
- **Plan file:** [path if exists]
- **Current step:** [which step in the plan, e.g. "Step 3 of 7: Engineer implementation"]
- **Status:** [in-progress / waiting for review / waiting for CEO input]

## Open Questions (Unresolved)
_Things that were NOT decided and need CEO input when resuming:_
1. [question 1]
2. [question 2]

## Next Steps (in order)
1. [exactly what to do first when resuming]
2. [what comes after that]
3. [...]

## Changed Files
_Files modified in this session (not yet committed or recently committed):_
- [path/to/file.py] — [what changed]
- [path/to/file.ts] — [what changed]

## Context Pointers
- STATE.md: `.pocketteam/STATE.md`
- CONTEXT.md: `.pocketteam/CONTEXT.md`
- Plan: [path]
- Branch: [git branch name]
- Last commit: [git log --oneline -1]

## Agent Memory
_Key facts an agent needs that aren't in the files above:_
- [e.g. "CEO approved option B for the cache layer (see row 3 in discuss table)"]
- [e.g. "The test suite currently has 2 failing tests — expected, they are for new features"]
```

After writing the file:
1. Confirm to the CEO: "Context saved to `.pocketteam/context-handoff.md`. Resume anytime."
2. Update STATE.md with current status (use state-management skill if appropriate).

---

## /resume — Restoring Context

**Triggers:** "resume", "wo waren wir", "let's continue", "back", "what were we doing"

### Steps

1. Read `.pocketteam/context-handoff.md`.
2. If the file does not exist: say "No saved context found. What would you like to work on?"
3. Read `.pocketteam/STATE.md` if it exists (for broader project context).
4. Present a summary to the CEO:

```
## Resuming Session

**Last saved:** [timestamp]

**We were:** [1-sentence summary of active task]

**Current step:** [step N of M — description]

**Open questions:**
- [question 1]
- [question 2]

**Next action:** [first item from Next Steps]

Shall I continue with [next action]? (y / tell me something different)
```

5. Wait for CEO confirmation before executing anything.
6. After CEO confirms, proceed with the first item in "Next Steps".

### Important: Do Not Auto-Execute

On resume, always summarize and ask before acting. The CEO may have changed
their mind, found a new approach, or want to pick up from a different point.
Never silently re-run the last agent.

---

## Handoff File Management

- One file only: `.pocketteam/context-handoff.md` — always overwrite on new pause.
- The file is human-readable — the CEO can edit it between sessions.
- Do not delete it after resume. It serves as a historical record.
- If multiple pauses happened, the most recent save is always the active one.
