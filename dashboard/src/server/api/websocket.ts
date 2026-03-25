import { IncomingMessage } from "http";
import { WebSocket, WebSocketServer } from "ws";
import { URL } from "url";
import { AuthManager } from "../auth.js";
import { SubagentReader } from "../readers/SubagentReader.js";
import { EventStreamReader } from "../readers/EventStreamReader.js";
import { AuditLogReader } from "../readers/AuditLogReader.js";
import { KillSwitchReader } from "../readers/KillSwitchReader.js";
import { redactPayload, stripSensitiveContent } from "../redaction.js";
import {
  AgentState,
  PocketTeamEvent,
  AuditEntry,
  WsMessage,
  DashboardSnapshot,
} from "../readers/types.js";

// Debounce delay for non-killswitch events (ms).
// Batches rapid agent-spawn bursts into a single broadcast.
const DEBOUNCE_MS = 200;

export interface WsReaders {
  subagentReader: SubagentReader;
  eventStreamReader: EventStreamReader;
  auditLogReader: AuditLogReader;
  killSwitchReader: KillSwitchReader;
}

export class WebSocketHub {
  private wss: WebSocketServer;
  private auth: AuthManager;
  private readers: WsReaders;
  private clients: Set<WebSocket> = new Set();
  private debounceTimer: ReturnType<typeof setTimeout> | null = null;

  // Pending incremental updates — flushed after debounce
  private pendingMessages: WsMessage[] = [];

  constructor(auth: AuthManager, readers: WsReaders) {
    this.auth = auth;
    this.readers = readers;
    this.wss = new WebSocketServer({ noServer: true });

    this.wss.on("connection", (ws: WebSocket) => {
      this.handleConnection(ws);
    });
  }

  // Called by server.ts on HTTP upgrade events.
  // Validates the one-time ticket from the query string before upgrading.
  handleUpgrade(req: IncomingMessage, socket: import("net").Socket, head: Buffer): void {
    const reqUrl = req.url ?? "/";
    let ticket: string | null = null;

    try {
      const parsed = new URL(reqUrl, `http://${req.headers.host ?? "localhost"}`);
      ticket = parsed.searchParams.get("ticket");
    } catch {
      // Malformed URL — reject
    }

    if (!ticket || !this.auth.validateTicket(ticket)) {
      socket.write("HTTP/1.1 401 Unauthorized\r\nConnection: close\r\n\r\n");
      socket.destroy();
      return;
    }

    this.wss.handleUpgrade(req, socket, head, (ws) => {
      this.wss.emit("connection", ws, req);
    });
  }

  // Send a snapshot of current state to a newly connected client.
  private sendSnapshot(ws: WebSocket): void {
    try {
      const snapshot: DashboardSnapshot = {
        agents: this.readers.subagentReader.readAll(),
        events: this.readers.eventStreamReader.getEvents(),
        auditStats: this.readers.auditLogReader.computeStats(),
        killSwitch: this.readers.killSwitchReader.isActive(),
      };

      const msg: WsMessage = { type: "snapshot", payload: snapshot };
      this.emitToClient(ws, msg);
    } catch (err) {
      console.error("[WsHub] sendSnapshot error:", err instanceof Error ? err.message : String(err));
    }
  }

  private handleConnection(ws: WebSocket): void {
    this.clients.add(ws);

    ws.on("close", () => {
      this.clients.delete(ws);
    });

    ws.on("error", (err: Error) => {
      console.error("[WsHub] client error:", err.message);
      this.clients.delete(ws);
    });

    // Send full snapshot immediately on connect
    this.sendSnapshot(ws);
  }

  // === Public broadcast methods — called from server.ts watcher events ===

  broadcastAgentSpawned(agent: AgentState): void {
    this.queueMessage({ type: "agent:spawned", payload: agent });
  }

  broadcastAgentUpdate(agent: AgentState): void {
    this.queueMessage({ type: "agent:update", payload: agent });
  }

  broadcastAgentCompleted(id: string, duration: number): void {
    this.queueMessage({ type: "agent:completed", payload: { id, duration } });
  }

  broadcastEventNew(event: PocketTeamEvent): void {
    this.queueMessage({ type: "event:new", payload: event });
  }

  broadcastAuditNew(entry: AuditEntry): void {
    this.queueMessage({ type: "audit:new", payload: entry });
  }

  // Kill switch change bypasses the debounce — immediate broadcast.
  broadcastKillSwitchChange(active: boolean): void {
    const msg: WsMessage = { type: "killswitch:change", payload: { active } };
    this.emitToAllClients(msg);
  }

  // Queue a message for debounced broadcast.
  // Multiple messages within DEBOUNCE_MS are sent together after the window closes.
  private queueMessage(msg: WsMessage): void {
    this.pendingMessages.push(msg);

    if (this.debounceTimer !== null) {
      clearTimeout(this.debounceTimer);
    }

    this.debounceTimer = setTimeout(() => {
      this.flushPending();
    }, DEBOUNCE_MS);
  }

  private flushPending(): void {
    this.debounceTimer = null;
    const messages = this.pendingMessages.splice(0);

    for (const msg of messages) {
      this.emitToAllClients(msg);
    }
  }

  // The single redaction gate for all client emissions.
  // ALL data — snapshot, incremental updates — must flow through here.
  // Layer 1: stripSensitiveContent (remove tool_result content)
  // Layer 2: redactPayload (regex redaction on remaining strings)
  private emitToAllClients(msg: WsMessage): void {
    if (this.clients.size === 0) return;

    const safePayload = redactPayload(stripSensitiveContent(msg.payload));
    const safeMsg: WsMessage = { type: msg.type, payload: safePayload };
    const serialized = JSON.stringify(safeMsg);

    for (const ws of this.clients) {
      if (ws.readyState === WebSocket.OPEN) {
        try {
          ws.send(serialized);
        } catch (err) {
          console.error("[WsHub] send error:", err instanceof Error ? err.message : String(err));
          this.clients.delete(ws);
        }
      } else {
        this.clients.delete(ws);
      }
    }
  }

  // Single-client emission — used for the initial snapshot.
  // Applies the same redaction gate as emitToAllClients.
  private emitToClient(ws: WebSocket, msg: WsMessage): void {
    const safePayload = redactPayload(stripSensitiveContent(msg.payload));
    const safeMsg: WsMessage = { type: msg.type, payload: safePayload };

    if (ws.readyState === WebSocket.OPEN) {
      try {
        ws.send(JSON.stringify(safeMsg));
      } catch (err) {
        console.error("[WsHub] single-send error:", err instanceof Error ? err.message : String(err));
        this.clients.delete(ws);
      }
    }
  }

  getClientCount(): number {
    return this.clients.size;
  }

  async close(): Promise<void> {
    if (this.debounceTimer !== null) {
      clearTimeout(this.debounceTimer);
      this.debounceTimer = null;
    }

    return new Promise((resolve) => {
      this.wss.close(() => resolve());
    });
  }
}
