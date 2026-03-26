import React from "react";

interface Props {
  x: number;
  y: number;
}

// Isometric coffee machine — tall box ~40px
const BOX_W = 28;
const BOX_H = 14;
const BOX_DEPTH = 36;

const COLOR_TOP   = "#3a3a3a";
const COLOR_LEFT  = "#2a2a2a";
const COLOR_RIGHT = "#222222";
const COLOR_SCREEN = "#1a4a8c";
const COLOR_SCREEN_GLOW = "#4488dd";

/**
 * Isometric coffee machine with screen, cup slot, and steam animation.
 * (x, y) is screen-space center of the top face.
 */
export function CoffeeMachine({ x, y }: Props): React.ReactElement {
  const hw = BOX_W / 2;
  const hh = BOX_H / 2;

  // Top face
  const topPoints = `${x},${y - hh} ${x + hw},${y} ${x},${y + hh} ${x - hw},${y}`;

  // Left face (goes down)
  const leftPoints = `${x - hw},${y} ${x},${y + hh} ${x},${y + hh + BOX_DEPTH} ${x - hw},${y + BOX_DEPTH}`;

  // Right face (goes down)
  const rightPoints = `${x},${y + hh} ${x + hw},${y} ${x + hw},${y + BOX_DEPTH} ${x},${y + hh + BOX_DEPTH}`;

  // Cup below dispenser slot
  const cupX = x - hw / 2 - 2;
  const cupY = y + hh + BOX_DEPTH + 2;

  // Steam origin — above the machine top
  const steamX = x - 4;
  const steamY = y - hh - 4;

  return (
    <g>
      {/* Shadow */}
      <ellipse
        cx={x}
        cy={y + hh + BOX_DEPTH + 5}
        rx={hw + 4}
        ry={6}
        fill="#000"
        opacity={0.25}
      />

      {/* Right face */}
      <polygon points={rightPoints} fill={COLOR_RIGHT} stroke="#333" strokeWidth={0.4} />

      {/* Left face */}
      <polygon points={leftPoints} fill={COLOR_LEFT} stroke="#1e1e1e" strokeWidth={0.4} />

      {/* Top face */}
      <polygon points={topPoints} fill={COLOR_TOP} stroke="#555" strokeWidth={0.5} />

      {/* Screen on right face */}
      <rect
        x={x + 4}
        y={y + hh + 5}
        width={10}
        height={7}
        rx={1}
        fill={COLOR_SCREEN}
        stroke={COLOR_SCREEN_GLOW}
        strokeWidth={0.5}
      />
      {/* Screen glow */}
      <rect
        x={x + 3}
        y={y + hh + 4}
        width={12}
        height={9}
        rx={2}
        fill={COLOR_SCREEN_GLOW}
        opacity={0.12}
      />

      {/* Button row on right face */}
      <rect x={x + 5}  y={y + hh + 16} width={3} height={3} rx={1} fill="#444" />
      <rect x={x + 10} y={y + hh + 16} width={3} height={3} rx={1} fill="#444" />

      {/* Cup dispenser slot on left face */}
      <rect
        x={x - hw + 4}
        y={y + hh + BOX_DEPTH - 10}
        width={8}
        height={4}
        rx={1}
        fill="#111"
        stroke="#444"
        strokeWidth={0.4}
      />

      {/* Cup */}
      <polygon
        points={`${cupX},${cupY} ${cupX + 8},${cupY} ${cupX + 7},${cupY + 7} ${cupX + 1},${cupY + 7}`}
        fill="#f0e8d0"
        opacity={0.9}
      />
      <rect
        x={cupX}
        y={cupY}
        width={8}
        height={2}
        rx={0.5}
        fill="#d4c8a8"
        opacity={0.8}
      />

      {/* Steam wisps — CSS animated */}
      <path
        d={`M ${steamX} ${steamY} Q ${steamX - 3} ${steamY - 4} ${steamX} ${steamY - 8} Q ${steamX + 3} ${steamY - 12} ${steamX} ${steamY - 16}`}
        fill="none"
        stroke="#aaaaaa"
        strokeWidth={1.5}
        strokeLinecap="round"
        opacity={0.4}
        style={{
          animation: "steam-rise 2s ease-out infinite",
          animationDelay: "0s",
        }}
      />
      <path
        d={`M ${steamX + 5} ${steamY + 2} Q ${steamX + 8} ${steamY - 2} ${steamX + 5} ${steamY - 6} Q ${steamX + 2} ${steamY - 10} ${steamX + 5} ${steamY - 14}`}
        fill="none"
        stroke="#aaaaaa"
        strokeWidth={1.5}
        strokeLinecap="round"
        opacity={0.4}
        style={{
          animation: "steam-rise 2s ease-out infinite",
          animationDelay: "0.7s",
        }}
      />
      <path
        d={`M ${steamX - 4} ${steamY + 1} Q ${steamX - 7} ${steamY - 3} ${steamX - 4} ${steamY - 7} Q ${steamX - 1} ${steamY - 11} ${steamX - 4} ${steamY - 15}`}
        fill="none"
        stroke="#aaaaaa"
        strokeWidth={1.2}
        strokeLinecap="round"
        opacity={0.3}
        style={{
          animation: "steam-rise 2s ease-out infinite",
          animationDelay: "1.3s",
        }}
      />
    </g>
  );
}
