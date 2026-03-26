"""
Security Agent — OWASP, STRIDE, and dependency audit.

Checks for OWASP Top 10 vulnerabilities, threat model (STRIDE),
insecure dependencies (CVEs), and LLM-specific trust boundary issues.
Read-only: does not modify code, only reports findings.

Two modes:
1. SDK mode (via execute()): full Claude session for comprehensive audit.
2. Programmatic mode (via scan_dependencies()): direct dependency scan —
   no LLM needed, used by self-healing pipeline and GitHub Actions.
"""

from __future__ import annotations

import asyncio
import json
import re
import shutil
from dataclasses import dataclass, field

from .base import AgentContext, AgentResult, BaseAgent


@dataclass
class DependencyScanResult:
    """Result of a dependency vulnerability scan."""
    success: bool           # True = scan ran cleanly (even if vulns found)
    vulnerabilities: list[dict] = field(default_factory=list)
    critical_count: int = 0
    high_count: int = 0
    total_count: int = 0
    output: str = ""
    scanner: str = "unknown"

    @property
    def has_critical(self) -> bool:
        return self.critical_count > 0

    @property
    def summary(self) -> str:
        return (
            f"{self.scanner}: {self.total_count} vulnerabilities "
            f"({self.critical_count} critical, {self.high_count} high)"
        )


class SecurityAgent(BaseAgent):
    def _get_agent_id(self) -> str:
        return "security"

    async def _run(self, task: str, context: AgentContext | None) -> AgentResult:
        result = await self._run_with_sdk(task)
        if result.success and result.output:
            result.artifacts["security_report"] = result.output
            # Pipeline uses "CRITICAL" marker to decide whether to block deploy
            result.artifacts["has_critical"] = "CRITICAL" in result.output.upper()
        return result

    async def scan_dependencies(self) -> AgentResult:
        """
        Programmatic dependency vulnerability scan — no SDK session needed.

        Tries (in order):
        1. `pip-audit` for Python projects
        2. `npm audit` for Node projects
        Falls back to a static check of known-dangerous packages.

        Used by self-healing pipeline and GitHub Actions pre-deploy checks.
        """
        await self._log_event("working", "Scanning dependencies for vulnerabilities")

        result = await self._run_dependency_scan()

        status = "CRITICAL" if result.has_critical else (
            "HIGH" if result.high_count > 0 else "CLEAN"
        )
        output = f"[{status}] {result.summary}\n\n{result.output}"

        return AgentResult(
            agent_id=self.agent_id,
            success=result.success,
            output=output,
            artifacts={
                "scan_result": result,
                "has_critical": result.has_critical,
                "security_report": output,
                "vulnerability_count": result.total_count,
            },
            error=None if not result.has_critical else (
                f"CRITICAL vulnerabilities found: {result.critical_count}"
            ),
        )

    async def _run_dependency_scan(self) -> DependencyScanResult:
        """Try available scanners in order of preference."""
        root = self.project_root

        # Python: pip-audit
        if (root / "pyproject.toml").exists() or (root / "requirements.txt").exists():
            if shutil.which("pip-audit"):
                return await self._run_pip_audit()
            # Fallback: check requirements.txt against known bad packages
            return await self._static_python_check()

        # Node: npm audit
        if (root / "package.json").exists():
            if shutil.which("npm"):
                return await self._run_npm_audit()

        return DependencyScanResult(
            success=True,
            output="No supported package manifest found (pyproject.toml/requirements.txt/package.json)",
            scanner="none",
        )

    async def _run_pip_audit(self) -> DependencyScanResult:
        """Run pip-audit and parse JSON output."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "pip-audit", "--format=json", "--progress-spinner=off",
                cwd=str(self.project_root),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
        except TimeoutError:
            return DependencyScanResult(
                success=False, output="pip-audit timed out", scanner="pip-audit"
            )
        except FileNotFoundError:
            return DependencyScanResult(
                success=False,
                output="pip-audit not found. Install: pip install pip-audit",
                scanner="pip-audit",
            )

        output = stdout.decode("utf-8", errors="replace")
        try:
            data = json.loads(output)
            vulns = data.get("vulnerabilities", []) if isinstance(data, dict) else []
            if isinstance(data, list):
                # Newer pip-audit format: list of dicts with "vulns" key
                vulns = [v for pkg in data for v in pkg.get("vulns", [])]
        except json.JSONDecodeError:
            return DependencyScanResult(
                success=True,
                output=output or stderr.decode("utf-8", errors="replace"),
                scanner="pip-audit",
            )

        critical = sum(1 for v in vulns if _is_critical(v))
        high = sum(1 for v in vulns if _is_high(v))
        return DependencyScanResult(
            success=True,
            vulnerabilities=vulns,
            critical_count=critical,
            high_count=high,
            total_count=len(vulns),
            output=output,
            scanner="pip-audit",
        )

    async def _run_npm_audit(self) -> DependencyScanResult:
        """Run npm audit --json and parse."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "npm", "audit", "--json",
                cwd=str(self.project_root),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
        except (TimeoutError, FileNotFoundError) as exc:
            return DependencyScanResult(
                success=False, output=str(exc), scanner="npm-audit"
            )

        output = stdout.decode("utf-8", errors="replace")
        try:
            data = json.loads(output)
            metadata = data.get("metadata", {}).get("vulnerabilities", {})
            critical = metadata.get("critical", 0)
            high = metadata.get("high", 0)
            total = metadata.get("total", 0)
            vulns_raw = data.get("vulnerabilities", {})
            vulns = list(vulns_raw.values()) if isinstance(vulns_raw, dict) else []
        except (json.JSONDecodeError, AttributeError):
            critical = high = total = 0
            vulns = []

        return DependencyScanResult(
            success=True,
            vulnerabilities=vulns,
            critical_count=critical,
            high_count=high,
            total_count=total,
            output=output,
            scanner="npm-audit",
        )

    async def _static_python_check(self) -> DependencyScanResult:
        """
        Fallback: scan requirements.txt for known dangerous packages.
        Not exhaustive — just a quick sanity check when pip-audit is absent.
        """
        # Known packages with serious historical CVEs
        known_dangerous = {
            "pyyaml<6.0": "CVE-2020-14343 (YAML deserialization RCE)",
            "pillow<10.0.1": "CVE-2023-50447 (heap overflow)",
            "requests<2.32.0": "CVE-2024-35195 (SSRF via proxy)",
            "urllib3<1.26.19": "CVE-2024-37891 (open redirect)",
            "cryptography<42.0.4": "CVE-2023-49083 (NULL pointer deref)",
            "setuptools<65.5.1": "CVE-2022-40897 (ReDoS)",
        }

        root = self.project_root
        req_file = root / "requirements.txt"
        if not req_file.exists():
            return DependencyScanResult(
                success=True,
                output="No requirements.txt found",
                scanner="static-check",
            )

        content = req_file.read_text()
        warnings: list[str] = []
        for pattern, cve in known_dangerous.items():
            pkg = pattern.split("<")[0]
            if re.search(rf"^{re.escape(pkg)}\b", content, re.MULTILINE | re.IGNORECASE):
                warnings.append(f"WARNING: {pkg} may be vulnerable — {cve}")

        return DependencyScanResult(
            success=True,
            total_count=len(warnings),
            output="\n".join(warnings) if warnings else "No known vulnerable packages detected",
            scanner="static-check",
        )


def _is_critical(vuln: dict) -> bool:
    return vuln.get("severity", "").upper() == "CRITICAL"


def _is_high(vuln: dict) -> bool:
    return vuln.get("severity", "").upper() == "HIGH"
