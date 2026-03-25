import React from "react";
import type { AgentState } from "../types";
import { useStore } from "../store/useStore";

function relativeTime(isoTs: string): string {
  const diffMs = Date.now() - new Date(isoTs).getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHour = Math.floor(diffMin / 60);
  if (diffHour < 24) return `${diffHour}h ago`;
  return `${Math.floor(diffHour / 24)}d ago`;
}

interface SessionSummary {
  sessionId: string;
  startedAt: string;
  agentCount: number;
  isActive: boolean;
}

function buildSessions(agents: AgentState[]): SessionSummary[] {
  const map = new Map<string, SessionSummary>();

  for (const agent of agents) {
    const existing = map.get(agent.sessionId);
    const isActive = agent.status === "working";

    if (!existing) {
      map.set(agent.sessionId, {
        sessionId: agent.sessionId,
        startedAt: agent.startedAt,
        agentCount: 1,
        isActive,
      });
    } else {
      map.set(agent.sessionId, {
        ...existing,
        agentCount: existing.agentCount + 1,
        isActive: existing.isActive || isActive,
        startedAt:
          new Date(agent.startedAt) < new Date(existing.startedAt)
            ? agent.startedAt
            : existing.startedAt,
      });
    }
  }

  return Array.from(map.values()).sort(
    (a, b) => new Date(b.startedAt).getTime() - new Date(a.startedAt).getTime()
  );
}

interface Props {
  agents: AgentState[];
}

export function SessionPicker({ agents }: Props): React.ReactElement | null {
  const selectedSessionId = useStore((s) => s.selectedSessionId);
  const setSelectedSessionId = useStore((s) => s.setSelectedSessionId);

  const sessions = buildSessions(agents);

  if (sessions.length <= 1) return null;

  return (
    <select
      className="bg-gray-900 border border-gray-700 text-gray-300 text-xs rounded px-2 py-1 focus:outline-none focus:border-gray-500"
      value={selectedSessionId ?? ""}
      onChange={(e) => setSelectedSessionId(e.target.value || null)}
    >
      {sessions.map((s) => (
        <option key={s.sessionId} value={s.sessionId}>
          {s.sessionId.slice(0, 12)}... — {s.agentCount} agent
          {s.agentCount !== 1 ? "s" : ""} — {relativeTime(s.startedAt)}
          {s.isActive ? " (active)" : " (historical)"}
        </option>
      ))}
    </select>
  );
}
