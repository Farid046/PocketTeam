import { useEffect, useRef } from "react";
import { useStore } from "../store/useStore";
import type { WsMessage, DashboardSnapshot, AgentState, PocketTeamEvent, AuditEntry } from "../types";

declare global {
  interface Window {
    __AUTH_TOKEN__: string;
  }
}

const BASE_DELAY_MS = 1000;
const MAX_DELAY_MS = 30000;

async function fetchTicket(): Promise<string> {
  const token = window.__AUTH_TOKEN__;
  const res = await fetch("/api/v1/ws-ticket", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
  });
  if (!res.ok) {
    throw new Error(`Ticket fetch failed: ${res.status}`);
  }
  const data = await res.json() as { ticket: string };
  return data.ticket;
}

export function useWebSocket(): void {
  const setSnapshot = useStore((s) => s.setSnapshot);
  const addAgent = useStore((s) => s.addAgent);
  const updateAgent = useStore((s) => s.updateAgent);
  const completeAgent = useStore((s) => s.completeAgent);
  const addEvent = useStore((s) => s.addEvent);
  const addAudit = useStore((s) => s.addAudit);
  const setKillSwitch = useStore((s) => s.setKillSwitch);
  const setConnectionStatus = useStore((s) => s.setConnectionStatus);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);

  function handleMessage(msg: WsMessage): void {
    switch (msg.type) {
      case "snapshot":
        setSnapshot(msg.payload as DashboardSnapshot);
        break;
      case "agent:spawned":
        addAgent(msg.payload as AgentState);
        break;
      case "agent:update":
        updateAgent(msg.payload as AgentState);
        break;
      case "agent:completed":
        completeAgent((msg.payload as { id: string }).id);
        break;
      case "event:new":
        addEvent(msg.payload as PocketTeamEvent);
        break;
      case "audit:new":
        addAudit(msg.payload as AuditEntry);
        break;
      case "killswitch:change":
        setKillSwitch((msg.payload as { active: boolean }).active);
        break;
      default:
        break;
    }
  }

  function connect(): void {
    if (!mountedRef.current) return;

    fetchTicket()
      .then((ticket) => {
        if (!mountedRef.current) return;

        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        const url = `${protocol}//${window.location.host}/ws?ticket=${encodeURIComponent(ticket)}`;

        const ws = new WebSocket(url);
        wsRef.current = ws;

        ws.addEventListener("open", () => {
          if (!mountedRef.current) {
            ws.close();
            return;
          }
          reconnectAttemptRef.current = 0;
          setConnectionStatus("connected");
        });

        ws.addEventListener("message", (event) => {
          try {
            const msg = JSON.parse(event.data as string) as WsMessage;
            handleMessage(msg);
          } catch {
            // Ignore malformed messages
          }
        });

        ws.addEventListener("close", () => {
          if (!mountedRef.current) return;
          wsRef.current = null;
          scheduleReconnect();
        });

        ws.addEventListener("error", () => {
          // close event will fire after error, scheduleReconnect is called there
        });
      })
      .catch(() => {
        if (!mountedRef.current) return;
        scheduleReconnect();
      });
  }

  function scheduleReconnect(): void {
    if (!mountedRef.current) return;

    const attempt = reconnectAttemptRef.current;
    const delay = Math.min(BASE_DELAY_MS * Math.pow(2, attempt), MAX_DELAY_MS);
    reconnectAttemptRef.current += 1;
    setConnectionStatus(attempt === 0 ? "reconnecting" : "reconnecting");

    reconnectTimerRef.current = setTimeout(() => {
      if (!mountedRef.current) return;
      connect();
    }, delay);
  }

  useEffect(() => {
    mountedRef.current = true;
    connect();

    return () => {
      mountedRef.current = false;
      if (reconnectTimerRef.current !== null) {
        clearTimeout(reconnectTimerRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      setConnectionStatus("disconnected");
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
}
