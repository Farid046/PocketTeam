import * as fs from "fs";
import * as path from "path";
import { AuditEntry, AuditStats } from "./types.js";
import { TailReader } from "../watcher/TailReader.js";

// Reads .pocketteam/artifacts/audit/<date>.jsonl and CRITICAL_ALERTS.jsonl
//
// Real entry format (from live data):
// {"ts":"...","agent":"engineer","tool":"Bash","input_hash":"sha256:...","decision":"DENIED_NEVER_ALLOW","layer":1,"reason":"..."}
// CRITICAL_ALERTS.jsonl adds: {"alert":true, ...}

export class AuditLogReader {
  private auditDir: string;
  private entries: AuditEntry[] = [];
  private criticalAlerts: AuditEntry[] = [];
  private onNew: (entry: AuditEntry) => void;
  private tailReader: TailReader | null = null;
  private criticalTailReader: TailReader | null = null;

  constructor(
    pocketteamDir: string,
    onNew: (entry: AuditEntry) => void = () => {}
  ) {
    this.auditDir = path.join(pocketteamDir, "artifacts", "audit");
    this.onNew = onNew;
  }

  // Build today's log file path: 2026-03-25.jsonl
  getTodayPath(): string {
    const today = new Date().toISOString().slice(0, 10); // YYYY-MM-DD
    return path.join(this.auditDir, `${today}.jsonl`);
  }

  getCriticalAlertsPath(): string {
    return path.join(this.auditDir, "CRITICAL_ALERTS.jsonl");
  }

  // Load today's audit log (last 2000 entries) + all critical alerts.
  // Returns initial stats.
  loadInitial(n: number = 2000): AuditStats {
    this.entries = [];
    this.criticalAlerts = [];

    const todayPath = this.getTodayPath();
    this.tailReader = new TailReader(
      todayPath,
      (raw) => this.handleEntry(raw, false),
      (msg) => console.warn("[AuditLogReader]", msg)
    );
    this.tailReader.readLastLines(n);

    const criticalPath = this.getCriticalAlertsPath();
    this.criticalTailReader = new TailReader(
      criticalPath,
      (raw) => this.handleEntry(raw, true),
      (msg) => console.warn("[AuditLogReader:critical]", msg)
    );
    this.criticalTailReader.readLastLines(500);

    return this.computeStats();
  }

  // Call when file-watcher fires a change for today's audit log
  onFileChange(filePath: string): void {
    const isCritical = path.resolve(filePath) === path.resolve(this.getCriticalAlertsPath());
    if (isCritical) {
      this.criticalTailReader?.readNew();
    } else {
      // Any other .jsonl in the audit dir (covers today's file)
      this.tailReader?.readNew();
    }
  }

  getEntries(): AuditEntry[] {
    return [...this.entries];
  }

  getCriticalAlerts(): AuditEntry[] {
    return [...this.criticalAlerts];
  }

  computeStats(): AuditStats {
    const allEntries = [...this.entries, ...this.criticalAlerts];

    const stats: AuditStats = {
      total: allEntries.length,
      allowed: 0,
      denied: 0,
      byLayer: {},
      byTool: {},
    };

    for (const e of allEntries) {
      const isAllowed = e.decision.startsWith("ALLOWED") || e.decision === "allowed";
      if (isAllowed) {
        stats.allowed++;
      } else {
        stats.denied++;
      }

      // byLayer — layer can be null for entries without it
      if (e.layer !== null && e.layer !== undefined) {
        if (!stats.byLayer[e.layer]) {
          stats.byLayer[e.layer] = { allowed: 0, denied: 0 };
        }
        if (isAllowed) {
          stats.byLayer[e.layer].allowed++;
        } else {
          stats.byLayer[e.layer].denied++;
        }
      }

      // byTool
      if (e.tool) {
        if (!stats.byTool[e.tool]) {
          stats.byTool[e.tool] = { allowed: 0, denied: 0 };
        }
        if (isAllowed) {
          stats.byTool[e.tool].allowed++;
        } else {
          stats.byTool[e.tool].denied++;
        }
      }
    }

    return stats;
  }

  // Returns which paths this reader wants to watch
  getWatchPaths(): string[] {
    const paths: string[] = [];
    const todayPath = this.getTodayPath();
    const criticalPath = this.getCriticalAlertsPath();
    if (fs.existsSync(this.auditDir)) {
      paths.push(todayPath, criticalPath);
    }
    return paths;
  }

  private handleEntry(raw: unknown, isCritical: boolean): void {
    if (typeof raw !== "object" || raw === null) return;

    const e = raw as Record<string, unknown>;

    const entry: AuditEntry = {
      ts: typeof e["ts"] === "string" ? e["ts"] : "",
      event: typeof e["event"] === "string" ? e["event"] : "",
      agent: typeof e["agent"] === "string" ? e["agent"] : "unknown",
      tool: typeof e["tool"] === "string" ? e["tool"] : "",
      input_hash: typeof e["input_hash"] === "string" ? e["input_hash"] : "",
      decision: typeof e["decision"] === "string" ? e["decision"] : "",
      layer:
        typeof e["layer"] === "number"
          ? e["layer"]
          : e["layer"] === null
          ? null
          : null,
      reason: typeof e["reason"] === "string" ? e["reason"] : "",
    };

    if (isCritical) {
      this.criticalAlerts.push(entry);
      if (this.criticalAlerts.length > 500) {
        this.criticalAlerts.shift();
      }
    } else {
      this.entries.push(entry);
      if (this.entries.length > 2000) {
        this.entries.shift();
      }
    }

    this.onNew(entry);
  }
}
