# Contributing to PocketTeam

Thank you for contributing to PocketTeam! This guide explains the development setup, testing, and how to add new agents and skills.

## Development Environment Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- Bun (for dashboard development)
- Docker + Docker Compose v2
- Claude Code (for testing agent integrations)

### Clone and Install

```bash
# Clone the repository
git clone https://github.com/Farid046/PocketTeam.git
cd pocketteam

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install Python dependencies
pip install -e .
pip install -e ".[dev]"

# Install dashboard dependencies
cd dashboard
bun install
cd ..
```

### Configure for Development

```bash
# Initialize a dev project
pocketteam init --name dev-project

# Set up local Telegram (optional)
# Set environment variables in your shell or use a secrets manager.
# Never write credentials to files in the repo.

# Create .env for dashboard
cat > .env << EOF
VITE_AUTH_TOKEN=test-token-12345
EOF
```

## Testing

### Run All Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=pocketteam --cov-report=html

# Run specific test file
python -m pytest tests/test_config.py -v

# Run specific test
python -m pytest tests/test_config.py::test_load_config -v
```

### Test Structure

```
tests/
├── test_channels.py
├── test_cli_health_logs.py
├── test_computer_use.py
├── test_coordination.py
├── test_e2e.py
├── test_guardian.py
├── test_hooks_coverage.py
├── test_init.py
├── test_safety_openclaw.py
├── test_telegram_daemon.py
└── sdk_integration/
    ├── test_healer_live.py
    └── test_init_github.py
```

### Key Test Commands

```bash
# Test safety system
python -m pytest tests/test_guardian.py -v

# Test hooks coverage
python -m pytest tests/test_hooks_coverage.py -v

# Test Telegram daemon
python -m pytest tests/test_telegram_daemon.py -v

# Test with live SDK (requires setup)
python -m pytest tests/sdk_integration/ -v

# Test dashboard frontend (Node)
cd dashboard && npm run test
```

## Code Style

### Python Code

We use **Ruff** for linting and **MyPy** for type checking.

```bash
# Lint with Ruff
ruff check pocketteam/ --fix

# Type check with MyPy
mypy pocketteam/ --strict

# Format with Black (built into Ruff in v0.5+)
ruff format pocketteam/
```

### Code Style Guidelines

- **Line length**: 100 characters max (enforced by Ruff)
- **Type hints**: Required for all functions and class methods
- **Docstrings**: Module, class, and public function docstrings required (Google style)
- **Imports**: Organized into stdlib, third-party, local (enforced by Ruff)

### TypeScript Code (Dashboard)

```bash
# Lint and type-check
cd dashboard
npm run lint
npm run type-check

# Format with Prettier
npm run format
```

### Example Function

```python
from pathlib import Path

def load_config(project_root: Path | None = None) -> Config:
    """Load configuration from .pocketteam/config.yaml.

    Args:
        project_root: Path to project root. Defaults to current directory.

    Returns:
        Loaded configuration object.

    Raises:
        FileNotFoundError: If config file doesn't exist.
        ValueError: If config is invalid.
    """
    ...
```

## Project Structure

```
pocketteam/
├── __init__.py                 # Package init
├── cli.py                      # CLI commands
├── config.py                   # Configuration system
├── constants.py                # Global constants
├── core/
│   ├── pipeline.py            # Main execution pipeline
│   └── phase.py               # Pipeline phases
├── hooks/
│   ├── __init__.py
│   ├── keyword_detector.py    # autopilot/ralph detection
│   ├── delegation_enforcer.py # Agent permission checks
│   ├── session_start.py       # Session initialization
│   ├── agent_lifecycle.py     # Spawn/complete events
│   └── telegram_inbox.py      # Telegram message persistence
├── safety/
│   ├── allowlist.py           # Allowlist validation
│   ├── dsac.py                # D-SAC pattern
│   ├── guardian.py            # Main safety orchestrator
│   ├── network_rules.py       # Network domain checks
│   └── sensitive_paths.py     # Secrets file protection
├── browse/
│   └── ptbrowse.py           # Browser automation
├── statusline/
│   └── index.js              # CLI status line
└── init.py                    # Project initialization

dashboard/
├── src/
│   ├── frontend/             # React UI
│   │   ├── components/       # Reusable components
│   │   ├── views/            # Page views
│   │   ├── store/            # Zustand state
│   │   └── ws/               # WebSocket client
│   └── server/               # Express backend
│       ├── api/              # REST routes and WebSocket
│       ├── readers/          # Data readers
│       ├── auth.ts           # Auth middleware
│       └── server.ts         # Express setup
└── docker-compose.yml

.claude/
├── settings.json             # Hook configuration
└── agents/pocketteam/        # Agent definitions

tests/
└── (structured as above)
```

## Adding a New Agent

Agents are specialized Claude Code projects that handle specific tasks.

### Step 1: Create Agent Definition

Create `.claude/agents/pocketteam/<agent-name>.md`:

```markdown
---
name: <agent-name>
description: Brief description of what the agent does
model: claude-sonnet-4-6  # or claude-opus-4-6 for complex tasks
budget_usd: 2.0            # From AGENT_BUDGETS in constants.py
max_turns: 15              # From AGENT_MAX_TURNS in constants.py
tools:
  - Read
  - Glob
  - Grep
---

# <Agent Name>

You are the [Agent Name] for PocketTeam.

## Your Role

Describe what the agent does and their responsibilities.

## Tools

You have access to:
- Read: Read files from the repository
- Glob: Find files by pattern
- Grep: Search file contents

## Workflow

Describe the typical workflow and decision tree.

## Output Format

Describe what success looks like and how to format the final output.
```

### Step 2: Update Constants

Add the agent to `pocketteam/constants.py`:

```python
AGENT_MODELS = {
    ...
    "<agent-name>": "claude-sonnet-4-6",
}

AGENT_BUDGETS = {
    ...
    "<agent-name>": 2.0,
}

AGENT_MAX_TURNS = {
    ...
    "<agent-name>": 15,
}

AGENT_ALLOWED_TOOLS = {
    ...
    "<agent-name>": ["Read", "Glob", "Grep"],
}
```

### Step 3: Register in CLI

Update `pocketteam/cli.py` to expose the agent:

```python
@main.command()
def agent_name(ctx: click.Context):
    """Brief description."""
    # Delegate to the agent via Claude Code's Agent tool
    ...
```

### Step 4: Add Tests

Create `tests/test_<agent-name>.py`:

```python
from pathlib import Path
import pytest

def test_agent_loads():
    """Test that the agent definition loads correctly."""
    agent_def = Path(".claude/agents/pocketteam/<agent-name>.md")
    assert agent_def.exists()
    assert "model:" in agent_def.read_text()

def test_agent_in_constants():
    """Test that agent is registered in constants."""
    from pocketteam.constants import AGENT_MODELS
    assert "<agent-name>" in AGENT_MODELS
```

### Step 5: Document in README

Update the Agents table in `README.md`:

```markdown
| **Agent Name** | Brief Description | Sonnet | Key Responsibility |
```

## Adding a New Skill

Skills are high-level capabilities that agents can invoke.

### Step 1: Create Skill Definition

Create `.claude/skills/pocketteam/<skill-name>.md`:

```markdown
---
name: <skill-name>
agents: ["engineer", "qa"]  # Which agents can use this
description: Brief description
---

# Skill: <Skill Name>

## What It Does

Describe what the skill accomplishes.

## Inputs

- `param1`: Description
- `param2`: Description

## Outputs

Describe the output format and success criteria.

## Example Usage

Skills are invoked internally via Claude Code agents, not via a CLI command.
To trigger a skill, ask PocketTeam's COO in your Claude Code session, e.g.:
> "Use the **engineer** agent with the `<skill-name>` skill."

## Implementation

Describe the underlying tools and workflow.
```

### Step 2: Register in CLI

```python
@main.group()
def skill():
    """Manage skills."""
    pass

@skill.command("<skill-name>")
@click.option("--param1", required=True)
def skill_name(param1: str):
    """Run the skill."""
    ...
```

### Step 3: Add Tests

Create `tests/test_<skill-name>.py`:

```python
def test_skill_exists():
    """Verify skill definition."""
    skill_def = Path(".claude/skills/pocketteam/<skill-name>.md")
    assert skill_def.exists()
```

## PR Workflow

1. **Create a branch** for your feature:
   ```bash
   git checkout -b feature/my-feature
   ```

2. **Make your changes** and test:
   ```bash
   python -m pytest tests/ -v
   ruff check . --fix
   mypy . --strict
   ```

3. **Commit with a clear message**:
   ```bash
   git commit -m "feat: add new agent capability"
   ```

4. **Push and open a PR**:
   ```bash
   git push origin feature/my-feature
   ```

5. **The CI/CD pipeline** will:
   - Run all tests
   - Check code style
   - Run security audits
   - (Optionally) deploy to staging

6. **Get reviewed** by the team and merge when approved.

## Commit Message Format

Follow conventional commits:

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

- `feat` — New feature
- `fix` — Bug fix
- `refactor` — Code refactoring
- `test` — Test additions/updates
- `docs` — Documentation updates
- `chore` — Maintenance tasks
- `security` — Security improvements

### Examples

```bash
git commit -m "feat(agents): add new documentation agent"
git commit -m "fix(dashboard): correct WebSocket message handling"
git commit -m "docs(config): add environment variable reference"
git commit -m "test(safety): add network allowlist tests"
```

## Common Development Tasks

### Add a New Agent Command

```python
# pocketteam/cli.py
@main.command()
@click.option("--param", required=True)
def new_command(param: str):
    """Description."""
    from pocketteam.core.pipeline import run_agent

    result = run_agent(
        agent_type="product",
        task=param,
        context={}
    )
    click.echo(result)
```

### Modify Configuration Schema

1. Update `.pocketteam/config.yaml` example
2. Update `pocketteam/config.py` dataclasses
3. Add migration if needed
4. Update `docs/CONFIGURATION.md`
5. Add tests in `tests/test_config.py`

### Add a New Hook

1. Create hook function in `pocketteam/hooks/<hook-name>.py`
2. Register in `.claude/settings.json` under the appropriate hook type
3. Document in `docs/HOOKS.md`
4. Add tests in `tests/test_hooks_coverage.py`

### Update Dashboard API

1. Add endpoint to `dashboard/src/server/api/routes.ts`
2. Add TypeScript types to `dashboard/src/server/readers/types.ts`
3. Update WebSocket handler in `dashboard/src/server/api/websocket.ts`
4. Update frontend in `dashboard/src/frontend/`
5. Add tests to `tests/integration/test_dashboard.py`
6. Document in `docs/DASHBOARD.md`

## Debugging

### Print Debug Logs

```python
import logging
logger = logging.getLogger(__name__)

logger.debug("Debug message")
logger.info("Info message")
logger.warning("Warning message")
logger.error("Error message")
```

Set log level:

```bash
LOGLEVEL=DEBUG pocketteam start
```

### Run Dashboard in Dev Mode

```bash
cd dashboard
VITE_AUTH_TOKEN=test-token npm run dev
# Runs on http://localhost:5173 with hot reload
```

### Test with Live Claude Code

```bash
# Start monitoring logs
tail -f .pocketteam/events/stream.jsonl

# In another terminal, send a task via Telegram or use Claude Code directly.
# Agents are invoked internally via the COO — there is no `pocketteam agent run` CLI command.

# Watch the events stream for real-time updates
```

### Inspect WebSocket Messages

```bash
# Open developer console in dashboard at http://localhost:3847
# WebSocket messages are logged in the browser console

# Or via command line:
python -c "
import json
with open('.pocketteam/events/stream.jsonl') as f:
    for line in f:
        print(json.dumps(json.loads(line), indent=2))
"
```

## Documentation

- Update `README.md` for user-facing features
- Update `docs/CONFIGURATION.md` for new config options
- Update `docs/DASHBOARD.md` for API changes
- Update `docs/HOOKS.md` for hook system changes
- Update `CHANGELOG.md` for all releases

## Getting Help

- **Bug reports**: Open a GitHub issue with reproduction steps
- **Feature requests**: Describe the use case in an issue
- **Questions**: Open a discussion or ask in the issue tracker

## License

By contributing to PocketTeam, you agree that your contributions will be licensed under the MIT License.
