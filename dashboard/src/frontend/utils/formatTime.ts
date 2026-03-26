/**
 * Shared time formatting utilities used across dashboard views.
 */

/**
 * Format an ISO timestamp string to a locale time string (HH:MM:SS).
 * Used in SafetyView audit log entries.
 */
export function formatTs(isoTs: string): string {
  try {
    const d = new Date(isoTs);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  } catch {
    return isoTs;
  }
}

/**
 * Format a Unix timestamp (ms) to a HH:MM string.
 * Used in TimelineView axis tick labels.
 */
export function formatAxisTime(ts: number): string {
  const d = new Date(ts);
  const h = d.getHours().toString().padStart(2, "0");
  const m = d.getMinutes().toString().padStart(2, "0");
  return `${h}:${m}`;
}
