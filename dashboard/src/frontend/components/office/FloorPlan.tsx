import React from "react";
import type { AgentState, PocketTeamEvent } from "../../types";
import { Desk } from "./Desk";
import { Chair } from "./Chair";
import { Plant } from "./Plant";
import { AgentAvatar } from "./AgentAvatar";
import { generateAvatar } from "./avatarGenerator";

// ---------------------------------------------------------------------------
// Layout constants
// ---------------------------------------------------------------------------

const SVG_W = 1200;
const SVG_H = 700;

// Zone rectangles: { x, y, w, h }
const ZONES = {
  planning:    { x: 0,   y: 0,   w: 580, h: 300, label: "PLANNING",    color: "#1e2a3a" },
  operations:  { x: 620, y: 0,   w: 580, h: 300, label: "OPERATIONS",  color: "#1e2e2a" },
  engineering: { x: 0,   y: 340, w: 580, h: 360, label: "ENGINEERING", color: "#1e2633" },
  support:     { x: 0,   y: 560, w: 580, h: 140, label: "SUPPORT",     color: "#261e2a" },
  coo:         { x: 620, y: 340, w: 580, h: 360, label: "COO OFFICE",  color: "#2a2520" },
  corridor:    { x: 0,   y: 300, w: 1200, h: 40,  label: "",           color: "#151a24" },
  vCorridorL:  { x: 580, y: 0,   w: 40,  h: 700, label: "",           color: "#151a24" },
} as const;

// Fixed desk positions per role
const DESK_POSITIONS: Record<string, { x: number; y: number }> = {
  product:       { x: 110,  y: 90  },
  planner:       { x: 290,  y: 90  },
  reviewer:      { x: 200,  y: 210 },
  devops:        { x: 710,  y: 90  },
  monitor:       { x: 890,  y: 90  },
  observer:      { x: 800,  y: 210 },
  engineer:      { x: 110,  y: 420 },
  qa:            { x: 290,  y: 420 },
  security:      { x: 200,  y: 520 },
  investigator:  { x: 110,  y: 625 },
  documentation: { x: 290,  y: 625 },
  coo:           { x: 870,  y: 500 },
};

// Roles that get a bigger desk (the COO)
const LARGE_DESK_ROLES = new Set(["coo"]);

// ---------------------------------------------------------------------------
// Zone background + label
// ---------------------------------------------------------------------------

function ZoneRect({
  zone,
}: {
  zone: { x: number; y: number; w: number; h: number; label: string; color: string };
}): React.ReactElement {
  return (
    <>
      <rect
        x={zone.x}
        y={zone.y}
        width={zone.w}
        height={zone.h}
        fill={zone.color}
        stroke="#0d1117"
        strokeWidth={1}
      />
      {zone.label && (
        <text
          x={zone.x + 12}
          y={zone.y + 20}
          fontSize={9}
          fill="#374151"
          fontFamily="monospace"
          fontWeight="700"
          letterSpacing="2"
        >
          {zone.label}
        </text>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// COO meeting table + chairs
// ---------------------------------------------------------------------------

function MeetingTable(): React.ReactElement {
  const cx = 750;
  const cy = 430;
  return (
    <g>
      {/* Table surface */}
      <ellipse cx={cx} cy={cy} rx={60} ry={36} fill="#2a1f18" stroke="#3d2f25" strokeWidth={1.5} />
      {/* Table leg hint */}
      <ellipse cx={cx} cy={cy} rx={40} ry={22} fill="none" stroke="#3d2f25" strokeWidth={0.5} />
      {/* Chairs around the table */}
      <Chair x={cx - 65} y={cy} />
      <Chair x={cx + 65} y={cy} />
      <Chair x={cx}      y={cy - 42} />
      <Chair x={cx}      y={cy + 42} />
    </g>
  );
}

// ---------------------------------------------------------------------------
// Grid floor tiles for visual richness
// ---------------------------------------------------------------------------

function FloorTiles(): React.ReactElement {
  const lines: React.ReactElement[] = [];
  const gridSize = 40;

  for (let x = 0; x <= SVG_W; x += gridSize) {
    lines.push(
      <line key={`v${x}`} x1={x} y1={0} x2={x} y2={SVG_H}
        stroke="#ffffff" strokeWidth={0.15} opacity={0.04} />
    );
  }
  for (let y = 0; y <= SVG_H; y += gridSize) {
    lines.push(
      <line key={`h${y}`} x1={0} y1={y} x2={SVG_W} y2={y}
        stroke="#ffffff" strokeWidth={0.15} opacity={0.04} />
    );
  }
  return <g>{lines}</g>;
}

// ---------------------------------------------------------------------------
// Zone separator lines
// ---------------------------------------------------------------------------

function ZoneBorders(): React.ReactElement {
  return (
    <g stroke="#0d1117" strokeWidth={2} fill="none">
      {/* Horizontal corridor top border */}
      <line x1={0} y1={300} x2={SVG_W} y2={300} />
      {/* Horizontal corridor bottom border */}
      <line x1={0} y1={340} x2={SVG_W} y2={340} />
      {/* Vertical corridor left border */}
      <line x1={580} y1={0} x2={580} y2={SVG_H} />
      {/* Vertical corridor right border */}
      <line x1={620} y1={0} x2={620} y2={SVG_H} />
      {/* Support zone separator */}
      <line x1={0} y1={560} x2={580} y2={560} strokeDasharray="6 4" strokeWidth={1} stroke="#1f2937" />
    </g>
  );
}

// ---------------------------------------------------------------------------
// Role desk + chair layout helper
// ---------------------------------------------------------------------------

interface DeskSlot {
  role: string;
  pos: { x: number; y: number };
  isLarge: boolean;
}

function getDeskSlots(): DeskSlot[] {
  return Object.entries(DESK_POSITIONS).map(([role, pos]) => ({
    role,
    pos,
    isLarge: LARGE_DESK_ROLES.has(role),
  }));
}

// ---------------------------------------------------------------------------
// Main FloorPlan component
// ---------------------------------------------------------------------------

interface Props {
  agents: AgentState[];
  events: PocketTeamEvent[];
}

export function FloorPlan({ agents }: Props): React.ReactElement {
  // Build a role -> agent map
  const agentsByRole = new Map<string, AgentState>();
  for (const agent of agents) {
    const role = agent.role.toLowerCase();
    const existing = agentsByRole.get(role);
    if (!existing || agentPriority(agent) > agentPriority(existing)) {
      agentsByRole.set(role, agent);
    }
  }

  const deskSlots = getDeskSlots();

  return (
    <svg
      viewBox={`0 0 ${SVG_W} ${SVG_H}`}
      preserveAspectRatio="xMidYMid meet"
      style={{ width: "100%", height: "100%", display: "block" }}
    >
      {/* ── Layer 0: Background ── */}
      <rect width={SVG_W} height={SVG_H} fill="#1a1f2e" />

      {/* ── Layer 1: Zone floors ── */}
      {Object.values(ZONES).map((zone, i) => (
        <ZoneRect key={i} zone={zone as { x: number; y: number; w: number; h: number; label: string; color: string }} />
      ))}

      {/* ── Layer 2: Subtle grid ── */}
      <FloorTiles />

      {/* ── Layer 3: Zone borders / walls ── */}
      <ZoneBorders />

      {/* ── Layer 4: Furniture ── */}
      {/* Regular desks + chairs */}
      {deskSlots.map(({ role, pos, isLarge }) => (
        <g key={role}>
          <Chair x={pos.x} y={pos.y + (isLarge ? 46 : 38)} />
          <Desk
            x={pos.x}
            y={pos.y}
            color={isLarge ? "#3a2e24" : "#2d3748"}
          />
        </g>
      ))}

      {/* COO meeting table */}
      <MeetingTable />

      {/* ── Layer 5: Decorative plants ── */}
      <Plant x={28}   y={270}  scale={0.85} />
      <Plant x={550}  y={270}  scale={0.85} />
      <Plant x={630}  y={270}  scale={0.85} />
      <Plant x={1170} y={270}  scale={0.85} />
      <Plant x={28}   y={530}  scale={0.85} />
      <Plant x={550}  y={530}  scale={0.85} />
      <Plant x={1170} y={530}  scale={0.85} />
      <Plant x={1170} y={670}  scale={0.85} />

      {/* ── Layer 6: Agents at their desks ── */}
      {deskSlots.map(({ role, pos }) => {
        const agent = agentsByRole.get(role) ?? null;
        const avatar = generateAvatar(role);

        if (agent === null) {
          // Idle placeholder — dimmed avatar
          return (
            <AgentAvatar
              key={role}
              x={pos.x}
              y={pos.y - 18}
              avatar={avatar}
              role={role}
              status="idle"
            />
          );
        }

        return (
          <AgentAvatar
            key={role}
            x={pos.x}
            y={pos.y - 18}
            avatar={avatar}
            role={role}
            status={agent.status}
            description={agent.description}
            toolCallCount={agent.toolCallCount}
          />
        );
      })}

      {/* ── Layer 7: Corridor label ── */}
      <text
        x={SVG_W / 2}
        y={325}
        textAnchor="middle"
        fontSize={8}
        fill="#374151"
        fontFamily="monospace"
        fontWeight="700"
        letterSpacing="3"
      >
        CORRIDOR
      </text>
    </svg>
  );
}

function agentPriority(a: AgentState): number {
  if (a.status === "working") return 2;
  if (a.status === "done") return 1;
  return 0;
}
