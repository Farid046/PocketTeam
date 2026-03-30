---
name: update-readme
description: "Update README with current project state. Use after significant changes."
---

# /update-readme — README Update

After a feature ships, update README.md so it reflects the current state of the project. Do not leave docs stale.

## What to Check

```bash
BASE=$(git rev-parse --show-toplevel)

# What changed in this feature? (compare to last README update)
git log --oneline --since="$(git log --format='%ci' README.md | head -1)" --diff-filter=A -- '*.md' '*.py' '*.ts'

# What's currently documented vs. what exists?
cat $BASE/README.md
ls $BASE/.claude/agents/pocketteam/
ls $BASE/.claude/skills/pocketteam/
```

## Sections to Update

| Section | Update When |
|---------|------------|
| Feature list / What's included | New feature shipped |
| Setup / Installation | New dependencies or config required |
| Agent table | New agent added or agent description changed |
| Skills list | New skill added or removed |
| Architecture overview | New component added |
| Commands / Usage | New CLI commands or workflow keywords |

## Writing Rules

- Use past tense for completed changes ("Added X", not "Adding X")
- Be specific about versions: "requires Node 20+" not "requires Node"
- Commands must be copy-pasteable and tested — never document a command that doesn't work
- Remove documentation for features that no longer exist

## Process

1. Read current README fully
2. Read the plan/PR for what was shipped
3. Edit only the sections that need updating (do not rewrite unrelated sections)
4. Verify: run any commands shown in README to confirm they still work
5. Commit: `docs: update README for [feature]`

## Do Not

- Do not rewrite the entire README when only one section changed
- Do not add marketing language ("powerful", "amazing", "seamlessly")
- Do not add aspirational features that are not yet built
