import React, { useMemo, useRef, useState } from "react";
import type { AgentState } from "../types";
import { EmptyState } from "./EmptyState";
import { ROLE_COLORS } from "../constants";
import { formatAxisTime } from "../utils/formatTime";

// Layout constants
const ROW_HEIGHT = 30;
const BAR_HEIGHT = 20;
const BAR_Y_OFFSET = (ROW_HEIGHT - BAR_HEIGHT) / 2; // 5px vertical centering
const LABEL_WIDTH = 90;
const AXIS_HEIGHT = 28;
const PADDING_RIGHT = 20;
const MIN_DURATION_PX = 4; // minimum bar width in pixels

function getRoleColor(role: string): string {
  return ROLE_COLORS[role.toLowerCase()] ?? "#6B7280";
}

function formatDuration(ms: number): string {
  const sec = Math.floor(ms / 1000);
  if (sec < 60) return `${sec}s`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ${sec % 60}s`;
  return `${Math.floor(min / 60)}h ${min % 60}m`;
}

interface GanttRow {
  role: string;
  color: string;
  bars: Array<{
    agentId: string;
    description: string;
    startTs: number;
    endTs: number;
    toolCallCount: number;
    tokenTotal: number;
    status: "idle" | "working" | "done";
  }>;
}

interface TooltipState {
  visible: boolean;
  x: number;
  y: number;
  agentId: string;
  role: string;
  description: string;
  startTs: number;
  endTs: number;
  toolCallCount: number;
  tokenTotal: number;
  status: string;
  color: string;
}

interface Props {
  agents: AgentState[];
}

export function TimelineView({ agents }: Props): React.ReactElement {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [tooltip, setTooltip] = useState<TooltipState | null>(null);

  // Filter agents that have valid time data (ignore idle with no activity)
  const activeAgents = useMemo(
    () =>
      agents.filter(
        (a) => a.startedAt && a.lastActivity && a.status !== "idle"
      ),
    [agents]
  );

  const now = Date.now();

  const { rows, minTs, maxTs } = useMemo<{
    rows: GanttRow[];
    minTs: number;
    maxTs: number;
  }>(() => {
    if (activeAgents.length === 0) {
      return { rows: [], minTs: now, maxTs: now };
    }

    const allStartTs = activeAgents.map((a) => new Date(a.startedAt).getTime());
    const allEndTs = activeAgents.map((a) =>
      Math.max(new Date(a.lastActivity).getTime(), now)
    );

    const minTs = Math.min(...allStartTs);
    const maxTs = Math.max(...allEndTs, now);

    // Group by role, preserving insertion order of first occurrence
    const roleOrder: string[] = [];
    const byRole = new Map<string, GanttRow>();

    for (const a of activeAgents) {
      const role = a.role || a.agentType;
      if (!byRole.has(role)) {
        roleOrder.push(role);
        byRole.set(role, { role, color: getRoleColor(role), bars: [] });
      }
      const row = byRole.get(role)!;
      const startTs = new Date(a.startedAt).getTime();
      const endTs =
        a.status === "working" ? now : new Date(a.lastActivity).getTime();
      const tokenTotal =
        (a.tokenUsage?.inputTokens ?? 0) +
        (a.tokenUsage?.outputTokens ?? 0) +
        (a.tokenUsage?.cacheReadTokens ?? 0);

      row.bars.push({
        agentId: a.id,
        description: a.description,
        startTs,
        endTs: Math.max(endTs, startTs + 1000),
        toolCallCount: a.toolCallCount,
        tokenTotal,
        status: a.status,
      });
    }

    // Only keep rows that have at least one bar (role with no activity is excluded)
    const rows = roleOrder
      .map((role) => byRole.get(role)!)
      .filter((row) => row.bars.length > 0);
    return { rows, minTs, maxTs };
  }, [activeAgents, now]);

  if (activeAgents.length === 0) {
    return (
      <div className="flex flex-col h-full">
        <EmptyState agents={agents} />
      </div>
    );
  }

  const totalDurationMs = maxTs - minTs;

  // Compute tick interval: aim for ~6–8 ticks, snapped to nice intervals
  const niceIntervals = [
    1 * 60 * 1000,      // 1 min
    2 * 60 * 1000,      // 2 min
    5 * 60 * 1000,      // 5 min
    10 * 60 * 1000,     // 10 min
    15 * 60 * 1000,     // 15 min
    30 * 60 * 1000,     // 30 min
    60 * 60 * 1000,     // 1 hour
  ];
  const targetTicks = 7;
  const rawInterval = totalDurationMs / targetTicks;
  const tickInterval =
    niceIntervals.find((n) => n >= rawInterval) ??
    niceIntervals[niceIntervals.length - 1];

  // Generate tick timestamps aligned to clock boundaries
  const firstTick =
    Math.ceil(minTs / tickInterval) * tickInterval;
  const ticks: number[] = [];
  for (let t = firstTick; t <= maxTs; t += tickInterval) {
    ticks.push(t);
  }

  // Chart dimensions — dynamic width based on content, minimum 400px
  const chartContentWidth = Math.max(400, totalDurationMs / 1000 * 2); // 2px per second minimum
  const svgWidth = LABEL_WIDTH + chartContentWidth + PADDING_RIGHT;
  const svgHeight = AXIS_HEIGHT + rows.length * ROW_HEIGHT + 4;

  // Convert a timestamp to an X pixel position within the chart area.
  // Newest (maxTs / now) is at the LEFT edge of the chart area;
  // oldest (minTs) is at the RIGHT edge.
  function tsToX(ts: number): number {
    return LABEL_WIDTH + (1 - (ts - minTs) / totalDurationMs) * chartContentWidth;
  }

  // For a bar that starts at startTs and ends at endTs, we need the
  // left edge of the rectangle to be the smaller x value (right side of
  // timeline = older = larger x value).
  // tsToX(endTs) <= tsToX(startTs) because endTs is newer, so:
  //   barLeft  = tsToX(endTs)
  //   barWidth = tsToX(startTs) - tsToX(endTs)

  const nowX = tsToX(now);

  function handleBarMouseEnter(
    e: React.MouseEvent,
    row: GanttRow,
    bar: GanttRow["bars"][0]
  ): void {
    const rect = (e.currentTarget as SVGRectElement).getBoundingClientRect();
    setTooltip({
      visible: true,
      x: rect.left + rect.width / 2,
      y: rect.top - 8,
      agentId: bar.agentId,
      role: row.role,
      description: bar.description,
      startTs: bar.startTs,
      endTs: bar.endTs,
      toolCallCount: bar.toolCallCount,
      tokenTotal: bar.tokenTotal,
      status: bar.status,
      color: row.color,
    });
  }

  function handleBarMouseLeave(): void {
    setTooltip(null);
  }

  return (
    <div className="flex flex-col h-full gap-2 p-2">
      <div className="flex items-center justify-between flex-shrink-0">
        <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">
          Agent Timeline
        </h2>
        <span className="text-xs text-gray-600 md:hidden">scroll horizontally</span>
      </div>

      {/* Scrollable chart container */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-x-auto overflow-y-hidden"
        style={{ minHeight: `${svgHeight + 8}px` }}
      >
        <svg
          width={svgWidth}
          height={svgHeight}
          style={{ display: "block", overflow: "visible" }}
        >
          {/* Time axis background */}
          <rect
            x={LABEL_WIDTH}
            y={0}
            width={chartContentWidth}
            height={AXIS_HEIGHT}
            fill="#111827"
          />

          {/* Tick lines and labels */}
          {ticks.map((tick) => {
            const x = tsToX(tick);
            return (
              <g key={tick}>
                <line
                  x1={x}
                  y1={AXIS_HEIGHT - 4}
                  x2={x}
                  y2={svgHeight}
                  stroke="#374151"
                  strokeWidth={1}
                  strokeDasharray="3,3"
                />
                <text
                  x={x}
                  y={AXIS_HEIGHT - 8}
                  textAnchor="middle"
                  fill="#6B7280"
                  fontSize={10}
                >
                  {formatAxisTime(tick)}
                </text>
              </g>
            );
          })}

          {/* Row backgrounds and bars */}
          {rows.map((row, rowIdx) => {
            const rowY = AXIS_HEIGHT + rowIdx * ROW_HEIGHT;
            return (
              <g key={row.role}>
                {/* Alternating row background */}
                <rect
                  x={0}
                  y={rowY}
                  width={svgWidth}
                  height={ROW_HEIGHT}
                  fill={rowIdx % 2 === 0 ? "#111827" : "#0F172A"}
                />

                {/* Role label */}
                <text
                  x={LABEL_WIDTH - 6}
                  y={rowY + ROW_HEIGHT / 2 + 4}
                  textAnchor="end"
                  fill={row.color}
                  fontSize={11}
                  fontWeight="500"
                >
                  {row.role.charAt(0).toUpperCase() + row.role.slice(1)}
                </text>

                {/* Agent bars */}
                {row.bars.map((bar) => {
                  // In the flipped layout, newer timestamps are further LEFT.
                  // tsToX(endTs) < tsToX(startTs), so endTs gives the left edge.
                  const xEnd = tsToX(bar.endTs);
                  const xStart = tsToX(bar.startTs);
                  const barW = Math.max(xStart - xEnd, MIN_DURATION_PX);
                  const barX = xEnd;
                  const barY = rowY + BAR_Y_OFFSET;
                  const isWorking = bar.status === "working";

                  return (
                    <g key={bar.agentId}>
                      <rect
                        x={barX}
                        y={barY}
                        width={barW}
                        height={BAR_HEIGHT}
                        rx={3}
                        ry={3}
                        fill={row.color}
                        fillOpacity={isWorking ? 0.9 : 0.55}
                        stroke={isWorking ? row.color : "transparent"}
                        strokeWidth={isWorking ? 1 : 0}
                        style={{ cursor: "pointer" }}
                        onMouseEnter={(e) => handleBarMouseEnter(e, row, bar)}
                        onMouseLeave={handleBarMouseLeave}
                      />
                      {/* Tool call count label — only if bar is wide enough */}
                      {barW > 24 && bar.toolCallCount > 0 && (
                        <text
                          x={barX + barW - 4}
                          y={barY + BAR_HEIGHT / 2 + 4}
                          textAnchor="end"
                          fill="rgba(255,255,255,0.75)"
                          fontSize={9}
                          style={{ pointerEvents: "none" }}
                        >
                          {bar.toolCallCount}
                        </text>
                      )}
                    </g>
                  );
                })}
              </g>
            );
          })}

          {/* Now line — solid, thick, clearly visible */}
          <line
            x1={nowX}
            y1={0}
            x2={nowX}
            y2={svgHeight}
            stroke="#FF2222"
            strokeWidth={2.5}
          />
          {/* NOW label background pill */}
          <rect
            x={nowX - 14}
            y={1}
            width={28}
            height={14}
            rx={3}
            ry={3}
            fill="#FF2222"
          />
          <text
            x={nowX}
            y={12}
            textAnchor="middle"
            fill="#FFFFFF"
            fontSize={9}
            fontWeight="700"
          >
            NOW
          </text>

          {/* Left border separating labels from chart */}
          <line
            x1={LABEL_WIDTH}
            y1={0}
            x2={LABEL_WIDTH}
            y2={svgHeight}
            stroke="#374151"
            strokeWidth={1}
          />
        </svg>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-3 pb-1 flex-shrink-0">
        {rows.map((row) => (
          <span
            key={row.role}
            className="flex items-center gap-1.5 text-xs text-gray-400"
          >
            <span
              className="inline-block w-3 h-3 rounded-sm"
              style={{ backgroundColor: row.color }}
            />
            {row.role}
          </span>
        ))}
      </div>

      {/* Tooltip — rendered in a fixed position overlay */}
      {tooltip && (
        <div
          className="fixed z-50 pointer-events-none bg-gray-900 border border-gray-700 rounded-lg p-3 text-xs shadow-xl"
          style={{
            left: tooltip.x,
            top: tooltip.y,
            transform: "translate(-50%, -100%)",
            maxWidth: "260px",
          }}
        >
          <div
            className="font-semibold text-sm mb-1"
            style={{ color: tooltip.color }}
          >
            {tooltip.role.toUpperCase()}
          </div>
          {tooltip.description && (
            <div className="text-gray-300 mb-1.5 leading-snug">
              {tooltip.description}
            </div>
          )}
          <div className="text-gray-400 space-y-0.5">
            <div>Duration: {formatDuration(tooltip.endTs - tooltip.startTs)}</div>
            <div>Tool calls: {tooltip.toolCallCount}</div>
            {tooltip.tokenTotal > 0 && (
              <div>Tokens: {tooltip.tokenTotal.toLocaleString()}</div>
            )}
            <div>
              Status:{" "}
              <span
                style={{
                  color:
                    tooltip.status === "working"
                      ? "#FBBF24"
                      : tooltip.status === "done"
                      ? "#4ADE80"
                      : "#6B7280",
                }}
              >
                {tooltip.status}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
