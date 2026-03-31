---
name: e2e-test
description: End-to-end test execution protocol for CLI and API integration tests
---

# /e2e-test — End-to-End Test Protocol

## When to Use

- After implementing a new CLI command or API endpoint
- Before production deploys when integration behavior must be confirmed
- When a bug spans multiple system layers (CLI → core → storage)
- When unit tests pass but the integrated system behaves unexpectedly

## Test Dimensions

### CLI Commands
- Execute every new/changed command with valid inputs
- Test flag combinations and edge-case argument values
- Verify exit codes (0 for success, non-zero for errors)
- Confirm stdout/stderr output matches expected format

### API Endpoints
- Test every HTTP method on new/changed routes
- Verify response status codes and response body structure
- Test authentication and authorization boundaries
- Confirm error responses return structured error payloads

### Integration Flows
- Test complete user journeys from entry point to final state
- Verify state persists correctly across command/request boundaries
- Confirm event stream and artifact outputs are correct
- Test that agent-to-agent handoffs pass the right context

### Error Paths
- Supply invalid inputs — confirm graceful rejection with clear message
- Simulate missing dependencies (missing config, missing files)
- Test timeout and retry behavior
- Verify partial failure does not corrupt system state

## Protocol

### Setup
1. Confirm test environment is isolated (do not run against production state)
2. Set required environment variables (`POCKETTEAM_ENV=test` or equivalent)
3. Seed any required fixtures or test data
4. Verify the service/process under test is in a known clean state

### Execute
5. Run each test case in order: happy path first, then error paths
6. Capture full stdout, stderr, exit codes, and any file outputs
7. Do not skip slow tests — E2E tests must run completely

### Assert
8. Compare actual output against expected output exactly
9. Verify no unexpected side effects (no extra files, no state mutations)
10. Confirm timing is within acceptable bounds (flag tests exceeding 10s)

### Cleanup
11. Remove test fixtures, temp files, and seeded state
12. Reset environment to pre-test state
13. Confirm no dangling processes remain

## Assertion Checklist

- [ ] Exit code matches expected value
- [ ] stdout contains expected content (or is empty when expected)
- [ ] stderr is empty (or contains only expected warnings)
- [ ] Response status codes are correct
- [ ] Response body structure is valid and complete
- [ ] File outputs exist and have expected content
- [ ] Database / state changes are correctly applied
- [ ] No unexpected side effects

## Reporting Format

```
E2E Test Report — [Feature / Component]
Date: [ISO timestamp]

Test Cases:
  [test-name]: PASS / FAIL
    Expected: [value]
    Actual:   [value]
    Duration: [ms]

Summary:
  Total:  [N]
  Passed: [N]
  Failed: [N]

Failed Details:
  [test-name]: [failure description]
    Steps to reproduce: [steps]
    Error output: [stderr / stack trace]

Verdict: PASS / FAIL
Next step: [proceed to Security | back to Engineer]
```

## Failure Protocol

If any E2E test fails:

1. **Do not proceed** to the next pipeline step
2. Record the failing test name, expected vs actual output, and full error
3. Return `STATUS: DONE_WITH_CONCERNS — [N] E2E tests failing` to the COO
4. The COO routes back to the Engineer with the failure details
5. Re-run the full E2E suite after the fix — do not run only the failing test
