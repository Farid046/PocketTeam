#!/usr/bin/env node
/**
 * PocketTeam Statusline for Claude Code
 *
 * Two-line HUD inspired by claude-hud:
 *   Line 1: [Model] ██████ ctx% | $cost | +lines/-lines | ⏱ duration | ⚡ rate%
 *   Line 2: 🏢 PocketTeam | agent info | session details
 *
 * Also writes data to .pocketteam/session-status.json for the dashboard.
 */

const fs = require("fs");
const path = require("path");
const readline = require("readline");

// ── Helpers ─────────────────────────────────────────────────────────────────

function findPocketteamDir() {
  let dir = process.cwd();
  for (let i = 0; i < 20; i++) {
    const candidate = path.join(dir, ".pocketteam");
    if (fs.existsSync(candidate)) return candidate;
    const parent = path.dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  return null;
}

function formatDuration(ms) {
  if (ms == null || ms <= 0) return null;
  const totalSec = Math.floor(ms / 1000);
  if (totalSec < 60) return `${totalSec}s`;
  const min = Math.floor(totalSec / 60);
  if (min < 60) return `${min}m`;
  const hr = Math.floor(min / 60);
  const remMin = min % 60;
  return remMin > 0 ? `${hr}h${remMin}m` : `${hr}h`;
}

function makeBar(pct, width) {
  if (pct == null) return "░".repeat(width);
  const filled = Math.round((pct / 100) * width);
  const empty = width - filled;
  let color = "\x1b[32m"; // green
  if (pct > 70) color = "\x1b[33m"; // yellow
  if (pct > 90) color = "\x1b[31m"; // red
  return color + "█".repeat(filled) + "\x1b[90m" + "░".repeat(empty) + "\x1b[0m";
}

function countActiveAgents(ptDir) {
  try {
    const eventsPath = path.join(ptDir, "events", "stream.jsonl");
    if (!fs.existsSync(eventsPath)) return { active: 0, total: 0 };
    // Read last 8KB for recent events
    const stat = fs.statSync(eventsPath);
    const readSize = Math.min(stat.size, 8192);
    const buf = Buffer.alloc(readSize);
    const fd = fs.openSync(eventsPath, "r");
    fs.readSync(fd, buf, 0, readSize, Math.max(0, stat.size - readSize));
    fs.closeSync(fd);
    const lines = buf.toString("utf8").split("\n").filter(Boolean);
    const agents = new Map();
    for (const l of lines) {
      try {
        const e = JSON.parse(l);
        if (e.agent && e.type) {
          if (e.type === "agent_start") agents.set(e.agent, "active");
          else if (e.type === "agent_stop") agents.set(e.agent, "done");
        }
      } catch {}
    }
    let active = 0, total = 0;
    for (const [, status] of agents) {
      total++;
      if (status === "active") active++;
    }
    return { active, total };
  } catch {
    return { active: 0, total: 0 };
  }
}

// ── Main ────────────────────────────────────────────────────────────────────

const ptDir = findPocketteamDir();
const outputPath = ptDir ? path.join(ptDir, "session-status.json") : null;

const rl = readline.createInterface({ input: process.stdin });

rl.on("line", (rawLine) => {
  let data;
  try {
    data = JSON.parse(rawLine);
  } catch {
    return;
  }

  const ctx = data.context_window || {};
  const rate = data.rate_limits || {};
  const cost = data.cost || {};
  const model = data.model || {};
  const agent = data.agent || {};

  // ── Write dashboard JSON ────────────────────────────────────────────────
  const status = {
    contextUsedPct: ctx.used_percentage ?? null,
    contextRemainingPct: ctx.remaining_percentage ?? null,
    contextWindowSize: ctx.context_window_size ?? null,
    rateLimits: {
      fiveHour: rate.five_hour?.used_percentage ?? null,
      fiveHourResetAt: rate.five_hour?.resets_at ?? rate.five_hour?.reset_at ?? null,
      sevenDay: rate.seven_day?.used_percentage ?? null,
      sevenDayResetAt: rate.seven_day?.resets_at ?? rate.seven_day?.reset_at ?? null,
    },
    cost: cost.total_cost_usd ?? null,
    linesAdded: cost.total_lines_added ?? null,
    linesRemoved: cost.total_lines_removed ?? null,
    durationMs: cost.total_duration_ms ?? null,
    model: model.display_name ?? model.id ?? null,
    modelId: model.id ?? null,
    sessionId: data.session_id ?? null,
    agentName: agent.name ?? null,
    version: data.version ?? null,
    updatedAt: new Date().toISOString(),
  };

  if (outputPath) {
    try {
      fs.writeFileSync(outputPath, JSON.stringify(status, null, 2));
    } catch {}
  }

  // ── Build terminal statusline ───────────────────────────────────────────
  const ctxPct = status.contextUsedPct;
  const ctxSize = status.contextWindowSize;
  const ctxLabel = ctxSize ? `${Math.round(ctxSize / 1000)}k` : "";

  // Line 1: [Model] ██████ ctx% | $cost | +lines/-lines | ⏱ duration
  const modelTag = `\x1b[36m[${status.model || "?"}]\x1b[0m`;
  const bar = makeBar(ctxPct, 12);
  const pctStr = ctxPct != null ? `${Math.round(ctxPct)}%` : "?";
  const ctxInfo = ctxLabel ? `${pctStr} of ${ctxLabel}` : pctStr;
  const costStr = status.cost != null ? `\x1b[33m$${status.cost.toFixed(2)}\x1b[0m` : "";
  const dur = formatDuration(status.durationMs);
  const durStr = dur ? `⏱ ${dur}` : "";

  const linesStr = (status.linesAdded != null || status.linesRemoved != null)
    ? `\x1b[32m+${status.linesAdded || 0}\x1b[0m/\x1b[31m-${status.linesRemoved || 0}\x1b[0m`
    : "";

  const rateVal = status.rateLimits.fiveHour;
  let rateStr = "";
  if (rateVal != null) {
    const resetAt = status.rateLimits.fiveHourResetAt;
    let resetInfo = "";
    if (resetAt) {
      const resetMs = (typeof resetAt === "number" && resetAt < 1e12) ? resetAt * 1000 : resetAt;
      const diffMin = Math.max(0, Math.round((resetMs - Date.now()) / 60000));
      if (diffMin < 60) resetInfo = ` ↻${diffMin}m`;
      else resetInfo = ` ↻${Math.floor(diffMin / 60)}h${diffMin % 60}m`;
    }
    rateStr = `⚡${Math.round(rateVal)}%${resetInfo}`;
  }

  const line1Parts = [modelTag, `${bar} ${ctxInfo}`, costStr, linesStr, durStr, rateStr].filter(Boolean);
  const line1 = line1Parts.join(" \x1b[90m|\x1b[0m ");

  // Line 2: 🏢 PocketTeam | agent info | session
  let line2Parts = ["🏢 \x1b[1mPocketTeam\x1b[0m"];

  if (status.agentName) {
    line2Parts.push(`🤖 ${status.agentName}`);
  }

  if (ptDir) {
    const { active, total } = countActiveAgents(ptDir);
    if (total > 0) {
      line2Parts.push(active > 0 ? `⚙ ${active} agents active` : `✓ ${total} agents done`);
    }
  }

  const line2 = line2Parts.join(" \x1b[90m|\x1b[0m ");

  process.stdout.write(line1 + "\n" + line2 + "\n");
});
