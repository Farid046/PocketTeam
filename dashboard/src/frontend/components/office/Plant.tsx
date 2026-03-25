import React from "react";

interface Props {
  x: number;
  y: number;
  scale?: number;
}

/**
 * Small decorative plant.
 * Origin (x, y) is the center-bottom of the pot.
 */
export function Plant({ x, y, scale = 1 }: Props): React.ReactElement {
  const s = scale;
  return (
    <g transform={`translate(${x}, ${y}) scale(${s})`}>
      {/* Pot */}
      <path
        d="M -7 0 L -9 -12 L 9 -12 L 7 0 Z"
        fill="#7c4f2b"
        stroke="#5a3614"
        strokeWidth={0.8}
      />
      {/* Pot rim */}
      <rect x={-9} y={-14} width={18} height={4} rx={1} fill="#8b5a2b" />
      {/* Soil */}
      <ellipse cx={0} cy={-14} rx={7} ry={3} fill="#3d2612" />
      {/* Left leaf */}
      <path
        d="M 0 -14 C -12 -24 -18 -30 -8 -36 C -4 -28 -2 -22 0 -14"
        fill="#2d6a2d"
        stroke="#1a4a1a"
        strokeWidth={0.5}
      />
      {/* Right leaf */}
      <path
        d="M 0 -14 C 12 -24 18 -30 8 -36 C 4 -28 2 -22 0 -14"
        fill="#2d8a2d"
        stroke="#1a4a1a"
        strokeWidth={0.5}
      />
      {/* Center stem + leaf */}
      <path
        d="M 0 -14 C 0 -26 -4 -34 0 -40 C 4 -34 0 -26 0 -14"
        fill="#3da03d"
        stroke="#1a4a1a"
        strokeWidth={0.5}
      />
    </g>
  );
}
