---
name: stale-doc-audit
description: "Find outdated documentation. Use when docs may not reflect current code."
---

# /stale-doc-audit — Stale Documentation Audit

Systematically find documentation that no longer matches the codebase.

## Step 1: Find All Docs

```bash
BASE=/Users/farid/Documents/entwicklung/PocketTeam

find $BASE -name "*.md" -not -path "*/node_modules/*" -not -path "*/.git/*" | sort
```

## Step 2: Extract References and Verify

```bash
# Find all file paths mentioned in docs
grep -rh '\`[^`]*\.[a-z]\{2,4\}\`\|`[^`]*/[^`]*`' $BASE --include="*.md" | \
  grep -oP '`[^`]+`' | sort -u | head -50

# Find all command examples (lines starting with common CLI prefixes)
grep -rn "^bun run\|^npm \|^python\|^docker\|^curl\|^git " $BASE --include="*.md" | head -30
```

## Step 3: Staleness Checks

```bash
# Check: do documented agent files exist?
for agent in engineer planner reviewer qa security devops investigator monitor documentation observer product; do
  test -f $BASE/.claude/agents/pocketteam/$agent.md && echo "OK: $agent" || echo "MISSING: $agent"
done

# Check: do documented skill files exist?
ls $BASE/.claude/skills/pocketteam/

# Check: do documented ports match running services
grep -rn "3848\|3849\|localhost:" $BASE --include="*.md" | grep -v "node_modules"

# Check: do documented env vars exist
grep -rn "POCKETTEAM_\|PT_\|CLAUDE_" $BASE --include="*.md" | grep -v "#"
```

## Step 4: Outdated Feature References

Search for references to things that were removed:
```bash
# Find references to old skill names that were deleted
grep -rn "review\.md\|investigate\.md\|security-audit\.md\|ship\.md" $BASE --include="*.md"
```

## Output Format

```markdown
## Stale Doc Audit: [Date]

### Confirmed Stale
| File | Line | Issue | Fix |
|------|------|-------|-----|
| README.md | 42 | References deleted skill ship.md | Remove reference |

### Potentially Stale (needs manual check)
- [file:line]: [why it might be stale]

### All Good
- [count] docs checked, no issues found
```

## After Audit

Fix stale docs in the same commit. Do not open tickets for one-line fixes.
