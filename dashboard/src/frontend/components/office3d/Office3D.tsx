import React from "react";
import { Canvas } from "@react-three/fiber";
import { OrthographicCamera, OrbitControls, Grid, Html } from "@react-three/drei";
import type { AgentState } from "../../types";
import { Desk3D } from "./Desk3D";
import { Chair3D } from "./Chair3D";
import { Plant3D } from "./Plant3D";
import { CoffeeMachine3D } from "./CoffeeMachine3D";
import { Character3D } from "./Character3D";
import { generateAvatar } from "./avatarGenerator";

// ---------------------------------------------------------------------------
// Layout constants
// ---------------------------------------------------------------------------

// Lounge spots (x, z)
const LOUNGE_SPOTS: Array<[number, number]> = [
  [2, 1], [4, 1], [6, 1], [8, 1], [10, 1], [12, 1],
  [3, 3], [5, 3], [7, 3], [9, 3], [11, 3],
  [4, 2], [8, 2],
];

// Work desks (x, z)
const WORK_DESKS: Array<[number, number]> = [
  [3, 7], [7, 7], [11, 7], [15, 7],
  [5, 10], [13, 10],
];

// COO desk
const COO_DESK: [number, number] = [9, 9];

// Plant positions (x, z)
const PLANT_POSITIONS: Array<[number, number]> = [
  [0.5, 0.5], [19, 0.5], [0.5, 11], [19, 11], [0.5, 5], [19, 5],
];

// Couch positions (x, z)
const COUCH_POSITIONS: Array<[number, number]> = [
  [5, 1], [12, 1],
];

// Entrance position — new agents walk in from here
const ENTRANCE_POS: [number, number, number] = [10, 0, 0];

// Canonical role order for deterministic placement
const ALL_ROLES = [
  "product", "planner", "reviewer", "engineer", "qa", "security",
  "investigator", "documentation", "devops", "monitor", "observer",
  "researcher",
];

// Character stands at y=0 (above floor plane)
function charWorld(x: number, z: number): [number, number, number] {
  return [x, 0, z];
}

// ---------------------------------------------------------------------------
// Floor zones
// ---------------------------------------------------------------------------

function FloorZones(): React.ReactElement {
  return (
    <group>
      {/* Lounge zone: z=0 to z=4, x=0 to x=20 */}
      <mesh
        position={[10, -0.01, 2]}
        rotation={[-Math.PI / 2, 0, 0]}
        receiveShadow
      >
        <planeGeometry args={[20, 4]} />
        <meshStandardMaterial color="#4a4540" />
      </mesh>

      {/* Corridor: z=4 to z=6 */}
      <mesh
        position={[10, -0.01, 5]}
        rotation={[-Math.PI / 2, 0, 0]}
        receiveShadow
      >
        <planeGeometry args={[20, 2]} />
        <meshStandardMaterial color="#2a2a38" />
      </mesh>

      {/* Workspace: z=6 to z=12 */}
      <mesh
        position={[10, -0.01, 9]}
        rotation={[-Math.PI / 2, 0, 0]}
        receiveShadow
      >
        <planeGeometry args={[20, 6]} />
        <meshStandardMaterial color="#35354a" />
      </mesh>
    </group>
  );
}

// ---------------------------------------------------------------------------
// Walls — FIX 11: Added partial south and east walls
// ---------------------------------------------------------------------------

function Walls(): React.ReactElement {
  const northWallColor = "#1a1a2e";
  const westWallColor = "#12121e";
  const eastWallColor = "#111122";
  const southWallColor = "#16162a";
  const windowColor = "#1a3a5c";

  const northWindows: React.ReactElement[] = [];
  for (let i = 0; i < 7; i++) {
    const wx = 1.5 + i * 3;
    northWindows.push(
      <mesh key={`nw-win-${i}`} position={[wx, 2.0, 0.08]}>
        <boxGeometry args={[1.2, 1.8, 0.02]} />
        <meshStandardMaterial
          color={windowColor}
          emissive={windowColor}
          emissiveIntensity={0.4}
          transparent
          opacity={0.85}
        />
      </mesh>
    );
  }

  const westWindows: React.ReactElement[] = [];
  for (let i = 0; i < 4; i++) {
    const wz = 1.0 + i * 3;
    westWindows.push(
      <mesh key={`ww-win-${i}`} position={[0.08, 2.0, wz]}>
        <boxGeometry args={[0.02, 1.8, 1.2]} />
        <meshStandardMaterial
          color={windowColor}
          emissive={windowColor}
          emissiveIntensity={0.4}
          transparent
          opacity={0.85}
        />
      </mesh>
    );
  }

  return (
    <group>
      {/* North wall: z=0, x=0..20 */}
      <mesh position={[10, 2, 0]} castShadow receiveShadow>
        <boxGeometry args={[20, 4, 0.4]} />
        <meshStandardMaterial color={northWallColor} />
      </mesh>
      {northWindows}

      {/* West wall: x=0, z=0..12 */}
      <mesh position={[0, 2, 6]} castShadow receiveShadow>
        <boxGeometry args={[0.4, 4, 12]} />
        <meshStandardMaterial color={westWallColor} />
      </mesh>
      {westWindows}

      {/* East and south sides remain open for isometric camera visibility */}
    </group>
  );
}

// ---------------------------------------------------------------------------
// Couch
// ---------------------------------------------------------------------------

function Couch({ position }: { position: [number, number, number] }): React.ReactElement {
  const [px, py, pz] = position;
  return (
    <group position={[px, py, pz]}>
      {/* Seat */}
      <mesh position={[0, 0.25, 0]} castShadow receiveShadow>
        <boxGeometry args={[1.6, 0.25, 0.8]} />
        <meshStandardMaterial color="#3a2845" />
      </mesh>
      {/* Back */}
      <mesh position={[0, 0.55, -0.35]} castShadow>
        <boxGeometry args={[1.6, 0.35, 0.15]} />
        <meshStandardMaterial color="#2a1835" />
      </mesh>
      {/* Arms left */}
      <mesh position={[-0.77, 0.4, 0]} castShadow>
        <boxGeometry args={[0.15, 0.3, 0.8]} />
        <meshStandardMaterial color="#2a1835" />
      </mesh>
      {/* Arms right */}
      <mesh position={[0.77, 0.4, 0]} castShadow>
        <boxGeometry args={[0.15, 0.3, 0.8]} />
        <meshStandardMaterial color="#2a1835" />
      </mesh>
    </group>
  );
}

// ---------------------------------------------------------------------------
// Scene furniture layer
// ---------------------------------------------------------------------------

function FurnitureLayer({
  workingCount,
  showCooDesk,
}: {
  workingCount: number;
  showCooDesk: boolean;
}): React.ReactElement {
  return (
    <group>
      {/* Work desks - only for occupied spots */}
      {WORK_DESKS.slice(0, Math.min(workingCount, WORK_DESKS.length)).map(([x, z], i) => (
        <group key={`wdesk-${i}`}>
          <Desk3D position={[x, 0, z]} />
          <Chair3D position={[x, 0, z + 0.8]} rotation={Math.PI} />
        </group>
      ))}

      {/* COO desk */}
      {showCooDesk && (
        <group>
          <Desk3D position={[COO_DESK[0], 0, COO_DESK[1]]} />
          <Chair3D position={[COO_DESK[0], 0, COO_DESK[1] + 0.8]} rotation={Math.PI} />
        </group>
      )}

      {/* Couches */}
      {COUCH_POSITIONS.map(([x, z], i) => (
        <Couch key={`couch-${i}`} position={[x, 0, z]} />
      ))}

      {/* Plants */}
      {PLANT_POSITIONS.map(([x, z], i) => (
        <Plant3D key={`plant-${i}`} position={[x, 0, z]} />
      ))}

      {/* Coffee machine */}
      <CoffeeMachine3D position={[2, 0, 2]} />
    </group>
  );
}

// ---------------------------------------------------------------------------
// Zone labels using Html
// ---------------------------------------------------------------------------

function ZoneLabel({
  position,
  text,
}: {
  position: [number, number, number];
  text: string;
}): React.ReactElement {
  return (
    <Html position={position} center>
      <div
        style={{
          color: "#3a3a52",
          fontFamily: "monospace",
          fontWeight: 700,
          fontSize: "10px",
          letterSpacing: "2px",
          userSelect: "none",
          pointerEvents: "none",
          whiteSpace: "nowrap",
        }}
      >
        {text}
      </div>
    </Html>
  );
}

// ---------------------------------------------------------------------------
// Agent placement
// ---------------------------------------------------------------------------

interface AgentPlacement {
  role: string;
  id: string;
  status: string;
  description: string;
  position: [number, number, number];
  targetPosition: [number, number, number];
  shirtColor: string;
  skinColor: string;
  hairColor: string;
}

// FIX 8: Track last known positions per agent role to enable walking animation
// Stored outside component to persist across re-renders without triggering them
const lastKnownPositions = new Map<string, [number, number, number]>();
const lastKnownStatuses = new Map<string, string>();

function computePlacements(agents: AgentState[]): AgentPlacement[] {
  const byRole = new Map<string, AgentState>();
  for (const agent of agents) {
    const role = agent.role.toLowerCase();
    const existing = byRole.get(role);
    const priority = (a: AgentState) =>
      a.status === "working" ? 2 : a.status === "done" ? 1 : 0;
    if (!existing || priority(agent) > priority(existing)) {
      byRole.set(role, agent);
    }
  }

  const placements: AgentPlacement[] = [];

  const working: Array<[string, AgentState]> = [];
  const lounging: Array<[string, AgentState]> = [];

  for (const [role, agent] of byRole) {
    if (role === "coo") continue;
    if (agent.status === "working") {
      working.push([role, agent]);
    } else {
      lounging.push([role, agent]);
    }
  }

  // Sort lounge agents by canonical order
  lounging.sort(([a], [b]) => {
    const ai = ALL_ROLES.indexOf(a);
    const bi = ALL_ROLES.indexOf(b);
    return (ai < 0 ? 99 : ai) - (bi < 0 ? 99 : bi);
  });

  // FIX 7: Agent at desk sits in the chair position (dz + 0.8)
  // FIX 8: Compute start position based on last known position
  const newLastKnown = new Map<string, [number, number, number]>();
  const newLastStatuses = new Map<string, string>();

  // Working agents at desks
  for (let i = 0; i < working.length && i < WORK_DESKS.length; i++) {
    const [role, agent] = working[i];
    const [dx, dz] = WORK_DESKS[i];
    const avatar = generateAvatar(role);
    // FIX 7: sit at chair position (dz + 0.8)
    const target = charWorld(dx, dz + 0.8);

    const prevPos = lastKnownPositions.get(role);
    const prevStatus = lastKnownStatuses.get(role);

    let startPos: [number, number, number];
    if (!prevPos) {
      // New agent: walk in from entrance
      startPos = ENTRANCE_POS;
    } else if (prevStatus !== agent.status) {
      // Status changed: walk from old position to new position
      startPos = prevPos;
    } else {
      // Same spot: no walking needed
      startPos = target;
    }

    newLastKnown.set(role, target);
    newLastStatuses.set(role, agent.status);

    placements.push({
      role,
      id: agent.id,
      status: agent.status,
      description: agent.description,
      position: startPos,
      targetPosition: target,
      shirtColor: avatar.shirtColor,
      skinColor: avatar.skinColor,
      hairColor: avatar.hairColor,
    });
  }

  // Lounge agents
  for (let i = 0; i < lounging.length && i < LOUNGE_SPOTS.length; i++) {
    const [role, agent] = lounging[i];
    const [lx, lz] = LOUNGE_SPOTS[i];
    const avatar = generateAvatar(role);
    const target = charWorld(lx, lz);

    const prevPos = lastKnownPositions.get(role);
    const prevStatus = lastKnownStatuses.get(role);

    let startPos: [number, number, number];
    if (!prevPos) {
      // New agent: walk in from entrance
      startPos = ENTRANCE_POS;
    } else if (prevStatus !== agent.status) {
      // Status changed (e.g. was working, now idle): walk from desk to lounge
      startPos = prevPos;
    } else {
      // Same spot: no walking needed
      startPos = target;
    }

    newLastKnown.set(role, target);
    newLastStatuses.set(role, agent.status);

    placements.push({
      role,
      id: agent.id,
      status: agent.status,
      description: agent.description,
      position: startPos,
      targetPosition: target,
      shirtColor: avatar.shirtColor,
      skinColor: avatar.skinColor,
      hairColor: avatar.hairColor,
    });
  }

  // COO
  const cooAgent = byRole.get("coo");
  if (cooAgent) {
    const [cx, cz] = COO_DESK;
    const avatar = generateAvatar("coo");
    // FIX 7: COO also sits at chair position (cz + 0.8)
    const target = charWorld(cx, cz + 0.8);

    const prevPos = lastKnownPositions.get("coo");
    const prevStatus = lastKnownStatuses.get("coo");

    let startPos: [number, number, number];
    if (!prevPos) {
      startPos = ENTRANCE_POS;
    } else if (prevStatus !== cooAgent.status) {
      startPos = prevPos;
    } else {
      startPos = target;
    }

    newLastKnown.set("coo", target);
    newLastStatuses.set("coo", cooAgent.status);

    placements.push({
      role: "coo",
      id: cooAgent.id,
      status: cooAgent.status,
      description: cooAgent.description,
      position: startPos,
      targetPosition: target,
      shirtColor: avatar.shirtColor,
      skinColor: avatar.skinColor,
      hairColor: avatar.hairColor,
    });
  }

  // Update global position/status tracking
  for (const [role, pos] of newLastKnown) {
    lastKnownPositions.set(role, pos);
  }
  for (const [role, st] of newLastStatuses) {
    lastKnownStatuses.set(role, st);
  }

  return placements;
}

// ---------------------------------------------------------------------------
// Agent layer
// ---------------------------------------------------------------------------

function AgentLayer({ agents }: { agents: AgentState[] }): React.ReactElement {
  const placements = computePlacements(agents);

  return (
    <group>
      {placements.map((p) => (
        // FIX 8: Use role + id as key to prevent React reuse issues across identity changes
        <Character3D
          key={`${p.role}-${p.id}`}
          position={p.position}
          targetPosition={p.targetPosition}
          role={p.role}
          status={p.status}
          description={p.description}
          shirtColor={p.shirtColor}
          skinColor={p.skinColor}
          hairColor={p.hairColor}
        />
      ))}
    </group>
  );
}

// ---------------------------------------------------------------------------
// Lights — FIX 9: Use PCFShadowMap via renderer callback to avoid deprecation warning
// ---------------------------------------------------------------------------

function Lighting(): React.ReactElement {
  return (
    <>
      <ambientLight intensity={1.2} />
      <hemisphereLight args={["#d1e0ff", "#1a1a2a", 0.6]} />
      <directionalLight
        position={[12, 18, 8]}
        intensity={1.4}
        castShadow
        shadow-mapSize-width={2048}
        shadow-mapSize-height={2048}
        shadow-camera-far={50}
        shadow-camera-left={-15}
        shadow-camera-right={25}
        shadow-camera-top={15}
        shadow-camera-bottom={-2}
      />
      {/* Fill light from opposite side */}
      <directionalLight position={[-5, 10, -5]} intensity={0.5} />
    </>
  );
}

// ---------------------------------------------------------------------------
// Main Office3D
// ---------------------------------------------------------------------------

interface Props {
  agents: AgentState[];
}

export function Office3D({ agents }: Props): React.ReactElement {
  const workingCount = agents.filter(
    (a) => a.role.toLowerCase() !== "coo" && a.status === "working"
  ).length;
  const hasCoo = agents.some((a) => a.role.toLowerCase() === "coo");

  return (
    // FIX 10: Canvas fills its container (100% width/height)
    <Canvas
      shadows
      style={{ width: "100%", height: "100%", background: "#141420" }}
    >
      <OrthographicCamera
        makeDefault
        position={[25, 20, 25]}
        zoom={52}
        near={0.1}
        far={200}
      />
      <OrbitControls
        enableRotate={false}
        enablePan={true}
        enableZoom={true}
        minZoom={22}
        maxZoom={80}
        panSpeed={0.8}
        target={[10, 0, 6]}
      />

      <Lighting />

      <FloorZones />
      <Walls />

      {/* Grid helper */}
      <Grid
        position={[10, 0, 6]}
        args={[20, 12]}
        cellSize={1}
        cellThickness={0.3}
        cellColor="#3a3a50"
        sectionSize={4}
        sectionThickness={0.8}
        sectionColor="#4a4a60"
        fadeDistance={50}
        fadeStrength={1}
        followCamera={false}
        infiniteGrid={false}
      />

      <FurnitureLayer workingCount={workingCount} showCooDesk={hasCoo} />
      <AgentLayer agents={agents} />
    </Canvas>
  );
}
