# Changelog

All notable changes to PocketTeam are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

---

## [1.0.11] - 2026-04-02

### Added

- **`pocketteam/insights_scheduler.py`**: Cross-platform OS scheduler for Auto-Insights.
  - macOS: creates a launchd plist at `~/Library/LaunchAgents/com.pocketteam.insights.plist`
  - Linux: installs a crontab entry with a `# pocketteam-insights` marker for safe removal
  - Windows: registers a daily task via `schtasks`
  - Public API: `install_scheduler(project_root, cron)`, `uninstall_scheduler()`, `scheduler_status()`

### Changed

- **`pocketteam insights on`**: Now calls `install_scheduler()` after saving config instead of
  printing manual `claude /schedule create` instructions.
- **`pocketteam insights off`**: Now calls `uninstall_scheduler()` after saving config instead of
  showing a manual removal URL.
- **`pocketteam insights status`**: Now displays OS scheduler registration status (platform,
  registered yes/no, detail string).

### Fixed

- **Telegram "Session gestartet" leaks into unrelated projects**: `_launch_claude()` in `cli.py`
  now requires `cfg.telegram.chat_id` to be non-empty in addition to `bot_token` before adding
  `--channels plugin:telegram@claude-plugins-official`. Previously, any project with a resolved
  `TELEGRAM_BOT_TOKEN` env var would activate the Telegram plugin even if that project never
  configured a `chat_id`.

---

## [1.0.10] - 2026-04-02

### Fixed

- **CRITICAL**: `_notify_telegram` in `session_start.py` now gates on the project-level
  `config.yaml` before attempting to send. Previously, the hook would send Telegram
  notifications in ANY project as long as the global `~/.claude/channels/telegram/.env`
  file existed — even if that project never configured Telegram. Now the function returns
  early if `config.yaml` is absent, if there is no `telegram:` section, or if `chat_id`
  is empty. Telegram notifications are strictly opt-in per project.

---

## [1.0.9] - 2026-04-02

---

## [1.0.8] - 2026-04-02

### Fixed

- `_setup_ptbrowse` now runs `bun install` in `pocketteam/browse/` after creating the
  wrapper script. Fixes missing `node_modules` (playwright-core etc.) for pipx users who
  never ran `bun install` manually.
- `_setup_statusline` now resolves the absolute path to `node` via `shutil.which` so the
  statusline command works regardless of the user's `PATH` at Claude Code startup.
- Updated stale docstring in `activity_logger.py`: removed obsolete `PYTHONPATH=.` prefix
  from the invocation example (hooks now use `sys.executable` and the installed package).

---

## [1.0.7] - 2026-04-02

### Fixed

- `_setup_statusline` now writes the absolute path to `statusline/index.js` in
  `settings.json` instead of the hardcoded relative path `pocketteam/statusline/index.js`.
  The relative path only worked when Claude Code was launched from the source-repo root;
  pipx installations have no `pocketteam/` directory in the project folder.
  Fix: use `Path(__file__).parent / "statusline" / "index.js"` which was already
  computed but not used for the command string.

---

## [1.0.6] - 2026-04-02

### Fixed

- Hooks now use `sys.executable` instead of the bare `python` command — fixes broken
  hooks on macOS (where only `python3` exists) and on pipx installations (where
  `pocketteam` lives in a venv and `PYTHONPATH=.` never resolved the package).
  Affected: `_setup_settings_json` in `init.py`, `TestRunner.run_pytest` in
  `test_runner.py`, and `BrowserTool.run_playwright_tests` in `browser_tools.py`.

---

## [1.0.5] - 2026-04-02

### Fixed

- `pocketteam uninstall` now stops the dashboard **before** deleting `.pocketteam/`
  (previously the config was deleted first, making it impossible to read the container name).

- Dashboard teardown now uses `docker compose -f <compose-file> down` instead of
  individual `docker stop` / `docker rm` calls — cleaner for Compose-managed containers.

- Replaced `except Exception: pass` in the dashboard-stop block with a visible
  `[yellow]Warning: could not stop dashboard container: ...[/]` message so failures
  are no longer silently swallowed.

---

## [1.0.4] - 2026-04-01

### Fixed

- `pocketteam uninstall` now stops and removes the dashboard Docker container and its compose directory.
  The command asks "Stop and remove dashboard container? [y/n]" before taking action (default: yes).
  Projects without a dashboard configured are not affected.

- Docker Compose project name is now set explicitly via a top-level `name:` field in the generated
  `docker-compose.yml`. This prevents Docker Desktop from grouping the container under a hash-derived
  ID — it now shows the readable container name (e.g. `myproject-dashboard`) as the project group.

---

## [1.0.3] - 2026-04-01

### Fixed

- `pocketteam start` no longer exits with "No conversation found to continue" when no previous session exists.
  The command now detects whether a Claude session exists for the current project (by checking `~/.claude/projects/<project-key>/*.jsonl`) and automatically starts a fresh session instead of passing `--continue` when none is found.

---

## [1.0.2] - 2026-04-01

### Fixed

- Dashboard Docker context was passed as executable instead of as `--context` flag; `pull` and `tag` subprocess calls now use `["docker", "--context", detected_context, ...]`

### Added

- COO delegation-only tool policy: tools restricted to `["Agent"]` via allowlist enforcement
- Fan-out/fan-in parallel investigation pattern for multi-agent research
- Skill catalog surfaced in COO system prompt
- `e2e-test` skill added for end-to-end test execution
- Session greeting dedup guard — prevents repeated Telegram welcome messages on re-entry
- Launch preparation: README polish, test coverage improvements, security hardening

### Fixed

- `pocketteam start` now correctly passes `--agent pocketteam/coo` flag to Claude Code
- Dashboard EmptyState properly displays new sessions without delegated agents

---

## [1.0.1] - 2026-04-02

### Fixed

- Dashboard auto-pulls from Docker Hub for pipx installations (no source code needed)
- API key warning softened — subscription mode is fully functional without API key
- GitHub repo creation handles empty repos gracefully
- Init no longer crashes when dashboard source is missing

---

## [1.0.0] - 2026-03-30

### Added

- **Self-Healing via GitHub Actions** — 24/7 monitoring of health and log endpoints
  - GitHub Actions workflow checks `/health` and `/logs` every hour
  - On failure: triggers Claude Code COO session on your machine via `/trigger-session`
  - COO analyzes, creates fix plan, notifies CEO via Telegram
  - CEO approves before any changes — no autonomous fixes
- **GitHub Integration in Init** — Step 5 automates full GitHub setup
  - Creates repo via `gh` CLI (or uses existing)
  - Sets secrets: ANTHROPIC_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, GH_PAT
  - Pushes monitoring workflow automatically
  - Fine-grained PAT for private repo access in GitHub Actions
- **Agent Registry for Safety Allowlist** — resolves Claude Code internal agent hash IDs to PocketTeam agent names
  - SubagentStart writes `agent_id → agent_type` mapping to `.pocketteam/agent-registry.json`
  - Guardian reads registry before checking the allowlist
  - Fixes critical bug where all subagent tool calls were denied as "Unknown agent"
- **59 skills** (was 37) — added `create-skill`, `add-mcp-server`, and 20 others
- **Agent SDK Integration Tests** — 47 tests covering healer, health checker, escalation, GitHub setup
  - Fake HTTP server with chaos modes for testing
  - CI workflow: `pocketteam-sdk-test.yml` (mock + live matrix)
- **Wave-Based Parallel Execution** — COO can run multiple agents simultaneously
- **Pre-Compact Context Snapshots** — task/plan/agent context preserved across context compaction
- **Auto-Triggered Session Detection** — marker file suppresses greeting for automated sessions

### Changed

- Version bumped from 0.1.0 to 1.0.0
- Healer rewritten: CEO-in-the-loop instead of autonomous auto-fix
- `GitHubActionsConfig` → `GitHubConfig` with repo_name, repo_owner, repo_private fields
- Backwards compat: `cfg.github_actions` still works as alias for `cfg.github`
- Repository URLs updated from pocketteamtest to PocketTeam
- Telegram daemon: sessions started with `-p` flag skip greeting message

### Fixed

- Agent allowlist: hash IDs now resolved to names via registry (was 100% denied)
- Workflow push: uses `git add -f` to override .gitignore
- Workflow push: uses `git push -u origin HEAD` for fresh branches
- Healer: reads Telegram credentials from env vars in CI (not just config)
- Dashboard: better error message when `dashboard/` directory not found

---

## [0.1.0] - 2026-03-26

### Added

- **12 specialized agents** with role-based permission models (COO, Product, Planner, Reviewer, Engineer, QA, Security, DevOps, Investigator, Documentation, Monitor, Observer)
- **Observer agent** for team learning and continuous improvement
  - Analyzes completed tasks for error patterns
  - Updates agent prompts with learnings
  - Tracks recurring issues and positive patterns
  - Stores learnings in `.pocketteam/learnings/`
- **Real-time 3D isometric dashboard** showing live agent activity, cost tracking, and team status
  - Pixel-art Habbo-style office visualization
  - Live event feed with agent actions and audit trail
  - Session picker for multi-session monitoring
  - Usage tracking (tokens, cost per agent, subscription vs API breakdown)
- **9-layer safety system** with runtime hooks that survive context compaction
  - PreToolUse and PostToolUse validation hooks
  - Network allowlist enforcement
  - Secrets detection and redaction
  - D-SAC v3.1 pattern for destructive operations (tool-call hash binding, re-initiation tracking)
  - Kill switch (< 1 second response time)
- **4 workflow modes** for different use cases
  - `autopilot:` full autonomous pipeline (plan → implement → test → deploy)
  - `ralph:` persistent mode with automatic fix loops until all tests pass
  - `quick:` speed mode skipping reviews
  - `deep-dive:` parallel research agents for thorough analysis
- **37 specialized skills** across the team
  - Product: market research, competitive analysis, product briefs
  - Planning: task breakdown, risk assessment, breaking-change plans
  - Engineering: scaffolding, debugging, hotfixes, refactoring
  - QA: smoke tests, visual QA, test data setup, E2E testing
  - Security: OWASP audits, CVE scanning, threat modeling
  - DevOps: staging deploys, canary releases, rollbacks
  - Documentation: README updates, architecture docs, stale-doc audits
  - Observer: retro, propose-improvements, weekly-digest
- **Configuration system** with `.pocketteam/config.yaml`
  - Auth modes (subscription, API key, hybrid)
  - Telegram integration with persistent sessions and auto-resume
  - Monitoring with auto-fix policy and staging-first deployment
  - Budget limits per agent per task
  - Network domain allowlist
  - Dashboard configuration
- **WebSocket real-time communication** between dashboard and backend
  - Agent spawn/update/complete events
  - Event stream with full audit trail
  - Debounced message batching (200ms)
  - Bearer token authentication with 60s ticket TTL
- **Telegram integration** with inbox persistence
  - Message recovery across session restarts
  - Message status tracking (received → presented)
  - Auto-resume on new messages
- **Event stream persistence** at `.pocketteam/events/stream.jsonl`
  - Agent lifecycle events (spawn, complete)
  - Tool call tracking and duration recording
- **Browser automation** via ptbrowse skill
  - Headed browser mode for visual debugging
  - Session management and screenshot capture
- **Git workflow integration**
  - Automatic stale branch cleanup
  - Release branch detection and versioning
- **CLI with extensive commands**
  - `pocketteam init` — project initialization
  - `pocketteam skill` — skill management (list, run, create)
  - `pocketteam agent` — agent status and management
  - `pocketteam monitor` — health check daemon
  - `pocketteam logs` — unified log viewer

### Changed

- **D-SAC upgraded to v3.1** with improved safety guarantees
  - Tool-call hash binding (prevents operation scope substitution)
  - Re-initiation tracking via sequence file
  - Lock file creation with 0o600 permissions
  - Persistent session_id fallback mechanism
- Upgraded dashboard frontend to React 18 with TypeScript
- Refactored WebSocket message types for stricter typing
- Improved agent lifecycle tracking with transcript-based tool call counting
- Enhanced auth system with timing-safe comparison to prevent token oracle attacks
- Switched from docker-compose v1 to v2 with fallback support
- Updated isometric rendering engine for smoother animations and better pixel-art quality

### Fixed

- COO live status now correctly reflects subagent activity
- Session detection improved for multi-session scenarios
- Layout overlaps in the 3D office view resolved
- Fixed idle animation timing and state management
- Kill switch response time now < 1 second (previously 2-5s)
- Network hook now correctly validates approved domains

### Security

- Bearer token authentication with timing-safe comparison on all API routes
- Secrets redaction on WebSocket messages (tool_result content stripped)
- Two-layer redaction system: sensitive content removal + regex-based redaction
- Network allowlist with approved domains (GitHub, npm, PyPI, Supabase, etc.)
- D-SAC pattern for destructive batch operations with approval tokens (5 min TTL)
- Sensitive files protected (config.yaml: 0o600)
- Environment variable isolation (.env files gitignored)

### Deprecated

- `docker-compose` (v1) — use `docker compose` (v2) instead

### Removed

- Disabled old survey aggregation endpoint (no longer used)

---

## Release Notes

### How to Deploy

1. **Initialize a project** with `pocketteam init`
2. **Configure** via `.pocketteam/config.yaml`
3. **Start the dashboard** with `pocketteam dashboard start`
4. **Send a task** via Telegram or Claude Code's input

### Next Steps

- Dashboard persistence (session state saved to disk)
- Advanced monitoring with custom health checks
- Multi-project dashboard aggregation
- Team slack integration
