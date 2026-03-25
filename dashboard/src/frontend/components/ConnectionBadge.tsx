import React from "react";
import type { ConnectionStatus } from "../store/useStore";

interface Props {
  status: ConnectionStatus;
}

const CONFIG: Record<ConnectionStatus, { dotClass: string; label: string; textClass: string }> = {
  connected: {
    dotClass: "bg-green-400",
    label: "Live",
    textClass: "text-green-400",
  },
  reconnecting: {
    dotClass: "bg-yellow-400 animate-pulse",
    label: "Reconnecting...",
    textClass: "text-yellow-400",
  },
  disconnected: {
    dotClass: "bg-red-500",
    label: "Disconnected",
    textClass: "text-red-400",
  },
  "no-data": {
    dotClass: "bg-green-400",
    label: "Waiting for session",
    textClass: "text-gray-500",
  },
};

export function ConnectionBadge({ status }: Props): React.ReactElement {
  const { dotClass, label, textClass } = CONFIG[status];

  return (
    <span className="flex items-center gap-1.5">
      <span className={`inline-block w-2 h-2 rounded-full ${dotClass}`} />
      <span className={`text-xs ${textClass}`}>{label}</span>
    </span>
  );
}
