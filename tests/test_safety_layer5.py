"""
Tests for Safety Layer 5: Sensitive File Protection
No agent (except explicitly permitted) may read/write credentials.
"""

from pocketteam.safety.sensitive_paths import check_sensitive_path, extract_path_from_tool_input


class TestSensitivePaths:
    """Layer 5: Credential and secret file protection."""

    # ── Environment files ─────────────────────────────────────────────────────

    def test_blocks_dotenv(self):
        result = check_sensitive_path("Read", ".env")
        assert result.blocked

    def test_blocks_dotenv_local(self):
        result = check_sensitive_path("Write", ".env.local")
        assert result.blocked

    def test_blocks_dotenv_production(self):
        result = check_sensitive_path("Read", ".env.production")
        assert result.blocked

    def test_allows_dotenv_example(self):
        """env.example is always safe — it's the template."""
        result = check_sensitive_path("Read", ".env.example")
        assert not result.blocked

    def test_allows_dotenv_template(self):
        result = check_sensitive_path("Read", ".env.template")
        assert not result.blocked

    # ── Private keys and certificates ─────────────────────────────────────────

    def test_blocks_pem_file(self):
        result = check_sensitive_path("Read", "server.pem")
        assert result.blocked

    def test_blocks_key_file(self):
        result = check_sensitive_path("Read", "private.key")
        assert result.blocked

    def test_blocks_p12_file(self):
        result = check_sensitive_path("Read", "cert.p12")
        assert result.blocked

    def test_blocks_crt_file(self):
        result = check_sensitive_path("Read", "ssl.crt")
        assert result.blocked

    # ── SSH keys ──────────────────────────────────────────────────────────────

    def test_blocks_ssh_id_rsa(self):
        result = check_sensitive_path("Read", "/home/user/.ssh/id_rsa")
        assert result.blocked

    def test_blocks_ssh_id_ed25519(self):
        result = check_sensitive_path("Read", "/root/.ssh/id_ed25519")
        assert result.blocked

    def test_blocks_ssh_authorized_keys(self):
        result = check_sensitive_path("Write", "/home/user/.ssh/authorized_keys")
        assert result.blocked

    def test_blocks_ssh_config(self):
        result = check_sensitive_path("Read", "/home/user/.ssh/config")
        assert result.blocked

    # ── Cloud credentials ─────────────────────────────────────────────────────

    def test_blocks_aws_credentials(self):
        result = check_sensitive_path("Read", "/home/user/.aws/credentials")
        assert result.blocked

    def test_blocks_aws_config(self):
        result = check_sensitive_path("Read", "/home/user/.aws/config")
        assert result.blocked

    def test_blocks_gcp_service_account(self):
        result = check_sensitive_path("Read", "/home/user/.gcp/service-account.json")
        assert result.blocked

    def test_blocks_service_account_json(self):
        result = check_sensitive_path("Read", "my-project-service-account.json")
        assert result.blocked

    # ── Named credentials ──────────────────────────────────────────────────────

    def test_blocks_credentials_file(self):
        result = check_sensitive_path("Read", "credentials.json")
        assert result.blocked

    def test_blocks_secrets_file(self):
        result = check_sensitive_path("Read", "secrets.yaml")
        assert result.blocked

    def test_blocks_api_keys_file(self):
        result = check_sensitive_path("Read", "api_keys.txt")
        assert result.blocked

    # ── Docker ────────────────────────────────────────────────────────────────

    def test_blocks_docker_config(self):
        result = check_sensitive_path("Read", "/root/.docker/config.json")
        assert result.blocked

    # ── NPM / package manager ──────────────────────────────────────────────────

    def test_blocks_npmrc(self):
        result = check_sensitive_path("Read", ".npmrc")
        assert result.blocked

    def test_blocks_netrc(self):
        result = check_sensitive_path("Read", ".netrc")
        assert result.blocked

    # ── Safe files ────────────────────────────────────────────────────────────

    def test_allows_python_source(self):
        result = check_sensitive_path("Read", "src/auth.py")
        assert not result.blocked

    def test_allows_yaml_config(self):
        result = check_sensitive_path("Read", "config.yaml")
        assert not result.blocked

    def test_allows_readme(self):
        result = check_sensitive_path("Read", "README.md")
        assert not result.blocked

    def test_allows_package_json(self):
        result = check_sensitive_path("Read", "package.json")
        assert not result.blocked

    def test_allows_tsconfig(self):
        result = check_sensitive_path("Write", "tsconfig.json")
        assert not result.blocked

    def test_allows_dockerfile(self):
        result = check_sensitive_path("Write", "Dockerfile")
        assert not result.blocked

    # ── Safe alternative suggestion ───────────────────────────────────────────

    def test_provides_safe_alternative_for_env(self):
        result = check_sensitive_path("Read", ".env")
        assert result.blocked
        assert result.safe_alternative is not None
        assert len(result.safe_alternative) > 0

    # ── Path extraction ───────────────────────────────────────────────────────

    def test_extract_path_from_bash_cat(self):
        paths = extract_path_from_tool_input("Bash", "cat .env")
        assert ".env" in paths

    def test_extract_path_from_bash_redirect(self):
        paths = extract_path_from_tool_input("Bash", "echo 'secret' > .env")
        assert ".env" in paths
