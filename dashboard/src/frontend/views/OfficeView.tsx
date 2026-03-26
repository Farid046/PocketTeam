import React from "react";
import type { AgentState, CooActivity } from "../types";
import { useStore } from "../store/useStore";
import { EventFeed } from "../components/EventFeed";
import { EmptyState } from "./EmptyState";
import { Office3D } from "../components/office3d/Office3D";
import { ErrorBoundary } from "../components/ErrorBoundary";
import type { PocketTeamEvent } from "../types";

interface Props {
  agents: AgentState[];
  events: PocketTeamEvent[];
}

export function OfficeView({ agents, events }: Props): React.ReactElement {
  const cooActivity = useStore((s) => s.cooActivity);

  const agentsByRole = new Map<string, AgentState>();
  for (const agent of agents) {
    const role = agent.role.toLowerCase();
    const existing = agentsByRole.get(role);
    if (!existing || agentPriority(agent) > agentPriority(existing)) {
      agentsByRole.set(role, agent);
    }
  }

  const hasAnyActive = agents.some(
    (a) => a.status === "working" || a.status === "done"
  );

  // COO is the main session — use real activity from main session JSONL
  if (hasAnyActive && !agentsByRole.has("coo")) {
    const anySubagentWorking = agents.some((a) => a.status === "working");
    // COO is "working" when main session JSONL written in last 60s OR a subagent is working
    const cooIsActive = (cooActivity?.isActive ?? false) || anySubagentWorking;
    const cooStatus = cooIsActive ? "working" : "done";
    const zeroTokens = { inputTokens: 0, outputTokens: 0, cacheCreationTokens: 0, cacheReadTokens: 0 };

    agentsByRole.set("coo", {
      id: "coo-main-session",
      role: "coo",
      agentType: "orchestrator",
      description: cooActivity?.lastToolCall ?? "Idle",
      status: cooStatus,
      startedAt: agents[0]?.startedAt ?? new Date().toISOString(),
      lastActivity: cooActivity?.lastActivity ?? new Date().toISOString(),
      toolCallCount: cooActivity?.toolCallCount ?? 0,
      messageCount: cooActivity?.messageCount ?? 0,
      sessionId: agents[0]?.sessionId ?? "",
      sessionActive: cooActivity?.isActive ?? false,
      tokenUsage: cooActivity?.tokenUsage ?? zeroTokens,
      model: cooActivity?.model ?? "",
      gitBranch: cooActivity?.gitBranch ?? "",
    });
  }

  // Flatten back to array for FloorPlan
  const normalizedAgents = Array.from(agentsByRole.values());

  return (
    <div className="flex flex-col md:flex-row gap-2 flex-1 min-h-0 h-full">
      {/* Main 3D office — fills all available space */}
      <div className="flex-1 min-w-0 min-h-0 h-full">
        {!hasAnyActive ? (
          <EmptyState agents={agents} />
        ) : (
          <ErrorBoundary fallback={
            <div className="flex items-center justify-center h-full text-red-400 text-sm font-mono p-4">
              3D view failed to initialize. WebGL may not be available.
            </div>
          }>
            <Office3D agents={normalizedAgents} />
          </ErrorBoundary>
        )}
      </div>

      {/* Event feed — full width on mobile (max 40vh), fixed sidebar on desktop */}
      <div className="w-full md:w-64 flex-shrink-0 min-h-0 max-h-[40vh] md:max-h-none">
        <EventFeed events={events} />
      </div>
    </div>
  );
}

function agentPriority(a: AgentState): number {
  if (a.status === "working") return 2;
  if (a.status === "done") return 1;
  return 0;
}
