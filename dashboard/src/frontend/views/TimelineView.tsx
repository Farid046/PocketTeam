import React, { useMemo } from "react";
import {
  ComposedChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
  LabelList,
} from "recharts";
import type { AgentState } from "../types";
import { EmptyState } from "./EmptyState";
import { ROLE_COLORS } from "../constants";

function getRoleColor(role: string): string {
  return ROLE_COLORS[role.toLowerCase()] ?? "#6B7280";
}

interface TimelineEntry {
  role: string;
  agentId: string;
  start: number; // epoch ms, relative offset from min
  duration: number; // ms
  toolCallCount: number;
  color: string;
}

interface Props {
  agents: AgentState[];
}

interface TooltipPayload {
  payload: TimelineEntry;
}

function formatDuration(ms: number): string {
  const sec = Math.floor(ms / 1000);
  if (sec < 60) return `${sec}s`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ${sec % 60}s`;
  return `${Math.floor(min / 60)}h ${min % 60}m`;
}

function formatMs(ms: number): string {
  const sec = Math.floor(ms / 1000);
  if (sec < 60) return `${sec}s`;
  return `${Math.floor(sec / 60)}m`;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: TooltipPayload[];
}

function CustomTooltip({ active, payload }: CustomTooltipProps): React.ReactElement | null {
  if (!active || !payload || payload.length === 0) return null;
  const entry = payload[0].payload;
  return (
    <div className="bg-gray-900 border border-gray-700 rounded p-2 text-xs">
      <div className="font-semibold" style={{ color: entry.color }}>
        {entry.role.toUpperCase()}
      </div>
      <div className="text-gray-400">Duration: {formatDuration(entry.duration)}</div>
      <div className="text-gray-400">Tool calls: {entry.toolCallCount}</div>
    </div>
  );
}

export function TimelineView({ agents }: Props): React.ReactElement {
  const activeAgents = agents.filter((a) => a.status !== "idle");

  const data = useMemo<TimelineEntry[]>(() => {
    if (activeAgents.length === 0) return [];

    const minStart = Math.min(
      ...activeAgents.map((a) => new Date(a.startedAt).getTime())
    );

    return activeAgents.map((agent) => {
      const start = new Date(agent.startedAt).getTime() - minStart;
      const end = new Date(agent.lastActivity).getTime();
      const duration = Math.max(end - new Date(agent.startedAt).getTime(), 1000);
      return {
        role: agent.role || agent.agentType,
        agentId: agent.id,
        start,
        duration,
        toolCallCount: agent.toolCallCount,
        color: getRoleColor(agent.role),
      };
    });
  }, [activeAgents]);

  if (activeAgents.length === 0) {
    return (
      <div className="flex flex-col h-full">
        <EmptyState agents={agents} />
      </div>
    );
  }

  // Compute max for x-axis ticks
  const maxTime = Math.max(...data.map((d) => d.start + d.duration));

  const tickCount = Math.min(8, Math.floor(maxTime / 5000) + 2);
  const tickValues = Array.from({ length: tickCount }, (_, i) =>
    Math.round((maxTime / (tickCount - 1)) * i)
  );

  return (
    <div className="flex flex-col h-full gap-4 p-2">
      <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">
        Agent Timeline
      </h2>

      <div className="flex-1" style={{ minHeight: "300px" }}>
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart
            layout="vertical"
            data={data}
            margin={{ top: 8, right: 40, left: 80, bottom: 16 }}
          >
            <XAxis
              type="number"
              dataKey="start"
              domain={[0, maxTime]}
              ticks={tickValues}
              tickFormatter={formatMs}
              tick={{ fill: "#6B7280", fontSize: 11 }}
              axisLine={{ stroke: "#374151" }}
              tickLine={false}
            />
            <YAxis
              type="category"
              dataKey="role"
              tick={{ fill: "#9CA3AF", fontSize: 11 }}
              axisLine={false}
              tickLine={false}
              width={72}
            />
            <Tooltip content={<CustomTooltip />} cursor={{ fill: "rgba(255,255,255,0.03)" }} />

            {/* Invisible bar for offset (stack base) */}
            <Bar dataKey="start" stackId="a" fill="transparent" />

            {/* Actual duration bar */}
            <Bar dataKey="duration" stackId="a" radius={[0, 4, 4, 0]}>
              {data.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.color} fillOpacity={0.85} />
              ))}
              <LabelList
                dataKey="toolCallCount"
                position="insideRight"
                formatter={(v: number) => (v > 0 ? `${v}` : "")}
                style={{ fill: "rgba(255,255,255,0.7)", fontSize: 10 }}
              />
            </Bar>
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-3 pb-2">
        {data.map((entry) => (
          <span key={entry.agentId} className="flex items-center gap-1.5 text-xs text-gray-400">
            <span
              className="inline-block w-3 h-3 rounded-sm"
              style={{ backgroundColor: entry.color }}
            />
            {entry.role}
          </span>
        ))}
      </div>
    </div>
  );
}
