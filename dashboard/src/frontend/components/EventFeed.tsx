import React, { useState } from "react";
import type { PocketTeamEvent } from "../types";
import { ROLE_COLORS } from "../constants";

function getRoleColor(role: string): string {
  const normalized = role.toLowerCase();
  for (const key of Object.keys(ROLE_COLORS)) {
    if (normalized.includes(key)) {
      return ROLE_COLORS[key];
    }
  }
  return "#6B7280";
}

const TOOL_COLORS: Record<string, string> = {
  Read: "#60A5FA",
  Edit: "#FBBF24",
  Write: "#34D399",
  Bash: "#F97316",
  Grep: "#A78BFA",
  Glob: "#A78BFA",
  Agent: "#EC4899",
  WebFetch: "#06B6D4",
  WebSearch: "#06B6D4",
};

function getToolColor(tool: string): string {
  if (!tool) return "#6B7280";
  for (const [key, color] of Object.entries(TOOL_COLORS)) {
    if (tool.toLowerCase().includes(key.toLowerCase())) return color;
  }
  return "#6B7280";
}

function relativeTime(isoTs: string): string {
  const diffMs = Date.now() - new Date(isoTs).getTime();
  const diffSec = Math.floor(diffMs / 1000);
  if (diffSec < 60) return `${diffSec}s ago`;
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHour = Math.floor(diffMin / 60);
  return `${diffHour}h ago`;
}

interface Props {
  events: PocketTeamEvent[];
}

const MAX_EVENTS = 50;

function getTypeIndicatorColor(type: string, tool: string): string {
  switch (type) {
    case "spawn":
      return "#22D3EE"; // cyan
    case "status":
      return "#FBBF24"; // yellow
    case "complete":
      return "#6B7280"; // gray
    case "tool":
      return getToolColor(tool);
    default:
      return "#6B7280";
  }
}

export function EventFeed({ events }: Props): React.ReactElement {
  const recent = events.slice(-MAX_EVENTS).reverse();
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);

  function toggleExpand(index: number): void {
    setExpandedIndex((prev) => (prev === index ? null : index));
  }

  return (
    <aside className="flex flex-col h-full bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
      <div className="px-3 py-2 border-b border-gray-800">
        <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
          Event Feed
        </h2>
      </div>
      <div className="flex-1 overflow-y-auto p-2 space-y-1.5">
        {recent.length === 0 ? (
          <p className="text-xs text-gray-600 text-center mt-4">No events yet</p>
        ) : (
          recent.map((evt, i) => {
            const roleColor = getRoleColor(evt.agent);
            const dotColor = getTypeIndicatorColor(evt.type, evt.tool);
            const isExpanded = expandedIndex === i;
            const isExpandable = Boolean(evt.action || evt.tool);
            return (
              <div
                key={`${evt.ts}-${evt.agent}-${evt.tool}-${i}`}
                className={`flex flex-col gap-1 p-2 rounded bg-gray-950/60 border border-gray-800/50 ${
                  isExpandable ? "cursor-pointer hover:border-gray-700 hover:bg-gray-900/60" : ""
                }`}
                onClick={isExpandable ? () => toggleExpand(i) : undefined}
                title={isExpandable && !isExpanded ? (evt.action || evt.tool) : undefined}
              >
                <div className="flex items-center justify-between gap-1">
                  <div className="flex items-center gap-1.5 min-w-0">
                    <span
                      className="flex-shrink-0 w-2 h-2 rounded-full"
                      style={{ backgroundColor: dotColor }}
                    />
                    <span
                      className="text-xs font-medium truncate"
                      style={{ color: roleColor }}
                    >
                      {evt.agent || "unknown"}
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5 flex-shrink-0">
                    <span className="text-xs text-gray-600">
                      {relativeTime(evt.ts)}
                    </span>
                    {isExpandable && (
                      <span className="text-gray-700 text-xs leading-none select-none">
                        {isExpanded ? "\u25B4" : "\u25BE"}
                      </span>
                    )}
                  </div>
                </div>
                {evt.action && (
                  <span
                    className={`text-xs text-gray-500 pl-3.5 ${isExpanded ? "whitespace-pre-wrap break-words" : "truncate"}`}
                  >
                    {evt.action}
                  </span>
                )}
                {evt.tool && (
                  <span
                    className={`text-xs pl-3.5 ${isExpanded ? "whitespace-pre-wrap break-words" : "truncate"}`}
                    style={{ color: getToolColor(evt.tool) }}
                  >
                    {evt.tool}
                  </span>
                )}
              </div>
            );
          })
        )}
      </div>
    </aside>
  );
}
