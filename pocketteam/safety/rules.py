"""
Safety Layer 1: NEVER_ALLOW patterns (absolute, no override)
Safety Layer 2: DESTRUCTIVE_PATTERNS (require plan approval)

These are pure regex rules — deterministic, 0ms, 0$ cost.
They can NEVER be overridden by conversation context or agent instructions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# ─────────────────────────────────────────────────────────────────────────────
# Layer 1: NEVER_ALLOW
# These patterns are ABSOLUTELY FORBIDDEN, no exceptions, no overrides.
# Even if the CEO asks, even if there's a "good reason" — NEVER.
# ─────────────────────────────────────────────────────────────────────────────

NEVER_ALLOW_PATTERNS: list[str] = [
    # Filesystem destruction
    r"rm\s+-[a-zA-Z]*r[a-zA-Z]*f\s+/(?!\w)",        # rm -rf / (root)
    r"rm\s+-[a-zA-Z]*f[a-zA-Z]*r\s+/(?!\w)",        # rm -fr / (root)
    r"dd\s+if=.*of=/dev/[sh]d[a-z]",                 # Disk overwrite
    r"dd\s+if=.*of=/dev/nvme",                        # NVMe overwrite
    r"mkfs\.",                                          # Filesystem format
    r">+\s*/dev/[sh]d[a-z]",                           # Redirect to disk device

    # Database nuclear options
    r"\bDROP\s+DATABASE\b",                             # Drop entire database
    r"\bDROP\s+SCHEMA\b.*CASCADE",                     # Drop schema with cascade

    # Fork bomb
    r":\(\)\s*\{",                                     # Fork bomb: :(){ :|:& };:
    r":\s*\(\s*\)\s*\{",                               # Fork bomb variant

    # Pipe to shell (arbitrary remote code execution)
    r"curl\s+[^|]*\|\s*(bash|sh|zsh|fish)",            # curl | bash
    r"wget\s+[^|]*\|\s*(bash|sh|zsh|fish)",            # wget | bash
    r"python\s+-c\s+.*requests.*\|\s*(bash|sh)",       # python -c | bash

    # World-writable (security hole)
    r"chmod\s+[0-7]*7\s+/",                            # chmod *7 / (world-writable root)
    r"chmod\s+-R\s+[0-7]*7\s+/",                      # chmod -R 777 /

    # Privilege escalation on system files
    r"sudo\s+rm\s+-[rRfF]+\s+/(?!\w)",                 # sudo rm -rf /

    # Crypto miner / resource abuse
    r"(xmrig|minerd|cgminer|cpuminer)",                # Known crypto miners

    # D-SAC integrity: block any command that references D-SAC state files
    # tee, dd, python -c, etc. could manipulate these files to bypass Layer 9
    r"\.pocketteam[/\\]dsac_tokens",                   # D-SAC token store
    r"\.pocketteam[/\\]dsac_sequence",                 # D-SAC sequence counters
    r"\.pocketteam[/\\]dsac_session",                  # D-SAC persistent session ID
    r"\.pocketteam[/\\]agent-registry\.json",          # Agent registry (privilege escalation via role injection)
]

# Compiled for performance
_NEVER_ALLOW_RE = [re.compile(p, re.IGNORECASE) for p in NEVER_ALLOW_PATTERNS]


# ─────────────────────────────────────────────────────────────────────────────
# Layer 2: DESTRUCTIVE_PATTERNS
# These require an approved plan token. Still allowed, but only with approval.
# ─────────────────────────────────────────────────────────────────────────────

# Safe targets: deleting these never needs approval
SAFE_DELETE_TARGETS = [
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    "dist/",
    "build/",
    ".cache",
    "*.pyc",
    "*.pyo",
    "coverage/",
    ".coverage",
    "htmlcov/",
    ".mypy_cache",
    ".ruff_cache",
    ".next/",
    "out/",
]

DESTRUCTIVE_PATTERNS: dict[str, list[str]] = {
    "Bash": [
        r"rm\s+-[rRfF]+",                             # rm -rf (any target)
        r"\bDROP\s+TABLE\b",                           # DROP TABLE
        r"\bTRUNCATE\b",                               # TRUNCATE
        r"DELETE\s+FROM\s+\w+\s*(?:;|$|\s+WHERE\s+1\s*=\s*1)",  # DELETE without WHERE
        r"git\s+push\s+.*--force",                    # Force push
        r"git\s+reset\s+--hard",                      # Hard reset
        r"git\s+clean\s+-[fd]+",                      # git clean
        r"kubectl\s+delete",                           # K8s delete
        r"docker\s+rm\s+-f",                           # Force docker rm
        r"terraform\s+destroy",                        # Terraform destroy
        r"systemctl\s+(stop|disable|mask)",            # Stop system services
        r"pkill\s+-[0-9]",                             # Kill processes by signal
    ],
    "Write": [
        r".*\.(env|pem|key|p12|pfx|cer|crt)$",        # Credentials/certs
        r".*/credentials(\.[a-z]+)?$",                  # Credentials files
        r".*/secrets(\.[a-z]+)?$",                      # Secrets files
        r".*/(\.ssh|\.aws|\.gcp)/.*",                  # Cloud credentials dirs
    ],
    "Edit": [
        r".*\.(env|pem|key|p12|pfx|cer|crt)$",        # Same for Edit
        r".*/credentials(\.[a-z]+)?$",
    ],
}

_DESTRUCTIVE_RE: dict[str, list[re.Pattern[str]]] = {
    tool: [re.compile(p, re.IGNORECASE) for p in patterns]
    for tool, patterns in DESTRUCTIVE_PATTERNS.items()
}

# Safe names (normalized: no trailing slash, no leading ./)
_SAFE_NAMES = {t.strip("./").rstrip("/") for t in SAFE_DELETE_TARGETS if not t.startswith("*")}
# Glob patterns handled separately (*.pyc, *.pyo)
_SAFE_GLOB_RE = re.compile(r"^\*\.[a-z]+$")

# rm command parser: rm [-flags] path ...
_RM_CMD_RE = re.compile(r"^rm\s+-[rRfF]+\s+(.+)$")


def _is_safe_delete_command(tool_input: str) -> bool:
    """
    Return True only if the rm command targets EXCLUSIVELY known safe directories.
    - No path traversal (..) allowed
    - Each target must exactly match a safe name (basename only, no parent paths)
    - Safe names: node_modules, __pycache__, dist, build, .cache, .pytest_cache, etc.
    """
    line = tool_input.strip().split("\n")[0]  # First command only
    match = _RM_CMD_RE.match(line)
    if not match:
        return False

    paths_str = match.group(1).strip()

    # No path traversal allowed under any circumstances
    if ".." in paths_str:
        return False

    # Split into individual paths (handles multiple targets: rm -rf dist/ build/)
    paths = paths_str.split()
    if not paths:
        return False

    for path in paths:
        # Normalize: strip leading ./ and trailing /
        normalized = path.lstrip("./").rstrip("/")

        # Allow known safe glob patterns like *.pyc
        if _SAFE_GLOB_RE.match(path):
            continue

        # Must exactly match a known safe name — no parent paths allowed
        if "/" in normalized:
            # Has a path separator → targeting something inside a directory
            # e.g., "dist/something" or "/var/__pycache__" — NOT safe
            return False

        if normalized not in _SAFE_NAMES:
            return False

    return True


# ─────────────────────────────────────────────────────────────────────────────
# Result types
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class RuleCheckResult:
    allowed: bool
    layer: int | None
    reason: str
    pattern: str | None = None
    requires_approval: bool = False


def check_never_allow(tool_name: str, tool_input: str) -> RuleCheckResult:
    """
    Layer 1 check: Is this absolutely forbidden?
    Returns immediately on first match — no further checks needed.
    """
    combined = f"{tool_name} {tool_input}"

    for pattern in _NEVER_ALLOW_RE:
        if pattern.search(combined):
            return RuleCheckResult(
                allowed=False,
                layer=1,
                reason=f"NEVER_ALLOW pattern matched: {pattern.pattern}",
                pattern=pattern.pattern,
            )

    return RuleCheckResult(allowed=True, layer=None, reason="")


def check_destructive(tool_name: str, tool_input: str) -> RuleCheckResult:
    """
    Layer 2 check: Is this destructive (requires plan approval)?
    """
    patterns = _DESTRUCTIVE_RE.get(tool_name, [])

    # Check if this is an rm command targeting ONLY known safe directories.
    # Important: must NOT use substring matching (rm -rf /data/__pycache__/.. would bypass).
    # Instead: extract the target path(s) and verify each is a known safe name.
    if tool_name == "Bash" and _is_safe_delete_command(tool_input):
        return RuleCheckResult(allowed=True, layer=None, reason="Safe delete target")

    for pattern in patterns:
        if pattern.search(tool_input):
            return RuleCheckResult(
                allowed=False,
                layer=2,
                reason="Destructive pattern requires plan approval",
                pattern=pattern.pattern,
                requires_approval=True,
            )

    return RuleCheckResult(allowed=True, layer=None, reason="")
