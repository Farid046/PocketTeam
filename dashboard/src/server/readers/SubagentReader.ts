import * as fs from "fs";
import * as path from "path";
import { AgentState, SubagentMeta } from "./types.js";
import { inferRole } from "../roleMap.js";

// Real on-disk structure (confirmed from live data):
//   <projectDir>/<sessionId>/subagents/agent-<id>.meta.json
//   <projectDir>/<sessionId>/subagents/agent-<id>.jsonl
//
// acompact-* files are memory-compaction artefacts — skip them.
// Entries without a .meta.json are skipped.

const ACTIVITY_TIMEOUT_MS = parseInt(
  process.env["ACTIVITY_TIMEOUT_MS"] ?? "300000",
  10
);

interface ParsedJsonlStats {
  startedAt: string;
  lastActivity: string;
  toolCallCount: number;
  messageCount: number;
  isDone: boolean;
  mtimeMs: number;
}

export class SubagentReader {
  private projectDir: string;

  constructor(projectDir: string) {
    this.projectDir = projectDir;
  }

  // Read all agents across all sessions under projectDir
  readAll(): AgentState[] {
    if (!fs.existsSync(this.projectDir)) return [];

    const agents: AgentState[] = [];
    let sessionDirs: string[] = [];

    try {
      sessionDirs = fs
        .readdirSync(this.projectDir, { withFileTypes: true })
        .filter((d) => d.isDirectory() && !d.name.startsWith("."))
        .map((d) => path.join(this.projectDir, d.name));
    } catch {
      return [];
    }

    for (const sessionDir of sessionDirs) {
      const sessionId = path.basename(sessionDir);
      const subagentsDir = path.join(sessionDir, "subagents");

      if (!fs.existsSync(subagentsDir)) continue;

      // Check parent session JSONL mtime — this file is written to actively by
      // the running Claude Code session, even when no subagent files change.
      // Path: <projectDir>/<sessionId>.jsonl  (sibling to the session directory)
      const parentJsonlPath = path.join(this.projectDir, `${sessionId}.jsonl`);
      let parentMtimeMs = 0;
      try {
        parentMtimeMs = fs.statSync(parentJsonlPath).mtimeMs;
      } catch {
        // Parent JSONL may not exist for very old sessions
      }
      const now = Date.now();
      const sessionActive = parentMtimeMs > now - ACTIVITY_TIMEOUT_MS;

      let files: string[] = [];
      try {
        files = fs.readdirSync(subagentsDir);
      } catch {
        continue;
      }

      // Collect all agent IDs that have a .meta.json (no meta = skip)
      const metaFiles = files.filter(
        (f) => f.startsWith("agent-") && f.endsWith(".meta.json")
      );

      for (const metaFile of metaFiles) {
        // agent-<id>.meta.json  →  agentId = <id>
        const agentId = metaFile.slice("agent-".length, -".meta.json".length);

        // Skip acompact entries
        if (agentId.startsWith("acompact")) continue;

        const metaPath = path.join(subagentsDir, metaFile);
        const jsonlPath = path.join(subagentsDir, `agent-${agentId}.jsonl`);

        const meta = this.readMeta(metaPath);
        if (!meta) continue;

        let mtimeMs = 0;
        try {
          mtimeMs = fs.statSync(jsonlPath).mtimeMs;
        } catch {
          // File missing or inaccessible
        }

        const stats = this.parseJsonl(jsonlPath, mtimeMs);
        const roleInfo = inferRole(meta.description);

        const isRecentlyWritten = mtimeMs > now - ACTIVITY_TIMEOUT_MS;
        const isDefinitelyDone = stats.isDone; // stop_reason === "end_turn"

        let status: AgentState["status"] = "idle";
        if (stats.messageCount === 0) {
          status = "idle";
        } else if (isDefinitelyDone || !isRecentlyWritten) {
          status = "done";
        } else {
          status = "working";
        }

        agents.push({
          id: agentId,
          role: roleInfo.role,
          agentType: meta.agentType,
          description: meta.description,
          status,
          startedAt: stats.startedAt,
          lastActivity: stats.lastActivity,
          toolCallCount: stats.toolCallCount,
          messageCount: stats.messageCount,
          sessionId,
          sessionActive,
        });
      }
    }

    // Sort newest first by startedAt
    agents.sort((a, b) => (b.startedAt > a.startedAt ? 1 : -1));
    return agents;
  }

  private readMeta(metaPath: string): SubagentMeta | null {
    try {
      const raw = fs.readFileSync(metaPath, "utf-8");
      const parsed = JSON.parse(raw);
      if (
        typeof parsed === "object" &&
        parsed !== null &&
        typeof parsed.agentType === "string" &&
        typeof parsed.description === "string"
      ) {
        return parsed as SubagentMeta;
      }
      return null;
    } catch {
      return null;
    }
  }

  private parseJsonl(jsonlPath: string, mtimeMs = 0): ParsedJsonlStats {
    const defaultStats: ParsedJsonlStats = {
      startedAt: new Date(0).toISOString(),
      lastActivity: new Date(0).toISOString(),
      toolCallCount: 0,
      messageCount: 0,
      isDone: false,
      mtimeMs,
    };

    if (!fs.existsSync(jsonlPath)) return defaultStats;

    let startedAt: string | null = null;
    let lastActivity: string | null = null;
    let toolCallCount = 0;
    let messageCount = 0;
    let isDone = false;

    let raw: string;
    try {
      raw = fs.readFileSync(jsonlPath, "utf-8");
    } catch {
      return defaultStats;
    }

    const lines = raw.split("\n").filter((l) => l.trim().length > 0);

    for (const line of lines) {
      let entry: Record<string, unknown>;
      try {
        entry = JSON.parse(line) as Record<string, unknown>;
      } catch {
        continue;
      }

      const ts = entry["timestamp"] as string | undefined;
      if (ts) {
        if (!startedAt || ts < startedAt) startedAt = ts;
        if (!lastActivity || ts > lastActivity) lastActivity = ts;
      }

      messageCount++;

      const type = entry["type"] as string | undefined;

      if (type === "assistant") {
        const message = entry["message"] as Record<string, unknown> | undefined;
        if (message) {
          const content = message["content"];
          if (Array.isArray(content)) {
            for (const item of content) {
              if (
                typeof item === "object" &&
                item !== null &&
                (item as Record<string, unknown>)["type"] === "tool_use"
              ) {
                toolCallCount++;
              }
            }
          }
          // Agent is done when the last assistant message has stop_reason = "end_turn"
          const stopReason = message["stop_reason"] as string | undefined;
          if (stopReason === "end_turn") {
            isDone = true;
          } else if (stopReason === "tool_use") {
            // Still invoking tools — mark as working (not done)
            isDone = false;
          }
        }
      }
    }

    return {
      startedAt: startedAt ?? new Date(0).toISOString(),
      lastActivity: lastActivity ?? new Date(0).toISOString(),
      toolCallCount,
      messageCount,
      isDone,
      mtimeMs,
    };
  }
}
