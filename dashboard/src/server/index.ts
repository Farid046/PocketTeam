// PocketTeam Dashboard Server — Entry Point
//
// Environment variables:
//   PORT              TCP port to listen on (default: 3847)
//   AUTH_TOKEN        Required. 64-char hex token for Bearer + WebSocket ticket auth.
//   CLAUDE_PROJECT_DIR  Path to Claude project directory (default: /data/claude/project)
//   POCKETTEAM_DIR    Path to .pocketteam directory (default: /data/pocketteam)

import { createServer } from "./server.js";

const PORT = parseInt(process.env["PORT"] ?? "3847", 10);
if (isNaN(PORT) || PORT < 1 || PORT > 65535) {
  console.error(`[startup] Invalid PORT: "${process.env["PORT"]}". Must be 1-65535.`);
  process.exit(1);
}

const AUTH_TOKEN = process.env["AUTH_TOKEN"];
if (!AUTH_TOKEN || AUTH_TOKEN.trim().length === 0) {
  console.error("[startup] AUTH_TOKEN environment variable is required but not set.");
  console.error("          Generate one with: python3 -c \"import secrets; print(secrets.token_hex(32))\"");
  process.exit(1);
}
if (!/^[0-9a-f]{64}$/.test(AUTH_TOKEN)) {
  console.error("[startup] AUTH_TOKEN must be exactly 64 lowercase hex characters.");
  console.error("          Generate one with: python3 -c \"import secrets; print(secrets.token_hex(32))\"");
  process.exit(1);
}

const CLAUDE_PROJECT_DIR = process.env["CLAUDE_PROJECT_DIR"] ?? "/data/claude/project";
const POCKETTEAM_DIR = process.env["POCKETTEAM_DIR"] ?? "/data/pocketteam";

// Startup — log config without revealing secrets
console.log("[startup] PocketTeam Dashboard");
console.log(`[startup]   port:           ${PORT}`);
console.log(`[startup]   project dir:    ${CLAUDE_PROJECT_DIR}`);
console.log(`[startup]   pocketteam dir: ${POCKETTEAM_DIR}`);
// AUTH_TOKEN is intentionally NOT logged

let server: ReturnType<typeof createServer>;
try {
  server = createServer({
    port: PORT,
    authToken: AUTH_TOKEN,
    projectDir: CLAUDE_PROJECT_DIR,
    pocketteamDir: POCKETTEAM_DIR,
  });
} catch (err) {
  console.error("[startup] Failed to create server:", err instanceof Error ? err.message : String(err));
  process.exit(1);
}

// Bind to 0.0.0.0 INSIDE container — the 127.0.0.1 restriction is at Docker port-mapping level
server.httpServer.listen(PORT, "0.0.0.0", () => {
  console.log(`[startup] Listening on http://0.0.0.0:${PORT}`);
  console.log(`[startup] Health: http://localhost:${PORT}/api/v1/health`);
});

server.httpServer.on("error", (err: NodeJS.ErrnoException) => {
  if (err.code === "EADDRINUSE") {
    console.error(`[startup] Port ${PORT} is already in use.`);
    console.error(`          Check: lsof -i :${PORT}`);
  } else {
    console.error("[startup] HTTP server error:", err.message);
  }
  process.exit(1);
});

// Graceful shutdown
async function shutdown(signal: string): Promise<void> {
  console.log(`[shutdown] Received ${signal} — shutting down gracefully`);
  try {
    await server.close();
    console.log("[shutdown] Clean exit");
    process.exit(0);
  } catch (err) {
    console.error("[shutdown] Error during shutdown:", err instanceof Error ? err.message : String(err));
    process.exit(1);
  }
}

process.on("SIGTERM", () => void shutdown("SIGTERM"));
process.on("SIGINT", () => void shutdown("SIGINT"));

// Prevent unhandled promise rejections from silently crashing the process
process.on("unhandledRejection", (reason: unknown) => {
  console.error("[runtime] Unhandled rejection:", reason instanceof Error ? reason.message : String(reason));
  // Do not exit — allow the server to continue serving other requests
});

process.on("uncaughtException", (err: Error) => {
  console.error("[runtime] Uncaught exception:", err.message);
  console.error(err.stack);
  process.exit(1);
});
