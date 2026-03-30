"""
Fake HTTP app for Agent SDK integration testing.

A pure-stdlib http.server with configurable chaos modes:
- GET  /health  → 200 OK or configurable failure (500, 503, timeout)
- GET  /logs    → JSON log output with configurable error patterns
- POST /chaos   → Enable/disable failure modes
- POST /reset   → Reset to healthy state

Usage:
    # As subprocess (used by conftest.py fixtures)
    python -m tests.sdk_integration.fake_app --port 0  # picks free port

    # Prints "READY:<port>" to stdout when listening
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any


class ChaosState:
    """Thread-safe chaos configuration."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._health_status: int = 200
        self._health_delay: float = 0.0
        self._error_rate: float = 0.0
        self._log_errors: int = 0
        self._log_warnings: int = 0
        self._request_count: int = 0

    def get(self) -> dict[str, Any]:
        with self._lock:
            return {
                "health_status": self._health_status,
                "health_delay": self._health_delay,
                "error_rate": self._error_rate,
                "log_errors": self._log_errors,
                "log_warnings": self._log_warnings,
                "request_count": self._request_count,
            }

    def update(self, **kwargs: Any) -> None:
        with self._lock:
            if "health_status" in kwargs:
                self._health_status = int(kwargs["health_status"])
            if "health_delay" in kwargs:
                self._health_delay = float(kwargs["health_delay"])
            if "error_rate" in kwargs:
                self._error_rate = float(kwargs["error_rate"])
            if "log_errors" in kwargs:
                self._log_errors = int(kwargs["log_errors"])
            if "log_warnings" in kwargs:
                self._log_warnings = int(kwargs["log_warnings"])

    def reset(self) -> None:
        with self._lock:
            self._health_status = 200
            self._health_delay = 0.0
            self._error_rate = 0.0
            self._log_errors = 0
            self._log_warnings = 0

    def record_request(self) -> None:
        with self._lock:
            self._request_count += 1

    @property
    def health_status(self) -> int:
        with self._lock:
            return self._health_status

    @property
    def health_delay(self) -> float:
        with self._lock:
            return self._health_delay

    @property
    def log_errors(self) -> int:
        with self._lock:
            return self._log_errors

    @property
    def log_warnings(self) -> int:
        with self._lock:
            return self._log_warnings


# Module-level state (set per server instance)
_chaos = ChaosState()


def _read_body(handler: BaseHTTPRequestHandler) -> bytes:
    length = int(handler.headers.get("Content-Length", 0))
    return handler.rfile.read(length) if length > 0 else b""


def _send_json(handler: BaseHTTPRequestHandler, status: int, data: Any) -> None:
    body = json.dumps(data).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class FakeAppHandler(BaseHTTPRequestHandler):
    """Request handler for the fake app."""

    # Suppress default access logs
    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        pass

    def do_GET(self) -> None:
        _chaos.record_request()

        if self.path == "/health":
            self._handle_health()
        elif self.path == "/logs":
            self._handle_logs()
        elif self.path == "/chaos":
            _send_json(self, 200, _chaos.get())
        else:
            _send_json(self, 404, {"error": "not found"})

    def do_POST(self) -> None:
        _chaos.record_request()

        if self.path == "/chaos":
            self._handle_chaos_update()
        elif self.path == "/reset":
            _chaos.reset()
            _send_json(self, 200, {"status": "reset", "state": _chaos.get()})
        else:
            _send_json(self, 404, {"error": "not found"})

    def _handle_health(self) -> None:
        delay = _chaos.health_delay
        if delay > 0:
            time.sleep(delay)

        status = _chaos.health_status
        if status == 200:
            _send_json(self, 200, {
                "status": "healthy",
                "uptime": 12345,
                "version": "1.0.0-test",
            })
        else:
            _send_json(self, status, {
                "status": "unhealthy",
                "error": f"Chaos mode: returning HTTP {status}",
            })

    def _handle_logs(self) -> None:
        lines = []
        ts = time.strftime("%Y-%m-%dT%H:%M:%S")

        # Normal log lines
        lines.append(f"{ts} INFO  [app] Request processed successfully")
        lines.append(f"{ts} INFO  [db] Connection pool: 5/10 active")

        # Inject errors based on chaos config
        for i in range(_chaos.log_errors):
            lines.append(f"{ts} ERROR [app] Unhandled exception in request handler (chaos #{i+1})")
            lines.append(f"{ts} FATAL [db] Connection refused: max retries exceeded (chaos #{i+1})")

        # Inject warnings
        for i in range(_chaos.log_warnings):
            lines.append(f"{ts} WARN  [app] Response time exceeded threshold: 3.2s (chaos #{i+1})")
            lines.append(f"{ts} WARN  [cache] Cache miss rate above 50% (chaos #{i+1})")

        _send_json(self, 200, {
            "lines": lines,
            "total_errors": _chaos.log_errors * 2,
            "total_warnings": _chaos.log_warnings * 2,
        })

    def _handle_chaos_update(self) -> None:
        body = _read_body(self)
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            _send_json(self, 400, {"error": "invalid JSON"})
            return

        _chaos.update(**data)
        _send_json(self, 200, {"status": "updated", "state": _chaos.get()})


def create_server(port: int = 0) -> HTTPServer:
    """Create a server on the given port (0 = auto-assign)."""
    global _chaos
    _chaos = ChaosState()
    server = HTTPServer(("127.0.0.1", port), FakeAppHandler)
    return server


def run_server(port: int = 0) -> None:
    """Run the server, printing READY:<port> when listening."""
    server = create_server(port)
    actual_port = server.server_address[1]
    # Signal to parent process that we're ready
    print(f"READY:{actual_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fake app for SDK testing")
    parser.add_argument("--port", type=int, default=0, help="Port (0=auto)")
    args = parser.parse_args()
    run_server(args.port)
