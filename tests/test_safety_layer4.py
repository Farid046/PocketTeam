"""
Tests for Safety Layer 4: Network Safety (Domain Allowlist)
Prevents data exfiltration via unauthorized HTTP requests.
"""

import pytest
from pocketteam.safety.network_rules import check_network_safety, extract_url_from_tool_input


class TestNetworkSafety:
    """Layer 4: Domain allowlist."""

    # ── Approved domains ─────────────────────────────────────────────────────

    def test_allows_github(self):
        result = check_network_safety("https://github.com/anthropics/claude-code")
        assert result.allowed

    def test_allows_github_api(self):
        result = check_network_safety("https://api.github.com/repos/foo/bar")
        assert result.allowed

    def test_allows_raw_githubusercontent(self):
        result = check_network_safety("https://raw.githubusercontent.com/foo/bar/main/README.md")
        assert result.allowed

    def test_allows_pypi(self):
        result = check_network_safety("https://pypi.org/pypi/requests/json")
        assert result.allowed

    def test_allows_npm_registry(self):
        result = check_network_safety("https://registry.npmjs.org/react")
        assert result.allowed

    def test_allows_supabase(self):
        result = check_network_safety("https://api.supabase.com/v1/projects")
        assert result.allowed

    def test_allows_supabase_project(self):
        result = check_network_safety("https://xyzproject.supabase.co/rest/v1/users")
        assert result.allowed

    def test_allows_docs(self):
        result = check_network_safety("https://docs.anthropic.com/claude/docs")
        assert result.allowed

    def test_allows_stackoverflow(self):
        result = check_network_safety("https://stackoverflow.com/questions/123")
        assert result.allowed

    # ── Local / internal always allowed ──────────────────────────────────────

    def test_allows_localhost(self):
        result = check_network_safety("http://localhost:3000/api")
        assert result.allowed

    def test_allows_localhost_ip(self):
        result = check_network_safety("http://127.0.0.1:8080/health")
        assert result.allowed

    def test_allows_local_ip_192_168(self):
        result = check_network_safety("http://192.168.1.100:5000/api")
        assert result.allowed

    def test_allows_local_domain(self):
        result = check_network_safety("http://myapp.local/health")
        assert result.allowed

    # ── Blocked: known exfiltration endpoints ────────────────────────────────

    def test_blocks_requestbin(self):
        result = check_network_safety("https://requestbin.com/r/abc123")
        assert not result.allowed

    def test_blocks_webhook_site(self):
        result = check_network_safety("https://webhook.site/abc-123-def")
        assert not result.allowed

    def test_blocks_ngrok(self):
        result = check_network_safety("https://abc123.ngrok.io/api")
        assert not result.allowed

    def test_blocks_ngrok_free(self):
        result = check_network_safety("https://abc123.ngrok-free.app/data")
        assert not result.allowed

    def test_blocks_canary_tokens(self):
        result = check_network_safety("https://canarytokens.com/feedback/abc")
        assert not result.allowed

    def test_blocks_oast(self):
        result = check_network_safety("https://abc.oast.me/test")
        assert not result.allowed

    # ── Blocked: unknown domains ──────────────────────────────────────────────

    def test_blocks_unknown_domain(self):
        result = check_network_safety("https://evil.example.com/steal-data")
        assert not result.allowed

    def test_blocks_random_api(self):
        result = check_network_safety("https://data-collector.io/submit")
        assert not result.allowed

    # ── Blocked: suspicious URL patterns ─────────────────────────────────────

    def test_blocks_api_key_in_url(self):
        result = check_network_safety("https://github.com/api?api_key=sk-secret-123")
        assert not result.allowed

    def test_blocks_token_in_url(self):
        result = check_network_safety("https://api.github.com/repos?token=ghp_xxxx")
        assert not result.allowed

    def test_blocks_password_in_url(self):
        result = check_network_safety("https://api.example.com/auth?password=mysecret")
        assert not result.allowed

    # ── Extra approved domains from config ───────────────────────────────────

    def test_allows_extra_approved_domain(self):
        result = check_network_safety(
            "https://my-custom-api.com/endpoint",
            extra_approved_domains=["my-custom-api.com"],
        )
        assert result.allowed

    def test_blocks_even_with_wrong_extra(self):
        result = check_network_safety(
            "https://evil.com/data",
            extra_approved_domains=["good-domain.com"],
        )
        assert not result.allowed

    # ── URL extraction ────────────────────────────────────────────────────────

    def test_extract_url_from_curl(self):
        url = extract_url_from_tool_input("Bash", "curl -s https://api.github.com/repos")
        assert url == "https://api.github.com/repos"

    def test_extract_url_from_wget(self):
        url = extract_url_from_tool_input("Bash", "wget https://pypi.org/file.tar.gz")
        assert url == "https://pypi.org/file.tar.gz"

    def test_extract_url_from_web_fetch_dict(self):
        url = extract_url_from_tool_input("WebFetch", {"url": "https://github.com/test"})
        assert url == "https://github.com/test"
