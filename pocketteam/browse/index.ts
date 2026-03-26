/**
 * index.ts — CLI Entry Point
 * Reads state file, auto-starts daemon if needed, sends commands to server.
 */

import { existsSync, readFileSync } from "fs";
import { mkdirSync } from "fs";
import { join } from "path";
import { homedir } from "os";

// ─────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────

const POCKETTEAM_DIR = join(homedir(), ".pocketteam");
const STATE_FILE = join(POCKETTEAM_DIR, "browse.json");
const DAEMON_START_TIMEOUT_MS = 8000;
const DAEMON_POLL_INTERVAL_MS = 200;

// Exit codes
const EXIT_SUCCESS = 0;
const EXIT_ASSERTION_FAIL = 1;
const EXIT_STALE_REF = 2;
const EXIT_TIMEOUT = 3;

// ─────────────────────────────────────────────
// State file
// ─────────────────────────────────────────────

interface DaemonState {
  pid: number;
  port: number;
  token: string;
  startedAt: string;
  version: string;
}

function readStateFile(): DaemonState | null {
  if (!existsSync(STATE_FILE)) return null;
  try {
    const raw = readFileSync(STATE_FILE, "utf8");
    return JSON.parse(raw) as DaemonState;
  } catch {
    return null;
  }
}

function isPidAlive(pid: number): boolean {
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}

function getDaemonState(): DaemonState | null {
  const state = readStateFile();
  if (!state) return null;
  if (!isPidAlive(state.pid)) {
    // Daemon is dead — clean up stale state
    return null;
  }
  return state;
}

// ─────────────────────────────────────────────
// Daemon management
// ─────────────────────────────────────────────

async function startDaemon(): Promise<DaemonState> {
  // Path to server.ts (same directory as this file)
  const serverPath = join(import.meta.dir, "server.ts");

  console.error("[ptbrowse] Starting daemon...");

  const headedFlag = process.env.PTBROWSE_HEADED === "1" ? "--headed" : "";
  const args = ["bun", "run", serverPath];
  if (headedFlag) args.push(headedFlag);

  const proc = Bun.spawn(args, {
    detached: true,
    stdio: ["ignore", "ignore", "ignore"],
  });

  proc.unref();

  // Wait for state file to appear (up to DAEMON_START_TIMEOUT_MS)
  const deadline = Date.now() + DAEMON_START_TIMEOUT_MS;

  while (Date.now() < deadline) {
    await Bun.sleep(DAEMON_POLL_INTERVAL_MS);
    const state = getDaemonState();
    if (state) {
      // Verify health
      try {
        const resp = await fetch(`http://localhost:${state.port}/health`, {
          signal: AbortSignal.timeout(2000),
        });
        if (resp.ok) {
          console.error(`[ptbrowse] Daemon ready on port ${state.port}`);
          return state;
        }
      } catch {
        // Not ready yet, keep polling
      }
    }
  }

  throw new Error("Daemon failed to start within 8 seconds");
}

async function ensureDaemon(): Promise<DaemonState> {
  const existing = getDaemonState();
  if (existing) {
    // Verify it's actually responding
    try {
      const resp = await fetch(`http://localhost:${existing.port}/health`, {
        signal: AbortSignal.timeout(2000),
      });
      if (resp.ok) return existing;
    } catch {
      // Daemon state file exists but server isn't responding — restart
      console.error("[ptbrowse] Daemon not responding, restarting...");
    }
  }
  return startDaemon();
}

// ─────────────────────────────────────────────
// HTTP communication
// ─────────────────────────────────────────────

interface CommandResult {
  output: string;
  exitCode: number;
}

async function sendCommand(
  state: DaemonState,
  cmd: string,
  args: string[]
): Promise<CommandResult> {
  const url = `http://localhost:${state.port}/command`;
  const isCloseCmd = cmd === "close" || cmd === "closeBrowser";

  let resp: Response;
  try {
    resp = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${state.token}`,
      },
      body: JSON.stringify({ cmd, args }),
      signal: AbortSignal.timeout(60000), // 60s command timeout
    });
  } catch (err: any) {
    if (err.name === "TimeoutError") {
      // close command: daemon may have shut down before responding
      if (isCloseCmd) {
        return { output: "Daemon stopped.", exitCode: EXIT_SUCCESS };
      }
      return {
        output: `Command timed out after 60s`,
        exitCode: EXIT_TIMEOUT,
      };
    }
    if (err.code === "ECONNREFUSED" || err.message?.includes("connect") ||
        err.message?.includes("ECONNRESET") || err.message?.includes("socket")) {
      // close command: connection reset means daemon successfully shut down
      if (isCloseCmd) {
        return { output: "Daemon stopped.", exitCode: EXIT_SUCCESS };
      }
      return {
        output: `Cannot connect to ptbrowse daemon. Is it running?`,
        exitCode: EXIT_TIMEOUT,
      };
    }
    // close: any connection error after sending close is a success
    if (isCloseCmd) {
      return { output: "Daemon stopped.", exitCode: EXIT_SUCCESS };
    }
    return {
      output: `Connection error: ${err.message}`,
      exitCode: EXIT_TIMEOUT,
    };
  }

  if (resp.status === 401) {
    return {
      output: `Authentication failed — daemon token mismatch`,
      exitCode: EXIT_TIMEOUT,
    };
  }

  if (!resp.ok) {
    const body = await resp.text().catch(() => "");
    return {
      output: `Server error ${resp.status}: ${body}`,
      exitCode: EXIT_TIMEOUT,
    };
  }

  const result = (await resp.json()) as CommandResult;
  return result;
}

// ─────────────────────────────────────────────
// Argument parsing
// ─────────────────────────────────────────────

/**
 * Map CLI subcommands to internal command names and handle compound commands.
 * Examples:
 *   wait text "foo"      → cmd=waitText, args=["foo"]
 *   wait idle 2000       → cmd=waitIdle, args=["2000"]
 *   assert text "foo"    → cmd=assertText, args=["foo"]
 *   assert no-text "foo" → cmd=assertNoText, args=["foo"]
 *   assert visible @e1   → cmd=assertVisible, args=["@e1"]
 */
function resolveCommand(
  rawCmd: string,
  restArgs: string[]
): { cmd: string; args: string[] } {
  switch (rawCmd) {
    case "wait": {
      const sub = restArgs[0];
      const remaining = restArgs.slice(1);
      switch (sub) {
        case "text":
          return { cmd: "waitText", args: remaining };
        case "selector":
          return { cmd: "waitSelector", args: remaining };
        case "idle":
          return { cmd: "waitIdle", args: remaining };
        case "url":
          return { cmd: "waitUrl", args: remaining };
        default:
          return { cmd: "waitText", args: restArgs };
      }
    }

    case "assert": {
      const sub = restArgs[0];
      const remaining = restArgs.slice(1);
      switch (sub) {
        case "text":
          return { cmd: "assertText", args: remaining };
        case "no-text":
        case "notext":
          return { cmd: "assertNoText", args: remaining };
        case "visible":
          return { cmd: "assertVisible", args: remaining };
        case "enabled":
          return { cmd: "assertEnabled", args: remaining };
        case "url":
          return { cmd: "assertUrl", args: remaining };
        default:
          return { cmd: "assertText", args: restArgs };
      }
    }

    case "eval":
      return { cmd: "eval", args: restArgs };

    case "console":
      return { cmd: "console", args: [] };

    case "close":
      return { cmd: "close", args: [] };

    case "status":
      return { cmd: "status", args: [] };

    default:
      return { cmd: rawCmd, args: restArgs };
  }
}

// ─────────────────────────────────────────────
// Main
// ─────────────────────────────────────────────

async function main() {
  // Parse CLI args: bun run index.ts <cmd> [args...]
  const argv = process.argv.slice(2);

  if (argv.length === 0) {
    printHelp();
    process.exit(0);
  }

  const rawCmd = argv[0];
  const rawArgs = argv.slice(1);

  // Special local commands that don't need the daemon
  if (rawCmd === "help" || rawCmd === "--help" || rawCmd === "-h") {
    printHelp();
    process.exit(0);
  }

  const { cmd, args } = resolveCommand(rawCmd, rawArgs);

  // Ensure daemon is running
  let state: DaemonState;
  try {
    state = await ensureDaemon();
  } catch (err: any) {
    process.stderr.write(`[ptbrowse] Failed to start daemon: ${err.message}\n`);
    process.exit(EXIT_TIMEOUT);
  }

  // Send command
  const result = await sendCommand(state, cmd, args);

  // Print output
  if (result.output) {
    process.stdout.write(result.output + "\n");
  }

  process.exit(result.exitCode);
}

function printHelp() {
  const help = `
ptbrowse — PocketTeam browser automation CLI

USAGE
  bun run pocketteam/browse/index.ts <command> [args]

NAVIGATION
  goto <url>                Navigate to URL
  back                      Go back
  forward                   Go forward
  reload                    Reload current page

SNAPSHOT
  snapshot                  Full accessibility tree with @e refs
  snapshot -i               Interactive elements only
  snapshot -c               Compact one-line format
  snapshot -D               Diff since last snapshot

INTERACTION
  click <ref>               Click element (e.g. @e1)
  fill <ref> <text>         Fill input field
  type <ref> <text>         Type keystroke by keystroke
  select <ref> <value>      Select dropdown option
  key <key>                 Press keyboard key (Enter, Escape, Tab...)
  hover <ref>               Hover element
  scroll <ref> <dir> <px>   Scroll (dir: up|down)

WAIT
  wait text <text>          Wait until text appears
  wait selector <css>       Wait until CSS selector exists
  wait idle [ms]            Wait for network idle (default 2000ms)
  wait url <pattern>        Wait for URL to match regex pattern

ASSERT (exit 1 on failure)
  assert text <text>        Assert page contains text
  assert no-text <text>     Assert page does NOT contain text
  assert visible <ref>      Assert element is visible
  assert enabled <ref>      Assert element is enabled
  assert url <pattern>      Assert URL matches regex pattern

READ
  text                      Extract page text (max 8000 chars)
  screenshot [path]         Save screenshot (default: ~/.pocketteam/screenshots/)
  console                   Show captured console messages
  eval <expr>               Evaluate JavaScript expression

META
  viewport <w> <h>          Set viewport size (e.g. 375 812)
  status                    Show daemon status
  close                     Close browser and stop daemon

EXIT CODES
  0  Success
  1  Assertion failed or element error
  2  Stale ref (run snapshot again)
  3  Timeout or daemon unreachable
`.trim();
  process.stdout.write(help + "\n");
}

main().catch((err) => {
  process.stderr.write(`[ptbrowse] Fatal: ${err.message}\n`);
  process.exit(EXIT_TIMEOUT);
});
