"""
Health Check — HTTP endpoint monitoring and log analysis.

Used by Monitor agent and GitHub Actions for:
- HTTP health endpoint checks (GET → 200)
- Response time measurement
- Error rate calculation from log patterns
- Log analysis for anomalies
"""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class HealthResult:
    """Result of a health check."""
    healthy: bool
    url: str = ""
    status_code: int = 0
    response_time_ms: float = 0.0
    error: Optional[str] = None


@dataclass
class LogAnalysisResult:
    """Result of log file analysis."""
    error_count: int = 0
    warning_count: int = 0
    error_patterns: list[str] = field(default_factory=list)
    error_rate: float = 0.0  # errors / total lines
    total_lines: int = 0
    anomaly_detected: bool = False
    summary: str = ""


class HealthChecker:
    """
    HTTP health endpoint checker.
    Supports multiple URLs with configurable thresholds.
    """

    def __init__(
        self,
        timeout_seconds: float = 10.0,
        max_response_time_ms: float = 2000.0,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_response_time_ms = max_response_time_ms

    async def check(self, url: str) -> HealthResult:
        """Check a single URL health."""
        start = time.monotonic()
        try:
            import httpx
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                resp = await client.get(url)
                elapsed_ms = (time.monotonic() - start) * 1000

                healthy = (
                    resp.status_code < 400
                    and elapsed_ms <= self.max_response_time_ms
                )

                return HealthResult(
                    healthy=healthy,
                    url=url,
                    status_code=resp.status_code,
                    response_time_ms=round(elapsed_ms, 1),
                    error=None if healthy else (
                        f"HTTP {resp.status_code}"
                        if resp.status_code >= 400
                        else f"Slow response: {elapsed_ms:.0f}ms"
                    ),
                )
        except Exception as e:
            return HealthResult(
                healthy=False,
                url=url,
                response_time_ms=round((time.monotonic() - start) * 1000, 1),
                error=str(e),
            )

    async def check_multiple(self, urls: list[str]) -> list[HealthResult]:
        """Check multiple URLs concurrently."""
        return await asyncio.gather(*(self.check(url) for url in urls))

    async def check_consecutive(
        self,
        url: str,
        count: int = 3,
        interval: float = 2.0,
    ) -> list[HealthResult]:
        """
        Check a URL multiple times consecutively.
        Used for confirming persistent failures (not transient).
        """
        results = []
        for i in range(count):
            results.append(await self.check(url))
            if i < count - 1:
                await asyncio.sleep(interval)
        return results


class LogAnalyzer:
    """
    Analyze log files for errors, warnings, and anomalies.
    Works with common log formats.
    """

    # Common error patterns
    ERROR_PATTERNS = [
        re.compile(r"\bERROR\b", re.IGNORECASE),
        re.compile(r"\bFATAL\b", re.IGNORECASE),
        re.compile(r"\bCRITICAL\b", re.IGNORECASE),
        re.compile(r"\bException\b"),
        re.compile(r"\bTraceback\b"),
        re.compile(r"\bPanic\b", re.IGNORECASE),
        re.compile(r"HTTP\s+5\d{2}"),  # 5xx errors
    ]

    WARNING_PATTERNS = [
        re.compile(r"\bWARN(?:ING)?\b", re.IGNORECASE),
        re.compile(r"\bDEPRECATED\b", re.IGNORECASE),
        re.compile(r"HTTP\s+4\d{2}"),  # 4xx errors
    ]

    def analyze_file(
        self,
        log_path: Path,
        max_lines: int = 10000,
        error_rate_threshold: float = 0.01,
    ) -> LogAnalysisResult:
        """Analyze a log file for errors and anomalies."""
        if not log_path.exists():
            return LogAnalysisResult(summary=f"Log file not found: {log_path}")

        lines = log_path.read_text().splitlines()[-max_lines:]
        total = len(lines)

        if total == 0:
            return LogAnalysisResult(summary="Empty log file")

        error_count = 0
        warning_count = 0
        error_samples: list[str] = []

        for line in lines:
            is_error = any(p.search(line) for p in self.ERROR_PATTERNS)
            is_warning = any(p.search(line) for p in self.WARNING_PATTERNS)

            if is_error:
                error_count += 1
                if len(error_samples) < 10:
                    error_samples.append(line[:200])
            elif is_warning:
                warning_count += 1

        error_rate = error_count / total if total > 0 else 0.0
        anomaly = error_rate > error_rate_threshold

        return LogAnalysisResult(
            error_count=error_count,
            warning_count=warning_count,
            error_patterns=error_samples,
            error_rate=round(error_rate, 4),
            total_lines=total,
            anomaly_detected=anomaly,
            summary=(
                f"{error_count} errors, {warning_count} warnings "
                f"in {total} lines (error rate: {error_rate:.2%})"
                + (" — ANOMALY DETECTED" if anomaly else "")
            ),
        )

    def analyze_text(
        self,
        text: str,
        error_rate_threshold: float = 0.01,
    ) -> LogAnalysisResult:
        """Analyze log text directly (e.g. from subprocess output)."""
        lines = text.splitlines()
        total = len(lines)

        if total == 0:
            return LogAnalysisResult(summary="Empty log text")

        error_count = 0
        warning_count = 0
        error_samples: list[str] = []

        for line in lines:
            is_error = any(p.search(line) for p in self.ERROR_PATTERNS)
            is_warning = any(p.search(line) for p in self.WARNING_PATTERNS)

            if is_error:
                error_count += 1
                if len(error_samples) < 10:
                    error_samples.append(line[:200])
            elif is_warning:
                warning_count += 1

        error_rate = error_count / total if total > 0 else 0.0

        return LogAnalysisResult(
            error_count=error_count,
            warning_count=warning_count,
            error_patterns=error_samples,
            error_rate=round(error_rate, 4),
            total_lines=total,
            anomaly_detected=error_rate > error_rate_threshold,
            summary=(
                f"{error_count} errors, {warning_count} warnings in {total} lines"
            ),
        )
