---
name: add-mcp-server
description: "Add an MCP server to the project or global Claude config. Handles installation, configuration, and verification."
---

# /add-mcp-server — Add an MCP Server

Add a new MCP (Model Context Protocol) server to extend Claude Code's capabilities.

## Steps

1. **Identify the MCP server** — name, package, purpose
2. **Determine scope**:
   - **Global** (`~/.claude.json`) — available in all projects
   - **Project** (`.claude/settings.json` or `.mcp.json`) — only this project

3. **Install via Claude CLI**:
```bash
# Global (recommended for general tools)
claude mcp add <name> -- npx -y <package>

# Project-scoped
claude mcp add --project <name> -- npx -y <package>
```

4. **For Python-based MCP servers**:
```bash
claude mcp add <name> -- python -m <module>
```

5. **Verify installation**:
   - Check `~/.claude.json` or `.mcp.json` for the server entry
   - Start a new Claude session — the server should appear in available tools
   - Test a tool call from the server

## Common MCP Servers

| Server | Command | Purpose |
|--------|---------|---------|
| Context7 | `npx -y @upstash/context7-mcp` | Library documentation |
| Supabase | `npx -y @supabase/mcp-server-supabase@latest` | Database management |
| Tavily | `npx -y tavily-mcp` | Web search |
| Kubernetes | `npx -y @anthropic-ai/kubernetes-mcp` | K8s cluster management |

## Troubleshooting

- **Server not loading**: Check `claude mcp list` for status
- **Permission denied**: Ensure the package is installed and executable
- **Timeout**: Some servers need environment variables (API keys) — set them in the MCP config
