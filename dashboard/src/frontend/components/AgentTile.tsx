import React from "react";
import type { AgentState } from "../types";
import { ROLE_COLORS } from "../constants";

function getRoleColor(role: string): string {
  return ROLE_COLORS[role.toLowerCase()] ?? "#6B7280";
}

interface StatusDotProps {
  status: AgentState["status"];
}

function StatusDot({ status }: StatusDotProps): React.ReactElement {
  if (status === "working") {
    return (
      <span className="inline-flex items-center justify-center w-3 h-3 rounded-full bg-green-400 animate-pulse" />
    );
  }
  if (status === "done") {
    return (
      <span className="inline-flex items-center justify-center w-3 h-3 rounded-full bg-gray-600 text-gray-300">
        <svg width="8" height="8" viewBox="0 0 8 8" fill="none">
          <path d="M1 4l2 2 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </span>
    );
  }
  // idle
  return <span className="inline-flex w-3 h-3 rounded-full bg-gray-700" />;
}

interface Props {
  agent: AgentState | null;
  role: string;
}

const MAX_DESCRIPTION_CHARS = 60;

export function AgentTile({ agent, role }: Props): React.ReactElement {
  const color = getRoleColor(role);
  const isActive = agent !== null && agent.status !== "idle";
  const isDone = agent?.status === "done";
  const isWorking = agent?.status === "working";

  const description = agent?.description ?? "";
  const truncatedDescription =
    description.length > MAX_DESCRIPTION_CHARS
      ? `${description.slice(0, MAX_DESCRIPTION_CHARS)}...`
      : description;

  const borderStyle = isActive
    ? { borderColor: color, borderWidth: "2px" }
    : { borderColor: "#1F2937", borderWidth: "1px" };

  const bgClass = isWorking
    ? "bg-gray-900"
    : isDone
    ? "bg-gray-900/60"
    : "bg-gray-900/30";

  const opacityClass = agent === null ? "opacity-40" : "opacity-100";

  return (
    <div
      className={`relative flex flex-col p-3 rounded-lg border transition-all duration-300 ${bgClass} ${opacityClass}`}
      style={borderStyle}
    >
      {/* Header row */}
      <div className="flex items-center justify-between mb-2">
        {/* Avatar */}
        <span
          className="flex items-center justify-center w-7 h-7 rounded-full text-xs font-bold text-gray-950 flex-shrink-0"
          style={{ backgroundColor: color }}
        >
          {role.charAt(0).toUpperCase()}
        </span>

        {/* Status dot */}
        <StatusDot status={agent?.status ?? "idle"} />
      </div>

      {/* Role name */}
      <span
        className="text-xs font-semibold uppercase tracking-wider mb-1"
        style={{ color: isActive ? color : "#9CA3AF" }}
      >
        {role}
      </span>

      {/* Description */}
      {truncatedDescription ? (
        <span className="text-xs text-gray-400 leading-relaxed min-h-[32px]">
          {truncatedDescription}
        </span>
      ) : (
        <span className="text-xs text-gray-700 min-h-[32px] italic">idle</span>
      )}

      {/* Tool call count when active */}
      {agent && agent.toolCallCount > 0 && (
        <span className="mt-2 text-xs text-gray-600">
          {agent.toolCallCount} tool call{agent.toolCallCount !== 1 ? "s" : ""}
        </span>
      )}
    </div>
  );
}
