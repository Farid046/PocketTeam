import React, { useEffect, useRef, useState } from "react";
import type { AgentState, PocketTeamEvent } from "../../types";
import { Desk } from "./Desk";
import { Chair } from "./Chair";
import { Plant } from "./Plant";
import { CoffeeMachine } from "./CoffeeMachine";
import { AgentAvatar } from "./AgentAvatar";
import { generateAvatar } from "./avatarGenerator";
import { tilePath, tileCenter, TILE_W, TILE_H } from "./isoUtils";

// ---------------------------------------------------------------------------
// SVG canvas and grid dimensions — 8 cols x 6 rows
// ---------------------------------------------------------------------------

const GRID_COLS = 8;
const GRID_ROWS = 6;
const SVG_W = 1400;
const SVG_H = 820;
const OFFSET_X = SVG_W / 2;
const OFFSET_Y = 120;

// ---------------------------------------------------------------------------
// Zone definitions
// ---------------------------------------------------------------------------

type ZoneName = "lounge" | "corridor" | "workspace" | "empty";

const ZONE_COLORS: Record<ZoneName, string> = {
  lounge:    "#2a2520",
  corridor:  "#1e1e28",
  workspace: "#1e2030",
  empty:     "#181820",
};

const ZONE_STROKE: Record<ZoneName, string> = {
  lounge:    "#3a3530",
  corridor:  "#282830",
  workspace: "#2a2a40",
  empty:     "#202028",
};

function buildZoneMap(): Map<string, ZoneName> {
  const map = new Map<string, ZoneName>();
  for (let c = 0; c < GRID_COLS; c++) {
    for (let r = 0; r < GRID_ROWS; r++) {
      if (r <= 1) map.set(`${c},${r}`, "lounge");
      else if (r === 2) map.set(`${c},${r}`, "corridor");
      else map.set(`${c},${r}`, "workspace");
    }
  }
  return map;
}

const ZONE_MAP = buildZoneMap();

// ---------------------------------------------------------------------------
// Layout positions — 8x6 grid
// ---------------------------------------------------------------------------

/** Work desks in workspace rows 3-5 */
const WORK_DESKS: Array<{ col: number; row: number }> = [
  { col: 1, row: 3 },
  { col: 3, row: 3 },
  { col: 5, row: 3 },
  { col: 7, row: 3 },
  { col: 2, row: 5 },
  { col: 6, row: 5 },
];

/** COO desk — center of workspace */
const COO_DESK = { col: 4, row: 4 };

/** Lounge spots for idle/done agents in rows 0-1 */
const LOUNGE_SPOTS: Array<{ col: number; row: number }> = [
  { col: 1, row: 0 },
  { col: 2, row: 0 },
  { col: 4, row: 0 },
  { col: 6, row: 0 },
  { col: 1, row: 1 },
  { col: 3, row: 1 },
  { col: 5, row: 1 },
  { col: 6, row: 1 },
  { col: 2, row: 1 },
  { col: 4, row: 1 },
  { col: 7, row: 1 },
  { col: 0, row: 1 },
];

/** Plants — corners and workspace edges */
const PLANT_POSITIONS: Array<{ col: number; row: number }> = [
  { col: 0, row: 0 },
  { col: 7, row: 0 },
  { col: 0, row: 1 },
  { col: 7, row: 1 },
  { col: 0, row: 5 },
  { col: 7, row: 5 },
];

/** Coffee machine in lounge */
const COFFEE_MACHINE_POS = { col: 1, row: 1 };

/** Couch positions in lounge */
const COUCH_POSITIONS = [
  { col: 3, row: 0 },
  { col: 5, row: 0 },
];

/** Canonical role order for deterministic lounge placement */
const ALL_ROLES = [
  "product", "planner", "reviewer", "engineer", "qa", "security",
  "investigator", "documentation", "devops", "monitor", "observer",
  "researcher",
];

// ---------------------------------------------------------------------------
// Agent position state machine
// ---------------------------------------------------------------------------

interface AgentVisualState {
  currentX: number;
  currentY: number;
  targetX: number;
  targetY: number;
  isWalking: boolean;
  zone: "lounge" | "desk";
  deskIndex: number;
  loungeIndex: number;
}

// ---------------------------------------------------------------------------
// Helper: grid position to screen coords
// ---------------------------------------------------------------------------

function gridCenter(col: number, row: number): { x: number; y: number } {
  const c = tileCenter(col, row);
  return { x: c.x + OFFSET_X, y: c.y + OFFSET_Y };
}

// ---------------------------------------------------------------------------
// Floor tiles
// ---------------------------------------------------------------------------

function FloorTiles(): React.ReactElement {
  const tiles: Array<{ col: number; row: number; zone: ZoneName; z: number }> = [];
  for (let c = 0; c < GRID_COLS; c++) {
    for (let r = 0; r < GRID_ROWS; r++) {
      tiles.push({ col: c, row: r, zone: ZONE_MAP.get(`${c},${r}`) ?? "empty", z: c + r });
    }
  }
  tiles.sort((a, b) => a.z - b.z || a.col - b.col);

  return (
    <g>
      {tiles.map(({ col, row, zone }) => {
        const raw = tilePath(col, row);
        const pts = raw
          .split(" ")
          .map((pt) => {
            const [px, py] = pt.split(",").map(Number);
            return `${px + OFFSET_X},${py + OFFSET_Y}`;
          })
          .join(" ");

        // Corridor row gets a subtle glass/stripe effect
        const isCorridorTile = zone === "corridor";

        return (
          <g key={`${col},${row}`}>
            <polygon
              points={pts}
              fill={ZONE_COLORS[zone]}
              stroke={ZONE_STROKE[zone]}
              strokeWidth={0.5}
            />
            {isCorridorTile && (
              <polygon
                points={pts}
                fill="none"
                stroke="#3a3a55"
                strokeWidth={0.3}
                opacity={0.4}
              />
            )}
          </g>
        );
      })}
    </g>
  );
}

// ---------------------------------------------------------------------------
// Walls — north + west, 80px tall with blue window cutouts
// ---------------------------------------------------------------------------

const WALL_HEIGHT = 80;

function WallLayer(): React.ReactElement {
  const wallColor = { north: "#1a1a2e", west: "#12121e", top: "#22223a" };
  const windowColor = "#1a3a5c";
  const windowGlow = "#2a5a8c";

  const northWallSegments: React.ReactElement[] = [];
  const westWallSegments: React.ReactElement[] = [];

  // North wall: along row=0
  for (let c = 0; c < GRID_COLS; c++) {
    const { x: tx, y: ty } = tileCenter(c, 0);
    const sx = tx + OFFSET_X;
    const sy = ty + OFFSET_Y;
    const hw = TILE_W / 2;
    const hh = TILE_H / 2;

    const x1 = sx;
    const y1 = sy - hh;
    const x2 = sx + hw;
    const y2 = sy;

    northWallSegments.push(
      <polygon
        key={`nw-${c}`}
        points={`${x1},${y1} ${x2},${y2} ${x2},${y2 - WALL_HEIGHT} ${x1},${y1 - WALL_HEIGHT}`}
        fill={wallColor.north}
        stroke="#252545"
        strokeWidth={0.3}
      />
    );

    // Window cutout — centered on wall face
    const winX1 = x1 + (x2 - x1) * 0.25;
    const winY1 = y1 + (y2 - y1) * 0.25;
    const winX2 = x1 + (x2 - x1) * 0.75;
    const winY2 = y1 + (y2 - y1) * 0.75;
    const winTop = WALL_HEIGHT * 0.2;
    const winBot = WALL_HEIGHT * 0.65;

    northWallSegments.push(
      <polygon
        key={`nw-win-${c}`}
        points={`${winX1},${winY1 - winTop} ${winX2},${winY2 - winTop} ${winX2},${winY2 - winBot} ${winX1},${winY1 - winBot}`}
        fill={windowColor}
        stroke={windowGlow}
        strokeWidth={0.6}
        opacity={0.7}
      />
    );

    northWallSegments.push(
      <line
        key={`nwt-${c}`}
        x1={x1} y1={y1 - WALL_HEIGHT}
        x2={x2} y2={y2 - WALL_HEIGHT}
        stroke="#303055"
        strokeWidth={0.8}
      />
    );
  }

  // West wall: along col=0
  for (let r = 0; r < GRID_ROWS; r++) {
    const { x: tx, y: ty } = tileCenter(0, r);
    const sx = tx + OFFSET_X;
    const sy = ty + OFFSET_Y;
    const hw = TILE_W / 2;
    const hh = TILE_H / 2;

    const x1 = sx;
    const y1 = sy - hh;
    const x2 = sx - hw;
    const y2 = sy;

    westWallSegments.push(
      <polygon
        key={`ww-${r}`}
        points={`${x1},${y1} ${x2},${y2} ${x2},${y2 - WALL_HEIGHT} ${x1},${y1 - WALL_HEIGHT}`}
        fill={wallColor.west}
        stroke="#1e1e38"
        strokeWidth={0.3}
      />
    );

    // Window cutout on west wall
    const winX1 = x1 + (x2 - x1) * 0.25;
    const winY1 = y1 + (y2 - y1) * 0.25;
    const winX2 = x1 + (x2 - x1) * 0.75;
    const winY2 = y1 + (y2 - y1) * 0.75;
    const winTop = WALL_HEIGHT * 0.2;
    const winBot = WALL_HEIGHT * 0.65;

    westWallSegments.push(
      <polygon
        key={`ww-win-${r}`}
        points={`${winX1},${winY1 - winTop} ${winX2},${winY2 - winTop} ${winX2},${winY2 - winBot} ${winX1},${winY1 - winBot}`}
        fill={windowColor}
        stroke={windowGlow}
        strokeWidth={0.6}
        opacity={0.7}
      />
    );

    westWallSegments.push(
      <line
        key={`wwt-${r}`}
        x1={x1} y1={y1 - WALL_HEIGHT}
        x2={x2} y2={y2 - WALL_HEIGHT}
        stroke="#282845"
        strokeWidth={0.8}
      />
    );
  }

  // Corner pillar
  const corner = tileCenter(0, 0);
  const cx = corner.x + OFFSET_X;
  const cy = corner.y + OFFSET_Y - TILE_H / 2;

  return (
    <g>
      {westWallSegments}
      {northWallSegments}
      <line
        x1={cx} y1={cy}
        x2={cx} y2={cy - WALL_HEIGHT}
        stroke="#303055"
        strokeWidth={2}
      />
    </g>
  );
}

// ---------------------------------------------------------------------------
// Zone labels
// ---------------------------------------------------------------------------

function ZoneLabels(): React.ReactElement {
  const labels = [
    { col: 3, row: 0, text: "LOUNGE" },
    { col: 3, row: 5, text: "WORKSPACE" },
  ];
  return (
    <g>
      {labels.map(({ col, row, text }) => {
        const { x, y } = gridCenter(col, row);
        return (
          <text
            key={text + col + row}
            x={x}
            y={y}
            textAnchor="middle"
            fontSize={8}
            fill="#3a3a52"
            fontFamily="monospace"
            fontWeight="700"
            letterSpacing="2"
          >
            {text}
          </text>
        );
      })}
    </g>
  );
}

// ---------------------------------------------------------------------------
// Inline lounge furniture
// ---------------------------------------------------------------------------

function Couch({ x, y }: { x: number; y: number }): React.ReactElement {
  return (
    <g>
      <polygon
        points={`${x - 28},${y - 8} ${x},${y - 22} ${x + 28},${y - 8} ${x},${y + 6}`}
        fill="#3a2845"
      />
      <polygon
        points={`${x - 28},${y - 8} ${x - 28},${y + 6} ${x - 14},${y + 13} ${x - 14},${y - 1}`}
        fill="#2a1835"
      />
      <polygon
        points={`${x + 28},${y - 8} ${x + 28},${y + 6} ${x + 14},${y + 13} ${x + 14},${y - 1}`}
        fill="#201030"
      />
      <polygon
        points={`${x - 20},${y - 10} ${x},${y - 22} ${x + 20},${y - 10} ${x},${y - 4}`}
        fill="#4a3058"
        opacity={0.5}
      />
    </g>
  );
}

// ---------------------------------------------------------------------------
// Furniture layer
// ---------------------------------------------------------------------------

function FurnitureLayer({
  occupiedDesks,
  showCooDesk,
}: {
  occupiedDesks: number;
  showCooDesk: boolean;
}): React.ReactElement {
  const items: Array<{ key: string; z: number; el: React.ReactElement }> = [];

  // Work desks — only render for occupied slots
  for (let i = 0; i < Math.min(occupiedDesks, WORK_DESKS.length); i++) {
    const { col, row } = WORK_DESKS[i];
    const c = gridCenter(col, row);
    items.push({
      key: `wdesk-${i}`,
      z: col + row,
      el: (
        <g>
          <Chair x={c.x + 12} y={c.y + 15} />
          <Desk x={c.x} y={c.y} />
        </g>
      ),
    });
  }

  // COO desk
  if (showCooDesk) {
    const c = gridCenter(COO_DESK.col, COO_DESK.row);
    items.push({
      key: "desk-coo",
      z: COO_DESK.col + COO_DESK.row,
      el: (
        <g>
          <Chair x={c.x + 12} y={c.y + 15} />
          <Desk x={c.x} y={c.y} />
        </g>
      ),
    });
  }

  // Couches
  for (let i = 0; i < COUCH_POSITIONS.length; i++) {
    const { col, row } = COUCH_POSITIONS[i];
    const { x, y } = gridCenter(col, row);
    items.push({ key: `couch-${i}`, z: col + row, el: <Couch x={x} y={y} /> });
  }

  items.sort((a, b) => a.z - b.z);

  return (
    <g>
      {items.map(({ key, el }) => (
        <React.Fragment key={key}>{el}</React.Fragment>
      ))}
    </g>
  );
}

// ---------------------------------------------------------------------------
// Plants
// ---------------------------------------------------------------------------

function PlantLayer(): React.ReactElement {
  const sorted = [...PLANT_POSITIONS]
    .map((p) => ({ ...p, z: p.col + p.row }))
    .sort((a, b) => a.z - b.z);

  return (
    <g>
      {sorted.map(({ col, row }) => {
        const { x, y } = gridCenter(col, row);
        return <Plant key={`p-${col}-${row}`} x={x} y={y} scale={1.3} />;
      })}
    </g>
  );
}

// ---------------------------------------------------------------------------
// Coffee machine
// ---------------------------------------------------------------------------

function CoffeeMachineLayer(): React.ReactElement {
  const { x, y } = gridCenter(COFFEE_MACHINE_POS.col, COFFEE_MACHINE_POS.row);
  return <CoffeeMachine x={x} y={y} />;
}

// ---------------------------------------------------------------------------
// Agent layer with smooth walking transitions
// ---------------------------------------------------------------------------

function agentPriority(a: AgentState): number {
  if (a.status === "working") return 2;
  if (a.status === "done") return 1;
  return 0;
}

interface AgentPos {
  x: number;
  y: number;
  targetX: number;
  targetY: number;
  isWalking: boolean;
}

function AgentLayer({ agents }: { agents: AgentState[] }): React.ReactElement {
  // Dedupe by role
  const byRole = new Map<string, AgentState>();
  for (const a of agents) {
    const r = a.role.toLowerCase();
    const prev = byRole.get(r);
    if (!prev || agentPriority(a) > agentPriority(prev)) byRole.set(r, a);
  }

  const cooAgent = byRole.get("coo") ?? null;

  const working: Array<{ role: string; agent: AgentState }> = [];
  const lounge: Array<{ role: string; agent: AgentState | null }> = [];

  for (const [role, agent] of byRole) {
    if (role === "coo") continue;
    if (agent.status === "working") working.push({ role, agent });
    else lounge.push({ role, agent });
  }

  // Ghost agents for roles with no data
  for (const role of ALL_ROLES) {
    if (!byRole.has(role)) lounge.push({ role, agent: null });
  }

  lounge.sort((a, b) => {
    const ai = ALL_ROLES.indexOf(a.role);
    const bi = ALL_ROLES.indexOf(b.role);
    return (ai < 0 ? 99 : ai) - (bi < 0 ? 99 : bi);
  });

  // Agent position state for smooth transitions
  const [positions, setPositions] = useState<Map<string, AgentPos>>(() => new Map());
  const prevStatusRef = useRef<Map<string, string>>(new Map());

  useEffect(() => {
    const newPositions = new Map(positions);
    let changed = false;

    // Working agents
    for (let i = 0; i < working.length && i < WORK_DESKS.length; i++) {
      const { role, agent } = working[i];
      const { col, row } = WORK_DESKS[i];
      const c = gridCenter(col, row);
      const targetX = c.x + 12;
      const targetY = c.y + 6;

      const prevStatus = prevStatusRef.current.get(role);
      const existing = newPositions.get(role);

      if (!existing) {
        // First time — start at lounge, walk to desk
        const loungeIdx = ALL_ROLES.indexOf(role) % LOUNGE_SPOTS.length;
        const lc = gridCenter(LOUNGE_SPOTS[loungeIdx].col, LOUNGE_SPOTS[loungeIdx].row);
        newPositions.set(role, {
          x: lc.x,
          y: lc.y,
          targetX,
          targetY,
          isWalking: true,
        });
        changed = true;
      } else if (prevStatus !== agent.status && (Math.abs(existing.targetX - targetX) > 5 || Math.abs(existing.targetY - targetY) > 5)) {
        newPositions.set(role, {
          ...existing,
          targetX,
          targetY,
          isWalking: true,
        });
        changed = true;
      }
    }

    // Lounge agents
    for (let i = 0; i < lounge.length && i < LOUNGE_SPOTS.length; i++) {
      const { role, agent } = lounge[i];
      const { col, row } = LOUNGE_SPOTS[i];
      const c = gridCenter(col, row);
      const targetX = c.x;
      const targetY = c.y;

      const prevStatus = prevStatusRef.current.get(role);
      const existing = newPositions.get(role);
      const currentStatus = agent?.status ?? "idle";

      if (!existing) {
        // First time — place directly in lounge
        newPositions.set(role, { x: targetX, y: targetY, targetX, targetY, isWalking: false });
        changed = true;
      } else if (prevStatus !== undefined && prevStatus !== currentStatus) {
        // Status changed → walk to lounge
        newPositions.set(role, { ...existing, targetX, targetY, isWalking: true });
        changed = true;
      }
    }

    // COO
    if (cooAgent) {
      const c = gridCenter(COO_DESK.col, COO_DESK.row);
      const targetX = c.x + 12;
      const targetY = c.y + 6;
      const existing = newPositions.get("coo");
      if (!existing) {
        newPositions.set("coo", { x: targetX, y: targetY, targetX, targetY, isWalking: false });
        changed = true;
      }
    }

    if (changed) {
      setPositions(newPositions);
    }

    // Update prev status refs
    for (const [role, agent] of byRole) {
      prevStatusRef.current.set(role, agent.status);
    }

    // After walking, stop the walk animation
    const walkingRoles: string[] = [];
    for (const [role, pos] of newPositions) {
      if (pos.isWalking) walkingRoles.push(role);
    }
    if (walkingRoles.length > 0) {
      const timer = setTimeout(() => {
        setPositions((prev) => {
          const updated = new Map(prev);
          for (const role of walkingRoles) {
            const p = updated.get(role);
            if (p) {
              updated.set(role, { x: p.targetX, y: p.targetY, targetX: p.targetX, targetY: p.targetY, isWalking: false });
            }
          }
          return updated;
        });
      }, 1600);
      return () => clearTimeout(timer);
    }
  }, [agents]); // eslint-disable-line react-hooks/exhaustive-deps

  const items: Array<{ key: string; z: number; el: React.ReactElement }> = [];

  // Working agents
  for (let i = 0; i < working.length && i < WORK_DESKS.length; i++) {
    const { role, agent } = working[i];
    const pos = positions.get(role);
    const { col, row } = WORK_DESKS[i];
    const fallback = gridCenter(col, row);
    const px = pos ? (pos.isWalking ? pos.x : pos.targetX) : fallback.x + 12;
    const py = pos ? (pos.isWalking ? pos.y : pos.targetY) : fallback.y + 6;

    items.push({
      key: `w-${role}`,
      z: col + row + 0.5,
      el: (
        <g
          style={{
            transform: `translate(${px}px, ${py}px)`,
            transition: pos?.isWalking ? "transform 1.5s ease-in-out" : "none",
          }}
        >
          <AgentAvatar
            x={0}
            y={0}
            avatar={generateAvatar(role)}
            role={role}
            status={agent.status}
            description={agent.description}
            toolCallCount={agent.toolCallCount}
          />
        </g>
      ),
    });
  }

  // Lounge agents
  for (let i = 0; i < lounge.length && i < LOUNGE_SPOTS.length; i++) {
    const { role, agent } = lounge[i];
    const { col, row } = LOUNGE_SPOTS[i];
    const pos = positions.get(role);
    const fallback = gridCenter(col, row);
    const px = pos ? (pos.isWalking ? pos.x : pos.targetX) : fallback.x;
    const py = pos ? (pos.isWalking ? pos.y : pos.targetY) : fallback.y;

    items.push({
      key: `l-${role}`,
      z: col + row + 0.1,
      el: (
        <g
          style={{
            transform: `translate(${px}px, ${py}px)`,
            transition: pos?.isWalking ? "transform 1.5s ease-in-out" : "none",
          }}
        >
          <AgentAvatar
            x={0}
            y={0}
            avatar={generateAvatar(role)}
            role={role}
            status={agent?.status ?? "idle"}
            description={agent?.description}
            toolCallCount={agent?.toolCallCount}
          />
        </g>
      ),
    });
  }

  // COO
  if (cooAgent) {
    const pos = positions.get("coo");
    const fallback = gridCenter(COO_DESK.col, COO_DESK.row);
    const px = pos?.targetX ?? fallback.x + 12;
    const py = pos?.targetY ?? fallback.y + 6;

    items.push({
      key: "coo",
      z: COO_DESK.col + COO_DESK.row + 0.5,
      el: (
        <g style={{ transform: `translate(${px}px, ${py}px)` }}>
          <AgentAvatar
            x={0}
            y={0}
            avatar={generateAvatar("coo")}
            role="coo"
            status={cooAgent.status}
            description={cooAgent.description}
            toolCallCount={cooAgent.toolCallCount}
          />
        </g>
      ),
    });
  }

  items.sort((a, b) => a.z - b.z);

  return (
    <g>
      {items.map(({ key, el }) => (
        <React.Fragment key={key}>{el}</React.Fragment>
      ))}
    </g>
  );
}

// ---------------------------------------------------------------------------
// CSS animations in SVG defs
// ---------------------------------------------------------------------------

function SvgStyles(): React.ReactElement {
  return (
    <defs>
      <style>{`
        @keyframes agent-type {
          0%, 100% { transform: translateY(0px); }
          25%  { transform: translateY(-1px); }
          50%  { transform: translateY(0px); }
          75%  { transform: translateY(-0.5px); }
        }
        @keyframes agent-walk {
          0%, 100% { transform: translateY(0px); }
          25%  { transform: translateY(-2px) translateX(-1px); }
          50%  { transform: translateY(0px); }
          75%  { transform: translateY(-2px) translateX(1px); }
        }
        @keyframes steam-rise {
          0%   { opacity: 0.6; transform: translateY(0px) scaleX(1); }
          50%  { opacity: 0.3; transform: translateY(-8px) scaleX(1.3); }
          100% { opacity: 0;   transform: translateY(-15px) scaleX(0.8); }
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
  const workingCount = agents.filter(
    (a) => a.role.toLowerCase() !== "coo" && a.status === "working",
  ).length;
  const hasCoo = agents.some((a) => a.role.toLowerCase() === "coo");

  return (
    <svg
      viewBox={`0 0 ${SVG_W} ${SVG_H}`}
      preserveAspectRatio="xMidYMid meet"
      style={{ width: "100%", height: "100%", display: "block" }}
    >
      <SvgStyles />
      <rect width={SVG_W} height={SVG_H} fill="#0e0e14" />
      <WallLayer />
      <FloorTiles />
      <ZoneLabels />
      <FurnitureLayer occupiedDesks={workingCount} showCooDesk={hasCoo} />
      <CoffeeMachineLayer />
      <PlantLayer />
      <AgentLayer agents={agents} />
    </svg>
  );
}
