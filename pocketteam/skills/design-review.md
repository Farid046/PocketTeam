---
name: design-review
description: "Review UI/UX for WCAG compliance and usability. Use after frontend changes."
---

# /design-review — UI/UX Review

Review the visual and interaction design of a UI change. Distinct from code quality — focus on user experience.

## Checklist

### Visual Hierarchy
- [ ] Most important element has highest visual weight (size, color, position)
- [ ] Secondary information is clearly subordinate
- [ ] Text is scannable — headings, not walls of prose

### Spacing & Layout
- [ ] Consistent spacing scale (not random pixel values)
- [ ] Content doesn't touch container edges
- [ ] Related elements are grouped, unrelated elements have clear separation

### Color
- [ ] Sufficient contrast (WCAG AA: 4.5:1 for text, 3:1 for UI elements)
- [ ] Color is not the only differentiator (also use icons, text, shape)
- [ ] Consistent use of brand colors — no ad-hoc hex values

### Responsive
- [ ] Works at 320px (mobile min), 768px (tablet), 1280px (desktop)
- [ ] Text remains readable at all sizes — no horizontal overflow
- [ ] Touch targets are at least 44×44px on mobile

### Accessibility (a11y)
- [ ] All images have alt text
- [ ] Form inputs have associated labels
- [ ] Interactive elements are keyboard-navigable (Tab order logical)
- [ ] Focus indicators visible
- [ ] No content conveyed by color alone

## Visual Verification (if ptbrowse available)

```bash
bun run pocketteam/browse/index.ts goto http://localhost:[port]
bun run pocketteam/browse/index.ts screenshot
bun run pocketteam/browse/index.ts viewport 375 812  # mobile
bun run pocketteam/browse/index.ts screenshot
```

## Output Format

```markdown
## Design Review: [Feature]

### Pass ✓
- [what works well]

### Fail ✗ (must fix)
- [issue]: [specific file/component] — [fix]

### Suggestions
- [improvement idea]: [rationale]

### Verdict: APPROVED / CHANGES REQUESTED
```
