import React, { useEffect, useRef } from "react";
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

const MAX_EVENTS = 20;

export function EventFeed({ events }: Props): React.ReactElement {
  const bottomRef = useRef<HTMLDivElement>(null);
  const recent = events.slice(-MAX_EVENTS);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events.length]);

  return (
    <aside className="flex flex-col h-full bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
      <div className="px-3 py-2 border-b border-gray-800">
        <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
          Event Feed
        </h2>
      </div>
      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {recent.length === 0 ? (
          <p className="text-xs text-gray-600 text-center mt-4">No events yet</p>
        ) : (
          recent.map((evt, i) => {
            const color = getRoleColor(evt.agent);
            return (
              <div
                key={`${evt.ts}-${evt.agent}-${evt.tool}-${i}`}
                className="flex flex-col gap-0.5 p-1.5 rounded bg-gray-950/60 border border-gray-800/50"
              >
                <div className="flex items-center justify-between">
                  <span
                    className="text-xs font-medium truncate max-w-[120px]"
                    style={{ color }}
                  >
                    {evt.agent || "unknown"}
                  </span>
                  <span className="text-xs text-gray-600 flex-shrink-0">
                    {relativeTime(evt.ts)}
                  </span>
                </div>
                {evt.tool && (
                  <span className="text-xs text-gray-500 truncate">
                    {evt.tool}
                  </span>
                )}
              </div>
            );
          })
        )}
        <div ref={bottomRef} />
      </div>
    </aside>
  );
}
