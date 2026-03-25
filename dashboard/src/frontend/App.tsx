import React from "react";
import { useStore } from "./store/useStore";
import { useWebSocket } from "./ws/useWebSocket";
import { ConnectionBadge } from "./components/ConnectionBadge";
import { KillSwitchBanner } from "./components/KillSwitchBanner";
import { SessionPicker } from "./components/SessionPicker";
import { OfficeView } from "./views/OfficeView";
import { TimelineView } from "./views/TimelineView";
import { SafetyView } from "./views/SafetyView";
import type { ActiveTab } from "./store/useStore";

const TABS: { id: ActiveTab; label: string }[] = [
  { id: "office", label: "Office" },
  { id: "timeline", label: "Timeline" },
  { id: "safety", label: "Safety" },
];

export default function App(): React.ReactElement {
  useWebSocket();

  const agents = useStore((s) => s.agents);
  const events = useStore((s) => s.events);
  const auditStats = useStore((s) => s.auditStats);
  const auditEntries = useStore((s) => s.auditEntries);
  const killSwitch = useStore((s) => s.killSwitch);
  const connectionStatus = useStore((s) => s.connectionStatus);
  const activeTab = useStore((s) => s.activeTab);
  const setActiveTab = useStore((s) => s.setActiveTab);

  // Session info
  const activeSessions = new Set(agents.map((a) => a.sessionId));
  const activeAgentCount = agents.filter((a) => a.status === "working").length;
  const sessionLabel =
    activeSessions.size === 0
      ? null
      : activeSessions.size === 1
      ? `Session ${[...activeSessions][0].slice(0, 8)}`
      : `${activeSessions.size} sessions`;

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 font-mono flex flex-col">
      {killSwitch && <KillSwitchBanner />}

      {/* Header */}
      <header
        className={`flex items-center justify-between px-5 py-3 border-b border-gray-800 bg-gray-950 flex-shrink-0 ${
          killSwitch ? "mt-10" : ""
        }`}
      >
        <div className="flex items-center gap-4">
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

          <SessionPicker
            agents={agents}
            selectedSessionId={null}
            onSelect={() => {
              // Future: filter view by session
            }}
          />
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
      <main className="flex-1 overflow-hidden p-4" style={{ minHeight: 0 }}>
        {activeTab === "office" && (
          <div className="h-full">
            <OfficeView agents={agents} events={events} />
          </div>
        )}
        {activeTab === "timeline" && (
          <div className="h-full">
            <TimelineView agents={agents} />
          </div>
        )}
        {activeTab === "safety" && (
          <div className="h-full">
            <SafetyView auditStats={auditStats} auditEntries={auditEntries} />
          </div>
        )}
      </main>
    </div>
  );
}
