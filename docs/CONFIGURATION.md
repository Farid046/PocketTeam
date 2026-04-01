# Configuration Guide

PocketTeam is configured via `.pocketteam/config.yaml`, environment variables, and the CLI. This guide covers all configuration options.

## Quick Start

Initialize a new project:

```bash
pocketteam init --name my-project
```

This creates `.pocketteam/config.yaml` with defaults. You can then customize it:

```bash
# Edit the config file
nano .pocketteam/config.yaml

# Verify configuration
pocketteam config show
```

## Configuration File Structure

The config file is stored at `.pocketteam/config.yaml` and uses YAML format:

```yaml
project:
  name: my-project
  health_url: https://api.example.com/health

auth:
  mode: subscription  # "subscription" | "api_key" | "hybrid"
  api_key: $ANTHROPIC_API_KEY

telegram:
  bot_token: $TELEGRAM_BOT_TOKEN
  chat_id: "123456789"
  persistent_sessions: true
  auto_resume: true

monitoring:
  enabled: true
  auto_fix: true
  staging_first: true
  max_fix_attempts: 3
  interval_steady: 300
  health_url: https://api.example.com/health

budget:
  max_per_task: 5.0
  prefer_subscription: true
  warn_api_costs: true

github_actions:
  enabled: true
  api_key: $ANTHROPIC_API_KEY
  model: claude-haiku-4-5-20251001
  schedule: "0 * * * *"

network:
  approved_domains: []  # Additional domains beyond defaults

dashboard:
  enabled: false
  port: 3847
  image: pocketteam-dashboard
  image_version: 1.0.0
  domain: ""
  compose_dir: ""
  docker_context: "default"
  compose_command: "docker compose"
  claude_version_at_init: ""
  compose_checksum: ""
  project_root: ""
  claude_project_hash: ""
```

## Configuration Options

### Project Section

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | string | (directory name) | Project name displayed in logs and Telegram |
| `health_url` | string | "" | Health check endpoint URL (used by monitor agent) |

### Auth Section

| Field | Type | Default | Description |
|---|---|---|---|
| `mode` | string | "subscription" | Authentication mode. `subscription` uses Claude Code's included tokens. `api_key` uses an API key. `hybrid` tries subscription first, then API key. |
| `api_key` | string | "" | Anthropic API key (only used in `api_key`/`hybrid` modes). Use `$ANTHROPIC_API_KEY` to reference an environment variable. |

**Secret storage**: Never commit the literal API key to git. Instead, use environment variable references:
- `$ANTHROPIC_API_KEY` — reads from `$ANTHROPIC_API_KEY` env var
- `${ANTHROPIC_API_KEY}` — same as above (alternative syntax)

The actual secret lives in `.pocketteam/.env` (gitignored):

```bash
# .pocketteam/.env
ANTHROPIC_API_KEY=sk-ant-...
```

### Telegram Section

| Field | Type | Default | Description |
|---|---|---|---|
| `bot_token` | string | "" | Telegram Bot API token. Use `$TELEGRAM_BOT_TOKEN` to reference an env var. |
| `chat_id` | string | "" | Telegram chat ID where the COO receives tasks. |
| `persistent_sessions` | bool | true | Save session state to disk for recovery after restarts. |
| `auto_resume` | bool | true | Automatically resume a paused task when a new message arrives. |

Setup Telegram:
1. Create a bot with @BotFather on Telegram
2. Get the bot token
3. Get your chat ID (send `/start` to @userinfobot)
4. Store in `.pocketteam/.env`:

```bash
TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
```

### Monitoring Section

| Field | Type | Default | Description |
|---|---|---|---|
| `enabled` | bool | true | Enable the monitor agent for 24/7 health checks. |
| `auto_fix` | bool | true | Automatically attempt to fix issues when detected. |
| `staging_first` | bool | true | Always deploy fixes to staging before production. |
| `max_fix_attempts` | int | 3 | Max auto-fix attempts (3-strike rule). After this, escalate to CEO. |
| `interval_steady` | int | 300 | Health check interval in steady state (seconds). Default: 5 min. |
| `health_url` | string | (from project) | Override the health check URL. |

The monitor agent:
- Checks every `interval_steady` seconds in steady state
- Switches to 30s checks on anomaly detection
- Runs for 15 min after each production deployment (canary monitoring)
- Stops on 3 failed fixes and escalates to CEO

### Budget Section

| Field | Type | Default | Description |
|---|---|---|---|
| `max_per_task` | float | 5.0 | Max API cost per task (USD). Only enforced in API key mode. |
| `prefer_subscription` | bool | true | Prioritize subscription over API key when both available. |
| `warn_api_costs` | bool | true | Print warnings when estimated API cost exceeds thresholds. |

Per-agent budgets (defaults, can't be overridden):

| Agent | Budget |
|---|---|
| COO | $2.00 |
| Product | $2.00 |
| Planner | $3.00 |
| Reviewer | $2.00 |
| Engineer | $5.00 |
| QA | $3.00 |
| Security | $2.00 |
| DevOps | $2.00 |
| Investigator | $3.00 |
| Documentation | $1.00 |
| Monitor | $0.50 |
| Observer | $0.50 |

### GitHub Actions Section

| Field | Type | Default | Description |
|---|---|---|---|
| `enabled` | bool | true | Enable automated CI/CD runs (if repo is on GitHub). |
| `api_key` | string | "" | Anthropic API key (stored as GitHub Secret `ANTHROPIC_API_KEY`). |
| `model` | string | "claude-haiku-4-5-20251001" | Model to use for headless CI/CD runs. |
| `schedule` | string | "0 * * * *" | Cron schedule for automated runs (default: every hour). |

To set up GitHub Actions:
1. Create a GitHub Secret called `ANTHROPIC_API_KEY` in your repo
2. Set it in config: `pocketteam config set github_actions.api_key '$ANTHROPIC_API_KEY'`
3. PocketTeam will auto-detect and use it in CI/CD workflows

### Network Section

| Field | Type | Default | Description |
|---|---|---|---|
| `approved_domains` | list | (see below) | Additional domains beyond the defaults. |

**Default approved domains**:
- github.com
- api.github.com
- api.supabase.com
- registry.npmjs.org
- pypi.org
- docs.anthropic.com

To add custom domains:

```yaml
network:
  approved_domains:
    - api.example.com
    - cdn.custom.com
```

### Dashboard Section

| Field | Type | Default | Description |
|---|---|---|---|
| `enabled` | bool | false | Enable the real-time 3D dashboard. |
| `port` | int | 3847 | Port to run the dashboard on. |
| `image` | string | "pocketteam-dashboard" | Docker image name. |
| `image_version` | string | "1.0.0" | Docker image version tag. |
| `domain` | string | "" | Custom domain for the dashboard (optional). |
| `compose_dir` | string | "" | Path to docker-compose.yml. |
| `docker_context` | string | "default" | Docker context to use for builds. |
| `compose_command` | string | "docker compose" | Use "docker-compose" for v1 or "docker compose" for v2. |

To enable the dashboard:

```bash
pocketteam dashboard start
```

This will:
1. Detect Docker and docker-compose
2. Build the dashboard image
3. Start the container on the configured port
4. Print the access URL with auth token

Access the dashboard:
- Local: `http://localhost:3847`
- Remote: `https://<your-domain>.com`
- Auth: Bearer token (printed on startup)

## Environment Variables

PocketTeam reads from system environment variables and `.pocketteam/.env`.

### Loading Order

1. System environment variables (highest priority)
2. `.pocketteam/.env` (gitignored, local overrides)
3. Config file defaults (lowest priority)

### Supported Variables

| Variable | Used By | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | Engineer, Planner, QA, Security | API key for Anthropic models |
| `TELEGRAM_BOT_TOKEN` | COO | Telegram bot token |
| `CLAUDE_SESSION_ID` | Hooks | Current Claude Code session ID |
| `PYTHONPATH` | Hooks | Python module search path |

### Example .env File

```bash
# .pocketteam/.env (gitignored)
ANTHROPIC_API_KEY=sk-ant-...
TELEGRAM_BOT_TOKEN=123456:ABC-...
```

Load with:

```bash
source .pocketteam/.env
export $(cat .pocketteam/.env | grep -v '^#' | xargs)
```

## Model Configuration

### Agent Models

Each agent uses a specific model. You cannot override this per-task, but you can change the defaults in `pocketteam/constants.py`:

```python
AGENT_MODELS = {
    "coo":           "claude-sonnet-4-6",
    "planner":       "claude-opus-4-6",     # Always Opus for best plans
    "engineer":      "claude-sonnet-4-6",   # Upgrade to Opus on-demand
    "documentation": "claude-haiku-4-5-20251001",  # Cheap for simple docs
    ...
}
```

### Model Selection Strategy

- **Sonnet** (claude-sonnet-4-6): Default for all agents. Fast and cost-effective.
- **Opus** (claude-opus-4-6): Used by Planner (first stop for every task) and Engineer on complex tasks.
- **Haiku** (claude-haiku-4-5-20251001): Used by Documentation, Monitor, Observer for simple tasks.

To upgrade engineer to Opus for a task, use the `ralph:` or `autopilot:` modes:

```
ralph: implement this complex feature
```

## Secrets Management

### Best Practices

1. **Never commit secrets** to git
2. **Use environment variable references** in config.yaml:
   ```yaml
   auth:
     api_key: $ANTHROPIC_API_KEY
   ```
3. **Store actual secrets in `.pocketteam/.env`**:
   ```bash
   ANTHROPIC_API_KEY=sk-ant-...
   ```
4. **Gitignore `.pocketteam/.env`** (already done in default .gitignore)
5. **Config.yaml is safe** to commit (no literal secrets)

### Secret Files

These files are always gitignored:

- `.pocketteam/.env` — local secrets
- `.pocketteam/telegram.env` — Telegram bot token
- `.pocketteam/config.yaml` — protected with 0o600 permissions
- `*.pem`, `*.key` — private keys
- `.aws/*` — AWS credentials
- `.ssh/*` — SSH keys

## Configuration Commands

### View Configuration

```bash
# Show entire config
pocketteam config show

# Show specific section
pocketteam config show auth
pocketteam config show dashboard
```

### Modify Configuration

```bash
# Set a value
pocketteam config set project.name "new-name"
pocketteam config set dashboard.enabled true
pocketteam config set monitoring.interval_steady 600

# Reset to defaults
pocketteam config reset
```

### Validate Configuration

```bash
# Check for errors
pocketteam config validate

# Show warnings (e.g., Telegram not configured)
pocketteam config check
```

## Example Configurations

### Development Project

```yaml
project:
  name: dev-project
  health_url: http://localhost:8000/health

auth:
  mode: subscription

telegram:
  bot_token: $TELEGRAM_BOT_TOKEN
  chat_id: "123456789"
  persistent_sessions: true
  auto_resume: true

monitoring:
  enabled: false  # Disable in dev

budget:
  max_per_task: 10.0  # More relaxed budget in dev

dashboard:
  enabled: true
  port: 3847
```

### Production Project

```yaml
project:
  name: prod-project
  health_url: https://api.example.com/health

auth:
  mode: hybrid  # Try subscription first, then API key
  api_key: $ANTHROPIC_API_KEY

telegram:
  bot_token: $TELEGRAM_BOT_TOKEN
  chat_id: "123456789"
  persistent_sessions: true
  auto_resume: true

monitoring:
  enabled: true
  auto_fix: true
  staging_first: true
  max_fix_attempts: 3
  interval_steady: 300

budget:
  max_per_task: 3.0  # Strict budget in production

github_actions:
  enabled: true
  api_key: $ANTHROPIC_API_KEY
  schedule: "0 */6 * * *"  # Every 6 hours

network:
  approved_domains:
    - api.example.com
    - cdn.example.com

dashboard:
  enabled: true
  port: 3847
  domain: dashboard.example.com
  docker_context: production
```

### Minimal Project (API Key Only)

```yaml
project:
  name: minimal-project

auth:
  mode: api_key
  api_key: $ANTHROPIC_API_KEY

monitoring:
  enabled: false

budget:
  max_per_task: 2.0

dashboard:
  enabled: false
```

## Troubleshooting

### "Config file not found"

Make sure you've initialized the project:

```bash
pocketteam init
```

### "API key not found"

Check that:
1. `.pocketteam/.env` exists
2. `ANTHROPIC_API_KEY` is set in the env file
3. Syntax is correct: `ANTHROPIC_API_KEY=sk-ant-...` (no quotes)

### "Telegram token invalid"

Verify:
1. Token is from @BotFather (starts with numbers and `:`)
2. Token is stored in `.pocketteam/.env`
3. Chat ID is valid (from @userinfobot)

### "Network domain not approved"

Add the domain to `network.approved_domains`:

```bash
pocketteam config set network.approved_domains '["api.example.com"]'
```

Or edit `.pocketteam/config.yaml`:

```yaml
network:
  approved_domains:
    - api.example.com
```

## See Also

- [CONTRIBUTING.md](CONTRIBUTING.md) — Development setup and testing
- [DASHBOARD.md](DASHBOARD.md) — Dashboard API and WebSocket messages
- [HOOKS.md](HOOKS.md) — Extensibility and hook system
