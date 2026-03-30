#!/usr/bin/env python3
"""
MCP Telegram Proxy Server for PocketTeam (DEPRECATED).

This file is no longer used. Telegram is handled entirely by
the official channel plugin (--channels plugin:telegram@claude-plugins-official).

The MCP proxy has been removed because:
- It conflicted with the channel plugin (409 Conflict on getUpdates)
- /kill interception via MCP was unreliable during active sessions
- The channel plugin handles both sending and receiving

Kept for reference only. Remove this file in a future cleanup.
"""
