# Changelog

All notable changes to PocketTeam are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
- **10-layer safety system** with runtime hooks that survive context compaction
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
3. **Start the dashboard** with the dashboard-deploy skill
4. **Send a task** via Telegram or Claude Code's input

### Next Steps

- Dashboard persistence (session state saved to disk)
- Advanced monitoring with custom health checks
- Multi-project dashboard aggregation
- Team slack integration
