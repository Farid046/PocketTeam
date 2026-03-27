# PocketTeam

<p align="center">
  <a href="https://github.com/farid046/pocketteam">
    <img alt="PocketTeam" src="https://img.shields.io/badge/PocketTeam-Autonomous%20AI%20Team-blue?style=for-the-badge" />
  </a>
  <img alt="Agents" src="https://img.shields.io/badge/agents-12-blue?style=for-the-badge" />
  <img alt="Skills" src="https://img.shields.io/badge/skills-37-purple?style=for-the-badge" />
  <img alt="Safety Layers" src="https://img.shields.io/badge/safety_layers-10-red?style=for-the-badge" />
  <img alt="License" src="https://img.shields.io/badge/license-MIT-green?style=for-the-badge" />
</p>

<p align="center">
  <strong>A complete autonomous AI IT team that plans, codes, reviews, tests, deploys, and self-heals—all inside Claude Code.</strong>
  <br />
  <sub>12 specialized agents • 37 skills • Real-time 3D dashboard • Browser automation • 10-layer safety system</sub>
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#how-it-works">How It Works</a> •
  <a href="#agents">Agents</a> •
  <a href="#safety">Safety</a> •
  <a href="#comparison">Comparison</a> •
  <a href="#commands">Commands</a>
</p>

---

## The Problem

AI coding agents are powerful but risky. Here's what went wrong with previous systems:

- **OpenClaw** deleted 200+ emails because safety constraints lived in conversation context—lost during compaction
- **Single-agent systems** lose context, skip reviews, forget tests, and make catastrophic production mistakes
- **Autonomous agents** have executed `DROP DATABASE`, force-pushed to production, and leaked secrets
- **Weak safety** lives in prompts, which can be manipulated or forgotten

You need a **team with enterprise-grade safety**, not a solo agent and a prayer.

## The Solution

PocketTeam gives you a full autonomous IT team where:

1. **Specialization wins**: 12 specialized agents, each with a clear role and permission model
2. **Safety is structural**: 10 runtime hooks that survive context compaction and cannot be bypassed
3. **You stay in control**: 4 human gates, kill switch (< 1 second), budget limits, audit trail
4. **Real-time visibility**: 3D isometric office dashboard showing which agents are working, what they're doing, and costs in real-time
5. **Cost-optimized**: Runs on Claude Code subscription ($20–$200/month flat) with Haiku for cheap tasks and Opus on-demand

---

## Features

### 12 Specialized Agents

| Agent | Role | Model | Key Responsibility |
|---|---|---|---|
| **COO** | Orchestrator | Opus | Delegates work, enforces pipeline, controls autopilot/ralph/quick modes |
| **Product** | Demand validator | Sonnet | Market research, competitive analysis, product briefs (asks 6 forcing questions) |
| **Planner** | Implementation lead | Sonnet | Task breakdown, risk assessment, breaking-change plans |
| **Reviewer** | Code & design auditor | Sonnet | Architecture review, performance analysis, code style enforcement |
| **Engineer** | Implementation | Sonnet | Scaffolding, implementation, debugging, hotfixes |
| **QA** | Testing & verification | Sonnet | Smoke tests, visual QA, test-data setup, E2E testing |
| **Security** | OWASP & threat auditor | Sonnet | OWASP audits, CVE scanning, threat modeling, secrets detection |
| **DevOps** | Deployment orchestrator | Sonnet | Staging deploys, canary releases, rollbacks, CI/CD |
| **Investigator** | Root-cause analyst | Sonnet | Timeline reconstruction, DB diagnostics, incident handoffs |
| **Documentation** | Docs synchronizer | Haiku | README updates, architecture docs, stale-doc audit |
| **Monitor** | 24/7 health watcher | Haiku | Health checks every 5 min, log analysis, auto-escalation |
| **Observer** | Team learner | Haiku | Retrospectives, weekly digests, agent improvement proposals |

### 37 Skills Across the Team

Each agent has specialized skills for their domain:

**Product**: market-research, competitive-analysis, product-brief

**Planning**: task-breakdown, risk-assessment, breaking-change-plan

**Engineering**: scaffold, debug, hotfix, architecture-review, design-review, performance-review

**QA**: smoke-test, visual-qa, test-data-setup, browse

**Security**: owasp-audit, dependency-scan, threat-model

**DevOps**: dashboard-deploy, service-deploy, rollback

**Investigator**: timeline-reconstruction, db-diagnostics, handoff-spec

**Monitoring**: health-check, log-analysis, escalation

**Documentation**: update-readme, architecture-docs, stale-doc-audit

**Observer**: retro, propose-improvements, weekly-digest

**Workflow modes**: autopilot, ralph, quick

And more, including Telegram integration and custom skill loading.

### Real-Time 3D Isometric Office Dashboard

Watch your AI team work in a pixel-art Habbo-style office:

- **Live agent visualization**: See which agents are active, idle, or thinking
- **Cost tracking**: Token usage, cost per agent, subscription vs API breakdown
- **Rate limits**: Real-time view of API calls remaining, context window usage
- **Event feed**: Live stream of decisions, approvals, and deployments
- **Session picker**: Resume previous work or start fresh
- Built with React Three Fiber + WebSocket real-time updates

Accessed via `pocketteam dashboard start` or embedded in Claude Code.

### ptbrowse: Own Browser Automation CLI

A lightweight, accessibility-tree-based browser automation tool built on Playwright and Bun. It exposes a persistent daemon so every command reuses the same browser instance — no cold-start overhead per step.

After `pocketteam init`, the `ptbrowse` alias is available directly in your shell:

```bash
ptbrowse goto https://app.example.com
ptbrowse snapshot -i
ptbrowse fill @e3 user@example.com
ptbrowse click @e5
ptbrowse assert text "Dashboard"
```

#### ptbrowse vs Alternatives

| Capability | ptbrowse | Playwright MCP | gstack /browse |
|---|---|---|---|
| **Cost per step** | ~$0.01 | ~$0.10–$0.30 | ~$0.10+ |
| **Token source** | Accessibility tree text | Full screenshot pixels | Full screenshot pixels |
| **Persistent daemon** | Yes (one Chromium, reused) | No (new context per call) | No |
| **Structured refs** | `@e1`…`@eN` (stable across steps) | CSS selectors | Not exposed |
| **Diff snapshots** | Yes (`snapshot -D`) | No | No |
| **Headed mode** | `PTBROWSE_HEADED=1` | Configurable | Configurable |
| **Assertion exit codes** | 0/1/2/3 (CI-friendly) | No | No |
| **JS eval** | Yes (opt-in, `PTBROWSE_ALLOW_EVAL=1`) | Yes | No |

#### Token-Cost Breakdown

A typical login + dashboard check with Playwright MCP sends a full viewport screenshot (~150 KB PNG) as each step response. With Claude Sonnet at ~$3 per million input tokens, a 150 KB image encodes to roughly 1,500–3,000 tokens:

```
Playwright MCP — 10 steps:
  10 × ~2,000 image tokens  = 20,000 tokens  ≈ $0.06

ptbrowse — 10 steps:
  10 × ~200 text tokens     =  2,000 tokens  ≈ $0.006

Savings per test run: ~90%
Savings at 100 runs/day:  ~$5.40/day  →  ~$162/month
```

Accessibility tree text is 10–15x smaller than a screenshot for the same page because it omits visual styling, images, and layout noise that AI models don't need to locate elements.

#### Architecture

```
ptbrowse <cmd> [args]
    │
    │  HTTP POST /command  (localhost, token-authenticated)
    ▼
ptbrowse daemon  (server.ts, Bun process, auto-started on first call)
    │
    │  Playwright API
    ▼
Chromium (headless by default, headed with PTBROWSE_HEADED=1)
```

The daemon writes its PID, port, and auth token to `~/.pocketteam/browse.json`. Subsequent `ptbrowse` calls connect to the running daemon in milliseconds. The daemon auto-restarts if it crashes.

#### Command Reference

**Navigation**

| Command | Description |
|---|---|
| `ptbrowse goto <url>` | Navigate to URL, reset snapshot refs |
| `ptbrowse back` | Go back in history |
| `ptbrowse forward` | Go forward in history |
| `ptbrowse reload` | Reload current page |

**Snapshot**

| Command | Description |
|---|---|
| `ptbrowse snapshot` | Full accessibility tree with `@e` refs |
| `ptbrowse snapshot -i` | Interactive elements only (buttons, links, inputs) |
| `ptbrowse snapshot -c` | Compact one-line format (`@e1 button "Submit"`) |
| `ptbrowse snapshot -D` | Diff since last snapshot (shows added/removed elements) |

**Interaction**

| Command | Description |
|---|---|
| `ptbrowse click <ref>` | Click element (e.g. `@e1`) |
| `ptbrowse fill <ref> <text>` | Fill input field (clears first) |
| `ptbrowse type <ref> <text>` | Type keystroke-by-keystroke (for apps watching keydown) |
| `ptbrowse select <ref> <value>` | Select dropdown option by value or label |
| `ptbrowse key <key>` | Press keyboard key (`Enter`, `Escape`, `Tab`, `ArrowDown`…) |
| `ptbrowse hover <ref>` | Hover element (triggers tooltips / dropdowns) |
| `ptbrowse scroll <ref> <dir> <px>` | Scroll `up` or `down` N pixels at element |

**Wait**

| Command | Description |
|---|---|
| `ptbrowse wait text <text>` | Wait until text appears (default 10 s) |
| `ptbrowse wait selector <css>` | Wait until CSS selector exists |
| `ptbrowse wait idle [ms]` | Wait for network idle (default 2000 ms, non-fatal) |
| `ptbrowse wait url <pattern>` | Wait for URL to match regex pattern |

**Assertions** (exit 1 on failure — CI-friendly)

| Command | Description |
|---|---|
| `ptbrowse assert text <text>` | Page contains text |
| `ptbrowse assert no-text <text>` | Page does NOT contain text |
| `ptbrowse assert visible <ref>` | Element is visible |
| `ptbrowse assert enabled <ref>` | Element is enabled (not disabled) |
| `ptbrowse assert url <pattern>` | Current URL matches regex |

**Read**

| Command | Description |
|---|---|
| `ptbrowse text` | Extract full page text (max 8000 chars) |
| `ptbrowse screenshot [path]` | Save PNG (default: `~/.pocketteam/screenshots/<timestamp>.png`) |
| `ptbrowse console` | Show captured browser console messages |
| `ptbrowse eval <expr>` | Evaluate JS expression (requires `PTBROWSE_ALLOW_EVAL=1`) |

**Meta**

| Command | Description |
|---|---|
| `ptbrowse viewport <w> <h>` | Set viewport size (e.g. `375 812` for mobile) |
| `ptbrowse status` | Show daemon status (port, uptime, current URL, ref count) |
| `ptbrowse close` | Close browser and stop daemon |

#### The `@e` Reference System

Every `snapshot` assigns short refs (`@e1`, `@e2`, …) to all elements in the accessibility tree. These refs are stable within a snapshot session — you use them directly in interaction commands:

```bash
# Step 1: take snapshot and find the email input
ptbrowse snapshot -i
# Output:
#   @e1 link "Home"
#   @e2 textbox "Email"
#   @e3 textbox "Password"
#   @e4 button "Sign in"

# Step 2: interact using refs — no fragile CSS selectors
ptbrowse fill @e2 user@example.com
ptbrowse fill @e3 hunter2
ptbrowse click @e4
```

Refs are reset on every `goto`, `back`, `forward`, or `reload`. If a ref is used after page navigation without a new snapshot, exit code 2 is returned.

#### Headed vs Headless

```bash
# Headless (default — CI and agent use)
ptbrowse goto https://example.com

# Headed (watch the browser — useful for QA debugging)
PTBROWSE_HEADED=1 ptbrowse goto https://example.com
```

#### Exit Codes

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | Assertion failed or element error |
| `2` | Stale ref (page navigated — run `snapshot` again) |
| `3` | Timeout or daemon unreachable |

#### Quick Example: E2E Login Test

```bash
#!/usr/bin/env bash
set -e

ptbrowse goto https://app.example.com/login
ptbrowse wait selector "#login-form"
ptbrowse snapshot -i

# Refs assigned: @e1=email, @e2=password, @e3=submit button
ptbrowse fill @e1 testuser@example.com
ptbrowse fill @e2 supersecret
ptbrowse click @e3

# Wait for redirect to dashboard
ptbrowse wait url "/dashboard"
ptbrowse assert text "Welcome"

echo "Login test passed"
ptbrowse close
```

### 10-Layer Safety Guardian

Safety is **structural**, not conversational. Every tool call passes through 10 runtime hooks:

```
Layer  1: NEVER_ALLOW         ──── Kill-switch blocklist (rm -rf /, DROP DATABASE, fork bombs)
Layer  2: DESTRUCTIVE_PATTERNS ──── Requires plan approval (git push --force, DELETE FROM)
Layer  3: MCP TOOL SAFETY     ──── SQL injection prevention, parameterized queries
Layer  4: NETWORK SAFETY      ──── Domain allowlist, exfiltration prevention
Layer  5: SENSITIVE FILES     ──── .env, .ssh, .aws, *.pem protected (never writable)
Layer  6: AGENT ALLOWLIST     ──── Per-agent tool permissions (Planner can't Write)
Layer  7: SCOPE + RATE LIMIT  ──── Budget per agent, file scope from plan
Layer  8: AUDIT LOG          ──── Every decision logged with incident playbooks
Layer  9: D-SAC PATTERN      ──── Dry-run → Staged → Approval → Commit for destructive ops
Layer 10: KILL SWITCH        ──── Out-of-band, separate process, < 1 second response
```

**Why survive context compaction?** OpenClaw's safety rules lived in the conversation and were forgotten during compaction. PocketTeam's safety is implemented as `.claude/settings.json` hooks that are loaded fresh on every Claude Code session. Prompts cannot override them.

### Telegram Integration

Control your AI team from your phone:

```
You: "Add OAuth2 authentication"

PocketTeam: "Plan ready. 3 questions:
   1. OAuth provider (GitHub, Google, Microsoft)?
   2. Scopes needed?
   3. Auto-login or explicit button?"

You: "GitHub, user+email, button"

PocketTeam: "Implementation started..."
   [15 minutes later]

PocketTeam: "✅ Tests: 23/23 passed. Code review: approved.
   PR #42 ready. Deploy to staging?"

You: "Deploy"

PocketTeam: "✅ Staging live. All smoke tests pass.
   Deploy to production?"

You: "Yes"

PocketTeam: "🚀 Live in production. Monitoring active."
```

### PocketTeam HUD

Terminal status line showing real-time metrics:

```
PocketTeam | Context: 78% | Cost: $1.23 | Agents: 3 active | Rate limit: 85 calls/min
```

One glance and you know:
- Whether you're getting close to context limits
- How much you've spent in this session
- How many agents are actively working
- API rate limit headroom

### Magic Keywords: Workflow Modes

Activate special workflow modes by starting your task with a keyword:

| Mode | Command | Behavior |
|---|---|---|
| **Autopilot** | `autopilot: Task` | Full pipeline with no human gates (CEO pre-approved by keyword) |
| **Ralph** | `ralph: Task` | Implement → Test loop, keeps going until all tests pass (max 5 iterations) |
| **Quick** | `quick: Task` | Skip planning, implement directly, quick test (for small fixes) |
| **Deep-Dive** | `deep-dive: Topic` | Spawn 3 parallel research agents for thorough analysis |

Example:
```
autopilot: Add dark mode toggle
```

The COO will plan, implement, test, review, audit, and deploy—all without asking. You get notified at key milestones.

### Session Management

Never lose work. PocketTeam persists all sessions:

```bash
pocketteam start              # Resume last session (auto mode + safety hooks)
pocketteam start new         # Fresh session
pocketteam start resume [id] # Session picker or specific ID
pocketteam sessions          # List all previous work
```

Each session has:
- Full transcript of decisions
- Cost breakdown per agent
- Artifact links (plans, reviews, audit logs)
- Kill-switch state
- Token usage graph

---

## Quick Start

### Prerequisites

- **Python 3.11+** — required
- **[Claude Code CLI](https://docs.anthropic.com/claude-code)** — `npm install -g @anthropic-ai/claude-code`
- **[Bun](https://bun.sh)** — required for ptbrowse (browser automation) and the Dashboard server; install with `curl -fsSL https://bun.sh/install | bash`
- **Docker** — optional, required for `pocketteam dashboard`
- **Telegram Bot Token** — optional, required for mobile control

### Installation

```bash
# Install from GitHub
pip install git+https://github.com/Farid046/pocketteam.git

# Or install locally for development
git clone https://github.com/Farid046/pocketteam.git
cd pocketteam
pip install -e ".[dev]"
```

### Set Up in Your Project

```bash
cd your-project
pocketteam init
```

You'll be asked:
1. Project name and description
2. Tech stack (frontend/backend/full-stack)
3. CI/CD platform (GitHub Actions, GitLab, etc.)
4. Slack or Telegram for notifications? (optional)
5. Deploy targets (staging/production URLs)

### Run Your First Task

Open Claude Code with PocketTeam safety hooks active:

```bash
pocketteam start
```

Then give PocketTeam a task:

```
> Build user authentication with OAuth2

```

The COO takes over:
1. **Planner** breaks down the work
2. **Reviewer** validates the plan
3. **Engineer** implements on a feature branch
4. **QA** runs tests
5. **Security** audits for OWASP violations
6. **Documentation** updates your README
7. **DevOps** deploys to staging
8. You approve production
9. **Monitor** watches for 15 minutes

Or use a magic keyword:

```
autopilot: Add dark mode toggle
```

---

## How It Works

### The Pipeline (5 Phases)

```
Phase 1: PLANNING
  ├── Planner reads codebase, writes detailed plan
  ├── Reviewer validates architecture, risks, design
  └── HUMAN GATE: You approve or ask for changes

Phase 2: IMPLEMENTATION
  ├── Engineer implements on feature branch
  ├── Reviewer code-reviews (max 3 rounds)
  ├── QA runs all tests (unit, integration, E2E, browser)
  ├── Security audits (OWASP, CVEs, threat model)
  └── Documentation updates README, API docs, architecture

Phase 3: STAGING
  └── DevOps deploys to staging + runs smoke tests

Phase 4: PRODUCTION
  ├── HUMAN GATE: You approve production deploy
  ├── DevOps deploys with canary strategy
  └── Monitor watches for 15 minutes

Phase 5: 24/7 MONITORING
  ├── Health checks every 5 minutes
  ├── Log analysis for error patterns
  ├── Auto-fix with staging-first strategy
  └── 3-strike rule: escalate after 3 failed auto-fixes
```

### Control Points (4 Human Gates)

1. **Product Gate**: Is this worth building? (Product agent asks 6 questions)
2. **Plan Gate**: Does the plan make sense? (You review + approve)
3. **Production Gate**: Ready to ship? (You approve deployment)
4. **Incident Gate**: Should we auto-fix or escalate? (You decide)

### Kill Switch (3 Ways)

Stop everything in < 1 second:

```bash
pocketteam kill          # CLI
/kill                    # Telegram
touch .pocketteam/KILL   # Signal file
```

---

## Safety Deep Dive

### Why 10 Layers?

OpenClaw teaches us that **prompts are not safety**. Their safety constraints lived in conversation context, got lost during compaction, and an agent deleted 200+ emails.

PocketTeam's safety is:
- **Structural**: Runtime hooks in `.claude/settings.json`, not conversation context
- **Persistent**: Survives context compaction, session restarts, agent handoffs
- **Enforced**: Cannot be "convinced" or "jailbroken"—they are code, not suggestions

### The D-SAC Pattern

D-SAC (Dry-run / Staged / Approval / Commit) is a cryptographically secured approval flow for destructive operations. It is Layer 9 of the safety stack and the primary mechanism that prevents agents from silently deleting files, wiping databases, or force-pushing to production.

**What triggers D-SAC:**
Any command matching a destructive pattern — `rm -rf`, `DELETE FROM`, `DROP TABLE`, `git push --force`, `TRUNCATE`, and others — is intercepted by the Guardian hook before execution.

**The four-step flow:**

```
1. DRY-RUN:  Guardian blocks the operation and produces a preview.
             Shows affected files, rows, scope, and a content hash.

2. STAGED:   System creates a cryptographic one-time-use approval token
             bound to the exact operation hash and the current session ID.

3. APPROVAL: CEO reviews the dry-run preview and either approves or rejects.
             On approval, the token is issued with a 5-minute TTL.

4. COMMIT:   Agent re-submits the operation with the token.
             Guardian validates the token (scope, session, TTL, one-time use)
             and allows exactly this operation, once.
```

**Security guarantees:**

| Guarantee | How it works |
|---|---|
| **Scope-binding** | The token encodes a hash of the exact operation. A token issued for `rm staging/` will be rejected by Guardian if the agent attempts `rm production/` — the hash does not match. |
| **Session-binding** | Tokens are tied to the session ID in which they were issued. A token cannot be replayed in a different session. |
| **One-time use** | Each token is consumed atomically (file-locking). A second attempt with the same token is rejected even within the TTL. |
| **Re-initiation protection** | After context compaction, the system detects when an agent tries to restart an approval flow with a wider scope than originally approved and warns the CEO before proceeding. |
| **Layer 1 override impossible** | Operations on the `NEVER_ALLOW` blocklist (`rm -rf /`, `DROP DATABASE`, fork bombs) cannot be unlocked by any token. D-SAC only applies to Layer 2 patterns — Layer 1 is a hard block with no bypass path. |

**Test coverage:** 94 dedicated D-SAC tests verify all attack vectors — scope substitution, token replay, cross-session reuse, TTL expiry, and compaction-triggered re-initiation.

### Example: Safe Deployment

```
Engineer: "Ready to deploy. Dry-run output:
  ✓ No DB migrations
  ✓ No schema changes
  ✓ 3 new API endpoints
  ✓ Cost impact: +$0.50/month

  Hash: abc123def456
  Approval required. Valid for 5 minutes."

You: "Approved"

DevOps: "Deploying to staging..."
  [Runs smoke tests]
  "✅ All tests pass. Ready for production?"

You: "Deploy to production"

Monitor: "🚀 Live. Watching for 15 min."
  [Logs in real-time]
  "✅ No errors. Health: 100%. Deployment successful."
```

### Self-Healing with Safety Rails

When something breaks in production:

1. **Detect**: Monitor finds error spike
2. **Diagnose**: Investigator runs root-cause analysis
3. **Plan**: Engineer proposes fix
4. **Staging First**: Fix is tested in staging before production
5. **Deploy**: If safe, auto-deploy. If risky, escalate to CEO
6. **3-Strike Rule**: After 3 failed auto-fixes, always escalate

---

## Commands

### Session & Workflow

```bash
pocketteam init              # Setup wizard (interview + config)
pocketteam start             # Resume last session
pocketteam start new         # Fresh session
pocketteam start resume      # Session picker
pocketteam sessions          # List all sessions
pocketteam status            # Show project status
```

### Safety & Control

```bash
pocketteam kill              # Emergency stop (< 1 second)
pocketteam resume            # Remove kill switch
```

### Monitoring & Logs

```bash
pocketteam logs              # Show event log
pocketteam logs -f           # Follow log (like tail -f)
pocketteam logs --agent qa   # Filter by agent
pocketteam logs --since 1h   # Last hour only
```

### Dashboard

```bash
pocketteam dashboard start       # Start dashboard server
pocketteam dashboard stop        # Stop dashboard
pocketteam dashboard status      # Check if running
pocketteam dashboard logs        # Show dashboard logs
pocketteam dashboard configure   # Port, auth, etc.
```

> **Security note:** When accessing the dashboard remotely, HTTPS is required.
> The auth token is embedded in the page DOM and is visible to anyone on the network
> if transmitted over plain HTTP. Use `pocketteam dashboard configure --domain` to set
> up a domain with Caddy (HTTPS auto-provisioned) before exposing the dashboard.

### Analysis & Improvement

```bash
pocketteam retro             # Retrospective on last task
pocketteam health            # System health check
pocketteam uninstall         # Clean removal (keeps artifacts)
```

---

## Project Structure

```
your-project/
├── .claude/
│   ├── CLAUDE.md              ← COO instructions (auto-generated)
│   ├── settings.json          ← Safety hooks + PreToolUse + PostToolUse
│   ├── agents/pocketteam/    ← 12 agent prompt definitions
│   └── skills/               ← Skill definitions for agents
├── .pocketteam/
│   ├── config.yaml            ← Project config (stack, deploy targets)
│   ├── KILL                   ← Kill switch signal file
│   ├── artifacts/
│   │   ├── plans/             ← Planner's detailed plans
│   │   ├── reviews/           ← Reviewer's code reviews
│   │   └── audit/             ← Security & audit logs
│   ├── events/
│   │   └── stream.jsonl       ← Real-time activity stream
│   ├── sessions/              ← Persistent pipeline sessions
│   └── learnings/             ← Observer's improvement suggestions
├── dashboard/                 ← React dashboard (build artifacts)
└── .github/workflows/
    └── pocketteam-monitor.yml ← 24/7 health monitoring
```

---

## Comparison: PocketTeam vs Alternatives

| Feature | PocketTeam | gstack | Oh-My-ClaudeCode | OpenClaw | CrewAI |
|---|---|---|---|---|---|
| **Agents** | 12 | 0 | 32 | 5 | Role-based |
| **Skills** | 37 | 25 | 28 | 0 | Custom |
| **Browser Automation** | ptbrowse (10–20x cheaper) | /browse | No | No | No |
| **Browser Test Cost** | ~$0.01/step | ~$0.10+/step | N/A | N/A | N/A |
| **Real-time Dashboard** | 3D isometric office | No | No | No | No |
| **Safety Layers** | 10 (runtime hooks) | 0 | 0 | 8 (context-only) | None |
| **Safety Architecture** | Runtime hooks (survives compaction) | Prompt-based | Prompt-based | Prompt-based (lost on compaction) | None |
| **Kill Switch** | < 1 second out-of-band | No | No | Missing | No |
| **Cost Model** | Subscription ($20–$200/mo) | API tokens | API tokens | API tokens | API tokens |
| **Telegram Integration** | Full control + approvals | No | No | No | No |
| **Terminal HUD** | 2-line statusline | No | No | No | No |
| **Magic Keywords** | autopilot/ralph/quick | No | autopilot | No | No |
| **Session Persistence** | Full transcripts + artifacts | Limited | No | No | No |
| **Audit Trail** | Every action logged | No | No | No | No |
| **Open Source** | MIT | MIT | MIT | MIT (insecure) | MIT |

> **OpenClaw footnote:** OpenClaw's 8 safety "layers" were implemented as system-prompt instructions. When Claude's context window compacted during a long session, those instructions were summarized or dropped. An agent proceeded to delete 200+ emails with no safety check triggering. This is a known failure mode of prompt-based safety — it cannot survive context compaction.

### Production Safety: The Critical Difference

Most agent frameworks treat safety as a conversation concern: they inject rules into the system prompt and hope the model follows them. This works until it doesn't.

PocketTeam treats safety as an infrastructure concern. Every tool call — regardless of which agent makes it, regardless of context window state — passes through `.claude/settings.json` runtime hooks before execution. These hooks are loaded fresh by Claude Code on every session start and run as pre/post-tool callbacks outside the model's context. The model cannot read, modify, or reason about them.

**What this means in practice:**
- An agent 150,000 tokens into a session has the same safety guarantees as one at token 0
- A jailbreak prompt cannot disable the hooks — they are not in the conversation
- The kill switch (`touch .pocketteam/KILL`) is checked by a hook, not a prompt instruction
- Budget limits, file scope, and domain allowlists enforce themselves

**Key Advantages:**
- **Most comprehensive safety** (10 layers as structural runtime hooks)
- **Only one with own browser tool** (ptbrowse: 10–20x cheaper than Playwright)
- **Only one with real-time 3D dashboard** (watch agents work in real-time)
- **Cheapest to operate** (flat subscription vs per-token API costs)
- **Most control** (4 human gates, kill switch, Telegram)
- **Most feedback loops** (Observer learns from mistakes, improves agent prompts)

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│              PocketTeam Core System                  │
│                                                     │
│  ┌──────────────┐  ┌──────────────┐                │
│  │   Pipeline   │──│   Context    │                │
│  │  (5 phases)  │  │  (shared)    │                │
│  └──────────────┘  └──────────────┘                │
│         │                                           │
│    ┌────┴──────────────────────────────┐           │
│    │    12 Specialized Agents           │           │
│    │  COO → Planner → Engineer → QA → ... │        │
│    └────┬──────────────────────────────┘           │
│         │                                           │
│    ┌────┴──────────────────────────────┐           │
│    │      10 Safety Layers              │           │
│    │ (Runtime hooks in .claude/settings.json)      │
│    └────┬──────────────────────────────┘           │
│         │                                           │
│    ┌────┴─────────┐  ┌────────────┐               │
│    │  Channels    │  │  Monitoring │               │
│    │  Telegram    │  │  Health     │               │
│    │  Dashboard   │  │  Monitor    │               │
│    └──────────────┘  └────────────┘               │
│                                                     │
│    ┌──────────────────────────────────┐           │
│    │   Supporting Tools                │           │
│    │  ptbrowse (browser automation)   │           │
│    │  Dashboard (3D office)            │           │
│    │  HUD (terminal statusline)        │           │
│    └──────────────────────────────────┘           │
└─────────────────────────────────────────────────────┘
```

---

## Development

### Setup

```bash
git clone https://github.com/Farid046/pocketteam.git
cd pocketteam

python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

pip install -e ".[dev]"
```

### Testing

```bash
# Run all tests
pytest

# With coverage
pytest --cov=pocketteam

# Watch mode
ptw
```

### Code Quality

```bash
# Lint
ruff check pocketteam/

# Type checking
mypy pocketteam/

# Format
ruff format pocketteam/
```

### Statistics

- **12 agents** with specialized prompts
- **37 skills** distributed across agents
- **78 Python files** | **~13,000 lines of code**
- **497 tests** | **21 test files** | **95% coverage**
- **10 safety layers** | **32 security patterns blocked**
- **2 integrations** (Telegram, Claude Code)

---

## Self-Improvement: PocketTeam Builds Itself

PocketTeam was designed to improve itself. Run `pocketteam init` in its own repo and watch:

1. **Planner** creates a plan to improve test coverage
2. **Engineer** implements the changes
3. **QA** verifies nothing broke
4. **Security** audits for new vulnerabilities
5. **Observer** learns from the process and improves agent prompts
6. Next task, the agents are better

This is the ultimate proof that the system works.

---

## Roadmap

- [x] 12 specialized agents
- [x] 10-layer safety system
- [x] 3D isometric office dashboard
- [x] ptbrowse browser automation
- [x] Telegram integration
- [x] Session persistence
- [ ] Slack integration
- [ ] Multi-project dashboard
- [ ] **VS Code Extension** (Target: Q3 2026)
  - Embedded Dashboard in VS Code Sidebar (WebView)
  - Live agent status, event feed, cost tracking
  - One-click Kill Switch
  - Session management
  - Reuses existing Dashboard WebSocket API — no new backend needed
- [ ] Custom agent/skill marketplace
- [ ] Auto-deployment policies (e.g., "auto-deploy if tests pass + security clean")

---

## Inspired By

- **[gstack](https://github.com/garrytan/gstack)** — Skills system, company hierarchy, completeness-first planning philosophy
- **[Oh-My-ClaudeCode](https://github.com/oh-my-claude/oh-my-clausecode)** — Agent specialization, autopilot/ralph workflow modes
- **[OpenClaw](https://github.com/evals-evals/openclaw)** — Multi-agent orchestration patterns (informed our decision to use runtime hooks instead of prompt-based safety)
- **[autoresearch](https://github.com/autoresearch/autoresearch)** — Parallel agent spawning and deep-dive research patterns
- **[claude-hud](https://github.com/anthropics/claude-hud)** — Terminal statusline inspiration
- **[claude-usage](https://github.com/anthropics/claude-usage)** — Token/cost tracking
- **[Devin](https://www.devin.ai/)** — Autonomous coding agent (we scale it to teams + fix safety)

---

## License

MIT License. See [LICENSE](LICENSE) for details.

---

<p align="center">
  <strong>Built by a CEO who got tired of being the bottleneck.</strong>
  <br />
  <sub>Give your AI team the safety rails, specialization, and real-time visibility it deserves.</sub>
</p>

<p align="center">
  <a href="https://github.com/Farid046/pocketteam">Star on GitHub</a> •
  <a href="https://discord.gg/pocketteam">Join Discord</a> •
  <a href="https://twitter.com/pocketteamhq">Follow on X</a>
</p>
