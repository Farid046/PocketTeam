"""
Safety Layer 5: Sensitive File Protection
Blocks read AND write access to credentials, keys, secrets.
Agents should never touch .env, SSH keys, cloud credentials, etc.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class SensitivePathResult:
    blocked: bool
    layer: int = 5
    reason: str = ""
    path: str = ""
    safe_alternative: str | None = None


# ─────────────────────────────────────────────────────────────────────────────
# Sensitive path patterns — both READ and WRITE are blocked
# ─────────────────────────────────────────────────────────────────────────────

SENSITIVE_PATH_PATTERNS: list[str] = [
    # Environment files with real secrets
    r".*\.env$",
    r".*\.env\.[a-z]+$",              # .env.local, .env.production, .env.test
    r".*\.envrc$",                     # direnv
    r".*/_env$",

    # Private keys and certificates
    r".*\.pem$",
    r".*\.key$",
    r".*\.p12$",
    r".*\.pfx$",
    r".*\.cer$",
    r".*\.crt$",
    r".*\.jks$",                       # Java keystore
    r".*\.keystore$",

    # SSH (id_rsa, id_ed25519, id_ecdsa — names can contain digits)
    r".*/\.ssh/id_[a-z0-9_-]+$",      # SSH private keys
    r".*/\.ssh/id_[a-z0-9_-]+\.pub$", # SSH public keys
    r".*/\.ssh/known_hosts",
    r".*/\.ssh/config",
    r".*/\.ssh/authorized_keys",

    # Cloud credentials
    r".*/\.aws/credentials",
    r".*/\.aws/config",
    r".*/\.gcp/.*\.json$",             # Service account keys
    r".*/\.config/gcloud/.*",
    r".*/\.azure/.*",
    r".*service[-_]?account.*\.json$", # GCP service accounts

    # Password managers / secret stores
    r".*/\.password-store/.*",
    r".*/\.gnupg/.*",
    r".*\.kdbx$",                      # KeePass

    # Database dumps with potential secrets
    r".*\.sql\.gz$",
    r".*\.dump$",
    r".*_dump\.sql$",

    # Named credential/secret files (with or without leading path)
    r"(.*[/\\])?credentials(\.[a-z]+)?$",
    r"(.*[/\\])?secrets(\.[a-z]+)?$",
    r"(.*[/\\])?secret(\.[a-z]+)?$",
    r"(.*[/\\])?api[_-]?key[s]?(\.[a-z]+)?$",
    r"(.*[/\\])?token[s]?(\.[a-z]+)?$",
    r"(.*[/\\])?password[s]?(\.[a-z]+)?$",

    # Docker secrets
    r".*/\.docker/config\.json$",
    r".*/run/secrets/.*",

    # NPM / package manager tokens
    r".*\.npmrc$",
    r".*\.pypirc$",
    r".*\.netrc$",

    # PocketTeam internal sensitive files
    r".*[/\\]\.pocketteam[/\\]browse\.json$",       # browser session state (may contain cookies/tokens)
    r".*[/\\]\.pocketteam[/\\]dsac_tokens\.json$",  # D-SAC approval tokens
    r".*[/\\]\.pocketteam[/\\]dsac_sequence\.json$",  # D-SAC sequence counters
    r".*[/\\]\.pocketteam[/\\]dsac_tokens\.lock$",    # D-SAC token lock file
    r".*[/\\]\.pocketteam[/\\]dsac_sequence\.lock$",  # D-SAC sequence lock file
    r".*[/\\]\.pocketteam[/\\]dsac_session\.txt$",    # D-SAC persistent session ID [v3.1 Fix B]
]

_SENSITIVE_RE = [re.compile(p, re.IGNORECASE) for p in SENSITIVE_PATH_PATTERNS]

# Safe alternatives to suggest
SAFE_ALTERNATIVES: dict[str, str] = {
    ".env": ".env.example (template) or environment variables",
    "id_rsa": "SSH agent or ssh-add command",
    "credentials": "IAM roles or environment variables",
    "service_account": "Workload Identity or environment variables",
}


def check_sensitive_path(
    tool_name: str,
    path: str,
    agent_id: str | None = None,
) -> SensitivePathResult:
    """
    Layer 5: Check if a file path is sensitive.
    Blocks Read, Write, Edit on sensitive files.
    """
    if not path:
        return SensitivePathResult(blocked=False, reason="")

    # Normalize path
    normalized = path.strip().lower()

    # .env.example is always safe
    if normalized.endswith(".env.example") or normalized.endswith(".env.template"):
        return SensitivePathResult(blocked=False, reason=".env.example is safe")

    # Check against sensitive patterns
    for pattern in _SENSITIVE_RE:
        if pattern.match(normalized):
            # Suggest safe alternative
            alternative = _suggest_alternative(path)

            return SensitivePathResult(
                blocked=True,
                reason=(
                    f"Sensitive file access blocked: {path}\n"
                    "Agents must never read or write credential files.\n"
                    f"Safe alternative: {alternative}"
                ),
                path=path,
                safe_alternative=alternative,
            )

    return SensitivePathResult(blocked=False, reason="")


def extract_path_from_tool_input(tool_name: str, tool_input: str | dict) -> list[str]:
    """Extract file paths from tool input for various tool types."""
    paths: list[str] = []

    if isinstance(tool_input, dict):
        # Common path parameter names
        for key in ("file_path", "path", "filename", "target", "destination", "source"):
            if key in tool_input:
                paths.append(str(tool_input[key]))
        return paths

    if isinstance(tool_input, str):
        if tool_name in ("Read", "Write", "Edit"):
            # First argument is typically the path
            parts = tool_input.strip().split()
            if parts:
                paths.append(parts[0])

        elif tool_name == "Bash":
            # Extract paths from common shell commands
            path_patterns = [
                r'(?:cat|head|tail|less|more|nano|vim|vi|emacs)\s+([^\s|&;><]+)',
                r'(?:cp|mv|chmod|chown)\s+\S+\s+([^\s|&;><]+)',
                r'(?:>|>>)\s*([^\s|&;><]+)',
                r'(?:echo|printf)\s+.*(?:>|>>)\s*([^\s|&;><]+)',
                r'(?:touch|rm)\s+([^\s|&;><]+)',
            ]
            for pat in path_patterns:
                matches = re.findall(pat, tool_input, re.IGNORECASE)
                paths.extend(matches)

    return [p for p in paths if p]


def _suggest_alternative(path: str) -> str:
    """Suggest a safe alternative for a sensitive file."""
    path_lower = path.lower()

    for key, alternative in SAFE_ALTERNATIVES.items():
        if key in path_lower:
            return alternative

    return "Use environment variables or a secrets manager instead"
