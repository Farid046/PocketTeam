---
name: visual-qa
description: "Screenshot-based visual testing. Use to verify UI matches design specs."
---

# /visual-qa — Visual QA with ptbrowse

Use the PocketTeam browser (ptbrowse) to verify UI changes visually and interactively.

## Setup

```bash
# Start dashboard if not running
cd /Users/farid/Documents/entwicklung/PocketTeam/dashboard
bun run dev &

# Open the page
bun run pocketteam/browse/index.ts goto http://localhost:3848
```

## Core Verification Workflow

```bash
# 1. Full page snapshot (see what's there)
bun run pocketteam/browse/index.ts snapshot

# 2. Screenshot for visual record
bun run pocketteam/browse/index.ts screenshot
# Saved to .pocketteam/screenshots/

# 3. Check specific text is present
bun run pocketteam/browse/index.ts assert text "Expected Label"

# 4. Check no error state
bun run pocketteam/browse/index.ts assert no-text "Error"
bun run pocketteam/browse/index.ts assert no-text "undefined"
bun run pocketteam/browse/index.ts assert no-text "NaN"
```

## Interactive Element Testing

```bash
# Find interactive elements
bun run pocketteam/browse/index.ts snapshot -i

# Click a button (use @e ref from snapshot output)
bun run pocketteam/browse/index.ts click @e5

# Wait for result, then check
bun run pocketteam/browse/index.ts wait text "Expected Result"
bun run pocketteam/browse/index.ts snapshot -D   # diff — shows only changes
```

## Responsive Testing

```bash
# Mobile
bun run pocketteam/browse/index.ts viewport 375 812
bun run pocketteam/browse/index.ts screenshot
bun run pocketteam/browse/index.ts assert no-text "overflow"

# Tablet
bun run pocketteam/browse/index.ts viewport 768 1024
bun run pocketteam/browse/index.ts screenshot

# Desktop
bun run pocketteam/browse/index.ts viewport 1440 900
bun run pocketteam/browse/index.ts screenshot
```

## Common Failure Patterns to Check

- Text "undefined" or "null" rendered to screen → data binding bug
- Empty containers with no loading/empty state → missing state handling
- Console errors: `bun run pocketteam/browse/index.ts console`
- Layout break at mobile: check with `viewport 375 812` + screenshot

## Report Format

```
Visual QA: [feature]
Screenshots: .pocketteam/screenshots/[names]
Checks:
  - [check]: PASS / FAIL
  - ...
Console errors: none / [list]
Verdict: APPROVED / ISSUES FOUND
```
