"""
PocketTeam Constants
All models, budgets, timeouts, and rate limits in one place.
"""

from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────────
# Model strategy: Subscription-first, cheap by default, Opus only on-demand
# ─────────────────────────────────────────────────────────────────────────────

AGENT_MODELS: dict[str, str] = {
    "coo":           "claude-sonnet-4-6",   # Orchestrates only, fast
    "product":       "claude-sonnet-4-6",   # Questions + demand validation
    "planner":       "claude-opus-4-6",     # Opus for maximum plan quality — first stop for every task
    "reviewer":      "claude-sonnet-4-6",   # Code + plan review
    "engineer":      "claude-sonnet-4-6",   # Default. Opus on-demand for complex tasks.
    "qa":            "claude-sonnet-4-6",   # Tests = medium tokens
    "security":      "claude-sonnet-4-6",   # Audit = medium tokens
    "devops":        "claude-sonnet-4-6",   # Deploy scripts = few tokens
    "investigator":  "claude-sonnet-4-6",   # Debug = medium tokens
    "documentation": "claude-haiku-4-5-20251001",  # Docs = simple task
    "monitor":       "claude-haiku-4-5-20251001",  # Health check = minimal tokens
    "observer":      "claude-haiku-4-5-20251001",  # Post-task learning = cheap
}

# GitHub Actions headless model (API Key, not Subscription)
GITHUB_ACTIONS_MODEL = "claude-haiku-4-5-20251001"

# Upgrade path: when engineer decides it's complex
ENGINEER_UPGRADE_MODEL = "claude-opus-4-6"

# ─────────────────────────────────────────────────────────────────────────────
# Budget limits per agent per task (USD, for API fallback mode)
# ─────────────────────────────────────────────────────────────────────────────

AGENT_BUDGETS: dict[str, float] = {
    "coo":           2.0,
    "product":       2.0,
    "planner":       3.0,
    "reviewer":      2.0,
    "engineer":      5.0,
    "qa":            3.0,
    "security":      2.0,
    "devops":        2.0,
    "investigator":  3.0,
    "documentation": 1.0,
    "monitor":       0.50,
    "observer":      0.50,
}

DEFAULT_BUDGET_USD = 5.0

# ─────────────────────────────────────────────────────────────────────────────
# Rate limits: max turns per agent per task
# ─────────────────────────────────────────────────────────────────────────────

AGENT_MAX_TURNS: dict[str, int] = {
    "coo":           30,
    "product":       15,
    "planner":       25,
    "reviewer":      15,
    "engineer":      60,
    "qa":            20,
    "security":      15,
    "devops":        15,
    "investigator":  20,
    "documentation": 30,
    "monitor":       8,
    "observer":      8,
}

# ─────────────────────────────────────────────────────────────────────────────
# Pipeline phase timeouts (seconds)
# ─────────────────────────────────────────────────────────────────────────────

PHASE_TIMEOUTS: dict[str, int] = {
    "product":         20 * 60,   # 20 min  (matches Phase.PRODUCT.value)
    "planning":        30 * 60,   # 30 min
    "implementation":  90 * 60,   # 90 min
    "staging":         15 * 60,   # 15 min
    "production":      10 * 60,   # 10 min  (matches Phase.PRODUCTION.value)
    "monitoring":      15 * 60,   # 15 min  (matches Phase.MONITORING.value)
}

# ─────────────────────────────────────────────────────────────────────────────
# Self-healing policy
# ─────────────────────────────────────────────────────────────────────────────

MAX_AUTO_FIX_ATTEMPTS = 3         # 3-Strike Rule: after 3 failed fixes → escalate to CEO
MONITOR_INTERVAL_STEADY = 5 * 60  # 5 min normal check interval
MONITOR_INTERVAL_ANOMALY = 30     # 30s when anomaly detected
CANARY_MONITOR_DURATION = 15 * 60 # 15 min post-deploy monitoring
ERROR_BUDGET_THRESHOLD = 0.01     # 1% error rate triggers self-healing
RESPONSE_TIME_THRESHOLD = 2.0     # 2s response time triggers investigation

# ─────────────────────────────────────────────────────────────────────────────
# Review / retry limits
# ─────────────────────────────────────────────────────────────────────────────

MAX_PLAN_REVIEW_LOOPS = 3
MAX_CODE_REVIEW_LOOPS = 3
MAX_QA_FIX_LOOPS = 5

# ─────────────────────────────────────────────────────────────────────────────
# D-SAC pattern
# ─────────────────────────────────────────────────────────────────────────────

DSAC_APPROVAL_TOKEN_TTL = 5 * 60   # Approval tokens expire after 5 min
DSAC_MAX_BATCH_SIZE = 10           # Max items per destructive batch
DSAC_BATCH_PAUSE = 1.0             # 1s pause between batch items
DSAC_TOKEN_INPUT_KEY = "__dsac_token"          # Key in tool_input dict for token passthrough
DSAC_SEQUENCE_FILE = "dsac_sequence.json"      # Relative to .pocketteam/
DSAC_MAX_REINITIATIONS = 2                     # Hard block after N re-initiations per session+agent
DSAC_SESSION_FILE = "dsac_session.txt"         # Persistent session ID fallback
DSAC_TOKEN_STALE_THRESHOLD = 3600              # Expired+unused tokens older than 1h are pruned

# ─────────────────────────────────────────────────────────────────────────────
# Observer
# ─────────────────────────────────────────────────────────────────────────────

OBSERVER_COOLDOWN_SECONDS = 120
OBSERVER_MAX_EVENTS_WINDOW = 200

# ─────────────────────────────────────────────────────────────────────────────
# Dashboard
# ─────────────────────────────────────────────────────────────────────────────

DASHBOARD_IMAGE = "pocketteam-dashboard"
DASHBOARD_VERSION = "1.0.0"
DASHBOARD_PORT = 3847
DASHBOARD_PORT_RANGE_END = 3857

# ─────────────────────────────────────────────────────────────────────────────
# Kill switch
# ─────────────────────────────────────────────────────────────────────────────

KILL_SWITCH_FILE = ".pocketteam/KILL"
KILL_SWITCH_CHECK_INTERVAL = 1    # Check every 1 second

RATE_LIMIT_WINDOW_SECONDS = 24 * 60 * 60  # Rolling 24-hour window for rate limiting

# ─────────────────────────────────────────────────────────────────────────────
# Context Awareness
# ─────────────────────────────────────────────────────────────────────────────

CONTEXT_BRIDGE_PATH = ".pocketteam/session-status.json"
CONTEXT_WARNING_YELLOW_PCT = 70
CONTEXT_WARNING_RED_PCT = 90

# ─────────────────────────────────────────────────────────────────────────────
# Cost Tracking
# ─────────────────────────────────────────────────────────────────────────────

COSTS_DIR = ".pocketteam/costs"

# ─────────────────────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────────────────────

POCKETTEAM_DIR = ".pocketteam"
CLAUDE_DIR = ".claude"
ARTIFACTS_DIR = ".pocketteam/artifacts"
PLANS_DIR = ".pocketteam/artifacts/plans"
REVIEWS_DIR = ".pocketteam/artifacts/reviews"
AUDIT_DIR = ".pocketteam/artifacts/audit"
INCIDENTS_DIR = ".pocketteam/artifacts/incidents"
SESSIONS_DIR = ".pocketteam/sessions"
LEARNINGS_DIR = ".pocketteam/learnings"
EVENTS_FILE = ".pocketteam/events/stream.jsonl"
CONFIG_FILE = ".pocketteam/config.yaml"
AGENTS_DIR = ".claude/agents/pocketteam"
SKILLS_DIR = ".claude/skills/pocketteam"

# ─────────────────────────────────────────────────────────────────────────────
# Per-agent tool allowlists
# Layer 6: Only these tools may be called by each agent
# ─────────────────────────────────────────────────────────────────────────────

AGENT_ALLOWED_TOOLS: dict[str, list[str]] = {
    # COO's actual allowed tools (Agent, Read, Glob, Grep, TodoWrite, TodoRead) are
    # handled via a special branch in allowlist.py — the empty list here means
    # "no tools permitted via the generic per-agent allowlist path".
    "coo": [],
    "product": ["Read", "Glob", "Grep", "WebSearch", "WebFetch"],
    "planner": ["Read", "Glob", "Grep"],
    "reviewer": ["Read", "Glob", "Grep"],
    "engineer": ["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
    "qa": ["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
    "security": ["Read", "Glob", "Grep", "Bash"],
    "devops": ["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
    "investigator": ["Read", "Glob", "Grep", "Bash"],
    "documentation": ["Read", "Write", "Edit", "Glob", "Grep"],
    "monitor": ["Read", "Bash"],
    "observer": ["Read", "Write", "Glob", "Grep"],  # Only agent/*.md files
}
