"""
Monitor Agent — production health monitoring.

Checks health endpoints, error rates, and response times.
Triggers self-healing when anomalies are detected.
Uses Haiku (cheap) because it runs continuously and mostly just reads.
"""

from __future__ import annotations

from typing import Optional

from .base import AgentContext, AgentResult, BaseAgent


class MonitorAgent(BaseAgent):
    def _get_agent_id(self) -> str:
        return "monitor"

    async def _run(self, task: str, context: Optional[AgentContext]) -> AgentResult:
        result = await self._run_with_sdk(task)
        if result.success and result.output:
            result.artifacts["health_report"] = result.output
            # Self-healing loop checks this flag
            result.artifacts["anomaly_detected"] = (
                "ANOMALY" in result.output.upper()
                or "ERROR" in result.output.upper()
                or "FAIL" in result.output.upper()
            )
        return result
