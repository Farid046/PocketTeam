import React from "react";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";
import type { AuditEntry, AuditStats } from "../types";
import { formatTs } from "../utils/formatTime";

interface Props {
  auditStats: AuditStats | null;
  auditEntries: AuditEntry[];
}

function pct(n: number, total: number): string {
  if (total === 0) return "0%";
  return `${Math.round((n / total) * 100)}%`;
}

interface DecisionBadgeProps {
  decision: string;
}

function DecisionBadge({ decision }: DecisionBadgeProps): React.ReactElement {
  let cls = "bg-gray-800 text-gray-400";
  if (decision === "ALLOWED") {
    cls = "bg-green-900/60 text-green-400 border border-green-800";
  } else if (decision.startsWith("DENIED")) {
    cls = "bg-red-900/60 text-red-400 border border-red-800";
  } else if (decision === "REQUIRES_APPROVAL") {
    cls = "bg-yellow-900/60 text-yellow-400 border border-yellow-800";
  }

  return (
    <span className={`inline-block px-1.5 py-0.5 rounded text-xs font-medium ${cls}`}>
      {decision}
    </span>
  );
}

interface PieTooltipProps {
  active?: boolean;
  payload?: Array<{ name: string; value: number }>;
}

function PieTooltipContent({ active, payload }: PieTooltipProps): React.ReactElement | null {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div className="bg-gray-900 border border-gray-700 rounded p-2 text-xs">
      <span className="text-gray-300">{payload[0].name}: {payload[0].value}</span>
    </div>
  );
}

export function SafetyView({ auditStats, auditEntries }: Props): React.ReactElement {
  const criticalAlerts = auditEntries.filter((e) => e.decision.startsWith("DENIED"));
  const recentEntries = auditEntries.slice(-100).reverse();

  const pieData = auditStats
    ? [
        { name: "Allowed", value: auditStats.allowed, color: "#4ADE80" },
        { name: "Denied", value: auditStats.denied, color: "#F87171" },
      ].filter((d) => d.value > 0)
    : [];

  const hasData = auditStats !== null && auditStats.total > 0;

  return (
    <div className="flex flex-col md:flex-row gap-4 h-full">
      {/* Summary panel — full width on mobile, fixed sidebar on desktop */}
      <div className="w-full md:w-64 flex-shrink-0 flex flex-col gap-4">
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
            Audit Summary
          </h2>

          {!hasData ? (
            <p className="text-xs text-gray-600">No audit data yet.</p>
          ) : (
            <>
              <div className="grid grid-cols-2 gap-3 mb-4">
                <div className="flex flex-col">
                  <span className="text-xs text-gray-500">Total</span>
                  <span className="text-lg font-bold text-gray-200">
                    {auditStats!.total}
                  </span>
                </div>
                <div className="flex flex-col">
                  <span className="text-xs text-gray-500">Allowed</span>
                  <span className="text-lg font-bold text-green-400">
                    {pct(auditStats!.allowed, auditStats!.total)}
                  </span>
                </div>
                <div className="flex flex-col">
                  <span className="text-xs text-gray-500">Denied</span>
                  <span className="text-lg font-bold text-red-400">
                    {pct(auditStats!.denied, auditStats!.total)}
                  </span>
                </div>
                <div className="flex flex-col">
                  <span className="text-xs text-gray-500">Denied count</span>
                  <span className="text-lg font-bold text-red-400">
                    {auditStats!.denied}
                  </span>
                </div>
              </div>

              {pieData.length > 0 && (
                <div style={{ height: "140px" }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={pieData}
                        cx="50%"
                        cy="50%"
                        innerRadius={35}
                        outerRadius={55}
                        paddingAngle={2}
                        dataKey="value"
                      >
                        {pieData.map((entry, i) => (
                          <Cell key={i} fill={entry.color} />
                        ))}
                      </Pie>
                      <Tooltip content={<PieTooltipContent />} />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              )}
            </>
          )}
        </div>

        {/* Critical alerts */}
        {criticalAlerts.length > 0 && (
          <div className="bg-red-950/40 border border-red-900 rounded-lg p-3">
            <h3 className="text-xs font-semibold text-red-400 uppercase tracking-wider mb-2">
              {criticalAlerts.length <= 5
                ? `Denied (${criticalAlerts.length})`
                : `Denied (showing 5 of ${criticalAlerts.length})`}
            </h3>
            <div className="space-y-1.5 max-h-48 overflow-y-auto">
              {criticalAlerts.slice(-5).reverse().map((entry, i) => (
                <div key={i} className="text-xs">
                  <span className="text-red-400">{entry.agent}</span>
                  <span className="text-gray-500"> — </span>
                  <span className="text-gray-400">{entry.tool}</span>
                  {entry.reason && (
                    <div className="text-gray-600 truncate">{entry.reason}</div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Right column — audit table */}
      <div className="flex-1 flex flex-col bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
        <div className="px-4 py-2.5 border-b border-gray-800">
          <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
            Audit Log
          </h2>
        </div>

        <div className="flex-1 overflow-y-auto">
          {recentEntries.length === 0 ? (
            <div className="flex items-center justify-center h-full">
              <p className="text-xs text-gray-600">No audit entries recorded.</p>
            </div>
          ) : (
            <table className="w-full text-xs border-collapse">
              <thead className="sticky top-0 bg-gray-900 z-10">
                <tr className="border-b border-gray-800">
                  <th className="text-left px-3 py-2 text-gray-500 font-medium w-20">Time</th>
                  <th className="text-left px-3 py-2 text-gray-500 font-medium w-28">Agent</th>
                  <th className="text-left px-3 py-2 text-gray-500 font-medium w-32">Tool</th>
                  <th className="text-left px-3 py-2 text-gray-500 font-medium w-48">Decision</th>
                  <th className="text-left px-3 py-2 text-gray-500 font-medium">Reason</th>
                </tr>
              </thead>
              <tbody>
                {recentEntries.map((entry, i) => {
                  const isDenied = entry.decision.startsWith("DENIED");
                  return (
                    <tr
                      key={i}
                      className={`border-b border-gray-800/50 ${
                        isDenied ? "bg-red-950/20" : "hover:bg-gray-800/30"
                      }`}
                    >
                      <td className="px-3 py-1.5 text-gray-600 whitespace-nowrap">
                        {formatTs(entry.ts)}
                      </td>
                      <td className="px-3 py-1.5 text-gray-400 truncate max-w-[112px]">
                        {entry.agent}
                      </td>
                      <td className="px-3 py-1.5 text-gray-400 truncate max-w-[128px]">
                        {entry.tool}
                      </td>
                      <td className="px-3 py-1.5">
                        <DecisionBadge decision={entry.decision} />
                      </td>
                      <td className="px-3 py-1.5 text-gray-500 truncate max-w-[200px]">
                        {entry.reason}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
