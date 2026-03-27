// Frontend types — mirrors server/readers/types.ts
// Cannot import from server code, so these are duplicated here.

export interface SubagentMeta {
  agentType: string;
  description: string;
}

export interface TokenUsage {
  inputTokens: number;
  outputTokens: number;
  cacheCreationTokens: number;
  cacheReadTokens: number;
}

export interface AgentState {
  id: string;
  role: string;
  agentType: string;
  description: string;
  status: "idle" | "working" | "done";
  startedAt: string;
  lastActivity: string;
  toolCallCount: number;
  messageCount: number;
  sessionId: string;
  sessionActive: boolean;
  tokenUsage: TokenUsage;
  model: string;
  gitBranch: string;
}

export interface SessionUsage {
  sessionId: string;
  totalTokens: TokenUsage;
  byModel: Record<string, TokenUsage>;
  byAgent: Record<string, { role: string; model: string; tokens: TokenUsage; cost: number }>;
  estimatedCost: number;
  burnRate: { tokensPerMin: number; costPerHour: number };
  timeline: Array<{ ts: string; tokens: number; cost: number }>;
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

export interface CooActivity {
  sessionId: string;
  lastToolCall: string;
  lastActivity: string;
  isActive: boolean;
  model: string;
  tokenUsage: TokenUsage;
  toolCallCount: number;
  messageCount: number;
  gitBranch: string;
}

export interface SessionStatus {
  contextUsedPct: number | null;
  contextRemainingPct: number | null;
  rateLimits: {
    fiveHour: number | null;
    fiveHourResetAt: string | null;
    sevenDay: number | null;
    sevenDayResetAt: string | null;
  };
  cost: number | null;
  model: string | null;
  sessionId: string | null;
  updatedAt: string;
}

export interface DashboardSnapshot {
  agents: AgentState[];
  events: PocketTeamEvent[];
  auditStats: AuditStats;
  auditEntries: AuditEntry[];
  killSwitch: boolean;
  sessionUsage: SessionUsage | null;
  cooActivity: CooActivity | null;
  sessionStatus: SessionStatus | null;
}

export interface WsMessage {
  type:
    | "snapshot"
    | "agent:spawned"
    | "agent:update"
    | "agent:completed"
    | "event:new"
    | "audit:new"
    | "killswitch:change"
    | "usage:update"
    | "session:status";
  payload: unknown;
}
