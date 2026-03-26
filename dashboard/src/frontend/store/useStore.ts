import { create } from "zustand";
import type {
  AgentState,
  PocketTeamEvent,
  AuditEntry,
  AuditStats,
  SessionUsage,
  CooActivity,
  SessionStatus,
  DashboardSnapshot,
} from "../types";

export type ConnectionStatus = "connected" | "reconnecting" | "disconnected" | "no-data";
export type ActiveTab = "office" | "timeline" | "safety" | "usage";

interface DashboardStore {
  agents: AgentState[];
  events: PocketTeamEvent[];
  auditEntries: AuditEntry[];
  auditStats: AuditStats | null;
  sessionUsage: SessionUsage | null;
  cooActivity: CooActivity | null;
  sessionStatus: SessionStatus | null;
  killSwitch: boolean;
  connectionStatus: ConnectionStatus;
  activeTab: ActiveTab;
  selectedSessionId: string | null;

  // Actions
  setSnapshot: (snapshot: DashboardSnapshot) => void;
  setSessionUsage: (usage: SessionUsage) => void;
  setSessionStatus: (status: SessionStatus) => void;
  addAgent: (agent: AgentState) => void;
  updateAgent: (agent: AgentState) => void;
  completeAgent: (id: string) => void;
  addEvent: (event: PocketTeamEvent) => void;
  addAudit: (entry: AuditEntry) => void;
  setKillSwitch: (active: boolean) => void;
  setConnectionStatus: (status: ConnectionStatus) => void;
  setActiveTab: (tab: ActiveTab) => void;
  setSelectedSessionId: (id: string | null) => void;
}

export const useStore = create<DashboardStore>((set, get) => ({
  agents: [],
  events: [],
  auditEntries: [],
  auditStats: null,
  sessionUsage: null,
  cooActivity: null,
  sessionStatus: null,
  killSwitch: false,
  connectionStatus: "no-data",
  activeTab: "office",
  selectedSessionId: null,

  setSnapshot: (snapshot) => {
    const prev = get();
    const events = [...prev.events];

    // Generate COO activity event if the lastToolCall changed and is not Idle
    if (
      snapshot.cooActivity?.lastToolCall &&
      snapshot.cooActivity.lastToolCall !== prev.cooActivity?.lastToolCall &&
      snapshot.cooActivity.lastToolCall !== "Idle"
    ) {
      events.push({
        ts: new Date().toISOString(),
        agent: "COO",
        type: "tool",
        tool: snapshot.cooActivity.lastToolCall.split(":")[0] ?? "",
        status: "working",
        action: snapshot.cooActivity.lastToolCall,
      });
      if (events.length > 200) events.splice(0, events.length - 200);
    }

    return set({
      agents: snapshot.agents,
      events,
      auditStats: snapshot.auditStats,
      auditEntries: snapshot.auditEntries ?? prev.auditEntries,
      killSwitch: snapshot.killSwitch,
      sessionUsage: snapshot.sessionUsage ?? null,
      cooActivity: snapshot.cooActivity ?? null,
      sessionStatus: snapshot.sessionStatus ?? prev.sessionStatus,
    });
  },

  setSessionUsage: (usage) => set({ sessionUsage: usage }),

  setSessionStatus: (status: SessionStatus) => set({ sessionStatus: status }),

  addAgent: (agent) =>
    set((state) => {
      const newEvent: PocketTeamEvent = {
        ts: new Date().toISOString(),
        agent: agent.role,
        type: "spawn",
        tool: "",
        status: agent.status,
        action: agent.description,
      };
      return {
        agents: [...state.agents.filter((a) => a.id !== agent.id), agent],
        events: [...state.events.slice(-199), newEvent],
      };
    }),

  updateAgent: (agent) =>
    set((state) => {
      const prev = state.agents.find((a) => a.id === agent.id);
      const events = [...state.events];
      // Only generate event if status actually changed
      if (prev && prev.status !== agent.status) {
        events.push({
          ts: new Date().toISOString(),
          agent: agent.role,
          type: "status",
          tool: "",
          status: agent.status,
          action:
            agent.status === "done"
              ? `Finished (${agent.toolCallCount} tool calls)`
              : agent.description,
        });
        if (events.length > 200) events.splice(0, events.length - 200);
      }
      return {
        agents: state.agents.map((a) => (a.id === agent.id ? agent : a)),
        events,
      };
    }),

  completeAgent: (id) =>
    set((state) => {
      const agent = state.agents.find((a) => a.id === id);
      const newEvent: PocketTeamEvent = {
        ts: new Date().toISOString(),
        agent: agent?.role ?? "unknown",
        type: "complete",
        tool: "",
        status: "done",
        action: "Completed",
      };
      return {
        agents: state.agents.map((a) =>
          a.id === id ? { ...a, status: "done" as const } : a
        ),
        events: [...state.events.slice(-199), newEvent],
      };
    }),

  addEvent: (event) =>
    set((state) => ({
      events: [...state.events.slice(-199), event],
    })),

  addAudit: (entry) =>
    set((state) => {
      const entries = [...state.auditEntries.slice(-499), entry];
      const isAllowed = entry.decision.startsWith("ALLOWED") || entry.decision.toLowerCase() === "allowed";
      const isDenied = entry.decision.startsWith("DENIED");
      const prev = state.auditStats ?? {
        total: 0,
        allowed: 0,
        denied: 0,
        byLayer: {},
        byTool: {},
      };

      const byLayer = { ...prev.byLayer };
      if (entry.layer !== null) {
        const layer = entry.layer;
        const existing = byLayer[layer] ?? { allowed: 0, denied: 0 };
        byLayer[layer] = {
          allowed: existing.allowed + (isAllowed ? 1 : 0),
          denied: existing.denied + (isDenied ? 1 : 0),
        };
      }

      const byTool = { ...prev.byTool };
      const toolKey = entry.tool;
      const existingTool = byTool[toolKey] ?? { allowed: 0, denied: 0 };
      byTool[toolKey] = {
        allowed: existingTool.allowed + (isAllowed ? 1 : 0),
        denied: existingTool.denied + (isDenied ? 1 : 0),
      };

      return {
        auditEntries: entries,
        auditStats: {
          total: prev.total + 1,
          allowed: prev.allowed + (isAllowed ? 1 : 0),
          denied: prev.denied + (isDenied ? 1 : 0),
          byLayer,
          byTool,
        },
      };
    }),

  setKillSwitch: (active) => set({ killSwitch: active }),

  setConnectionStatus: (status) => set({ connectionStatus: status }),

  setActiveTab: (tab) => set({ activeTab: tab }),

  setSelectedSessionId: (id) => set({ selectedSessionId: id }),
}));
