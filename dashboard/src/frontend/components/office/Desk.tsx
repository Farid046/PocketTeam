import React from "react";

interface Props {
  x: number;
  y: number;
  /** If true, the desk faces up; false = faces down (chair below). Default: true. */
  facingUp?: boolean;
  color?: string;
}

const DESK_W = 72;
const DESK_H = 40;
const DESK_DEPTH = 10;
const MONITOR_W = 22;
const MONITOR_H = 14;
const MONITOR_BASE_W = 6;
const MONITOR_BASE_H = 3;

/**
 * Isometric-flavoured top-down desk.
 * Origin (x, y) is the center of the desk surface.
 */
export function Desk({ x, y, color = "#2d3748" }: Props): React.ReactElement {
  const halfW = DESK_W / 2;
  const halfH = DESK_H / 2;

  // Surface
  const surfaceX = x - halfW;
  const surfaceY = y - halfH;

  // Front panel (bottom edge, gives a sense of depth)
  const panelX = x - halfW;
  const panelY = y + halfH;

  // Monitor center
  const monX = x - MONITOR_W / 2;
  const monY = y - halfH + 5;

  // Keyboard hint
  const kbX = x - 14;
  const kbY = y + 2;

  return (
    <g>
      {/* Front depth panel */}
      <rect
        x={panelX}
        y={panelY}
        width={DESK_W}
        height={DESK_DEPTH}
        rx={2}
        fill={adjustBrightness(color, -30)}
      />
      {/* Desktop surface */}
      <rect
        x={surfaceX}
        y={surfaceY}
        width={DESK_W}
        height={DESK_H}
        rx={3}
        fill={color}
        stroke={adjustBrightness(color, -50)}
        strokeWidth={1}
      />
      {/* Monitor stand */}
      <rect
        x={x - MONITOR_BASE_W / 2}
        y={monY + MONITOR_H}
        width={MONITOR_BASE_W}
        height={MONITOR_BASE_H}
        fill={adjustBrightness(color, -20)}
      />
      {/* Monitor screen */}
      <rect
        x={monX}
        y={monY}
        width={MONITOR_W}
        height={MONITOR_H}
        rx={2}
        fill="#0d1117"
        stroke="#374151"
        strokeWidth={0.5}
      />
      {/* Screen glow (subtle) */}
      <rect
        x={monX + 2}
        y={monY + 2}
        width={MONITOR_W - 4}
        height={MONITOR_H - 4}
        rx={1}
        fill="#1a2a4a"
        opacity={0.8}
      />
      {/* Keyboard hint */}
      <rect
        x={kbX}
        y={kbY}
        width={28}
        height={10}
        rx={2}
        fill={adjustBrightness(color, -15)}
        stroke={adjustBrightness(color, -40)}
        strokeWidth={0.5}
      />
    </g>
  );
}

function adjustBrightness(hex: string, amount: number): string {
  const num = parseInt(hex.replace("#", ""), 16);
  const r = Math.max(0, Math.min(255, (num >> 16) + amount));
  const g = Math.max(0, Math.min(255, ((num >> 8) & 0xff) + amount));
  const b = Math.max(0, Math.min(255, (num & 0xff) + amount));
  return `#${r.toString(16).padStart(2, "0")}${g.toString(16).padStart(2, "0")}${b.toString(16).padStart(2, "0")}`;
}
