import React from "react";
import type { AgentState } from "../types";

function relativeTime(isoTs: string): string {
  const diffMs = Date.now() - new Date(isoTs).getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHour = Math.floor(diffMin / 60);
  if (diffHour < 24) return `${diffHour}h ago`;
  return `${Math.floor(diffHour / 24)}d ago`;
}

interface Props {
  agents: AgentState[];
}

export function EmptyState({ agents }: Props): React.ReactElement {
  const hasHistory = agents.length > 0 && agents.every((a) => a.status === "done");
  const lastAgent = hasHistory
    ? agents.reduce((latest, a) =>
        new Date(a.lastActivity) > new Date(latest.lastActivity) ? a : latest
      )
    : null;

  return (
    <div className="flex flex-col items-center justify-center h-full text-center gap-4 py-16">
      {/* Icon */}
      <div className="w-16 h-16 rounded-full border-2 border-gray-700 flex items-center justify-center">
        <svg
          width="32"
          height="32"
          viewBox="0 0 32 32"
          fill="none"
          className="text-gray-600"
        >
          <circle cx="16" cy="16" r="10" stroke="currentColor" strokeWidth="1.5" />
          <circle cx="10" cy="13" r="2" fill="currentColor" />
          <circle cx="22" cy="13" r="2" fill="currentColor" />
          <path
            d="M10 20c1.5 2 4.5 3 6 3s4.5-1 6-3"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
          />
        </svg>
      </div>

      {hasHistory && lastAgent ? (
        <>
          <div>
            <p className="text-gray-400 text-sm font-medium">Last session ended</p>
            <p className="text-gray-600 text-xs mt-1">
              {relativeTime(lastAgent.lastActivity)} &mdash; {agents.length} agent
              {agents.length !== 1 ? "s" : ""} ran
            </p>
          </div>
          <p className="text-gray-600 text-xs">
            No active session. Run{" "}
            <code className="text-gray-400 bg-gray-900 px-1.5 py-0.5 rounded">
              pocketteam start
            </code>{" "}
            in your project to begin.
          </p>
        </>
      ) : (
        <>
          <div>
            <p className="text-gray-300 text-sm font-medium">
              No active PocketTeam session detected.
            </p>
            <p className="text-gray-600 text-xs mt-2">
              Run{" "}
              <code className="text-gray-400 bg-gray-900 px-1.5 py-0.5 rounded">
                pocketteam start
              </code>{" "}
              in your project to begin.
            </p>
          </div>
        </>
      )}
    </div>
  );
}
