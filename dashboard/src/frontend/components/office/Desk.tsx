import React from "react";

interface Props {
  x: number;
  y: number;
}

// Isometric desk dimensions — scaled up 1.5x
const DESK_W = 54;
const DESK_H = 27;
const DESK_DEPTH = 18;

// Colors — warm wood tones
const COLOR_TOP   = "#8B7355";
const COLOR_LEFT  = "#6B5B45";
const COLOR_RIGHT = "#5B4B35";
const COLOR_MONITOR_FRAME  = "#2a2a2a";
const COLOR_MONITOR_SCREEN = "#4488cc";

/**
 * Isometric desk with 3 visible faces: top, left, right.
 * Includes dual monitors and wide keyboard.
 * (x, y) is the screen-space center of the top face.
 */
export function Desk({ x, y }: Props): React.ReactElement {
  const hw = DESK_W / 2;
  const hh = DESK_H / 2;

  // Top face — diamond
  const topPoints = `${x},${y - hh} ${x + hw},${y} ${x},${y + hh} ${x - hw},${y}`;

  // Left face
  const leftPoints = `${x - hw},${y} ${x},${y + hh} ${x},${y + hh + DESK_DEPTH} ${x - hw},${y + DESK_DEPTH}`;

  // Right face
  const rightPoints = `${x},${y + hh} ${x + hw},${y} ${x + hw},${y + DESK_DEPTH} ${x},${y + hh + DESK_DEPTH}`;

  // Primary monitor — left of center (back area)
  const mon1X = x - 18;
  const mon1Y = y - hh - 20;
  const mon1W = 18;
  const mon1H = 13;

  // Secondary monitor — right of primary
  const mon2X = x + 2;
  const mon2Y = y - hh - 18;
  const mon2W = 14;
  const mon2H = 11;

  // Keyboard — wide flat rectangle
  const kbX = x - 14;
  const kbY = y - 1;

  return (
    <g>
      {/* Shadow beneath desk */}
      <ellipse
        cx={x}
        cy={y + hh + DESK_DEPTH + 4}
        rx={hw + 3}
        ry={7}
        fill="#000"
        opacity={0.2}
      />

      {/* Right face (darkest) */}
      <polygon points={rightPoints} fill={COLOR_RIGHT} />

      {/* Left face (medium) */}
      <polygon points={leftPoints} fill={COLOR_LEFT} />

      {/* Top face (lightest) */}
      <polygon points={topPoints} fill={COLOR_TOP} />
      <polygon points={topPoints} fill="none" stroke="#3d2d1a" strokeWidth={0.6} />

      {/* Primary monitor frame */}
      <rect
        x={mon1X} y={mon1Y}
        width={mon1W} height={mon1H}
        rx={1.5} fill={COLOR_MONITOR_FRAME}
        stroke="#111" strokeWidth={0.5}
      />
      {/* Primary screen */}
      <rect
        x={mon1X + 2} y={mon1Y + 2}
        width={mon1W - 4} height={mon1H - 4}
        rx={0.5} fill={COLOR_MONITOR_SCREEN}
        opacity={0.9}
      />
      {/* Primary screen glow */}
      <rect
        x={mon1X - 1} y={mon1Y - 1}
        width={mon1W + 2} height={mon1H + 2}
        rx={2} fill={COLOR_MONITOR_SCREEN}
        opacity={0.1}
      />
      {/* Primary stand */}
      <rect
        x={mon1X + mon1W / 2 - 1} y={mon1Y + mon1H}
        width={2} height={4}
        fill="#333"
      />

      {/* Secondary monitor frame */}
      <rect
        x={mon2X} y={mon2Y}
        width={mon2W} height={mon2H}
        rx={1.5} fill={COLOR_MONITOR_FRAME}
        stroke="#111" strokeWidth={0.5}
      />
      {/* Secondary screen — slightly different blue */}
      <rect
        x={mon2X + 2} y={mon2Y + 2}
        width={mon2W - 4} height={mon2H - 4}
        rx={0.5} fill="#3377bb"
        opacity={0.85}
      />
      {/* Secondary stand */}
      <rect
        x={mon2X + mon2W / 2 - 1} y={mon2Y + mon2H}
        width={2} height={3}
        fill="#333"
      />

      {/* Keyboard — wide */}
      <rect
        x={kbX} y={kbY}
        width={28} height={9}
        rx={1.5} fill="#5a4a30"
        stroke="#3d2d1a" strokeWidth={0.4}
        opacity={0.9}
      />
      {/* Keyboard key rows hint */}
      <rect
        x={kbX + 2} y={kbY + 2}
        width={24} height={2}
        rx={0.5} fill="#4a3a20"
        opacity={0.5}
      />
      <rect
        x={kbX + 2} y={kbY + 5}
        width={22} height={2}
        rx={0.5} fill="#4a3a20"
        opacity={0.5}
      />
    </g>
  );
}
