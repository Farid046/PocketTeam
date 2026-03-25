import React from "react";
import type { AgentState } from "../types";
import { EventFeed } from "../components/EventFeed";
import { EmptyState } from "./EmptyState";
import { FloorPlan } from "../components/office/FloorPlan";
import type { PocketTeamEvent } from "../types";

interface Props {
  agents: AgentState[];
  events: PocketTeamEvent[];
}

export function OfficeView({ agents, events }: Props): React.ReactElement {
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

  // COO is the main session (parent) — always active when subagents exist
  if (hasAnyActive && !agentsByRole.has("coo")) {
    const anyWorking = agents.some((a) => a.status === "working");
    const cooStatus = anyWorking ? "working" : "done";
    agentsByRole.set("coo", {
      id: "coo-main-session",
      role: "coo",
      agentType: "orchestrator",
      description: "Orchestrating tasks, delegating to agents",
      status: cooStatus,
      startedAt: agents[0]?.startedAt ?? new Date().toISOString(),
      lastActivity: new Date().toISOString(),
      toolCallCount: agents.length,
      messageCount: 0,
      sessionId: agents[0]?.sessionId ?? "",
    });
  }

  // Flatten back to array for FloorPlan
  const normalizedAgents = Array.from(agentsByRole.values());

  return (
    <div className="flex gap-4 h-full">
      {/* Main office floor plan */}
      <div className="flex-1 min-w-0" style={{ minHeight: "400px" }}>
        {!hasAnyActive ? (
          <EmptyState agents={agents} />
        ) : (
          <FloorPlan agents={normalizedAgents} events={events} />
        )}
      </div>

      {/* Right sidebar — event feed */}
      <div className="w-56 flex-shrink-0 h-full" style={{ minHeight: "400px" }}>
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
