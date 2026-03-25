import { create } from "zustand";
import type {
  AgentState,
  PocketTeamEvent,
  AuditEntry,
  AuditStats,
  DashboardSnapshot,
} from "../types";

export type ConnectionStatus = "connected" | "reconnecting" | "disconnected" | "no-data";
export type ActiveTab = "office" | "timeline" | "safety";

interface DashboardStore {
  agents: AgentState[];
  events: PocketTeamEvent[];
  auditEntries: AuditEntry[];
  auditStats: AuditStats | null;
  killSwitch: boolean;
  connectionStatus: ConnectionStatus;
  activeTab: ActiveTab;

  // Actions
  setSnapshot: (snapshot: DashboardSnapshot) => void;
  addAgent: (agent: AgentState) => void;
  updateAgent: (agent: AgentState) => void;
  completeAgent: (id: string) => void;
  addEvent: (event: PocketTeamEvent) => void;
  addAudit: (entry: AuditEntry) => void;
  setKillSwitch: (active: boolean) => void;
  setConnectionStatus: (status: ConnectionStatus) => void;
  setActiveTab: (tab: ActiveTab) => void;
}

export const useStore = create<DashboardStore>((set) => ({
  agents: [],
  events: [],
  auditEntries: [],
  auditStats: null,
  killSwitch: false,
  connectionStatus: "no-data",
  activeTab: "office",

  setSnapshot: (snapshot) =>
    set({
      agents: snapshot.agents,
      events: snapshot.events,
      auditStats: snapshot.auditStats,
      killSwitch: snapshot.killSwitch,
    }),

  addAgent: (agent) =>
    set((state) => ({
      agents: [...state.agents.filter((a) => a.id !== agent.id), agent],
    })),

  updateAgent: (agent) =>
    set((state) => ({
      agents: state.agents.map((a) => (a.id === agent.id ? agent : a)),
    })),

  completeAgent: (id) =>
    set((state) => ({
      agents: state.agents.map((a) =>
        a.id === id ? { ...a, status: "done" as const } : a
      ),
    })),

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
}));
