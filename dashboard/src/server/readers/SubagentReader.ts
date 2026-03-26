import * as fs from "fs";
import * as path from "path";
import { AgentState, SubagentMeta, TokenUsage, CooActivity } from "./types.js";
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
  tokenUsage: TokenUsage;
  model: string;
  gitBranch: string;
}

/**
 * Extract and accumulate token usage from an assistant message's usage object.
 * Mutates the provided tokenUsage accumulator in place.
 */
function parseTokenUsage(
  usage: Record<string, unknown> | undefined,
  accumulator: TokenUsage
): void {
  if (!usage) return;
  accumulator.inputTokens += (usage["input_tokens"] as number) ?? 0;
  accumulator.outputTokens += (usage["output_tokens"] as number) ?? 0;
  accumulator.cacheCreationTokens += (usage["cache_creation_input_tokens"] as number) ?? 0;
  accumulator.cacheReadTokens += (usage["cache_read_input_tokens"] as number) ?? 0;
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
        const roleInfo = inferRole(meta.description, meta.agentType);

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
          tokenUsage: stats.tokenUsage,
          model: stats.model,
          gitBranch: stats.gitBranch,
        });
      }
    }

    // Sort newest first by startedAt
    agents.sort((a, b) => (b.startedAt > a.startedAt ? 1 : -1));
    return agents;
  }

  /** Read the tail of the main session JSONL to get COO's real-time activity */
  readCooActivity(sessionId: string): CooActivity | null {
    const parentJsonlPath = path.join(this.projectDir, `${sessionId}.jsonl`);
    let mtimeMs = 0;
    let fileSize = 0;
    try {
      const stat = fs.statSync(parentJsonlPath);
      mtimeMs = stat.mtimeMs;
      fileSize = stat.size;
    } catch {
      return null;
    }

    const now = Date.now();
    const isActive = mtimeMs > now - 60_000; // 60s threshold for COO

    // Read last ~32KB to find recent tool calls
    const readSize = Math.min(fileSize, 32768);
    let tail = "";
    try {
      const fd = fs.openSync(parentJsonlPath, "r");
      const buf = Buffer.alloc(readSize);
      fs.readSync(fd, buf, 0, readSize, Math.max(0, fileSize - readSize));
      fs.closeSync(fd);
      tail = buf.toString("utf-8");
    } catch {
      return null;
    }

    const lines = tail.split("\n").filter((l) => l.trim().length > 0);

    let lastToolCall = "";
    let lastActivity = "";
    let model = "";
    let gitBranch = "";
    let toolCallCount = 0;
    let messageCount = 0;
    const tokenUsage: TokenUsage = { inputTokens: 0, outputTokens: 0, cacheCreationTokens: 0, cacheReadTokens: 0 };

    for (const line of lines) {
      let entry: Record<string, unknown>;
      try {
        entry = JSON.parse(line) as Record<string, unknown>;
      } catch {
        continue;
      }

      const ts = entry["timestamp"] as string | undefined;
      if (ts && (!lastActivity || ts > lastActivity)) lastActivity = ts;
      if (!gitBranch && typeof entry["gitBranch"] === "string") {
        gitBranch = entry["gitBranch"] as string;
      }

      messageCount++;
      const type = entry["type"] as string | undefined;

      if (type === "assistant") {
        const message = entry["message"] as Record<string, unknown> | undefined;
        if (!message) continue;

        if (typeof message["model"] === "string") model = message["model"] as string;

        parseTokenUsage(message["usage"] as Record<string, unknown> | undefined, tokenUsage);

        const content = message["content"];
        if (Array.isArray(content)) {
          for (const item of content) {
            if (typeof item === "object" && item !== null && (item as Record<string, unknown>)["type"] === "tool_use") {
              toolCallCount++;
              const toolName = (item as Record<string, unknown>)["name"] as string ?? "";
              const input = (item as Record<string, unknown>)["input"] as Record<string, unknown> | undefined;

              // Build a readable description of the tool call
              let target = "";
              if (input) {
                if (typeof input["file_path"] === "string") {
                  target = (input["file_path"] as string).split("/").pop() ?? "";
                } else if (typeof input["command"] === "string") {
                  target = (input["command"] as string).slice(0, 60);
                } else if (typeof input["pattern"] === "string") {
                  target = (input["pattern"] as string);
                } else if (typeof input["prompt"] === "string") {
                  target = (input["prompt"] as string).slice(0, 50);
                } else if (typeof input["description"] === "string") {
                  target = (input["description"] as string).slice(0, 50);
                }
              }
              lastToolCall = target ? `${toolName}: ${target}` : toolName;
            }
          }
        }
      }
    }

    return {
      sessionId,
      lastToolCall: lastToolCall || "Idle",
      lastActivity: lastActivity || new Date(0).toISOString(),
      isActive,
      model,
      tokenUsage,
      toolCallCount,
      messageCount,
      gitBranch,
    };
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
    const zeroTokens: TokenUsage = { inputTokens: 0, outputTokens: 0, cacheCreationTokens: 0, cacheReadTokens: 0 };
    const defaultStats: ParsedJsonlStats = {
      startedAt: new Date(0).toISOString(),
      lastActivity: new Date(0).toISOString(),
      toolCallCount: 0,
      messageCount: 0,
      isDone: false,
      mtimeMs,
      tokenUsage: { ...zeroTokens },
      model: "",
      gitBranch: "",
    };

    let startedAt: string | null = null;
    let lastActivity: string | null = null;
    let toolCallCount = 0;
    let messageCount = 0;
    let isDone = false;
    const tokenUsage: TokenUsage = { ...zeroTokens };
    let model = "";
    let gitBranch = "";

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

      // Extract gitBranch from first entry that has it
      if (!gitBranch && typeof entry["gitBranch"] === "string") {
        gitBranch = entry["gitBranch"] as string;
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

          // Extract token usage
          parseTokenUsage(message["usage"] as Record<string, unknown> | undefined, tokenUsage);

          // Track most recent model
          if (typeof message["model"] === "string") {
            model = message["model"] as string;
          }

          // Agent is done when the last assistant message has stop_reason = "end_turn"
          const stopReason = message["stop_reason"] as string | undefined;
          if (stopReason === "end_turn") {
            isDone = true;
          } else if (stopReason === "tool_use") {
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
      tokenUsage,
      model,
      gitBranch,
    };
  }
}
