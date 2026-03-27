"""
Tests for Phase 12: Deploy Tools + Health Check.
No real Docker/HTTP calls — all external calls are mocked.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from pocketteam.tools.deploy_tools import DeployTools
from pocketteam.tools.health_check import (
    HealthChecker,
    LogAnalyzer,
)

# ── DeployTools ─────────────────────────────────────────────────────────────

class TestDeployTools:
    async def _mock_process(self, output: str, returncode: int = 0) -> MagicMock:
        proc = MagicMock()
        proc.returncode = returncode
        proc.communicate = AsyncMock(return_value=(output.encode(), b""))
        proc.kill = MagicMock()
        return proc

    async def test_docker_build_success(self, tmp_path: Path):
        dt = DeployTools(tmp_path)
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.return_value = await self._mock_process("Successfully built abc123")
            result = await dt.docker_build(tag="myapp:latest")

        assert result.success is True
        assert "abc123" in result.output

    async def test_docker_build_failure(self, tmp_path: Path):
        dt = DeployTools(tmp_path)
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.return_value = await self._mock_process("Error: Dockerfile not found", 1)
            result = await dt.docker_build()

        assert result.success is False
        assert result.error is not None

    async def test_docker_build_with_args(self, tmp_path: Path):
        dt = DeployTools(tmp_path)
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.return_value = await self._mock_process("built", 0)
            await dt.docker_build(tag="app:v1", build_args={"NODE_ENV": "production"})

        call_args = mock_exec.call_args[0]
        assert "--build-arg" in call_args
        assert "NODE_ENV=production" in call_args

    async def test_docker_push(self, tmp_path: Path):
        dt = DeployTools(tmp_path)
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.return_value = await self._mock_process("pushed")
            result = await dt.docker_push("myapp:latest")
        assert result.success is True

    async def test_docker_compose_up(self, tmp_path: Path):
        dt = DeployTools(tmp_path)
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.return_value = await self._mock_process("started")
            result = await dt.docker_compose_up(service="web")
        assert result.success is True

    async def test_docker_compose_down(self, tmp_path: Path):
        dt = DeployTools(tmp_path)
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.return_value = await self._mock_process("stopped")
            result = await dt.docker_compose_down()
        assert result.success is True

    async def test_docker_compose_restart(self, tmp_path: Path):
        dt = DeployTools(tmp_path)
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.return_value = await self._mock_process("restarted")
            result = await dt.docker_compose_restart(service="api")
        assert result.success is True

    async def test_command_not_found(self, tmp_path: Path):
        dt = DeployTools(tmp_path)
        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
            result = await dt.docker_build()
        assert result.success is False
        assert "not found" in result.error.lower()

    async def test_command_timeout(self, tmp_path: Path):
        dt = DeployTools(tmp_path)

        call_count = 0
        async def _communicate():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise TimeoutError()
            return b"", b""

        proc = MagicMock()
        proc.communicate = _communicate
        proc.kill = MagicMock()

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await dt._run_command(["test"], timeout=1)

        assert result.success is False
        assert "timed out" in result.output.lower()

    async def test_get_current_version(self, tmp_path: Path):
        dt = DeployTools(tmp_path)
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.return_value = await self._mock_process("v1.2.3")
            version = await dt.get_current_version()
        assert version == "v1.2.3"

    async def test_create_rollback_point(self, tmp_path: Path):
        dt = DeployTools(tmp_path)
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.return_value = await self._mock_process("")
            result = await dt.create_rollback_point()
        assert "rollback" in result.rollback_info.lower()

    async def test_git_deploy(self, tmp_path: Path):
        dt = DeployTools(tmp_path)
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.return_value = await self._mock_process("deployed")
            result = await dt.git_deploy(remote="production", branch="main")
        assert result.success is True


# ── HealthChecker ───────────────────────────────────────────────────────────

class TestHealthChecker:
    async def test_check_healthy(self):
        hc = HealthChecker(timeout_seconds=5)

        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client
            result = await hc.check("http://localhost:3000/health")

        assert result.healthy is True
        assert result.status_code == 200

    async def test_check_unhealthy_500(self):
        hc = HealthChecker()

        mock_resp = MagicMock()
        mock_resp.status_code = 500

        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client
            result = await hc.check("http://example.com/health")

        assert result.healthy is False
        assert "500" in result.error

    async def test_check_connection_error(self):
        hc = HealthChecker()

        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client
            result = await hc.check("http://down.example.com")

        assert result.healthy is False
        assert "refused" in result.error.lower()

    async def test_check_multiple(self):
        hc = HealthChecker()

        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch("httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client
            results = await hc.check_multiple([
                "http://app1.com/health",
                "http://app2.com/health",
            ])

        assert len(results) == 2
        assert all(r.healthy for r in results)


# ── LogAnalyzer ─────────────────────────────────────────────────────────────

class TestLogAnalyzer:
    def test_analyze_file_not_found(self, tmp_path: Path):
        la = LogAnalyzer()
        result = la.analyze_file(tmp_path / "nonexistent.log")
        assert "not found" in result.summary.lower()

    def test_analyze_empty_file(self, tmp_path: Path):
        log = tmp_path / "empty.log"
        log.write_text("")
        la = LogAnalyzer()
        result = la.analyze_file(log)
        assert result.total_lines == 0

    def test_analyze_clean_log(self, tmp_path: Path):
        log = tmp_path / "app.log"
        log.write_text(
            "2024-01-01 INFO Starting server\n"
            "2024-01-01 INFO Request handled\n"
            "2024-01-01 INFO Server running\n"
        )
        la = LogAnalyzer()
        result = la.analyze_file(log)
        assert result.error_count == 0
        assert result.warning_count == 0
        assert result.anomaly_detected is False

    def test_analyze_log_with_errors(self, tmp_path: Path):
        log = tmp_path / "app.log"
        lines = ["INFO normal line\n"] * 100
        lines.append("ERROR database connection failed\n")
        lines.append("FATAL out of memory\n")
        lines.append("WARNING disk space low\n")
        log.write_text("".join(lines))

        la = LogAnalyzer()
        result = la.analyze_file(log)
        assert result.error_count == 2
        assert result.warning_count == 1
        assert result.total_lines == 103

    def test_analyze_log_anomaly_detected(self, tmp_path: Path):
        log = tmp_path / "app.log"
        lines = ["INFO ok\n"] * 50
        lines.extend(["ERROR fail\n"] * 10)  # 10/60 = 16.7% error rate
        log.write_text("".join(lines))

        la = LogAnalyzer()
        result = la.analyze_file(log, error_rate_threshold=0.01)
        assert result.anomaly_detected is True

    def test_analyze_text(self):
        la = LogAnalyzer()
        text = "INFO ok\nERROR bad\nWARNING meh\nCRITICAL boom"
        result = la.analyze_text(text)
        assert result.error_count == 2  # ERROR + CRITICAL
        assert result.warning_count == 1

    def test_analyze_text_empty(self):
        la = LogAnalyzer()
        result = la.analyze_text("")
        assert result.total_lines == 0

    def test_error_patterns_http_5xx(self, tmp_path: Path):
        log = tmp_path / "access.log"
        log.write_text(
            "GET /api HTTP 200 OK\n"
            "GET /api HTTP 500 Internal Server Error\n"
            "GET /api HTTP 503 Service Unavailable\n"
            "GET /api HTTP 404 Not Found\n"
        )
        la = LogAnalyzer()
        result = la.analyze_file(log)
        assert result.error_count == 2  # 500 + 503
        assert result.warning_count == 1  # 404

    def test_error_patterns_traceback(self):
        la = LogAnalyzer()
        text = (
            "Traceback (most recent call last):\n"
            "  File 'app.py', line 42\n"
            "Exception: something broke\n"
        )
        result = la.analyze_text(text)
        assert result.error_count == 2  # Traceback + Exception

    def test_error_samples_limited(self, tmp_path: Path):
        log = tmp_path / "big.log"
        lines = [f"ERROR line {i}\n" for i in range(100)]
        log.write_text("".join(lines))

        la = LogAnalyzer()
        result = la.analyze_file(log)
        assert result.error_count == 100
        assert len(result.error_patterns) == 10  # Capped at 10 samples
