import express, { Express } from "express";
import helmet from "helmet";
import * as http from "http";
import * as fs from "fs";
import * as path from "path";
import { fileURLToPath } from "url";
import { AuthManager } from "./auth.js";
import { SubagentReader } from "./readers/SubagentReader.js";
import { EventStreamReader } from "./readers/EventStreamReader.js";
import { AuditLogReader } from "./readers/AuditLogReader.js";
import { KillSwitchReader } from "./readers/KillSwitchReader.js";
import { FileWatcher } from "./watcher/FileWatcher.js";
import { createRouter } from "./api/routes.js";
import { WebSocketHub } from "./api/websocket.js";

export interface ServerConfig {
  port: number;
  authToken: string;
  projectDir: string;    // /data/claude/project
  pocketteamDir: string; // /data/pocketteam
}

export interface PocketTeamServer {
  app: Express;
  httpServer: http.Server;
  wsHub: WebSocketHub;
  close: () => Promise<void>;
}

export function createServer(config: ServerConfig): PocketTeamServer {
  const { port, authToken, projectDir, pocketteamDir } = config;

  const app = express();

  // === Security headers (S8: inject specific port into connectSrc) ===
  app.use(
    helmet({
      contentSecurityPolicy: {
        directives: {
          defaultSrc: ["'self'"],
          scriptSrc: ["'self'"],
          connectSrc: ["'self'", `ws://localhost:${port}`, `wss://localhost:${port}`, `ws://127.0.0.1:${port}`, `wss://127.0.0.1:${port}`],
          styleSrc: ["'self'", "'unsafe-inline'"], // required for Tailwind utility classes
          imgSrc: ["'self'", "data:"],
          fontSrc: ["'self'"],
          objectSrc: ["'none'"],
          frameAncestors: ["'none'"],
        },
      },
      // Prevent clickjacking
      frameguard: { action: "deny" },
    })
  );

  // === Auth middleware — applied before all routes ===
  const auth = new AuthManager(authToken);
  app.use(auth.middleware());

  // === Readers ===
  const subagentReader = new SubagentReader(projectDir);

  const eventStreamReader = new EventStreamReader(pocketteamDir);
  eventStreamReader.loadInitial(1000);

  const auditLogReader = new AuditLogReader(pocketteamDir);
  auditLogReader.loadInitial(2000);

  // === WebSocket hub ===
  // KillSwitchReader is created once (with WebSocket callback) and shared with routes.
  const killSwitchReader = new KillSwitchReader(pocketteamDir, (active: boolean) => {
    wsHub.broadcastKillSwitchChange(active);
  });

  const wsHub = new WebSocketHub(auth, {
    subagentReader,
    eventStreamReader,
    auditLogReader,
    killSwitchReader,
  });

  killSwitchReader.init();

  // === File watcher — drives incremental WebSocket broadcasts ===
  const watcher = new FileWatcher({
    onFileChange: (filePath: string) => {
      handleFileChange(filePath);
    },
    onFileAdd: (filePath: string) => {
      handleFileChange(filePath);
    },
    onError: (error: Error) => {
      console.error("[FileWatcher] error:", error.message);
    },
  });

  // Determine what to watch: pocketteam dir + project dir subagents
  const watchPaths: string[] = [];
  if (fs.existsSync(pocketteamDir)) {
    watchPaths.push(pocketteamDir);
  }
  if (fs.existsSync(projectDir)) {
    watchPaths.push(projectDir);
  }

  if (watchPaths.length > 0) {
    watcher.watch(watchPaths);
  }

  // Track known agent IDs so we can distinguish new spawns from updates
  const knownAgentIds = new Set<string>();

  function handleFileChange(filePath: string): void {
    const normalizedPath = path.normalize(filePath);

    // Events stream
    if (normalizedPath === path.normalize(eventStreamReader.getStreamPath())) {
      const before = eventStreamReader.getEvents().length;
      eventStreamReader.onFileChange();
      const after = eventStreamReader.getEvents();
      const newEvents = after.slice(before);
      for (const event of newEvents) {
        wsHub.broadcastEventNew(event);
      }
      return;
    }

    // Audit logs
    const auditWatchPaths = auditLogReader.getWatchPaths().map(path.normalize);
    if (auditWatchPaths.some((p) => p === normalizedPath)) {
      const before = auditLogReader.getEntries().length;
      auditLogReader.onFileChange(filePath);
      const after = auditLogReader.getEntries();
      const newEntries = after.slice(before);
      for (const entry of newEntries) {
        wsHub.broadcastAuditNew(entry);
      }
      return;
    }

    // Agent JSONL or meta changes — re-read all agents and broadcast updates
    if (
      normalizedPath.includes(path.sep + "subagents" + path.sep) &&
      (normalizedPath.endsWith(".jsonl") || normalizedPath.endsWith(".meta.json"))
    ) {
      const agents = subagentReader.readAll();
      for (const agent of agents) {
        if (agent.status === "done") {
          wsHub.broadcastAgentCompleted(agent.id, 0);
        } else if (!knownAgentIds.has(agent.id)) {
          wsHub.broadcastAgentSpawned(agent);
        } else {
          wsHub.broadcastAgentUpdate(agent);
        }
        knownAgentIds.add(agent.id);
      }
    }
  }

  // === REST routes ===
  app.use(
    "/api/v1",
    createRouter(auth, {
      subagentReader,
      eventStreamReader,
      auditLogReader,
      killSwitchReader,
    })
  );

  // === Serve frontend static files ===
  // dist/client/ is built by vite. Resolve relative to this file's location at runtime.
  // Use import.meta.url for ESM compatibility (__dirname is not available in ESM).
  const __filename = fileURLToPath(import.meta.url);
  const __dirname = path.dirname(__filename);
  const clientDistDir = path.resolve(__dirname, "..", "client");

  if (fs.existsSync(clientDistDir)) {
    // Serve all static assets without auth (auth middleware already passes non-/api/ paths)
    app.use(express.static(clientDistDir, { index: false }));

    // Serve index.html with auth token injected.
    // Token replaces __AUTH_TOKEN__ placeholder so the frontend can initiate
    // authenticated requests without ever putting the token in a URL.
    app.get("*", (_req, res) => {
      const indexPath = path.join(clientDistDir, "index.html");

      if (!fs.existsSync(indexPath)) {
        res.status(404).send("Dashboard not built. Run: npm run build:client");
        return;
      }

      try {
        let html = fs.readFileSync(indexPath, "utf-8");
        html = html.replace(/__AUTH_TOKEN__/g, authToken);
        res.type("html").send(html);
      } catch (err) {
        console.error("[server] index.html read error:", err instanceof Error ? err.message : String(err));
        res.status(500).send("Internal server error");
      }
    });
  } else {
    // No frontend built — return 404 for non-API routes
    app.get("*", (_req, res) => {
      res.status(404).json({ error: "Frontend not built. Run: npm run build:client" });
    });
  }

  // === HTTP server + WebSocket upgrade ===
  const httpServer = http.createServer(app);

  httpServer.on("upgrade", (req, socket, head) => {
    const url = req.url ?? "/";
    if (url.startsWith("/ws")) {
      wsHub.handleUpgrade(req, socket as import("net").Socket, head);
    } else {
      socket.write("HTTP/1.1 404 Not Found\r\nConnection: close\r\n\r\n");
      socket.destroy();
    }
  });

  const close = async (): Promise<void> => {
    await Promise.all([
      watcher.close(),
      killSwitchReader.close(),
      wsHub.close(),
      new Promise<void>((resolve) => httpServer.close(() => resolve())),
    ]);
  };

  return { app, httpServer, wsHub, close };
}
