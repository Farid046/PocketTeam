/**
 * server.ts — HTTP Daemon
 * Bun HTTP server with Bearer token auth, command routing, and idle timeout.
 */

import { existsSync, writeFileSync, readFileSync, unlinkSync } from "fs";
import { mkdirSync } from "fs";
import { join } from "path";
import { homedir } from "os";
import { BrowserManager } from "./browser.ts";
import {
  cmdGoto,
  cmdBack,
  cmdForward,
  cmdReload,
  cmdSnapshot,
  cmdClick,
  cmdFill,
  cmdType,
  cmdSelect,
  cmdKey,
  cmdHover,
  cmdScroll,
  cmdWaitText,
  cmdWaitSelector,
  cmdWaitIdle,
  cmdWaitUrl,
  cmdAssertText,
  cmdAssertNoText,
  cmdAssertVisible,
  cmdAssertEnabled,
  cmdAssertUrl,
  cmdText,
  cmdScreenshot,
  cmdConsole,
  cmdEvalJs,
  cmdViewport,
  cmdStatus,
  cmdCloseBrowser,
  CommandResult,
} from "./commands.ts";

// ─────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────

const POCKETTEAM_DIR = join(homedir(), ".pocketteam");
const STATE_FILE = join(POCKETTEAM_DIR, "browse.json");
const LOCK_FILE = join(POCKETTEAM_DIR, "browse.lock");
const IDLE_TIMEOUT_MS = 30 * 60 * 1000; // 30 minutes
const PORT_MIN = 10000;
const PORT_MAX = 60000;
const VERSION = "1.0.0";

// ─────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────

function randomPort(): number {
  return Math.floor(Math.random() * (PORT_MAX - PORT_MIN + 1)) + PORT_MIN;
}

function randomToken(): string {
  return crypto.randomUUID();
}

function ensurePocketTeamDir(): void {
  if (!existsSync(POCKETTEAM_DIR)) {
    mkdirSync(POCKETTEAM_DIR, { recursive: true });
  }
}

function checkLockfile(): void {
  if (existsSync(LOCK_FILE)) {
    const existingPid = parseInt(readFileSync(LOCK_FILE, "utf8").trim(), 10);
    if (!isNaN(existingPid)) {
      // Check if that PID is actually alive
      try {
        process.kill(existingPid, 0); // signal 0 = check existence only
        // PID is alive — another daemon is running
        console.error(
          `[server] Another ptbrowse daemon is already running (PID ${existingPid}). ` +
          `Run 'ptbrowse close' to stop it first.`
        );
        process.exit(1);
      } catch {
        // PID is dead — stale lockfile, clean up
        console.log(`[server] Removing stale lockfile for dead PID ${existingPid}`);
        unlinkSync(LOCK_FILE);
        if (existsSync(STATE_FILE)) unlinkSync(STATE_FILE);
      }
    }
  }
}

function writeLockfile(pid: number): void {
  writeFileSync(LOCK_FILE, String(pid), "utf8");
}

function writeStateFile(port: number, token: string): void {
  const state = {
    pid: process.pid,
    port,
    token,
    startedAt: new Date().toISOString(),
    version: VERSION,
  };
  // mode 0o600: owner read/write only — the Bearer token must not be world-readable.
  writeFileSync(STATE_FILE, JSON.stringify(state, null, 2), { encoding: "utf8", mode: 0o600 });
}

function cleanup(): void {
  try {
    if (existsSync(LOCK_FILE)) unlinkSync(LOCK_FILE);
    if (existsSync(STATE_FILE)) unlinkSync(STATE_FILE);
  } catch {
    // Best effort
  }
}

// ─────────────────────────────────────────────
// Main
// ─────────────────────────────────────────────

async function main() {
  ensurePocketTeamDir();
  checkLockfile();

  const port = randomPort();
  const token = randomToken();
  const startedAt = new Date().toISOString();

  // Write lockfile before anything else
  writeLockfile(process.pid);

  // Register cleanup handlers
  process.on("exit", cleanup);
  process.on("SIGINT", () => {
    cleanup();
    process.exit(0);
  });
  process.on("SIGTERM", () => {
    cleanup();
    process.exit(0);
  });

  // Launch Chromium (--headed flag enables visible browser window)
  const isHeaded = process.argv.includes("--headed");
  const browser = new BrowserManager(() => {
    console.error("[server] Chromium disconnected — shutting down");
    cleanup();
    process.exit(1);
  });

  try {
    await browser.launch(isHeaded);
    console.log(`[server] Chromium launched (${isHeaded ? "headed" : "headless"})`);
  } catch (err: any) {
    console.error(`[server] Failed to launch Chromium: ${err.message}`);
    cleanup();
    process.exit(1);
  }

  // Write state file AFTER successful launch
  writeStateFile(port, token);
  console.log(`[server] Listening on port ${port}`);

  // Idle timeout
  let idleTimer: ReturnType<typeof setTimeout> | null = null;

  function resetIdleTimer() {
    if (idleTimer) clearTimeout(idleTimer);
    idleTimer = setTimeout(async () => {
      console.log("[server] Idle timeout — shutting down");
      await browser.close();
      cleanup();
      process.exit(0);
    }, IDLE_TIMEOUT_MS);
  }

  resetIdleTimer();

  // ─────────────────────────────────────────────
  // Command dispatcher
  // ─────────────────────────────────────────────

  async function dispatch(cmd: string, args: string[]): Promise<CommandResult> {
    resetIdleTimer();

    switch (cmd) {
      // Navigation
      case "goto":
        return cmdGoto(browser, args);
      case "back":
        return cmdBack(browser);
      case "forward":
        return cmdForward(browser);
      case "reload":
        return cmdReload(browser);

      // Snapshot
      case "snapshot":
        return cmdSnapshot(browser, args);

      // Interaction
      case "click":
        return cmdClick(browser, args);
      case "fill":
        return cmdFill(browser, args);
      case "type":
        return cmdType(browser, args);
      case "select":
        return cmdSelect(browser, args);
      case "key":
        return cmdKey(browser, args);
      case "hover":
        return cmdHover(browser, args);
      case "scroll":
        return cmdScroll(browser, args);

      // Wait
      case "waitText":
      case "wait-text":
        return cmdWaitText(browser, args);
      case "waitSelector":
      case "wait-selector":
        return cmdWaitSelector(browser, args);
      case "waitIdle":
      case "wait-idle":
        return cmdWaitIdle(browser, args);
      case "waitUrl":
      case "wait-url":
        return cmdWaitUrl(browser, args);

      // Assert
      case "assertText":
      case "assert-text":
        return cmdAssertText(browser, args);
      case "assertNoText":
      case "assert-no-text":
        return cmdAssertNoText(browser, args);
      case "assertVisible":
      case "assert-visible":
        return cmdAssertVisible(browser, args);
      case "assertEnabled":
      case "assert-enabled":
        return cmdAssertEnabled(browser, args);
      case "assertUrl":
      case "assert-url":
        return cmdAssertUrl(browser, args);

      // Read
      case "text":
        return cmdText(browser);
      case "screenshot":
        return cmdScreenshot(browser, args);
      case "console":
        return cmdConsole(browser);
      case "eval":
        return cmdEvalJs(browser, args);

      // Meta
      case "viewport":
        return cmdViewport(browser, args);
      case "status":
        return cmdStatus(browser, startedAt, port);
      case "close":
      case "closeBrowser": {
        const result = await cmdCloseBrowser(browser);
        // Schedule shutdown after response is sent (500ms grace for HTTP response to flush)
        setTimeout(() => {
          cleanup();
          process.exit(0);
        }, 500);
        return result;
      }

      default:
        return { output: `Unknown command: ${cmd}`, exitCode: 1 };
    }
  }

  // ─────────────────────────────────────────────
  // HTTP Server
  // ─────────────────────────────────────────────

  Bun.serve({
    port,
    async fetch(req) {
      const url = new URL(req.url);

      // Health endpoint — no auth required
      if (req.method === "GET" && url.pathname === "/health") {
        return new Response(JSON.stringify({ status: "ok" }), {
          headers: { "Content-Type": "application/json" },
        });
      }

      // All other endpoints require Bearer token
      const authHeader = req.headers.get("Authorization") || "";
      if (!authHeader.startsWith("Bearer ") || authHeader.slice(7) !== token) {
        return new Response(JSON.stringify({ error: "Unauthorized" }), {
          status: 401,
          headers: { "Content-Type": "application/json" },
        });
      }

      // Command endpoint
      if (req.method === "POST" && url.pathname === "/command") {
        let body: { cmd: string; args: string[] };
        try {
          body = await req.json();
        } catch {
          return new Response(JSON.stringify({ error: "Invalid JSON" }), {
            status: 400,
            headers: { "Content-Type": "application/json" },
          });
        }

        if (!body.cmd) {
          return new Response(JSON.stringify({ error: "cmd field required" }), {
            status: 400,
            headers: { "Content-Type": "application/json" },
          });
        }

        const result = await dispatch(body.cmd, body.args || []);
        return new Response(JSON.stringify(result), {
          headers: { "Content-Type": "application/json" },
        });
      }

      return new Response(JSON.stringify({ error: "Not Found" }), {
        status: 404,
        headers: { "Content-Type": "application/json" },
      });
    },

    error(error) {
      console.error("[server] HTTP error:", error.message);
      return new Response(JSON.stringify({ error: "Internal Server Error" }), {
        status: 500,
        headers: { "Content-Type": "application/json" },
      });
    },
  });
}

main().catch((err) => {
  console.error("[server] Fatal:", err);
  process.exit(1);
});
