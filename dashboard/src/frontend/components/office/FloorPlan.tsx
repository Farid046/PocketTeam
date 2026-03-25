import React from "react";
import type { AgentState, PocketTeamEvent } from "../../types";
import { Desk } from "./Desk";
import { Chair } from "./Chair";
import { Plant } from "./Plant";
import { AgentAvatar } from "./AgentAvatar";
import { generateAvatar } from "./avatarGenerator";
import { toIso, tilePath, tileCenter } from "./isoUtils";

// ---------------------------------------------------------------------------
// SVG canvas and grid dimensions
// ---------------------------------------------------------------------------

// Total grid: 12 cols x 10 rows. SVG canvas sized to fit the whole diamond grid.
// Isometric grid spans: x from -(COLS+ROWS)*TILE_W/2 to +(COLS+ROWS)*TILE_W/2
// We use a generous viewBox with origin at the center-top.
const GRID_COLS = 12;
const GRID_ROWS = 10;

// Canvas dimensions — give extra room for characters and speech bubbles
const SVG_W = 1100;
const SVG_H = 660;

// The iso grid's leftmost screen X is at (0 - GRID_ROWS) * (TILE_W/2)
// We translate by OFFSET to center the grid in the SVG.
const OFFSET_X = SVG_W / 2;  // center horizontally
const OFFSET_Y = 80;          // push down from top so row 0 is visible

// ---------------------------------------------------------------------------
// Zone definitions — which grid cells belong to which zone
// ---------------------------------------------------------------------------

type ZoneName = "planning" | "engineering" | "operations" | "support" | "coo" | "corridor" | "empty";

const ZONE_COLORS: Record<ZoneName, string> = {
  planning:    "#2a2a3a",
  engineering: "#2a2833",
  operations:  "#2a3030",
  support:     "#2a2a2e",
  coo:         "#332a20",
  corridor:    "#1e1e28",
  empty:       "#181820",
};

const ZONE_STROKE: Record<ZoneName, string> = {
  planning:    "#3a3a4e",
  engineering: "#3a3845",
  operations:  "#3a4040",
  support:     "#3a3a3e",
  coo:         "#453a2e",
  corridor:    "#282830",
  empty:       "#202028",
};

// Build a lookup: "col,row" -> zone name
function buildZoneMap(): Map<string, ZoneName> {
  const map = new Map<string, ZoneName>();

  const set = (col: number, row: number, zone: ZoneName) => {
    map.set(`${col},${row}`, zone);
  };

  // Fill all tiles as empty first (only fill defined areas)
  for (let c = 0; c < GRID_COLS; c++) {
    for (let r = 0; r < GRID_ROWS; r++) {
      set(c, r, "empty");
    }
  }

  // Planning zone — cols 0-4, rows 0-4
  for (let c = 0; c <= 4; c++) for (let r = 0; r <= 4; r++) set(c, r, "planning");

  // Engineering zone — cols 0-4, rows 5-9
  for (let c = 0; c <= 4; c++) for (let r = 5; r <= 9; r++) set(c, r, "engineering");

  // Corridor — col 5, all rows
  for (let r = 0; r < GRID_ROWS; r++) set(5, r, "corridor");

  // Operations zone — cols 6-10, rows 0-4
  for (let c = 6; c <= 10; c++) for (let r = 0; r <= 4; r++) set(c, r, "operations");

  // COO office — cols 6-10, rows 5-9
  for (let c = 6; c <= 10; c++) for (let r = 5; r <= 9; r++) set(c, r, "coo");

  // Support sub-zone — bottom of engineering (rows 7-9, cols 0-3) kept as engineering but visually distinct
  // (support agents share engineering floor, just their positions differ)

  return map;
}

const ZONE_MAP = buildZoneMap();

// ---------------------------------------------------------------------------
// Zone labels — placed at zone center tiles
// ---------------------------------------------------------------------------

const ZONE_LABELS: Array<{ col: number; row: number; text: string }> = [
  { col: 2, row: 0, text: "PLANNING" },
  { col: 2, row: 5, text: "ENGINEERING" },
  { col: 2, row: 8, text: "SUPPORT" },
  { col: 8, row: 0, text: "OPERATIONS" },
  { col: 8, row: 7, text: "COO OFFICE" },
];

// ---------------------------------------------------------------------------
// Desk positions per role — grid (col, row) coordinates
// ---------------------------------------------------------------------------

const DESK_GRID: Record<string, { col: number; row: number }> = {
  product:       { col: 1, row: 1 },
  planner:       { col: 3, row: 1 },
  reviewer:      { col: 2, row: 3 },
  engineer:      { col: 1, row: 5 },
  qa:            { col: 3, row: 5 },
  security:      { col: 2, row: 7 },
  investigator:  { col: 1, row: 8 },
  documentation: { col: 3, row: 8 },
  devops:        { col: 7, row: 1 },
  monitor:       { col: 9, row: 1 },
  observer:      { col: 8, row: 3 },
  coo:           { col: 8, row: 6 },
};

// Plant decoration positions
const PLANT_GRID: Array<{ col: number; row: number }> = [
  { col: 0, row: 0 },
  { col: 4, row: 0 },
  { col: 0, row: 4 },
  { col: 4, row: 4 },
  { col: 6, row: 0 },
  { col: 10, row: 0 },
  { col: 6, row: 4 },
  { col: 10, row: 4 },
  { col: 0, row: 9 },
  { col: 4, row: 9 },
  { col: 6, row: 9 },
  { col: 10, row: 9 },
];

// ---------------------------------------------------------------------------
// Helper: convert grid coord to SVG screen coord (with canvas offset)
// ---------------------------------------------------------------------------

function gridTileCenter(col: number, row: number): { x: number; y: number } {
  const center = tileCenter(col, row);
  return { x: center.x + OFFSET_X, y: center.y + OFFSET_Y };
}

// ---------------------------------------------------------------------------
// Floor tile grid — sorted by zOrder for correct isometric rendering
// ---------------------------------------------------------------------------

function FloorTiles(): React.ReactElement {
  // Collect all tiles with their z-order
  const tiles: Array<{ col: number; row: number; zone: ZoneName; z: number }> = [];

  for (let c = 0; c < GRID_COLS; c++) {
    for (let r = 0; r < GRID_ROWS; r++) {
      const zone = ZONE_MAP.get(`${c},${r}`) ?? "empty";
      tiles.push({ col: c, row: r, zone, z: c + r });
    }
  }

  // Sort by z-order (painter's algorithm)
  tiles.sort((a, b) => a.z - b.z || a.col - b.col);

  return (
    <g>
      {tiles.map(({ col, row, zone }) => {
        const rawPoints = tilePath(col, row);
        // Offset points by OFFSET_X, OFFSET_Y
        const points = rawPoints
          .split(" ")
          .map((pt) => {
            const [px, py] = pt.split(",").map(Number);
            return `${px + OFFSET_X},${py + OFFSET_Y}`;
          })
          .join(" ");

        return (
          <polygon
            key={`${col},${row}`}
            points={points}
            fill={ZONE_COLORS[zone]}
            stroke={ZONE_STROKE[zone]}
            strokeWidth={0.5}
          />
        );
      })}
    </g>
  );
}

// ---------------------------------------------------------------------------
// Zone labels
// ---------------------------------------------------------------------------

function ZoneLabels(): React.ReactElement {
  return (
    <g>
      {ZONE_LABELS.map(({ col, row, text }) => {
        const { x, y } = gridTileCenter(col, row);
        return (
          <text
            key={text}
            x={x}
            y={y}
            textAnchor="middle"
            fontSize={7}
            fill="#3a3a50"
            fontFamily="monospace"
            fontWeight="700"
            letterSpacing="1.5"
          >
            {text}
          </text>
        );
      })}
    </g>
  );
}

// ---------------------------------------------------------------------------
// Corridor label
// ---------------------------------------------------------------------------

function CorridorLabel(): React.ReactElement {
  const { x, y } = gridTileCenter(5, 5);
  return (
    <text
      x={x}
      y={y}
      textAnchor="middle"
      fontSize={6}
      fill="#2a2a38"
      fontFamily="monospace"
      fontWeight="700"
      letterSpacing="2"
    >
      CORRIDOR
    </text>
  );
}

// ---------------------------------------------------------------------------
// Furniture layer — desks and chairs, z-sorted
// ---------------------------------------------------------------------------

interface DeskSlot {
  role: string;
  col: number;
  row: number;
}

function FurnitureLayer(): React.ReactElement {
  // Sort desks by z-order so closer ones render on top
  const slots = Object.entries(DESK_GRID)
    .map(([role, { col, row }]) => ({ role, col, row, z: col + row }))
    .sort((a, b) => a.z - b.z);

  return (
    <g>
      {slots.map(({ role, col, row }) => {
        const center = gridTileCenter(col, row);
        // Chair sits slightly in front (lower-right of the desk in iso space)
        const chairOffset = { x: center.x + 8, y: center.y + 10 };
        return (
          <g key={role}>
            {/* Chair renders first (behind desk in z) */}
            <Chair x={chairOffset.x} y={chairOffset.y} />
            <Desk x={center.x} y={center.y} />
          </g>
        );
      })}
    </g>
  );
}

// ---------------------------------------------------------------------------
// Plant decorations
// ---------------------------------------------------------------------------

function PlantLayer(): React.ReactElement {
  const plants = PLANT_GRID
    .map(({ col, row }) => ({ col, row, z: col + row }))
    .sort((a, b) => a.z - b.z);

  return (
    <g>
      {plants.map(({ col, row }) => {
        const { x, y } = gridTileCenter(col, row);
        return (
          <Plant key={`plant-${col}-${row}`} x={x} y={y} scale={0.85} />
        );
      })}
    </g>
  );
}

// ---------------------------------------------------------------------------
// Agent layer — characters at their desks
// ---------------------------------------------------------------------------

interface AgentLayerProps {
  agents: AgentState[];
}

function AgentLayer({ agents }: AgentLayerProps): React.ReactElement {
  // Build role -> agent map (prefer working > done > idle)
  const agentsByRole = new Map<string, AgentState>();
  for (const agent of agents) {
    const role = agent.role.toLowerCase();
    const existing = agentsByRole.get(role);
    if (!existing || agentPriority(agent) > agentPriority(existing)) {
      agentsByRole.set(role, agent);
    }
  }

  // Sort by z-order
  const slots = Object.entries(DESK_GRID)
    .map(([role, { col, row }]) => ({ role, col, row, z: col + row }))
    .sort((a, b) => a.z - b.z);

  return (
    <g>
      {slots.map(({ role, col, row }) => {
        const center = gridTileCenter(col, row);
        // Agent sits in the chair: slightly forward (toward viewer) from desk center
        const avatarX = center.x + 8;
        const avatarY = center.y + 6;

        const agent = agentsByRole.get(role) ?? null;
        const avatar = generateAvatar(role);

        if (agent === null) {
          return (
            <AgentAvatar
              key={role}
              x={avatarX}
              y={avatarY}
              avatar={avatar}
              role={role}
              status="idle"
            />
          );
        }

        return (
          <AgentAvatar
            key={role}
            x={avatarX}
            y={avatarY}
            avatar={avatar}
            role={role}
            status={agent.status}
            description={agent.description}
            toolCallCount={agent.toolCallCount}
          />
        );
      })}
    </g>
  );
}

// ---------------------------------------------------------------------------
// CSS animations injected as <style> in the SVG
// ---------------------------------------------------------------------------

function SvgStyles(): React.ReactElement {
  return (
    <defs>
      <style>{`
        @keyframes pulse-ring {
          0%   { opacity: 0.7; transform: scale(1); }
          50%  { opacity: 0.3; transform: scale(1.15); }
          100% { opacity: 0.7; transform: scale(1); }
        }
        @keyframes float-bubble {
          0%   { transform: translateY(0px); }
          50%  { transform: translateY(-3px); }
          100% { transform: translateY(0px); }
        }
      `}</style>
    </defs>
  );
}

// ---------------------------------------------------------------------------
// Main FloorPlan component
// ---------------------------------------------------------------------------

interface Props {
  agents: AgentState[];
  events: PocketTeamEvent[];
}

export function FloorPlan({ agents }: Props): React.ReactElement {
  return (
    <svg
      viewBox={`0 0 ${SVG_W} ${SVG_H}`}
      preserveAspectRatio="xMidYMid meet"
      style={{ width: "100%", height: "100%", display: "block" }}
    >
      <SvgStyles />

      {/* ── Layer 0: Background ── */}
      <rect width={SVG_W} height={SVG_H} fill="#13131c" />

      {/* ── Layer 1: Isometric floor tiles ── */}
      <FloorTiles />

      {/* ── Layer 2: Zone labels on floor ── */}
      <ZoneLabels />
      <CorridorLabel />

      {/* ── Layer 3: Furniture (desks + chairs) ── */}
      <FurnitureLayer />

      {/* ── Layer 4: Decorative plants ── */}
      <PlantLayer />

      {/* ── Layer 5: Agent characters ── */}
      <AgentLayer agents={agents} />
    </svg>
  );
}

function agentPriority(a: AgentState): number {
  if (a.status === "working") return 2;
  if (a.status === "done") return 1;
  return 0;
}
