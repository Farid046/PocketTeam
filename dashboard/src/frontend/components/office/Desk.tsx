import React from "react";

interface Props {
  x: number;
  y: number;
}

// Isometric desk dimensions — scaled down ~10% to reduce crowding
const DESK_W = 36;   // width of the top diamond face
const DESK_H = 18;   // height of the top diamond face (half of DESK_W in iso)
const DESK_DEPTH = 12; // vertical face height

// Colors — warm wood tones
const COLOR_TOP   = "#8B7355";
const COLOR_LEFT  = "#6B5B45";
const COLOR_RIGHT = "#5B4B35";
const COLOR_MONITOR_FRAME = "#2a2a2a";
const COLOR_MONITOR_SCREEN = "#4488cc";

/**
 * Isometric desk with 3 visible faces: top, left, right.
 * (x, y) is the screen-space center of the top face.
 */
export function Desk({ x, y }: Props): React.ReactElement {
  const hw = DESK_W / 2;   // half-width
  const hh = DESK_H / 2;   // half-height of the top diamond face

  // Top face — diamond shape
  const topPoints = `${x},${y - hh} ${x + hw},${y} ${x},${y + hh} ${x - hw},${y}`;

  // Left face — trapezoid going down-left
  const leftPoints = `${x - hw},${y} ${x},${y + hh} ${x},${y + hh + DESK_DEPTH} ${x - hw},${y + DESK_DEPTH}`;

  // Right face — trapezoid going down-right
  const rightPoints = `${x},${y + hh} ${x + hw},${y} ${x + hw},${y + DESK_DEPTH} ${x},${y + hh + DESK_DEPTH}`;

  // Monitor sits on the top face, toward the back (upper-left of the diamond)
  const monX = x - 6;
  const monY = y - hh - 14;
  const monW = 14;
  const monH = 10;

  // Keyboard — a small flat rectangle on the top face
  const kbX = x - 8;
  const kbY = y - 2;

  return (
    <g>
      {/* Shadow beneath desk */}
      <ellipse
        cx={x}
        cy={y + hh + DESK_DEPTH + 3}
        rx={hw + 2}
        ry={5}
        fill="#000"
        opacity={0.18}
      />

      {/* Right face (darkest) */}
      <polygon points={rightPoints} fill={COLOR_RIGHT} />

      {/* Left face (medium) */}
      <polygon points={leftPoints} fill={COLOR_LEFT} />

      {/* Top face (lightest) */}
      <polygon points={topPoints} fill={COLOR_TOP} />

      {/* Top face edge lines for crispness */}
      <polygon points={topPoints} fill="none" stroke="#3d2d1a" strokeWidth={0.6} />

      {/* Monitor frame */}
      <rect
        x={monX}
        y={monY}
        width={monW}
        height={monH}
        rx={1}
        fill={COLOR_MONITOR_FRAME}
        stroke="#111"
        strokeWidth={0.5}
      />

      {/* Monitor screen with blue glow */}
      <rect
        x={monX + 1.5}
        y={monY + 1.5}
        width={monW - 3}
        height={monH - 3}
        rx={0.5}
        fill={COLOR_MONITOR_SCREEN}
        opacity={0.85}
      />

      {/* Screen glow effect */}
      <rect
        x={monX - 1}
        y={monY - 1}
        width={monW + 2}
        height={monH + 2}
        rx={2}
        fill={COLOR_MONITOR_SCREEN}
        opacity={0.12}
      />

      {/* Monitor stand */}
      <rect
        x={monX + monW / 2 - 1}
        y={monY + monH}
        width={2}
        height={3}
        fill="#333"
      />

      {/* Keyboard */}
      <rect
        x={kbX}
        y={kbY}
        width={16}
        height={6}
        rx={1}
        fill="#5a4a30"
        stroke="#3d2d1a"
        strokeWidth={0.4}
        opacity={0.9}
      />
    </g>
  );
}
