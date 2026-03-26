import { Router, Request, Response } from "express";
import { AuthManager } from "../auth.js";
import { SubagentReader } from "../readers/SubagentReader.js";
import { EventStreamReader } from "../readers/EventStreamReader.js";
import { AuditLogReader } from "../readers/AuditLogReader.js";
import { KillSwitchReader } from "../readers/KillSwitchReader.js";
import { UsageReader } from "../readers/UsageReader.js";
import { redactPayload, stripSensitiveContent } from "../redaction.js";

export interface RouteReaders {
  subagentReader: SubagentReader;
  eventStreamReader: EventStreamReader;
  auditLogReader: AuditLogReader;
  killSwitchReader: KillSwitchReader;
  usageReader: UsageReader;
}

// Apply both redaction layers and send as JSON.
// All REST responses MUST go through this function.
function sendRedacted(res: Response, data: unknown): void {
  const safe = redactPayload(stripSensitiveContent(data));
  res.json(safe);
}

export function createRouter(
  auth: AuthManager,
  readers: RouteReaders
): Router {
  const router = Router();

  // GET /api/v1/health — public, returns ONLY { status: "ok" }
  // No version, no internal data, no timing info.
  router.get("/health", (_req: Request, res: Response) => {
    res.json({ status: "ok" });
  });

  // GET /api/v1/agents — current AgentState[]
  router.get("/agents", (_req: Request, res: Response) => {
    try {
      const agents = readers.subagentReader.readAll();
      sendRedacted(res, agents);
    } catch (err) {
      console.error("[routes] /agents error:", err instanceof Error ? err.message : String(err));
      res.status(500).json({ error: "Internal server error" });
    }
  });

  // GET /api/v1/events?limit=100 — last N events from stream
  router.get("/events", (req: Request, res: Response) => {
    try {
      const limitParam = req.query["limit"];
      const limit =
        typeof limitParam === "string" && /^\d+$/.test(limitParam)
          ? Math.min(parseInt(limitParam, 10), 1000)
          : 100;

      const events = readers.eventStreamReader.getEvents().slice(-limit);
      sendRedacted(res, events);
    } catch (err) {
      console.error("[routes] /events error:", err instanceof Error ? err.message : String(err));
      res.status(500).json({ error: "Internal server error" });
    }
  });

  // GET /api/v1/audit?date=today — audit entries for a given date (defaults to today)
  router.get("/audit", (req: Request, res: Response) => {
    try {
      const dateParam = req.query["date"];
      // Only "today" is supported in v0.1 — the reader loads today's file at startup
      if (dateParam && dateParam !== "today") {
        res.status(400).json({ error: "Only date=today is supported" });
        return;
      }
      const entries = readers.auditLogReader.getEntries();
      sendRedacted(res, entries);
    } catch (err) {
      console.error("[routes] /audit error:", err instanceof Error ? err.message : String(err));
      res.status(500).json({ error: "Internal server error" });
    }
  });

  // GET /api/v1/audit/stats — aggregated AuditStats
  router.get("/audit/stats", (_req: Request, res: Response) => {
    try {
      const stats = readers.auditLogReader.computeStats();
      sendRedacted(res, stats);
    } catch (err) {
      console.error("[routes] /audit/stats error:", err instanceof Error ? err.message : String(err));
      res.status(500).json({ error: "Internal server error" });
    }
  });

  // GET /api/v1/usage?sessionId=... — token/cost usage for a session
  router.get("/usage", (req: Request, res: Response) => {
    try {
      const agents = readers.subagentReader.readAll();
      const sessionId = typeof req.query["sessionId"] === "string"
        ? req.query["sessionId"]
        : agents.length > 0 ? agents[0].sessionId : null;
      if (!sessionId) {
        res.json(null);
        return;
      }
      const usage = readers.usageReader.computeSessionUsage(sessionId, agents);
      sendRedacted(res, usage);
    } catch (err) {
      console.error("[routes] /usage error:", err instanceof Error ? err.message : String(err));
      res.status(500).json({ error: "Internal server error" });
    }
  });

  // GET /api/v1/killswitch — { active: boolean }
  router.get("/killswitch", (_req: Request, res: Response) => {
    try {
      const active = readers.killSwitchReader.isActive();
      res.json({ active });
    } catch (err) {
      console.error("[routes] /killswitch error:", err instanceof Error ? err.message : String(err));
      res.status(500).json({ error: "Internal server error" });
    }
  });

  // POST /api/v1/ws-ticket — issue a short-lived WebSocket upgrade ticket
  // Requires Bearer auth (enforced by auth middleware in server.ts).
  router.post("/ws-ticket", (_req: Request, res: Response) => {
    try {
      const ticket = auth.createTicket();
      res.json({ ticket: ticket.ticket, expiresAt: ticket.expiresAt });
    } catch (err) {
      console.error("[routes] /ws-ticket error:", err instanceof Error ? err.message : String(err));
      res.status(500).json({ error: "Internal server error" });
    }
  });

  return router;
}
