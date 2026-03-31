---
name: pocketteam-help
description: "Show all PocketTeam workflow modes and commands at a glance."
---

# /pocketteam-help — Quick Reference

Display the following overview exactly as formatted below.

---

**PocketTeam Workflow Modes**

| Mode | Command | Behavior |
|---|---|---|
| **Autopilot** | `autopilot: Task` | Full pipeline with no human gates (CEO pre-approved) |
| **Ralph** | `ralph: Task` | Implement → Test loop, keeps going until all tests pass (max 5 iterations) |
| **Quick** | `quick: Task` | Skip planning/review, implement directly, quick test |
| **Deep-Dive** | `deep-dive: Topic` | Spawn 3 parallel research agents for thorough analysis |
| **Standard** | *(just type your task)* | Full pipeline: Plan → Review → Approve → Implement → Test → Security → Docs |

---

**Quick Reference:**
- `pocketteam start` — resume last session with COO agent
- `pocketteam start new` — fresh session with COO agent
- `pocketteam kill` — emergency stop
- `pocketteam resume` — clear kill switch
- `pocketteam status` — show project status
- `pocketteam health` — system health check
- `pocketteam logs -f` — follow event stream

---

**Telegram:** Messages arrive via channel plugin. Use CLI for time-critical commands.

---

**Computer Use** *(opt-in)*

| Mode | How to activate |
|---|---|
| Browser MCP | Installed at init. Always available to agents via MCP tool. |
| Native macOS | Run `/mcp` in a Claude Code session. Requires Accessibility permissions. |

- Browser MCP: `claude mcp add --scope project computer-use -- npx -y @anthropic-ai/claude-code-computer-use`
- Native: System Settings → Privacy & Security → Accessibility → Claude Code ✓
- Not installed with `--yes` — must be explicitly opted in.
