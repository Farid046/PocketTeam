import React from "react";
import { useStore } from "./store/useStore";
import { useWebSocket } from "./ws/useWebSocket";
import { ConnectionBadge } from "./components/ConnectionBadge";
import { KillSwitchBanner } from "./components/KillSwitchBanner";
import { SessionPicker } from "./components/SessionPicker";
import { OfficeView } from "./views/OfficeView";
import { TimelineView } from "./views/TimelineView";
import { SafetyView } from "./views/SafetyView";
import { UsageView } from "./views/UsageView";
import type { ActiveTab } from "./store/useStore";

function formatModelName(model: string): string {
  const match = model.match(/(opus|sonnet|haiku)[- ]?(\d+)[- .]?(\d+)/i);
  if (match) {
    return `${match[1].charAt(0).toUpperCase() + match[1].slice(1)} ${match[2]}.${match[3]}`;
  }
  return model;
}

function truncateBranch(branch: string, maxLen: number = 20): string {
  if (branch.length <= maxLen) return branch;
  return branch.slice(0, maxLen - 1) + "\u2026";
}

function formatTokenRate(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K/min`;
  return `${n}/min`;
}

const TABS: { id: ActiveTab; label: string }[] = [
  { id: "office", label: "Office" },
  { id: "timeline", label: "Timeline" },
  { id: "safety", label: "Safety" },
  { id: "usage", label: "Usage" },
];

export default function App(): React.ReactElement {
  useWebSocket();

  const agents = useStore((s) => s.agents);
  const events = useStore((s) => s.events);
  const auditStats = useStore((s) => s.auditStats);
  const auditEntries = useStore((s) => s.auditEntries);
  const sessionUsage = useStore((s) => s.sessionUsage);
  const cooActivity = useStore((s) => s.cooActivity);
  const sessionStatus = useStore((s) => s.sessionStatus);
  const killSwitch = useStore((s) => s.killSwitch);
  const connectionStatus = useStore((s) => s.connectionStatus);
  const activeTab = useStore((s) => s.activeTab);
  const setActiveTab = useStore((s) => s.setActiveTab);
  const selectedSessionId = useStore((s) => s.selectedSessionId);

  // Session filtering
  const visibleAgents = selectedSessionId
    ? agents.filter((a) => a.sessionId === selectedSessionId)
    : agents;

  // Session info
  const activeSessions = new Set(agents.map((a) => a.sessionId));
  const activeAgentCount = visibleAgents.filter((a) => a.status === "working").length;
  const sessionLabel =
    activeSessions.size === 0
      ? null
      : activeSessions.size === 1
      ? `Session ${[...activeSessions][0].slice(0, 8)}`
      : `${activeSessions.size} sessions`;

  return (
    <div className="h-screen bg-gray-950 text-gray-100 font-mono flex flex-col overflow-hidden">
      {killSwitch && <KillSwitchBanner />}

      {/* Header */}
      <header
        className={`flex items-center justify-between px-5 py-2 border-b border-gray-800 bg-gray-950 flex-shrink-0 flex-wrap gap-y-1.5 ${
          killSwitch ? "mt-10" : ""
        }`}
      >
        {/* Primary row: always-visible chips */}
        <div className="flex items-center flex-wrap gap-2">
          <h1 className="text-sm font-semibold text-gray-200 tracking-tight">
            PocketTeam Dashboard
          </h1>

          {sessionLabel && (
            <span className="text-xs text-gray-600 border border-gray-800 rounded px-2 py-0.5">
              {sessionLabel}
            </span>
          )}

          {activeAgentCount > 0 && (
            <span className="text-xs text-green-400 border border-green-900 rounded px-2 py-0.5">
              {activeAgentCount} active
            </span>
          )}

          {cooActivity?.model && (
            <span className="text-xs text-gray-400 border border-gray-800 rounded px-2 py-0.5">
              {formatModelName(cooActivity.model)}
            </span>
          )}

          {cooActivity?.gitBranch && (
            <span
              className="text-xs text-gray-400 border border-gray-800 rounded px-2 py-0.5 max-w-[12rem] truncate"
              title={cooActivity.gitBranch}
            >
              {truncateBranch(cooActivity.gitBranch)}
            </span>
          )}

          {sessionUsage?.estimatedCost != null && (
            <span className="text-xs text-gray-400 border border-gray-800 rounded px-2 py-0.5">
              ${sessionUsage.estimatedCost.toFixed(2)}
            </span>
          )}

          {sessionStatus?.contextUsedPct != null && (
            <span className="text-xs text-gray-400 border border-gray-800 rounded px-2 py-0.5 flex items-center gap-1.5">
              <span className="text-gray-500">Ctx</span>
              <span className="inline-block w-16 h-1.5 bg-gray-800 rounded-full overflow-hidden">
                <span
                  className="block h-full rounded-full"
                  style={{
                    width: `${sessionStatus.contextUsedPct}%`,
                    backgroundColor:
                      sessionStatus.contextUsedPct > 85 ? "#ef4444" :
                      sessionStatus.contextUsedPct > 70 ? "#eab308" : "#22c55e",
                  }}
                />
              </span>
              <span>{sessionStatus.contextUsedPct}%</span>
            </span>
          )}

          {/* Secondary chips: less important stats that wrap gracefully */}
          {sessionUsage?.burnRate?.tokensPerMin != null && (
            <span className="text-xs text-gray-500 border border-gray-800 rounded px-2 py-0.5">
              {formatTokenRate(sessionUsage.burnRate.tokensPerMin)}
            </span>
          )}

          {sessionUsage?.burnRate?.costPerHour != null && (
            <span className="text-xs text-gray-500 border border-gray-800 rounded px-2 py-0.5">
              ~${sessionUsage.burnRate.costPerHour.toFixed(2)}/hr
            </span>
          )}

          {sessionStatus?.rateLimits?.fiveHour != null && (
            <span className="text-xs text-gray-500 border border-gray-800 rounded px-2 py-0.5">
              5h: {sessionStatus.rateLimits.fiveHour}%
            </span>
          )}

          <SessionPicker agents={agents} />
        </div>

        <div className="flex items-center gap-4">
          <ConnectionBadge status={connectionStatus} />
        </div>
      </header>

      {/* Tab bar */}
      <nav className="flex border-b border-gray-800 bg-gray-950 flex-shrink-0">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-5 py-2.5 text-xs font-medium tracking-wider uppercase transition-colors border-b-2 ${
              activeTab === tab.id
                ? "text-gray-100 border-gray-300"
                : "text-gray-500 border-transparent hover:text-gray-300 hover:border-gray-600"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      {/* Main content */}
      <main className="flex-1 overflow-hidden px-2 py-1" style={{ minHeight: 0 }}>
        {activeTab === "office" && (
          <div className="h-full">
            <OfficeView agents={visibleAgents} events={events} />
          </div>
        )}
        {activeTab === "timeline" && (
          <div className="h-full">
            <TimelineView agents={visibleAgents} />
          </div>
        )}
        {activeTab === "safety" && (
          <div className="h-full">
            <SafetyView auditStats={auditStats} auditEntries={auditEntries} />
          </div>
        )}
        {activeTab === "usage" && (
          <div className="h-full">
            <UsageView usage={sessionUsage} />
          </div>
        )}
      </main>
    </div>
  );
}
