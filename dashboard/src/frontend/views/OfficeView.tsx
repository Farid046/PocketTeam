import React from "react";
import type { AgentState } from "../types";
import { AgentTile } from "../components/AgentTile";
import { EventFeed } from "../components/EventFeed";
import { EmptyState } from "./EmptyState";
import type { PocketTeamEvent } from "../types";

// Grid layout: 4 columns x 3 rows
const GRID_ROLES: string[][] = [
  ["product", "planner", "reviewer", "coo"],
  ["engineer", "qa", "security", "devops"],
  ["investigator", "documentation", "monitor", "observer"],
];

interface Props {
  agents: AgentState[];
  events: PocketTeamEvent[];
}

export function OfficeView({ agents, events }: Props): React.ReactElement {
  const agentsByRole = new Map<string, AgentState>();
  for (const agent of agents) {
    const role = agent.role.toLowerCase();
    const existing = agentsByRole.get(role);
    // Prefer working over done over idle; most recent if same status
    if (!existing || agentPriority(agent) > agentPriority(existing)) {
      agentsByRole.set(role, agent);
    }
  }

  const hasAnyActive = agents.some(
    (a) => a.status === "working" || a.status === "done"
  );

  // COO is the main session (parent) — always active when subagents exist
  if (hasAnyActive && !agentsByRole.has("coo")) {
    agentsByRole.set("coo", {
      id: "coo-main-session",
      role: "coo",
      agentType: "orchestrator",
      description: "Orchestrating tasks, delegating to agents",
      status: "working",
      startedAt: agents[0]?.startedAt ?? new Date().toISOString(),
      lastActivity: new Date().toISOString(),
      toolCallCount: agents.length,
      messageCount: 0,
      sessionId: agents[0]?.sessionId ?? "",
    });
  }

  return (
    <div className="flex gap-4 h-full">
      {/* Main grid */}
      <div className="flex-1 flex flex-col gap-4">
        {!hasAnyActive ? (
          <EmptyState agents={agents} />
        ) : (
          <div className="grid gap-3" style={{ gridTemplateColumns: "repeat(4, 1fr)" }}>
            {GRID_ROLES.flat().map((role) => {
              const agent = agentsByRole.get(role) ?? null;
              return (
                <AgentTile key={role} role={role} agent={agent} />
              );
            })}
          </div>
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
