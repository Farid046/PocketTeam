"""
Safety Layer 4: Network Safety
Domain allowlist — prevents data exfiltration via WebFetch/HTTP requests.
Known failure mode (token exfiltration via HTTP gateway): block outbound requests to non-allowlisted domains.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass
class NetworkCheckResult:
    allowed: bool
    layer: int = 4
    reason: str = ""
    domain: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# Default approved domains (safe for all agents)
# Additional domains can be added via .pocketteam/config.yaml
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_APPROVED_DOMAINS: list[str] = [
    # Package registries
    "registry.npmjs.org",
    "pypi.org",
    "files.pythonhosted.org",
    "rubygems.org",
    "pkg.go.dev",
    "crates.io",

    # Version control
    "github.com",
    "api.github.com",
    "raw.githubusercontent.com",
    "gitlab.com",
    "bitbucket.org",

    # Cloud services (Supabase)
    "api.supabase.com",
    "supabase.co",
    "supabase.com",

    # AI / Anthropic
    "docs.anthropic.com",
    "api.anthropic.com",

    # Documentation
    "docs.github.com",
    "developer.mozilla.org",
    "docs.python.org",
    "nodejs.org",
    "reactjs.org",
    "nextjs.org",
    "tailwindcss.com",
    "stackoverflow.com",

    # CDN / assets
    "cdn.jsdelivr.net",
    "unpkg.com",

    # Search
    "api.tavily.com",
]

# Always blocked — known exfiltration / malicious patterns
BLOCKED_DOMAINS: list[str] = [
    "requestbin.com",
    "webhook.site",
    "pipedream.net",
    "ngrok.io",
    "ngrok-free.app",
    "hookbin.com",
    "canarytokens.com",
    "interact.sh",
    "oast.me",
    "oast.site",
]

# Suspicious URL patterns (even if domain is allowed)
SUSPICIOUS_URL_PATTERNS = [
    r"[?&](token|api_key|apikey|secret|password|auth)=",  # Secrets in URL params
    r"[?&](key|pass|pwd|credential)=",
    r"(?:^|\.)onion$",                                     # Tor hidden services
    r"data:[^;]+;base64,",                                  # Data URLs with base64
]

_SUSPICIOUS_RE = [re.compile(p, re.IGNORECASE) for p in SUSPICIOUS_URL_PATTERNS]


def check_network_safety(
    url: str,
    extra_approved_domains: list[str] | None = None,
) -> NetworkCheckResult:
    """
    Layer 4: Check if a URL is safe to access.
    Returns allowed=True only if domain is in the allowlist.
    """
    if not url:
        return NetworkCheckResult(allowed=True, reason="No URL")

    # Parse URL
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        # Strip port
        if ":" in domain:
            domain = domain.split(":")[0]
    except Exception:
        return NetworkCheckResult(
            allowed=False,
            reason="Could not parse URL",
            domain=url,
        )

    # localhost / internal always allowed (local development)
    if _is_local(domain):
        return NetworkCheckResult(allowed=True, reason="Local/internal address", domain=domain)

    # Block cloud provider Instance Metadata Service (IMDS) endpoints.
    # These can expose IAM credentials — must be blocked before any allowlist check.
    if _is_cloud_metadata(domain):
        return NetworkCheckResult(
            allowed=False,
            reason=(
                f"Domain {domain} is a cloud metadata service endpoint (IMDS). "
                "Access to instance metadata is blocked to prevent credential theft."
            ),
            domain=domain,
        )

    # Check blocked list first
    if domain in BLOCKED_DOMAINS or any(domain.endswith(f".{b}") for b in BLOCKED_DOMAINS):
        return NetworkCheckResult(
            allowed=False,
            reason=f"Domain {domain} is on the blocked list (known exfiltration endpoint)",
            domain=domain,
        )

    # Check suspicious URL patterns
    for pattern in _SUSPICIOUS_RE:
        if pattern.search(url):
            return NetworkCheckResult(
                allowed=False,
                reason="Suspicious URL pattern detected (possible credential leakage)",
                domain=domain,
            )

    # Build combined approved list
    approved = list(DEFAULT_APPROVED_DOMAINS)
    if extra_approved_domains:
        approved.extend(extra_approved_domains)

    # Check allowlist (exact match or subdomain of approved)
    for approved_domain in approved:
        if approved_domain.startswith("*."):
            base = approved_domain[2:]
            if domain == base or domain.endswith(f".{base}"):
                return NetworkCheckResult(allowed=True, reason="", domain=domain)
        elif domain == approved_domain or domain.endswith(f".{approved_domain}"):
            return NetworkCheckResult(allowed=True, reason="", domain=domain)

    return NetworkCheckResult(
        allowed=False,
        reason=(
            f"Domain {domain} is not in the approved list. "
            "Add it to .pocketteam/config.yaml [network.approved_domains] if needed."
        ),
        domain=domain,
    )


def _is_local(domain: str) -> bool:
    """Check if a domain is localhost or a local network address."""
    if not domain:
        return True
    local_patterns = [
        "localhost",
        "127.0.0.1",
        "::1",
        "0.0.0.0",
    ]
    if domain in local_patterns:
        return True
    # Private IP ranges
    if domain.startswith(("10.", "192.168.", "172.16.", "172.17.", "172.18.",
                          "172.19.", "172.20.", "172.21.", "172.22.", "172.23.",
                          "172.24.", "172.25.", "172.26.", "172.27.", "172.28.",
                          "172.29.", "172.30.", "172.31.")):
        return True
    # .local domains (mDNS)
    if domain.endswith(".local"):
        return True
    return False


def _is_cloud_metadata(domain: str) -> bool:
    """
    Check if a domain targets a cloud provider Instance Metadata Service (IMDS).
    These endpoints expose credentials and must never be reachable from agent code.
    Covers AWS, GCP, Azure, and generic link-local IMDS addresses.
    """
    # AWS/GCP/Azure link-local IMDS IP
    if domain == "169.254.169.254":
        return True
    # Entire link-local range (169.254.0.0/16) — no legitimate public use
    if domain.startswith("169.254."):
        return True
    # GCP metadata domain
    if domain == "metadata.google.internal":
        return True
    return False


def extract_url_from_tool_input(tool_name: str, tool_input: str | dict) -> str | None:
    """Extract URL from various tool input formats."""
    if isinstance(tool_input, dict):
        # Common URL parameter names
        for key in ("url", "URL", "href", "endpoint", "uri"):
            if key in tool_input:
                return str(tool_input[key])

    if isinstance(tool_input, str):
        # WebFetch: first argument is typically the URL
        if tool_name in ("WebFetch",) or tool_name.startswith("mcp__tavily"):
            parts = tool_input.strip().split()
            if parts and parts[0].startswith(("http://", "https://")):
                return parts[0]

        # Extract URL from bash curl/wget commands
        url_re = re.compile(r'(?:curl|wget)\s+(?:-[^\s]+\s+)*(["\']?)(https?://[^\s"\']+)\1')
        match = url_re.search(tool_input)
        if match:
            return match.group(2)

    return None
