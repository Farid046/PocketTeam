<p align="center">
  <img src="https://img.shields.io/badge/agents-11-blue?style=for-the-badge" alt="11 Agents" />
  <img src="https://img.shields.io/badge/safety_layers-10-red?style=for-the-badge" alt="10 Safety Layers" />
  <img src="https://img.shields.io/badge/tests-497-brightgreen?style=for-the-badge" alt="497 Tests" />
  <img src="https://img.shields.io/badge/license-MIT-green?style=for-the-badge" alt="MIT License" />
</p>

<h1 align="center">PocketTeam</h1>

<p align="center">
  <strong>Your autonomous AI IT team that plans, codes, reviews, tests, deploys, and self-heals.</strong>
  <br />
  <strong>11 specialized agents. 10 safety layers. Runs on your Claude Code subscription.</strong>
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> &bull;
  <a href="#how-it-works">How It Works</a> &bull;
  <a href="#agents">Agents</a> &bull;
  <a href="#safety">Safety</a> &bull;
  <a href="#commands">Commands</a> &bull;
  <a href="#comparison">Comparison</a>
</p>

---

## The Problem

AI coding agents are powerful but dangerous. Without proper guardrails:

- **OpenClaw** deleted 200+ emails because safety constraints lived in the conversation context and were lost during compaction
- **Autonomous agents** have run `DROP DATABASE`, pushed to production without tests, and leaked secrets
- **Single-agent systems** can't handle complex projects — they lose context, skip reviews, forget to test

You need a **team**, not a solo agent. And that team needs **real safety** — not just a prompt saying "be careful."

## The Solution

PocketTeam gives you a full autonomous IT team with enterprise-grade safety:

```
CEO (You)
  |
  v
COO (orchestrator) ─── coordinates everything
  |
  ├── Product Advisor ── validates demand before building
  ├── Planner ────────── creates detailed plans
  ├── Reviewer ──────── reviews plans + code + design
  ├── Engineer ──────── implements (Opus for complex tasks)
  ├── QA ─────────────── runs tests + browser testing
  ├── Security ──────── OWASP audit + dependency scanning
  ├── DevOps ─────────── deploys (staging-first, canary)
  ├── Investigator ──── root-cause analysis
  ├── Documentation ─── keeps docs in sync
  ├── Monitor ────────── watches production 24/7
  └── Observer ──────── learns from team mistakes
```

Every tool call passes through **10 safety layers** that are implemented as runtime hooks — not prompts that can be lost or manipulated.

## Quick Start

```bash
# Install from GitHub (private repo — needs access)
pip install git+https://github.com/Farid046/pocketteamtest.git

# Or install locally for development
git clone https://github.com/Farid046/pocketteamtest.git
cd pocketteamtest
pip install -e ".[dev]"

# Initialize in your project
cd your-project
pocketteam init

# Run a task
pocketteam run "Add user authentication with OAuth2"

# Or just open Claude Code — PocketTeam is active via .claude/CLAUDE.md
claude
> Build a REST API with pagination and rate limiting
```

> **PyPI**: `pip install pocketteam` will work once we publish to PyPI. For now, install from GitHub or locally.

That's it. The COO takes over: plans the work, delegates to agents, reviews code, runs tests, audits security, and asks you to approve before deploying.

## How It Works

### 1. You give a task (Terminal, VS Code, or Telegram)

```
You: "Build a dark mode toggle"
```

### 2. The pipeline runs automatically

```
Phase 1: PLANNING
  ├── Planner reads codebase, writes plan
  ├── Reviewer validates architecture + risks
  └── HUMAN GATE: You approve the plan

Phase 2: IMPLEMENTATION
  ├── Engineer implements on feature branch
  ├── Reviewer code-reviews (max 3 rounds)
  ├── QA runs all tests (unit + integration + browser)
  ├── Security audits (OWASP + dependency CVEs)
  └── Documentation updates docs

Phase 3: STAGING
  └── DevOps deploys to staging + smoke tests

Phase 4: PRODUCTION
  ├── HUMAN GATE: You approve production deploy
  ├── DevOps deploys (canary strategy)
  └── Monitor watches for 15 min post-deploy

Phase 5: MONITORING (24/7)
  ├── Health checks every 5 minutes
  ├── Log analysis for error patterns
  └── Auto-fix with staging-first + 3-strike rule
```

### 3. You stay in control

- **4 Human Gates**: Product, Plan, Production, Incident
- **Kill Switch**: `pocketteam kill` or `/kill` via Telegram — stops everything in <1 second
- **Telegram**: Get updates and approve deployments from your phone
- **Budget Tracking**: Per-agent spend limits, subscription-first cost model

## Agents

| Agent | Role | Model | Tools |
|---|---|---|---|
| **COO** | Orchestrates the team | Sonnet | Delegation only |
| **Product Advisor** | Validates demand (6 forcing questions) | Sonnet | Read, Search, Web |
| **Planner** | Creates detailed plans | Sonnet | Read, Search |
| **Reviewer** | Reviews plans + code + design | Sonnet | Read, Search |
| **Engineer** | Implements features | Sonnet/Opus | Full access |
| **QA** | Tests (unit, integration, E2E) | Sonnet | Full access |
| **Security** | OWASP, STRIDE, CVE scanning | Sonnet | Read, Bash |
| **DevOps** | Deploy, rollback, CI/CD | Sonnet | Full access |
| **Investigator** | Root-cause analysis | Sonnet | Read, Bash |
| **Documentation** | Keeps docs in sync | Haiku | Read, Write |
| **Monitor** | Production health 24/7 | Haiku | Read, Bash |
| **Observer** | Learns from team mistakes | Haiku | Read, Write |

### Cost Model: Subscription-First

PocketTeam is designed to run on your **Claude Code subscription** ($20 Pro / $100 Max / $200 Team).

- **No API key needed** for interactive use
- **Haiku for cheap tasks** (monitoring, docs) — minimal token usage
- **Sonnet for most work** — good balance of quality and speed
- **Opus only on-demand** — when Engineer encounters complex multi-file tasks
- **API key fallback** — for CI/CD and headless environments

**Result**: A full AI team for $100/month flat. Not $X per token.

## Safety

### Why 10 Layers?

Because OpenClaw taught us that prompts are not safety. Their safety constraints lived in conversation context, got compacted away, and an agent deleted 200+ emails. Our safety lives in **runtime hooks** that survive context compaction and cannot be "convinced" to bypass.

```
Layer  1: NEVER_ALLOW ──────── Absolute blocklist (rm -rf /, DROP DATABASE, fork bombs)
Layer  2: DESTRUCTIVE_PATTERNS  Only with plan approval (git push --force, DELETE FROM)
Layer  3: MCP TOOL SAFETY ──── SQL injection prevention, parameterized queries
Layer  4: NETWORK SAFETY ───── Domain allowlist, exfiltration prevention
Layer  5: SENSITIVE FILES ──── .env, .ssh, .aws, *.pem protected
Layer  6: AGENT ALLOWLIST ──── Per-agent tool permissions (planner can't Write)
Layer  7: SCOPE + RATE LIMIT ─ Budget per agent, file scope from plan
Layer  8: AUDIT LOG ─────────── Every decision logged, incident playbooks
Layer  9: D-SAC PATTERN ────── Dry-run → Staged → Approval → Commit
Layer 10: KILL SWITCH ──────── Out-of-band, separate process, <1s response
```

### Key Safety Features

**D-SAC Pattern** (for all destructive operations):
```
1. DRY-RUN:  Show exactly what will change (with hash)
2. STAGED:   Create time-limited approval token (5 min TTL)
3. APPROVAL: CEO approves (or plan pre-approves)
4. COMMIT:   Execute with rate limiting + audit trail
```

**Kill Switch** (3 ways to activate):
```bash
pocketteam kill          # CLI
/kill                    # Telegram
touch .pocketteam/KILL   # Signal file
```

**Self-Healing Safety**:
- Always staging-first (never fix production directly)
- 3-Strike Rule: after 3 failed auto-fixes, escalate to CEO
- CEO is always notified, even for successful auto-fixes

## Commands

```bash
pocketteam init              # Setup wizard (interview + config)
pocketteam run "task"        # Run task through pipeline
pocketteam status            # Show project status
pocketteam kill              # Emergency stop
pocketteam resume            # Remove kill switch
pocketteam logs              # Show event log
pocketteam logs -f           # Follow log (like tail -f)
pocketteam logs --agent qa   # Filter by agent
pocketteam sessions          # List pipeline sessions
pocketteam retro             # Retrospective analysis
pocketteam uninstall         # Clean removal
```

## Project Structure

```
your-project/
├── .claude/
│   ├── CLAUDE.md              ← COO instructions (auto-generated)
│   ├── settings.json          ← Safety hooks (PreToolUse/PostToolUse)
│   └── agents/pocketteam/    ← Agent prompt definitions
├── .pocketteam/
│   ├── config.yaml            ← Project config
│   ├── artifacts/             ← Plans, reviews, audit logs
│   ├── events/stream.jsonl    ← Real-time activity stream
│   └── sessions/              ← Persistent pipeline sessions
└── .github/workflows/
    └── pocketteam-monitor.yml ← 24/7 health monitoring
```

## Telegram Integration

Control PocketTeam from your phone:

```
You: "Add search to the product catalog"
Bot: "Plan erstellt. 3 Fragen:
      1. Full-text or filter-based?
      2. Which fields searchable?
      3. Pagination style?"
You: "Full-text, name+description, cursor-based"
Bot: "Implementation gestartet..."
     [15 min later]
Bot: "Tests bestanden (23/23). PR erstellt.
      Deploy to production?"
You: "Ja"
Bot: "Production live. Monitoring aktiv."
```

Setup:
1. Create a bot via [@BotFather](https://t.me/BotFather)
2. Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` as env vars
3. `pocketteam init` → enable Telegram

## AutoResearch Module

Optional module for metric-driven optimization loops:

```python
from pocketteam.modules.autoresearch import AutoResearchModule

mod = AutoResearchModule(project_root)
mod.create_experiment(
    name="email-subject-lines",
    metric_name="open_rate",
    target_file="templates/subjects.yaml",
    maximize=True,
)

# After each campaign:
mod.record_result("email-subject-lines", "Variation A", 0.32)
mod.record_result("email-subject-lines", "Variation B", 0.41)

best = mod.get_best("email-subject-lines")
# → {"variation": "Variation B", "metric_value": 0.41}
```

## Comparison

| Feature | PocketTeam | Devin | CrewAI | OpenClaw |
|---|---|---|---|---|
| Multi-Agent Team | 11 agents + sub-agents | Single agent | Role-based | Single |
| Safety Layers | 10 (runtime hooks) | Minimal | None | None (CVEs!) |
| Kill Switch | Out-of-band, <1s | No | No | Missing |
| Cost Model | Subscription ($100/mo) | $500/mo | API tokens | API tokens |
| Mobile Access | Telegram + Remote | Web UI | No | Multi-channel |
| Self-Healing | Staging-first + 3-strike | No | No | No |
| Open Source | MIT | No | MIT | MIT (insecure) |
| Audit Trail | Every action logged | No | No | No |

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    PocketTeam Core                       │
│                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│  │ Pipeline │──│ Context  │──│ Budget   │             │
│  │ (phases) │  │ (shared) │  │ (track)  │             │
│  └────┬─────┘  └──────────┘  └──────────┘             │
│       │                                                 │
│  ┌────┴──────────────────────────────────┐             │
│  │         11 Specialized Agents          │             │
│  │  COO → Planner → Engineer → QA → ...  │             │
│  └────┬──────────────────────────────────┘             │
│       │                                                 │
│  ┌────┴──────────────────────────────────┐             │
│  │         10 Safety Layers               │             │
│  │  Runtime hooks, NOT conversation ctx   │             │
│  │  Survives context compaction           │             │
│  └────┬──────────────────────────────────┘             │
│       │                                                 │
│  ┌────┴─────┐  ┌──────────┐  ┌──────────┐             │
│  │ Channels │  │ Monitor  │  │ Tools    │             │
│  │ Telegram │  │ Watcher  │  │ Deploy   │             │
│  │ Remote   │  │ Healer   │  │ Health   │             │
│  └──────────┘  └──────────┘  └──────────┘             │
└─────────────────────────────────────────────────────────┘
```

## Development

```bash
# Clone
git clone https://github.com/Farid046/pocketteamtest.git
cd pocketteamtest

# Setup
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Test
pytest                    # 497 tests, ~7s
pytest --cov=pocketteam   # With coverage

# Lint
ruff check pocketteam/
mypy pocketteam/
```

### Stats

- **78 Python files** | **~13,000 lines of code**
- **497 tests** | **21 test files**
- **10 safety layers** | **32 safety patterns blocked**
- **11 agents** | **5 tools** | **3 monitoring components**

## Bootstrapping: PocketTeam builds itself

PocketTeam was designed to improve itself. Run `pocketteam init` in its own repo, and it will:

1. Use its own pipeline to plan improvements
2. Review its own code with the Reviewer agent
3. Test itself with the QA agent
4. Security-audit itself with the Security agent
5. The Observer agent learns from mistakes and improves agent prompts

This is the ultimate proof that the system works.

## Roadmap

- [ ] Habbo-style real-time dashboard (isometric office visualization)
- [ ] Slack integration (in addition to Telegram)
- [ ] Multi-project management from a single interface
- [ ] Plugin system for custom agents
- [ ] VS Code extension with embedded dashboard

## Inspired By

- **[gstack](https://github.com/garrytan/gstack)** — 28 Skills, Company Hierarchy, "Boil the Lake" philosophy
- **[autoresearch](https://github.com/karpathy/autoresearch)** — Autonomous experiment loops
- **[claude-agent-sdk](https://github.com/anthropics/claude-code-sdk-python)** — Agent orchestration, 6-layer safety
- **OpenClaw** (cautionary tale) — What happens when safety lives in prompts

## License

MIT License. See [LICENSE](LICENSE) for details.

---

<p align="center">
  <strong>Built by a CEO who was tired of being the bottleneck.</strong>
  <br />
  <sub>Give your AI team the safety rails it deserves.</sub>
</p>
