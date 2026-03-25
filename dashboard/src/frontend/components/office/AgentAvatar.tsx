import React from "react";
import type { AvatarStyle, HairStyle } from "./avatarGenerator";

interface Props {
  x: number;
  y: number;
  avatar: AvatarStyle;
  role: string;
  status: "idle" | "working" | "done";
  description?: string;
  toolCallCount?: number;
}

const HEAD_W = 10;
const HEAD_H = 10;
const BODY_W = 12;
const BODY_H = 14;
const MAX_BUBBLE_CHARS = 25;

/**
 * Pixel-art isometric character sitting at a desk.
 * (x, y) is the screen-space anchor — roughly where the character sits.
 */
export function AgentAvatar({
  x,
  y,
  avatar,
  role,
  status,
  description,
  // toolCallCount prop retained for API compatibility but badge removed to reduce clutter
}: Props): React.ReactElement {
  const isWorking = status === "working";
  const isDone = status === "done";
  const isIdle = status === "idle";

  const opacity = isIdle ? 0.3 : isDone ? 0.7 : 1;

  const truncatedDesc =
    description && description.length > MAX_BUBBLE_CHARS
      ? `${description.slice(0, MAX_BUBBLE_CHARS)}…`
      : (description ?? "");

  // Character is rendered from center-bottom
  // Body center
  const bx = x - BODY_W / 2;
  const by = y - BODY_H;
  // Head center
  const hx = x - HEAD_W / 2;
  const hy = by - HEAD_H - 1;

  return (
    <g opacity={opacity}>
      {/* Working: pulsing green ring around character */}
      {isWorking && (
        <ellipse
          cx={x}
          cy={y - BODY_H / 2 - HEAD_H / 2}
          rx={16}
          ry={16}
          fill="none"
          stroke="#22c55e"
          strokeWidth={1.5}
          opacity={0.65}
          style={{ animation: "pulse-ring 1.4s ease-in-out infinite" }}
        />
      )}

      {/* Body / shirt */}
      <rect
        x={bx}
        y={by}
        width={BODY_W}
        height={BODY_H}
        rx={2}
        fill={avatar.shirtColor}
      />

      {/* Body shading — right side darker for iso feel */}
      <rect
        x={bx + BODY_W * 0.6}
        y={by}
        width={BODY_W * 0.4}
        height={BODY_H}
        rx={2}
        fill="#000"
        opacity={0.18}
      />

      {/* Head */}
      <rect
        x={hx}
        y={hy}
        width={HEAD_W}
        height={HEAD_H}
        rx={2}
        fill={avatar.skinColor}
      />

      {/* Hair */}
      <HairShape
        style={avatar.hairStyle}
        color={avatar.hairColor}
        hx={hx}
        hy={hy}
        hw={HEAD_W}
        hh={HEAD_H}
      />

      {/* Eyes — two small dark pixels */}
      <rect x={hx + 2} y={hy + 3} width={2} height={2} fill="#1a1a1a" rx={0.5} />
      <rect x={hx + 6} y={hy + 3} width={2} height={2} fill="#1a1a1a" rx={0.5} />

      {/* Done: green checkmark badge — reduced size by ~30% */}
      {isDone && (
        <g transform={`translate(${x + 5}, ${hy - 2})`}>
          <circle r={3.5} fill="#1a2a1a" stroke="#22c55e" strokeWidth={0.7} />
          <path
            d="M -1.8 0 L -0.4 1.4 L 2.1 -1.1"
            stroke="#22c55e"
            strokeWidth={0.9}
            strokeLinecap="round"
            strokeLinejoin="round"
            fill="none"
          />
        </g>
      )}

      {/* Working: green status dot above head — smaller */}
      {isWorking && (
        <circle
          cx={x + 5}
          cy={hy - 3}
          r={2}
          fill="#22c55e"
          style={{ animation: "pulse-ring 1s ease-in-out infinite" }}
        />
      )}

      {/* Speech bubble when working */}
      {isWorking && truncatedDesc && (
        <g style={{ animation: "float-bubble 2.5s ease-in-out infinite" }}>
          <SpeechBubble x={x} y={hy} text={truncatedDesc} />
        </g>
      )}

      {/* Tool call count badge removed — clutters the view */}

      {/* Role label below character — pushed further down, smaller font, with bg rect */}
      {(() => {
        const labelText = role.toUpperCase();
        const labelW = labelText.length * 4.5 + 6;
        const labelX = x - labelW / 2;
        const labelY = y + 12; // 12px below anchor (was 6)
        return (
          <g>
            <rect
              x={labelX}
              y={labelY - 7}
              width={labelW}
              height={10}
              rx={2}
              fill="#0d0d14"
              opacity={0.72}
            />
            <text
              x={x}
              textAnchor="middle"
              y={labelY}
              fontSize={6}
              fill={isIdle ? "#3b4050" : "#6a7389"}
              fontFamily="monospace"
              fontWeight="700"
              letterSpacing="0.5"
            >
              {labelText}
            </text>
          </g>
        );
      })()}
    </g>
  );
}

// ---------------------------------------------------------------------------
// Speech bubble
// ---------------------------------------------------------------------------

function SpeechBubble({ x, y, text }: { x: number; y: number; text: string }): React.ReactElement {
  const bubbleW = Math.max(55, text.length * 4.5 + 12);
  const bubbleH = 16;
  const bx = x - bubbleW / 2;
  const by = y - bubbleH - 14;

  return (
    <g>
      <rect
        x={bx}
        y={by}
        width={bubbleW}
        height={bubbleH}
        rx={4}
        fill="#0f172a"
        stroke="#22c55e"
        strokeWidth={0.7}
        opacity={0.93}
      />
      {/* Tail */}
      <path
        d={`M ${x - 3} ${by + bubbleH} L ${x} ${by + bubbleH + 5} L ${x + 3} ${by + bubbleH}`}
        fill="#0f172a"
        stroke="#22c55e"
        strokeWidth={0.7}
      />
      <text
        x={x}
        y={by + 11}
        textAnchor="middle"
        fontSize={6.5}
        fill="#86efac"
        fontFamily="monospace"
      >
        {text}
      </text>
    </g>
  );
}

// ---------------------------------------------------------------------------
// Hair shapes — pixel-art style at small scale
// ---------------------------------------------------------------------------

function HairShape({
  style,
  color,
  hx,
  hy,
  hw,
  hh,
}: {
  style: HairStyle;
  color: string;
  hx: number;
  hy: number;
  hw: number;
  hh: number;
}): React.ReactElement | null {
  switch (style) {
    case "flat":
      // Flat cap — simple rect across top of head
      return (
        <rect
          x={hx - 1}
          y={hy - 2}
          width={hw + 2}
          height={4}
          rx={1}
          fill={color}
        />
      );
    case "spiky":
      // Three spikes on top
      return (
        <g fill={color}>
          <polygon points={`${hx + 1},${hy} ${hx + 3},${hy - 6} ${hx + 5},${hy}`} />
          <polygon points={`${hx + 4},${hy} ${hx + 5},${hy - 7} ${hx + 7},${hy}`} />
          <polygon points={`${hx + 7},${hy} ${hx + 8},${hy - 5} ${hx + 10},${hy}`} />
        </g>
      );
    case "round":
      // Round puff — semicircle on top
      return (
        <ellipse
          cx={hx + hw / 2}
          cy={hy + 1}
          rx={hw / 2 + 1}
          ry={5}
          fill={color}
        />
      );
    case "long":
      // Long hair — extends down the sides
      return (
        <g fill={color}>
          <rect x={hx - 1} y={hy - 1} width={hw + 2} height={4} rx={1} />
          {/* Left side hang */}
          <rect x={hx - 2} y={hy + 2} width={3} height={hh} rx={1} />
          {/* Right side hang */}
          <rect x={hx + hw - 1} y={hy + 2} width={3} height={hh} rx={1} />
        </g>
      );
    case "buzz":
      // Very close-cropped — thin strip
      return (
        <rect
          x={hx}
          y={hy}
          width={hw}
          height={3}
          rx={1}
          fill={color}
          opacity={0.8}
        />
      );
    default:
      return null;
  }
}
