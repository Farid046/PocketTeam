import { TokenUsage, SessionUsage, AgentState } from "./types.js";

// Model pricing per million tokens (USD)
const MODEL_PRICING: Record<string, { input: number; output: number }> = {
  "claude-opus-4-6":   { input: 15, output: 75 },
  "claude-opus-4-5":   { input: 15, output: 75 },
  "claude-sonnet-4-6": { input: 3, output: 15 },
  "claude-sonnet-4-5": { input: 3, output: 15 },
  "claude-haiku-4-5":  { input: 0.25, output: 1.25 },
};

// Cache pricing multipliers relative to input rate
const CACHE_CREATE_MULTIPLIER = 1.25;
const CACHE_READ_MULTIPLIER = 0.1;

function getModelFamily(model: string): string {
  const lower = model.toLowerCase();
  if (lower.includes("opus")) return "opus";
  if (lower.includes("haiku")) return "haiku";
  if (lower.includes("sonnet")) return "sonnet";
  return "unknown";
}

function getPricing(model: string): { input: number; output: number } {
  // Exact match first
  if (MODEL_PRICING[model]) return MODEL_PRICING[model];
  // Family fallback
  const family = getModelFamily(model);
  if (family === "opus") return { input: 15, output: 75 };
  if (family === "haiku") return { input: 0.25, output: 1.25 };
  return { input: 3, output: 15 }; // default to sonnet
}

function calcCost(tokens: TokenUsage, model: string): number {
  const pricing = getPricing(model);
  const inputCost = (tokens.inputTokens / 1_000_000) * pricing.input;
  const outputCost = (tokens.outputTokens / 1_000_000) * pricing.output;
  const cacheCreateCost = (tokens.cacheCreationTokens / 1_000_000) * pricing.input * CACHE_CREATE_MULTIPLIER;
  const cacheReadCost = (tokens.cacheReadTokens / 1_000_000) * pricing.input * CACHE_READ_MULTIPLIER;
  return inputCost + outputCost + cacheCreateCost + cacheReadCost;
}

const ZERO_TOKENS: TokenUsage = { inputTokens: 0, outputTokens: 0, cacheCreationTokens: 0, cacheReadTokens: 0 };

function addTokens(a: TokenUsage, b: TokenUsage): TokenUsage {
  return {
    inputTokens: a.inputTokens + b.inputTokens,
    outputTokens: a.outputTokens + b.outputTokens,
    cacheCreationTokens: a.cacheCreationTokens + b.cacheCreationTokens,
    cacheReadTokens: a.cacheReadTokens + b.cacheReadTokens,
  };
}

export class UsageReader {
  computeSessionUsage(sessionId: string, agents: AgentState[]): SessionUsage {
    const sessionAgents = agents.filter((a) => a.sessionId === sessionId);

    let totalTokens: TokenUsage = { ...ZERO_TOKENS };
    const byModel: Record<string, TokenUsage> = {};
    const byAgent: Record<string, { role: string; model: string; tokens: TokenUsage; cost: number }> = {};
    let totalCost = 0;

    for (const agent of sessionAgents) {
      const t = agent.tokenUsage;
      totalTokens = addTokens(totalTokens, t);

      // By model
      const modelKey = getModelFamily(agent.model) || "unknown";
      byModel[modelKey] = addTokens(byModel[modelKey] ?? { ...ZERO_TOKENS }, t);

      // By agent
      const agentCost = calcCost(t, agent.model);
      byAgent[agent.id] = { role: agent.role, model: getModelFamily(agent.model), tokens: t, cost: agentCost };
      totalCost += agentCost;
    }

    // Burn rate: tokens per minute over the active window
    const now = Date.now();
    let earliestMs = now;
    let latestMs = 0;
    for (const agent of sessionAgents) {
      const start = new Date(agent.startedAt).getTime();
      const last = new Date(agent.lastActivity).getTime();
      if (start > 0 && start < earliestMs) earliestMs = start;
      if (last > latestMs) latestMs = last;
    }
    const durationMin = Math.max(1, (latestMs - earliestMs) / 60_000);
    const totalTok = totalTokens.inputTokens + totalTokens.outputTokens +
      totalTokens.cacheCreationTokens + totalTokens.cacheReadTokens;
    const tokensPerMin = totalTok / durationMin;
    const costPerHour = (totalCost / durationMin) * 60;

    // Simple timeline: bucket by 5-min intervals (from agent start/activity times)
    const timeline: Array<{ ts: string; tokens: number; cost: number }> = [];
    if (sessionAgents.length > 0) {
      const bucketMs = 5 * 60_000;
      const start = Math.floor(earliestMs / bucketMs) * bucketMs;
      const end = Math.ceil(latestMs / bucketMs) * bucketMs;
      for (let t = start; t <= end; t += bucketMs) {
        // Approximate: distribute each agent's tokens evenly across its active window
        let bucketTokens = 0;
        let bucketCost = 0;
        for (const agent of sessionAgents) {
          const aStart = new Date(agent.startedAt).getTime();
          const aEnd = new Date(agent.lastActivity).getTime();
          const aDuration = Math.max(1, aEnd - aStart);
          const overlap = Math.max(0, Math.min(t + bucketMs, aEnd) - Math.max(t, aStart));
          if (overlap > 0) {
            const fraction = overlap / aDuration;
            const aTok = agent.tokenUsage.inputTokens + agent.tokenUsage.outputTokens +
              agent.tokenUsage.cacheCreationTokens + agent.tokenUsage.cacheReadTokens;
            bucketTokens += aTok * fraction;
            bucketCost += calcCost(agent.tokenUsage, agent.model) * fraction;
          }
        }
        timeline.push({ ts: new Date(t).toISOString(), tokens: Math.round(bucketTokens), cost: Math.round(bucketCost * 10000) / 10000 });
      }
    }

    return {
      sessionId,
      totalTokens,
      byModel,
      byAgent,
      estimatedCost: Math.round(totalCost * 10000) / 10000,
      burnRate: { tokensPerMin: Math.round(tokensPerMin), costPerHour: Math.round(costPerHour * 10000) / 10000 },
      timeline,
    };
  }
}
