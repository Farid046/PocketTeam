import React from "react";

interface Props {
  x: number;
  y: number;
}

/**
 * Simple top-down office chair.
 * Origin (x, y) is the center of the seat.
 */
export function Chair({ x, y }: Props): React.ReactElement {
  return (
    <g>
      {/* Seat */}
      <rect
        x={x - 11}
        y={y - 10}
        width={22}
        height={20}
        rx={4}
        fill="#1e2535"
        stroke="#2d3a50"
        strokeWidth={1}
      />
      {/* Backrest */}
      <rect
        x={x - 10}
        y={y - 18}
        width={20}
        height={10}
        rx={3}
        fill="#252e42"
        stroke="#2d3a50"
        strokeWidth={1}
      />
      {/* Armrests */}
      <rect x={x - 14} y={y - 8} width={4} height={12} rx={2} fill="#1e2535" stroke="#2d3a50" strokeWidth={0.5} />
      <rect x={x + 10} y={y - 8} width={4} height={12} rx={2} fill="#1e2535" stroke="#2d3a50" strokeWidth={0.5} />
    </g>
  );
}
