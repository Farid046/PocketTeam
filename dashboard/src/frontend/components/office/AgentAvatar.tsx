import React, { useState } from "react";
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

// Character body dimensions — ~3x larger than before
const HEAD_W = 18;
const HEAD_H = 16;
const TORSO_W = 22;
const TORSO_H = 18;
const ARM_W = 5;
const ARM_H = 14;
const LEG_W = 7;
const LEG_H = 14;

/**
 * Pixel-art isometric character with separate body parts.
 * Working agents glow gold; idle/done agents are desaturated at 0.3 opacity.
 * Speech bubble shown on hover (instant, 0.05s), pinnable on click.
 */
export function AgentAvatar({
  x,
  y,
  avatar,
  role,
  status,
  description,
}: Props): React.ReactElement {
  const [pinned, setPinned] = useState(false);
  const [hovered, setHovered] = useState(false);

  const isWorking = status === "working";
  const opacity = isWorking ? 1 : 0.3;

  // Animation class
  const animClass = isWorking ? "working" : status === "idle" ? "" : "";

  // Unique animation delay per role so characters don't sync
  const animDelay = `${(role.charCodeAt(0) % 5) * 0.4}s`;

  // Character layout — anchored at (x, y) = feet center
  // Legs
  const leftLegX = x - LEG_W - 1;
  const rightLegX = x + 1;
  const legY = y - LEG_H;

  // Torso sits above legs
  const torsoX = x - TORSO_W / 2;
  const torsoY = legY - TORSO_H;

  // Arms beside torso
  const leftArmX = torsoX - ARM_W - 1;
  const rightArmX = torsoX + TORSO_W + 1;
  const armY = torsoY;

  // Head above torso
  const headX = x - HEAD_W / 2;
  const headY = torsoY - HEAD_H - 2;

  // Total character height for shadow
  const totalH = LEG_H + TORSO_H + HEAD_H + 2;

  // Shadow ellipse beneath feet
  const shadowRx = TORSO_W * 0.55;

  // Label
  const labelText = role.toUpperCase();
  const labelW = labelText.length * 5 + 8;
  const labelX = x - labelW / 2;
  const labelY = y + 8;

  // Speech bubble visibility
  const bubbleVisible = pinned || hovered;

  // Glow filter id — unique per role to avoid conflicts
  const glowId = `glow-${role}`;

  // Darker shirt color for right-side shading
  const shirtRight = darkenHex(avatar.shirtColor, 0.3);

  return (
    <g
      opacity={opacity}
      style={{ cursor: "pointer" }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onClick={() => setPinned((p) => !p)}
    >
      {/* Filter defs for this agent */}
      <defs>
        {isWorking && (
          <filter id={glowId} x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feColorMatrix
              in="blur"
              type="matrix"
              values="0.8 0.6 0 0 0  0.6 0.5 0 0 0  0 0 0 0 0  0 0 0 1 0"
              result="goldBlur"
            />
            <feMerge>
              <feMergeNode in="goldBlur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        )}
      </defs>

      {/* Main character group — apply glow filter and animations */}
      <g
        filter={isWorking ? `url(#${glowId})` : undefined}
        className={animClass}
        style={{
          animation: isWorking
            ? `agent-type 1.2s ease-in-out infinite`
            : "none",
          animationDelay: animDelay,
        }}
      >
        {/* Shadow */}
        <ellipse
          cx={x}
          cy={y + 3}
          rx={shadowRx}
          ry={shadowRx * 0.4}
          fill="#000"
          opacity={0.25}
        />

        {/* Left leg */}
        <rect
          x={leftLegX}
          y={legY}
          width={LEG_W}
          height={LEG_H}
          rx={2}
          fill={avatar.skinColor}
          className="agent-left-leg"
        />

        {/* Right leg */}
        <rect
          x={rightLegX}
          y={legY}
          width={LEG_W}
          height={LEG_H}
          rx={2}
          fill={avatar.skinColor}
          className="agent-right-leg"
        />

        {/* Left arm */}
        <rect
          x={leftArmX}
          y={armY}
          width={ARM_W}
          height={ARM_H}
          rx={2}
          fill={avatar.shirtColor}
          className="agent-left-arm"
        />

        {/* Right arm */}
        <rect
          x={rightArmX}
          y={armY}
          width={ARM_W}
          height={ARM_H}
          rx={2}
          fill={avatar.shirtColor}
          className="agent-right-arm"
        />

        {/* Torso */}
        <rect
          x={torsoX}
          y={torsoY}
          width={TORSO_W}
          height={TORSO_H}
          rx={3}
          fill={avatar.shirtColor}
        />

        {/* Torso right-side shading for iso depth */}
        <rect
          x={torsoX + TORSO_W * 0.6}
          y={torsoY}
          width={TORSO_W * 0.4}
          height={TORSO_H}
          rx={3}
          fill={shirtRight}
          opacity={0.5}
        />

        {/* Head */}
        <rect
          x={headX}
          y={headY}
          width={HEAD_W}
          height={HEAD_H}
          rx={3}
          fill={avatar.skinColor}
        />

        {/* Hair */}
        <HairShape
          style={avatar.hairStyle}
          color={avatar.hairColor}
          hx={headX}
          hy={headY}
          hw={HEAD_W}
          hh={HEAD_H}
        />

        {/* Eyes — 2x2 pixel eyes */}
        <rect x={headX + 3} y={headY + 5} width={3} height={3} fill="#1a1a1a" rx={0.5} />
        <rect x={headX + HEAD_W - 6} y={headY + 5} width={3} height={3} fill="#1a1a1a" rx={0.5} />

        {/* Mouth — small line */}
        <rect x={headX + 5} y={headY + HEAD_H - 4} width={8} height={1.5} rx={0.5} fill="#8a5a40" opacity={0.7} />
      </g>

      {/* Transparent hit-area covering the full character for hover */}
      <rect
        x={x - TORSO_W / 2 - ARM_W - 2}
        y={headY - 20}
        width={TORSO_W + ARM_W * 2 + 4}
        height={totalH + 30}
        fill="transparent"
      />

      {/* Role label */}
      <g>
        <rect
          x={labelX}
          y={labelY - 7}
          width={labelW}
          height={11}
          rx={2}
          fill="#0d0d14"
          opacity={0.75}
        />
        <text
          x={x}
          textAnchor="middle"
          y={labelY + 1}
          fontSize={7}
          fill={isWorking ? "#8a93a9" : "#3b4050"}
          fontFamily="monospace"
          fontWeight="700"
          letterSpacing="0.5"
        >
          {labelText}
        </text>
      </g>

      {/* Speech bubble — shown on hover or when pinned */}
      <g
        style={{
          opacity: bubbleVisible ? 1 : 0,
          visibility: bubbleVisible ? "visible" : "hidden",
          transition: "opacity 0.05s",
          pointerEvents: "none",
        }}
      >
        <SpeechBubble x={x} y={headY} text={description ?? ""} pinned={pinned} />
      </g>
    </g>
  );
}

// ---------------------------------------------------------------------------
// Speech bubble — auto-sizing, no truncation
// ---------------------------------------------------------------------------

function SpeechBubble({
  x,
  y,
  text,
  pinned,
}: {
  x: number;
  y: number;
  text: string;
  pinned: boolean;
}): React.ReactElement {
  const maxLineW = 120;
  const charPerLine = 18;
  const lines = wrapText(text, charPerLine);
  const lineH = 10;
  const padX = 8;
  const padY = 6;
  const bubbleW = Math.min(maxLineW, Math.max(50, lines.reduce((m, l) => Math.max(m, l.length), 0) * 5.5 + padX * 2));
  const bubbleH = lines.length * lineH + padY * 2;
  const bx = x - bubbleW / 2;
  const by = y - bubbleH - 18;

  return (
    <g>
      {/* Bubble background */}
      <rect
        x={bx}
        y={by}
        width={bubbleW}
        height={bubbleH}
        rx={5}
        fill="#0f172a"
        stroke={pinned ? "#f59e0b" : "#4a5568"}
        strokeWidth={pinned ? 1.2 : 0.8}
        opacity={0.96}
      />
      {/* Tail */}
      <path
        d={`M ${x - 4} ${by + bubbleH} L ${x} ${by + bubbleH + 7} L ${x + 4} ${by + bubbleH}`}
        fill="#0f172a"
        stroke={pinned ? "#f59e0b" : "#4a5568"}
        strokeWidth={pinned ? 1.2 : 0.8}
      />
      {/* Text lines */}
      {lines.map((line, i) => (
        <text
          key={i}
          x={bx + padX}
          y={by + padY + (i + 1) * lineH - 1}
          fontSize={7}
          fill="#cbd5e1"
          fontFamily="monospace"
        >
          {line}
        </text>
      ))}
      {/* Pin indicator */}
      {pinned && (
        <text
          x={bx + bubbleW - 6}
          y={by + 9}
          fontSize={6}
          fill="#f59e0b"
          fontFamily="monospace"
        >
          ●
        </text>
      )}
    </g>
  );
}

function wrapText(text: string, charsPerLine: number): string[] {
  if (!text) return ["(no description)"];
  const words = text.split(" ");
  const lines: string[] = [];
  let current = "";
  for (const word of words) {
    if ((current + " " + word).trim().length > charsPerLine) {
      if (current) lines.push(current);
      current = word;
    } else {
      current = (current + " " + word).trim();
    }
  }
  if (current) lines.push(current);
  return lines.length ? lines : ["(no description)"];
}

// ---------------------------------------------------------------------------
// Hair shapes — scaled up for larger head
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
      return (
        <rect
          x={hx - 1}
          y={hy - 3}
          width={hw + 2}
          height={6}
          rx={2}
          fill={color}
        />
      );
    case "spiky":
      return (
        <g fill={color}>
          <polygon points={`${hx + 1},${hy} ${hx + 4},${hy - 9} ${hx + 7},${hy}`} />
          <polygon points={`${hx + 6},${hy} ${hx + 8},${hy - 10} ${hx + 12},${hy}`} />
          <polygon points={`${hx + 11},${hy} ${hx + 13},${hy - 8} ${hx + 17},${hy}`} />
        </g>
      );
    case "round":
      return (
        <ellipse
          cx={hx + hw / 2}
          cy={hy + 1}
          rx={hw / 2 + 2}
          ry={7}
          fill={color}
        />
      );
    case "long":
      return (
        <g fill={color}>
          <rect x={hx - 1} y={hy - 2} width={hw + 2} height={6} rx={2} />
          <rect x={hx - 2} y={hy + 3} width={4} height={hh + 4} rx={2} />
          <rect x={hx + hw - 2} y={hy + 3} width={4} height={hh + 4} rx={2} />
        </g>
      );
    case "buzz":
      return (
        <rect
          x={hx}
          y={hy}
          width={hw}
          height={4}
          rx={1}
          fill={color}
          opacity={0.85}
        />
      );
    default:
      return null;
  }
}

// ---------------------------------------------------------------------------
// Color utility
// ---------------------------------------------------------------------------

function darkenHex(hex: string, amount: number): string {
  const n = parseInt(hex.replace("#", ""), 16);
  const r = Math.max(0, Math.floor(((n >> 16) & 0xff) * (1 - amount)));
  const g = Math.max(0, Math.floor(((n >> 8) & 0xff) * (1 - amount)));
  const b = Math.max(0, Math.floor((n & 0xff) * (1 - amount)));
  return `#${r.toString(16).padStart(2, "0")}${g.toString(16).padStart(2, "0")}${b.toString(16).padStart(2, "0")}`;
}
