import { Request, Response, NextFunction } from "express";
import crypto, { timingSafeEqual } from "crypto";

// Ticket: 60s TTL, single-use (S1 — WS ticket system to avoid token in URL)
interface WsTicket {
  ticket: string;
  expiresAt: number;
}

export class AuthManager {
  private authToken: string;
  private tickets: Map<string, WsTicket> = new Map();

  constructor(authToken: string) {
    this.authToken = authToken;
  }

  // Express middleware — checks Bearer token on all /api/* routes.
  // Public exceptions: /api/v1/health (public), /, /index.html, and static assets.
  middleware() {
    return (req: Request, res: Response, next: NextFunction): void => {
      // Health endpoint is public — no auth required
      if (req.path === "/api/v1/health") {
        next();
        return;
      }

      // Root and index.html: serve without auth (HTML has __AUTH_TOKEN__ injected)
      if (req.path === "/" || req.path === "/index.html") {
        next();
        return;
      }

      // Static assets (JS, CSS, images, fonts): no auth
      if (!req.path.startsWith("/api/")) {
        next();
        return;
      }

      // All /api/* routes require Bearer token.
      // Use timingSafeEqual to prevent timing-based token oracle attacks.
      const auth = req.headers.authorization;
      const expected = Buffer.from(`Bearer ${this.authToken}`);
      const received = Buffer.from(auth || "");
      if (expected.length !== received.length || !timingSafeEqual(expected, received)) {
        res.status(401).json({ error: "Unauthorized" });
        return;
      }

      next();
    };
  }

  // Create a short-lived ticket for WebSocket upgrade auth.
  // Tickets are 60s TTL, single-use. Stale tickets are purged on each call.
  createTicket(): WsTicket {
    const now = Date.now();

    // Purge expired tickets to prevent unbounded memory growth
    for (const [k, v] of this.tickets) {
      if (v.expiresAt < now) {
        this.tickets.delete(k);
      }
    }

    const ticket: WsTicket = {
      ticket: crypto.randomBytes(32).toString("hex"),
      expiresAt: now + 60_000,
    };
    this.tickets.set(ticket.ticket, ticket);
    return ticket;
  }

  // Validate and consume a ticket. Returns false if missing, expired, or already used.
  validateTicket(ticketStr: string): boolean {
    if (!ticketStr || typeof ticketStr !== "string") return false;

    const ticket = this.tickets.get(ticketStr);
    if (!ticket) return false;

    if (ticket.expiresAt < Date.now()) {
      this.tickets.delete(ticketStr);
      return false;
    }

    // Single-use: delete immediately on first valid use
    this.tickets.delete(ticketStr);
    return true;
  }

  // Validate a Bearer token directly (used by non-HTTP upgrade paths).
  // Uses timingSafeEqual to prevent timing-based token oracle attacks.
  validateToken(token: string): boolean {
    if (typeof token !== "string") return false;
    const expected = Buffer.from(this.authToken);
    const received = Buffer.from(token);
    return expected.length === received.length && timingSafeEqual(expected, received);
  }

  getToken(): string {
    return this.authToken;
  }
}
