---
name: tdd
description: "Test-driven development discipline. Write failing test first, then implement."
---

# Test-Driven Development

## The Iron Law
NO production code without a failing test first.

## Red-Green-Refactor Cycle

### RED — Write the failing test
1. Write a test that describes the desired behavior
2. Run it — confirm it FAILS
3. Verify the failure message is correct (not a syntax error, but a real assertion failure)

### GREEN — Write minimal code
4. Write the MINIMUM code to make the test pass
5. Run it — confirm it PASSES
6. No extra code. No "while I'm here" additions.

### REFACTOR
7. Clean up only if needed (remove duplication, improve naming)
8. Run tests — confirm still GREEN

## Rationalization Table

| Excuse | Counter |
|--------|---------|
| "Too simple to test" | Tests document behavior. Simple code still needs documentation. |
| "I'll test after" | Test-after only covers what you remember. Test-first discovers edge cases. |
| "This is just a refactor" | Refactors change behavior. Write the test that proves it doesn't. |
| "The framework handles this" | Test YOUR code's use of the framework, not the framework itself. |
| "I already wrote the code" | Delete it. Start with the test. Sunk cost is not a reason. |
| "It's obvious it works" | If it's obvious, the test takes 30 seconds to write. |
| "Tests slow me down" | Bugs slow you down more. Tests prevent bugs. |
| "I'm confident" | Confidence is not evidence. Run the test. |
| "The deadline is tight" | Bugs found later cost 10x more than tests written now. |
| "This is internal code" | Internal code has users too — future you. |
| "I'll add tests in the next PR" | You won't. Write them now. |
| "The existing code has no tests" | Be the change. Start here. |

## When NOT to use TDD
- Exploratory prototyping (throw-away code)
- Configuration changes (no logic to test)
- Documentation-only changes
