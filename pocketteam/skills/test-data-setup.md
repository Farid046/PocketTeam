---
name: test-data-setup
description: "Create realistic test data and fixtures. Use when tests need sample data."
---

# /test-data-setup — Test Data & Fixtures

Set up the test data infrastructure so tests are isolated, repeatable, and don't depend on real external services.

## Principles

- Tests must not depend on production data or prod environment variables
- Each test cleans up after itself (no state leaking between tests)
- Fixtures live in `tests/fixtures/` or `tests/conftest.py`

## Python (pytest) Setup

```python
# tests/conftest.py
import pytest

@pytest.fixture(autouse=True)
def reset_state():
    """Reset any global state before each test."""
    yield
    # teardown here

@pytest.fixture
def mock_agent_event():
    return {
        "type": "tool_use",
        "agent": "engineer",
        "session_id": "test-session-123",
        "tool": "Write",
        "timestamp": "2026-01-01T00:00:00Z"
    }

@pytest.fixture
def tmp_event_stream(tmp_path):
    stream = tmp_path / "stream.jsonl"
    stream.write_text("")
    return stream
```

## TypeScript (Vitest/Jest) Setup

```typescript
// tests/setup.ts
beforeEach(() => {
  vi.clearAllMocks();
  vi.resetModules();
});

// Fixture factory
export function makeAgent(overrides = {}) {
  return {
    id: "engineer",
    name: "Engineer",
    status: "idle",
    sessionId: "test-123",
    ...overrides,
  };
}
```

## Mocking External Services

```python
# Mock file system reads
with patch("builtins.open", mock_open(read_data='{"key": "value"}')):
    result = my_function()

# Mock subprocess calls
with patch("subprocess.run") as mock_run:
    mock_run.return_value = MagicMock(returncode=0, stdout=b"ok")
    result = my_function()
```

## Checklist

- [ ] No test reads from `.pocketteam/events/stream.jsonl` (use `tmp_path` fixture)
- [ ] No test calls real HTTP endpoints (mock or use local test server)
- [ ] No test depends on a specific file existing in the repo at a hardcoded path
- [ ] Fixtures are documented with a one-line docstring
- [ ] Tests can run in any order without failing
