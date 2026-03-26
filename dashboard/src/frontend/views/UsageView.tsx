import React from "react";
import type { SessionUsage, TokenUsage } from "../types";
import { ROLE_COLORS } from "../constants";

interface Props {
  usage: SessionUsage | null;
}

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function totalTokenCount(t: TokenUsage): number {
  return t.inputTokens + t.outputTokens + t.cacheCreationTokens + t.cacheReadTokens;
}

function formatCost(n: number): string {
  if (n < 0.01) return `$${n.toFixed(4)}`;
  return `$${n.toFixed(2)}`;
}

// Simple SVG donut chart
function ModelDonut({ byModel }: { byModel: Record<string, TokenUsage> }): React.ReactElement {
  const entries = Object.entries(byModel)
    .map(([model, tokens]) => ({ model, total: totalTokenCount(tokens) }))
    .filter((e) => e.total > 0)
    .sort((a, b) => b.total - a.total);

  const grandTotal = entries.reduce((s, e) => s + e.total, 0);
  if (grandTotal === 0) {
    return <div className="text-xs text-gray-600">No token data</div>;
  }

  const colors: Record<string, string> = {
    opus: "#FFD700",
    sonnet: "#5B9BD5",
    haiku: "#70AD47",
    unknown: "#808080",
  };

  const R = 40;
  const cx = 50;
  const cy = 50;
  const circumference = 2 * Math.PI * R;
  let offset = 0;

  return (
    <div className="flex items-center gap-4">
      <svg width={100} height={100} viewBox="0 0 100 100">
        {entries.map(({ model, total }) => {
          const pct = total / grandTotal;
          const dash = pct * circumference;
          const el = (
            <circle
              key={model}
              cx={cx}
              cy={cy}
              r={R}
              fill="none"
              stroke={colors[model] ?? "#808080"}
              strokeWidth={16}
              strokeDasharray={`${dash} ${circumference - dash}`}
              strokeDashoffset={-offset}
              transform={`rotate(-90 ${cx} ${cy})`}
            />
          );
          offset += dash;
          return el;
        })}
        <circle cx={cx} cy={cy} r={32} fill="#111827" />
      </svg>
      <div className="flex flex-col gap-1">
        {entries.map(({ model, total }) => (
          <div key={model} className="flex items-center gap-2 text-xs">
            <span
              className="w-2 h-2 rounded-full inline-block"
              style={{ backgroundColor: colors[model] ?? "#808080" }}
            />
            <span className="text-gray-300 capitalize">{model}</span>
            <span className="text-gray-500">
              {((total / grandTotal) * 100).toFixed(0)}% ({formatTokens(total)})
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// Per-agent breakdown table
function AgentTable({ byAgent }: { byAgent: Record<string, { role: string; tokens: TokenUsage; cost: number }> }): React.ReactElement {
  const entries = Object.entries(byAgent)
    .map(([id, data]) => ({ id, ...data, total: totalTokenCount(data.tokens) }))
    .sort((a, b) => b.total - a.total);

  // Count how many times each role appears so duplicates get a "#N" suffix
  const roleCount: Record<string, number> = {};
  for (const e of entries) {
    roleCount[e.role] = (roleCount[e.role] ?? 0) + 1;
  }
  const roleSeen: Record<string, number> = {};
  const disambiguated = entries.map((e) => {
    roleSeen[e.role] = (roleSeen[e.role] ?? 0) + 1;
    const label =
      roleCount[e.role] > 1
        ? `${e.role} #${roleSeen[e.role]}`
        : e.role;
    return { ...e, label };
  });

  const maxTokens = disambiguated.length > 0 ? disambiguated[0].total : 1;

  return (
    <div className="space-y-1">
      {disambiguated.map(({ id, label, role, total, cost }) => {
        const pct = (total / maxTokens) * 100;
        const color = ROLE_COLORS[role] ?? "#808080";
        return (
          <div key={id} className="flex items-center gap-2 text-xs">
            <span
              className="w-24 truncate font-medium flex-shrink-0"
              style={{ color }}
              title={label}
            >
              {label}
            </span>
            <div className="flex-1 h-3 bg-gray-800 rounded overflow-hidden">
              <div
                className="h-full rounded"
                style={{ width: `${pct}%`, backgroundColor: color, opacity: 0.7 }}
              />
            </div>
            <span className="w-16 text-right text-gray-400 flex-shrink-0">{formatTokens(total)}</span>
            <span className="w-14 text-right text-gray-500 flex-shrink-0">{formatCost(cost)}</span>
          </div>
        );
      })}
    </div>
  );
}

// Mini area chart for token timeline
function TokenTimeline({ timeline }: { timeline: Array<{ ts: string; tokens: number; cost: number }> }): React.ReactElement {
  if (timeline.length < 2) {
    return <div className="text-xs text-gray-600">Not enough data for timeline</div>;
  }

  const maxTokens = Math.max(...timeline.map((t) => t.tokens), 1);
  const w = 400;
  const h = 100;
  const stepX = w / (timeline.length - 1);

  const points = timeline.map((t, i) => {
    const x = i * stepX;
    const y = h - (t.tokens / maxTokens) * h;
    return `${x},${y}`;
  });

  const areaPoints = `0,${h} ${points.join(" ")} ${w},${h}`;
  const linePoints = points.join(" ");

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-24">
      <polygon points={areaPoints} fill="#22c55e" opacity={0.15} />
      <polyline points={linePoints} fill="none" stroke="#22c55e" strokeWidth={1.5} />
    </svg>
  );
}

export function UsageView({ usage }: Props): React.ReactElement {
  if (!usage) {
    return (
      <div className="flex items-center justify-center h-full text-gray-600 text-sm">
        No usage data available. Select a session with agent activity.
      </div>
    );
  }

  const total = totalTokenCount(usage.totalTokens);

  return (
    <div className="h-full overflow-y-auto space-y-4 p-2">
      {/* Stats cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard label="Session Cost" value={formatCost(usage.estimatedCost)} />
        <StatCard label="Total Tokens" value={formatTokens(total)} />
        <StatCard label="Burn Rate" value={`${formatTokens(usage.burnRate.tokensPerMin)}/min`} />
        <StatCard label="Cost Rate" value={`${formatCost(usage.burnRate.costPerHour)}/hr`} />
      </div>

      <div className="grid grid-cols-2 gap-4">
        {/* Model distribution */}
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
            By Model
          </h3>
          <ModelDonut byModel={usage.byModel} />
        </div>

        {/* Token timeline */}
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
            Token Timeline
          </h3>
          <TokenTimeline timeline={usage.timeline} />
        </div>
      </div>

      {/* Per-agent breakdown */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
          Per Agent Breakdown
        </h3>
        <AgentTable byAgent={usage.byAgent} />
      </div>

      {/* Token details */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
          Token Breakdown
        </h3>
        <div className="grid grid-cols-4 gap-3 text-xs">
          <TokenDetail label="Input" value={usage.totalTokens.inputTokens} />
          <TokenDetail label="Output" value={usage.totalTokens.outputTokens} />
          <TokenDetail label="Cache Create" value={usage.totalTokens.cacheCreationTokens} />
          <TokenDetail label="Cache Read" value={usage.totalTokens.cacheReadTokens} />
        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string }): React.ReactElement {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-3">
      <div className="text-xs text-gray-500 uppercase tracking-wider">{label}</div>
      <div className="text-lg font-semibold text-gray-100 mt-1">{value}</div>
    </div>
  );
}

function TokenDetail({ label, value }: { label: string; value: number }): React.ReactElement {
  return (
    <div>
      <div className="text-gray-500">{label}</div>
      <div className="text-gray-200 font-medium">{formatTokens(value)}</div>
    </div>
  );
}
