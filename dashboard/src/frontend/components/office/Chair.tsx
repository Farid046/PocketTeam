import React from "react";

interface Props {
  x: number;
  y: number;
}

// Chair dimensions — scaled up ~1.5x
const SEAT_W = 27;
const SEAT_H = 14;
const SEAT_DEPTH = 12;
const BACK_H = 15;

const COLOR_SEAT_TOP   = "#3a3a52";
const COLOR_SEAT_LEFT  = "#2a2a3e";
const COLOR_SEAT_RIGHT = "#222232";
const COLOR_BACK_FRONT = "#2e2e46";
const COLOR_BACK_SIDE  = "#242436";

/**
 * Isometric office chair — 3-face seat box with backrest.
 * (x, y) is screen-space center of the seat top face.
 */
export function Chair({ x, y }: Props): React.ReactElement {
  const hw = SEAT_W / 2;
  const hh = SEAT_H / 2;

  // Seat top face — diamond
  const seatTop = `${x},${y - hh} ${x + hw},${y} ${x},${y + hh} ${x - hw},${y}`;

  // Seat left face
  const seatLeft = `${x - hw},${y} ${x},${y + hh} ${x},${y + hh + SEAT_DEPTH} ${x - hw},${y + SEAT_DEPTH}`;

  // Seat right face
  const seatRight = `${x},${y + hh} ${x + hw},${y} ${x + hw},${y + SEAT_DEPTH} ${x},${y + hh + SEAT_DEPTH}`;

  // Backrest
  const backBaseY = y - hh;
  const backW = SEAT_W * 0.6;
  const backHW = backW / 2;
  const backHH = (SEAT_H * 0.6) / 2;

  const backX = x - 6;
  const backY = backBaseY - BACK_H;

  const backFront = `${backX},${backY} ${backX + backHW},${backY + backHH} ${backX},${backY + backHH + BACK_H} ${backX - backHW},${backY + backHH}`;
  const backSide = `${backX},${backY + backHH} ${backX + backHW},${backY} ${backX + backHW},${backY + BACK_H} ${backX},${backY + backHH + BACK_H}`;

  return (
    <g>
      {/* Seat right face */}
      <polygon points={seatRight} fill={COLOR_SEAT_RIGHT} />
      {/* Seat left face */}
      <polygon points={seatLeft} fill={COLOR_SEAT_LEFT} />
      {/* Seat top */}
      <polygon points={seatTop} fill={COLOR_SEAT_TOP} />
      <polygon points={seatTop} fill="none" stroke="#1a1a28" strokeWidth={0.4} />

      {/* Backrest side */}
      <polygon points={backSide} fill={COLOR_BACK_SIDE} />
      {/* Backrest front */}
      <polygon points={backFront} fill={COLOR_BACK_FRONT} />

      {/* Seat cushion highlight */}
      <polygon
        points={`${x},${y - hh + 2} ${x + hw * 0.6},${y - 1} ${x},${y + hh - 2} ${x - hw * 0.6},${y - 1}`}
        fill="#45455e"
        opacity={0.4}
      />
    </g>
  );
}
