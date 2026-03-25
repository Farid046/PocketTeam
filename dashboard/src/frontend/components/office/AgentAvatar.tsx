import React from "react";
import type { AvatarData, HairStyle } from "./avatarGenerator";

interface Props {
  x: number;
  y: number;
  avatar: AvatarData;
  role: string;
  status: "idle" | "working" | "done";
  description?: string;
  toolCallCount?: number;
}

const HEAD_R = 12;
const BODY_W = 18;
const BODY_H = 16;
const MAX_BUBBLE_CHARS = 28;

export function AgentAvatar({
  x,
  y,
  avatar,
  role,
  status,
  description,
  toolCallCount,
}: Props): React.ReactElement {
  const isWorking = status === "working";
  const isDone = status === "done";
  const isIdle = status === "idle";

  const opacity = isIdle ? 0.35 : 1;

  const truncatedDesc =
    description && description.length > MAX_BUBBLE_CHARS
      ? `${description.slice(0, MAX_BUBBLE_CHARS)}…`
      : (description ?? "");

  return (
    <g transform={`translate(${x}, ${y})`} opacity={opacity}>
      {/* Working: pulsing status ring */}
      {isWorking && (
        <circle
          r={HEAD_R + 5}
          fill="none"
          stroke="#22c55e"
          strokeWidth={1.5}
          opacity={0.7}
          style={{ animation: "pulse-ring 1.4s ease-in-out infinite" }}
        />
      )}

      {/* Hair */}
      <HairShape style={avatar.hairStyle} color={avatar.hairColor} r={HEAD_R} />

      {/* Head */}
      <circle r={HEAD_R} fill={avatar.faceColor} />

      {/* Eyes */}
      <circle cx={-4} cy={-2} r={1.8} fill="#222" />
      <circle cx={4} cy={-2} r={1.8} fill="#222" />

      {/* Body / shirt */}
      <rect
        x={-BODY_W / 2}
        y={HEAD_R - 2}
        width={BODY_W}
        height={BODY_H}
        rx={4}
        fill={avatar.shirtColor}
        opacity={0.9}
      />

      {/* Done: checkmark badge */}
      {isDone && (
        <g transform={`translate(${HEAD_R - 2}, ${-HEAD_R + 2})`}>
          <circle r={6} fill="#1a2a1a" stroke="#22c55e" strokeWidth={1} />
          <path
            d="M -3 0 L -1 2.5 L 3.5 -2"
            stroke="#22c55e"
            strokeWidth={1.5}
            strokeLinecap="round"
            strokeLinejoin="round"
            fill="none"
          />
        </g>
      )}

      {/* Speech bubble when working */}
      {isWorking && truncatedDesc && (
        <g style={{ animation: "float-bubble 2.5s ease-in-out infinite" }}>
          <BubbleRect text={truncatedDesc} />
        </g>
      )}

      {/* Role label */}
      <text
        textAnchor="middle"
        y={HEAD_R + BODY_H + 10}
        fontSize={8}
        fill={isIdle ? "#4b5563" : "#9ca3af"}
        fontFamily="monospace"
        fontWeight="600"
        letterSpacing="0.5"
      >
        {role.toUpperCase()}
      </text>

      {/* Tool call badge when working */}
      {isWorking && toolCallCount !== undefined && toolCallCount > 0 && (
        <g transform={`translate(${-HEAD_R + 2}, ${-HEAD_R + 2})`}>
          <circle r={6} fill="#1e3a5f" stroke="#3b82f6" strokeWidth={0.8} />
          <text
            textAnchor="middle"
            dy="3"
            fontSize={6}
            fill="#93c5fd"
            fontFamily="monospace"
          >
            {toolCallCount > 99 ? "99+" : toolCallCount}
          </text>
        </g>
      )}
    </g>
  );
}

function BubbleRect({ text }: { text: string }): React.ReactElement {
  const bubbleW = Math.max(60, text.length * 4.8 + 14);
  const bubbleH = 18;
  const bx = -bubbleW / 2;
  const by = -(HEAD_R + bubbleH + 10);

  return (
    <g>
      <rect
        x={bx}
        y={by}
        width={bubbleW}
        height={bubbleH}
        rx={5}
        fill="#0f172a"
        stroke="#22c55e"
        strokeWidth={0.8}
        opacity={0.92}
      />
      {/* Tail */}
      <path
        d={`M -4 ${by + bubbleH} L 0 ${by + bubbleH + 6} L 4 ${by + bubbleH}`}
        fill="#0f172a"
        stroke="#22c55e"
        strokeWidth={0.8}
      />
      <text
        x={0}
        y={by + 12}
        textAnchor="middle"
        fontSize={7.5}
        fill="#86efac"
        fontFamily="monospace"
      >
        {text}
      </text>
    </g>
  );
}

function HairShape({
  style,
  color,
  r,
}: {
  style: HairStyle;
  color: string;
  r: number;
}): React.ReactElement | null {
  switch (style) {
    case "short":
      return (
        <ellipse cx={0} cy={-r * 0.5} rx={r * 0.95} ry={r * 0.6} fill={color} />
      );
    case "spiky":
      return (
        <g>
          <ellipse cx={0} cy={-r * 0.5} rx={r * 0.9} ry={r * 0.5} fill={color} />
          {([-0.55, -0.2, 0.15, 0.5] as number[]).map((off, i) => (
            <polygon
              key={i}
              points={`${off * r * 2},${-r * 1.3} ${off * r * 2 - 3},${-r * 0.6} ${off * r * 2 + 3},${-r * 0.6}`}
              fill={color}
            />
          ))}
        </g>
      );
    case "side":
      return (
        <g>
          <ellipse cx={-r * 0.1} cy={-r * 0.5} rx={r} ry={r * 0.55} fill={color} />
          <rect
            x={r * 0.3}
            y={-r * 1.1}
            width={r * 0.5}
            height={r * 0.4}
            rx={2}
            fill={color}
          />
        </g>
      );
    case "curly":
      return (
        <g>
          {([[-0.5, -0.9], [0, -1.05], [0.5, -0.9], [-0.75, -0.55], [0.75, -0.55]] as [number, number][]).map(
            ([ox, oy], i) => (
              <circle key={i} cx={ox * r} cy={oy * r} r={r * 0.32} fill={color} />
            )
          )}
        </g>
      );
    case "buzz":
      return (
        <ellipse
          cx={0}
          cy={-r * 0.45}
          rx={r * 0.88}
          ry={r * 0.48}
          fill={color}
          opacity={0.75}
        />
      );
    default:
      return null;
  }
}
