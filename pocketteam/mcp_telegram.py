#!/usr/bin/env python3
"""
MCP Telegram Proxy Server for PocketTeam.

Replaces the official Telegram plugin with kill-switch interception.
Polls Bot API directly, intercepts /kill BEFORE Claude sees it,
forwards all other messages as Channel-XML.

Usage (registered via claude mcp add):
    python3 pocketteam/mcp_telegram.py

MCP Tools exposed to Claude:
    reply              — Send message to Telegram chat
    react              — Add emoji reaction
    edit_message       — Edit a sent message
    download_attachment — Download file from Telegram
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

logger = logging.getLogger("pocketteam.mcp_telegram")

# ─────────────────────────────────────────────────────────────────────────────
# Config loaders (reuse paths from Telegram plugin)
# ─────────────────────────────────────────────────────────────────────────────

CHANNEL_DIR = Path.home() / ".claude" / "channels" / "telegram"


def load_bot_token() -> str:
    env_file = CHANNEL_DIR / ".env"
    if not env_file.exists():
        return ""
    for line in env_file.read_text().splitlines():
        if line.startswith("TELEGRAM_BOT_TOKEN="):
            return line.split("=", 1)[1].strip().strip("\"'")
    return ""


def load_allowed_users() -> list[str]:
    access_file = CHANNEL_DIR / "access.json"
    try:
        data = json.loads(access_file.read_text())
        return data.get("allowFrom", [])
    except Exception:
        return []


def find_project_root() -> Path:
    env_root = os.environ.get("POCKETTEAM_PROJECT_ROOT")
    if env_root:
        return Path(env_root)
    d = Path.cwd()
    for _ in range(20):
        if (d / ".pocketteam").is_dir():
            return d
        parent = d.parent
        if parent == d:
            break
        d = parent
    return Path.cwd()


# ─────────────────────────────────────────────────────────────────────────────
# Telegram Proxy Core
# ─────────────────────────────────────────────────────────────────────────────

KILL_COMMANDS = frozenset({"/kill", "/stop", "kill", "stop"})


class TelegramProxy:
    def __init__(self, token: str, allowed_users: list[str], project_root: Path):
        self.token = token
        self.allowed_users = list(allowed_users)
        self.project_root = project_root
        self.api_base = f"https://api.telegram.org/bot{token}"
        self.kill_file = project_root / ".pocketteam" / "KILL"
        self.offset = 0
        self._queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=100)
        self._http: httpx.AsyncClient | None = None

    # ── Polling ──────────────────────────────────────────────────────────

    async def poll_loop(self) -> None:
        """Background task: long-poll Telegram Bot API."""
        async with httpx.AsyncClient(timeout=httpx.Timeout(35.0, connect=10.0)) as client:
            self._http = client
            while True:
                try:
                    resp = await client.get(
                        f"{self.api_base}/getUpdates",
                        params={
                            "offset": self.offset,
                            "timeout": 25,
                            "allowed_updates": '["message"]',
                        },
                    )
                    if resp.status_code == 409:
                        logger.debug("409 Conflict — another consumer active")
                        await asyncio.sleep(10)
                        continue

                    resp.raise_for_status()
                    data = resp.json()

                    for update in data.get("result", []):
                        self.offset = update["update_id"] + 1
                        await self._handle_update(update)

                except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout):
                    await asyncio.sleep(5)
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 409:
                        await asyncio.sleep(10)
                    else:
                        logger.error("HTTP error: %s", e)
                        await asyncio.sleep(5)
                except Exception:
                    logger.exception("Poll loop error")
                    await asyncio.sleep(10)

    async def _handle_update(self, update: dict) -> None:
        msg = update.get("message", {})
        text = (msg.get("text") or "").strip()
        user_id = str(msg.get("from", {}).get("id", ""))
        chat_id = str(msg.get("chat", {}).get("id", ""))
        message_id = str(msg.get("message_id", ""))
        ts = msg.get("date", 0)

        if not user_id:
            return

        # ── KILL SWITCH — checked FIRST, before access control ──
        # Even unauthorized users can't abuse this because kill only
        # activates for allowed users. But kill is checked before
        # dmPolicy so that "disabled" policy doesn't prevent kill.
        if text.lower() in KILL_COMMANDS and self._is_allowed(user_id):
            self.kill_file.parent.mkdir(parents=True, exist_ok=True)
            self.kill_file.touch()
            logger.warning("KILL SWITCH activated via Telegram by user %s", user_id)
            await self._api_send_message(
                chat_id,
                "🛑 Kill switch activated. All agents stopped.\n"
                "Run `pocketteam resume` to re-enable.",
            )
            return

        # ── Access control ──
        self._reload_access()
        if not self._is_allowed(user_id):
            logger.debug("Dropped message from unauthorized user %s", user_id)
            return

        # ── Kill active — don't forward anything ──
        if self.kill_file.exists():
            logger.debug("Kill switch active, dropping message")
            return

        # ── Extract attachment info ──
        image_path = ""
        attachment_file_id = ""

        if msg.get("photo"):
            # Largest photo
            photo = msg["photo"][-1]
            file_id = photo["file_id"]
            downloaded = await self._download_file(file_id)
            if downloaded:
                image_path = downloaded

        if msg.get("document"):
            attachment_file_id = msg["document"]["file_id"]

        # ── Queue for Claude ──
        entry = {
            "chat_id": chat_id,
            "message_id": message_id,
            "user": user_id,
            "user_id": user_id,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(ts)) if ts else "",
            "text": text,
            "image_path": image_path,
            "attachment_file_id": attachment_file_id,
        }

        try:
            self._queue.put_nowait(entry)
        except asyncio.QueueFull:
            logger.warning("Message queue full, dropping oldest")
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            self._queue.put_nowait(entry)

    def _is_allowed(self, user_id: str) -> bool:
        return user_id in self.allowed_users

    def _reload_access(self) -> None:
        try:
            data = json.loads((CHANNEL_DIR / "access.json").read_text())
            self.allowed_users = data.get("allowFrom", [])
        except Exception:
            pass

    # ── Telegram API helpers ─────────────────────────────────────────────

    async def _api_send_message(
        self, chat_id: str, text: str, reply_to: str | None = None,
        parse_mode: str | None = None,
    ) -> dict:
        if not self._http:
            return {"error": "HTTP client not initialized"}
        body: dict[str, Any] = {"chat_id": chat_id, "text": text[:4096]}
        if reply_to:
            body["reply_to_message_id"] = int(reply_to)
        if parse_mode:
            body["parse_mode"] = parse_mode
        try:
            resp = await self._http.post(f"{self.api_base}/sendMessage", json=body)
            data = resp.json()
            if data.get("ok"):
                return {"message_id": str(data["result"]["message_id"])}
            return {"error": data.get("description", "unknown error")}
        except Exception as e:
            return {"error": str(e)}

    async def _api_send_document(
        self, chat_id: str, file_path: str, caption: str = "",
    ) -> dict:
        if not self._http:
            return {"error": "HTTP client not initialized"}
        try:
            with open(file_path, "rb") as f:
                resp = await self._http.post(
                    f"{self.api_base}/sendDocument",
                    data={"chat_id": chat_id, "caption": caption[:1024]},
                    files={"document": (Path(file_path).name, f)},
                )
            data = resp.json()
            if data.get("ok"):
                return {"message_id": str(data["result"]["message_id"])}
            return {"error": data.get("description", "unknown")}
        except Exception as e:
            return {"error": str(e)}

    async def _download_file(self, file_id: str) -> str:
        """Download a Telegram file to the inbox directory."""
        if not self._http:
            return ""
        try:
            resp = await self._http.get(
                f"{self.api_base}/getFile", params={"file_id": file_id}
            )
            data = resp.json()
            if not data.get("ok"):
                return ""
            file_path = data["result"]["file_path"]
            file_url = f"https://api.telegram.org/file/bot{self.token}/{file_path}"

            inbox_dir = CHANNEL_DIR / "inbox"
            inbox_dir.mkdir(parents=True, exist_ok=True)
            local_name = f"{int(time.time() * 1000)}-{Path(file_path).name}"
            local_path = inbox_dir / local_name

            file_resp = await self._http.get(file_url)
            local_path.write_bytes(file_resp.content)
            return str(local_path)
        except Exception:
            logger.debug("File download failed", exc_info=True)
            return ""

    # ── MCP Tool: get pending messages ───────────────────────────────────

    def drain_messages(self) -> list[dict]:
        """Drain all pending messages from the queue."""
        messages = []
        while not self._queue.empty():
            try:
                messages.append(self._queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        return messages

    def format_channel_xml(self, msg: dict) -> str:
        """Format a message as Channel XML (same format as the official plugin)."""
        attrs = [
            f'source="plugin:telegram:telegram"',
            f'chat_id="{msg["chat_id"]}"',
            f'message_id="{msg["message_id"]}"',
            f'user="{msg["user"]}"',
            f'user_id="{msg["user_id"]}"',
            f'ts="{msg["ts"]}"',
        ]
        if msg.get("image_path"):
            attrs.append(f'image_path="{msg["image_path"]}"')
        if msg.get("attachment_file_id"):
            attrs.append(f'attachment_file_id="{msg["attachment_file_id"]}"')

        attr_str = " ".join(attrs)
        return f'<channel {attr_str}>\n{msg["text"]}\n</channel>'


# ─────────────────────────────────────────────────────────────────────────────
# MCP Server Setup
# ─────────────────────────────────────────────────────────────────────────────

def create_server(proxy: TelegramProxy) -> Server:
    server = Server("pocketteam-telegram")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="reply",
                description=(
                    "Reply on Telegram. Pass chat_id from the inbound message. "
                    "Optionally pass reply_to (message_id) for threading, "
                    "and files (absolute paths) to attach."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "chat_id": {"type": "string"},
                        "text": {"type": "string"},
                        "reply_to": {"type": "string", "description": "Message ID to thread under"},
                        "files": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Absolute file paths to attach",
                        },
                        "format": {
                            "type": "string",
                            "enum": ["text", "markdownv2"],
                            "description": "Rendering mode. Default: text",
                        },
                    },
                    "required": ["chat_id", "text"],
                },
            ),
            Tool(
                name="react",
                description="Add an emoji reaction to a Telegram message.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "chat_id": {"type": "string"},
                        "message_id": {"type": "string"},
                        "emoji": {"type": "string"},
                    },
                    "required": ["chat_id", "message_id", "emoji"],
                },
            ),
            Tool(
                name="edit_message",
                description="Edit a previously sent Telegram message.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "chat_id": {"type": "string"},
                        "message_id": {"type": "string"},
                        "text": {"type": "string"},
                    },
                    "required": ["chat_id", "message_id", "text"],
                },
            ),
            Tool(
                name="download_attachment",
                description="Download a Telegram file attachment by file_id.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "file_id": {"type": "string"},
                    },
                    "required": ["file_id"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        if name == "reply":
            chat_id = arguments["chat_id"]
            text = arguments["text"]
            reply_to = arguments.get("reply_to")
            files = arguments.get("files", [])
            fmt = arguments.get("format", "text")
            parse_mode = "MarkdownV2" if fmt == "markdownv2" else None

            # Send text
            result = await proxy._api_send_message(
                chat_id, text, reply_to=reply_to, parse_mode=parse_mode
            )

            # Send files as documents
            for file_path in (files or []):
                if os.path.isfile(file_path):
                    await proxy._api_send_document(chat_id, file_path)

            return [TextContent(type="text", text=f"sent (id: {result.get('message_id', 'error')})")]

        elif name == "react":
            if not proxy._http:
                return [TextContent(type="text", text="error: no HTTP client")]
            try:
                resp = await proxy._http.post(
                    f"{proxy.api_base}/setMessageReaction",
                    json={
                        "chat_id": arguments["chat_id"],
                        "message_id": int(arguments["message_id"]),
                        "reaction": [{"type": "emoji", "emoji": arguments["emoji"]}],
                    },
                )
                return [TextContent(type="text", text="reacted" if resp.json().get("ok") else "failed")]
            except Exception as e:
                return [TextContent(type="text", text=f"error: {e}")]

        elif name == "edit_message":
            if not proxy._http:
                return [TextContent(type="text", text="error: no HTTP client")]
            try:
                resp = await proxy._http.post(
                    f"{proxy.api_base}/editMessageText",
                    json={
                        "chat_id": arguments["chat_id"],
                        "message_id": int(arguments["message_id"]),
                        "text": arguments["text"],
                    },
                )
                return [TextContent(type="text", text="edited" if resp.json().get("ok") else "failed")]
            except Exception as e:
                return [TextContent(type="text", text=f"error: {e}")]

        elif name == "download_attachment":
            path = await proxy._download_file(arguments["file_id"])
            if path:
                return [TextContent(type="text", text=f"downloaded: {path}")]
            return [TextContent(type="text", text="download failed")]

        return [TextContent(type="text", text=f"unknown tool: {name}")]

    return server


# ─────────────────────────────────────────────────────────────────────────────
# Notification delivery: push messages into Claude's context
# ─────────────────────────────────────────────────────────────────────────────

async def notification_loop(proxy: TelegramProxy, server: Server) -> None:
    """Periodically check for new messages and send them as notifications."""
    while True:
        await asyncio.sleep(2)
        messages = proxy.drain_messages()
        if not messages:
            continue

        for msg in messages:
            xml = proxy.format_channel_xml(msg)
            try:
                await server.request_context.session.send_log_message(
                    level="info", data=xml
                )
            except Exception:
                logger.debug("Failed to send notification", exc_info=True)


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

async def main() -> None:
    token = load_bot_token()
    if not token:
        logger.error("No TELEGRAM_BOT_TOKEN found in %s/.env", CHANNEL_DIR)
        return

    allowed = load_allowed_users()
    project_root = find_project_root()

    proxy = TelegramProxy(token, allowed, project_root)
    server = create_server(proxy)

    # Start polling in background
    poll_task = asyncio.create_task(proxy.poll_loop())

    # Run MCP server over stdio
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

    poll_task.cancel()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=open("/tmp/pocketteam-mcp-telegram.log", "a"),
    )
    asyncio.run(main())
