// Frontend types — mirrors server/readers/types.ts
// Cannot import from server code, so these are duplicated here.

export interface SubagentMeta {
  agentType: string;
  description: string;
}

export interface AgentState {
  id: string;
  role: string;          // Inferred PocketTeam role (planner, engineer, etc.)
  agentType: string;     // Raw Claude Code type (Explore, Plan, etc.)
  description: string;
  status: "idle" | "working" | "done";
  startedAt: string;     // ISO-8601
  lastActivity: string;  // ISO-8601
  toolCallCount: number;
  messageCount: number;
  sessionId: string;
}

export interface PocketTeamEvent {
  ts: string;
  agent: string;
  type: string;
  tool: string;
  status: string;
  action: string;
}

export interface AuditEntry {
  ts: string;
  event: string;
  agent: string;
  tool: string;
  input_hash: string;
  decision: string;
  layer: number | null;
  reason: string;
}

export interface AuditStats {
  total: number;
  allowed: number;
  denied: number;
  byLayer: Record<number, { allowed: number; denied: number }>;
  byTool: Record<string, { allowed: number; denied: number }>;
}

export interface DashboardSnapshot {
  agents: AgentState[];
  events: PocketTeamEvent[];
  auditStats: AuditStats;
  killSwitch: boolean;
}

export interface WsMessage {
  type:
    | "snapshot"
    | "agent:spawned"
    | "agent:update"
    | "agent:completed"
    | "event:new"
    | "audit:new"
    | "killswitch:change";
  payload: unknown;
}
