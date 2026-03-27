// Data contract — all readers produce these types

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
  role: string;          // Inferred PocketTeam role (planner, engineer, etc.)
  agentType: string;     // Raw Claude Code type (Explore, Plan, etc.)
  description: string;
  status: "idle" | "working" | "done";
  startedAt: string;     // ISO-8601
  lastActivity: string;  // ISO-8601
  toolCallCount: number;
  messageCount: number;
  sessionId: string;
  sessionActive: boolean; // true if the parent session JSONL was written within ACTIVITY_TIMEOUT_MS
  tokenUsage: TokenUsage;
  model: string;
  gitBranch: string;
}

export interface CooActivity {
  sessionId: string;
  lastToolCall: string;   // e.g. "Edit: OfficeView.tsx"
  lastActivity: string;   // ISO-8601
  isActive: boolean;      // mtime < 60s
  model: string;
  tokenUsage: TokenUsage;
  toolCallCount: number;
  messageCount: number;
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
