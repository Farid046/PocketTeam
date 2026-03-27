import React, { useRef } from "react";
import { Canvas } from "@react-three/fiber";
import { useFrame } from "@react-three/fiber";
import { OrthographicCamera, OrbitControls, Grid, Html } from "@react-three/drei";
import type * as THREE from "three";
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

// Lounge spots (x, z) — agents on couches at z=1.5 or z=3.0, 6 couches à 2 seats = 12 spots
const LOUNGE_SPOTS: Array<[number, number]> = [
  [2.58, 1.5], [3.42, 1.5],
  [7.58, 1.5], [8.42, 1.5],
  [13.58, 1.5], [14.42, 1.5],
  [2.58, 3.0], [3.42, 3.0],
  [7.58, 3.0], [8.42, 3.0],
  [13.58, 3.0], [14.42, 3.0],
];

// Permanent desks per agent role
const AGENT_DESKS: Record<string, [number, number]> = {
  product:       [2, 7],
  planner:       [5, 7],
  reviewer:      [8, 7],
  engineer:      [11, 7],
  qa:            [14, 7],
  security:      [17, 7],
  investigator:  [2, 10],
  documentation: [5, 10],
  devops:        [8, 10],
  monitor:       [11, 10],
  observer:      [14, 10],
  researcher:    [17, 10],
};

// COO desk
const COO_DESK: [number, number] = [10, 13];

// Plant positions (x, z)
const PLANT_POSITIONS: Array<[number, number]> = [
  [0.5, 0.5], [19, 0.5],
  [0.5, 13.5], [19, 13.5],
  [0.5, 5], [19, 5],
  [7, 0.5], [15, 0.5],
  [10, 5.5], [16, 5.5],
  [7, 13.5], [13, 13.5],
];

// Entrance position — new agents walk in from here
const ENTRANCE_POS: [number, number, number] = [21, 0, 6];

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
        <meshStandardMaterial color="#5a554e" />
      </mesh>

      {/* Corridor: z=4 to z=6 */}
      <mesh
        position={[10, -0.01, 5]}
        rotation={[-Math.PI / 2, 0, 0]}
        receiveShadow
      >
        <planeGeometry args={[20, 2]} />
        <meshStandardMaterial color="#383848" />
      </mesh>

      {/* Workspace: z=6 to z=14 */}
      <mesh
        position={[10, -0.01, 10]}
        rotation={[-Math.PI / 2, 0, 0]}
        receiveShadow
      >
        <planeGeometry args={[20, 8]} />
        <meshStandardMaterial color="#424258" />
      </mesh>
    </group>
  );
}

// ---------------------------------------------------------------------------
// LED Sign
// ---------------------------------------------------------------------------

function LEDSign(): React.ReactElement {
  const glowRef = useRef<THREE.MeshStandardMaterial>(null!);

  useFrame(({ clock }) => {
    if (glowRef.current) {
      glowRef.current.emissiveIntensity = 0.3 + Math.sin(clock.elapsedTime * 2) * 0.15;
    }
  });

  return (
    <group>
      <mesh position={[10, 3.2, 0.22]}>
        <boxGeometry args={[4.2, 0.7, 0.06]} />
        <meshStandardMaterial
          ref={glowRef}
          color="#0a0a15"
          emissive="#003322"
          emissiveIntensity={0.3}
        />
      </mesh>
      {/* LED text via Html — no external font needed, no CDN dependency */}
      <Html position={[10, 3.2, 0.26]} center transform occlude="blending">
        <div style={{
          fontFamily: 'monospace',
          fontSize: '22px',
          fontWeight: 900,
          letterSpacing: '6px',
          color: '#00ffcc',
          textShadow: '0 0 8px #00ffcc, 0 0 16px #00ffcc, 0 0 32px #00aa88',
          userSelect: 'none',
          pointerEvents: 'none',
        }}>
          POCKETTEAM
        </div>
      </Html>
    </group>
  );
}

// ---------------------------------------------------------------------------
// Walls
// ---------------------------------------------------------------------------

function Walls(): React.ReactElement {
  const northWallColor = "#222240";
  const westWallColor = "#1a1a30";
  const windowColor = "#2a4a6c";

  const northWindows: React.ReactElement[] = [];
  for (let i = 0; i < 7; i++) {
    const wx = 1.5 + i * 3;
    northWindows.push(
      <mesh key={`nw-win-${i}`} position={[wx, 2.0, 0.08]}>
        <boxGeometry args={[1.2, 1.8, 0.02]} />
        <meshStandardMaterial
          color={windowColor}
          emissive={windowColor}
          emissiveIntensity={0.6}
          transparent
          opacity={0.85}
        />
      </mesh>
    );
  }

  const westWindows: React.ReactElement[] = [];
  for (let i = 0; i < 5; i++) {
    const wz = 1.0 + i * 3;
    westWindows.push(
      <mesh key={`ww-win-${i}`} position={[0.08, 2.0, wz]}>
        <boxGeometry args={[0.02, 1.8, 1.2]} />
        <meshStandardMaterial
          color={windowColor}
          emissive={windowColor}
          emissiveIntensity={0.6}
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

      {/* West wall: x=0, z=0..14 */}
      <mesh position={[0, 2, 7]} castShadow receiveShadow>
        <boxGeometry args={[0.4, 4, 14]} />
        <meshStandardMaterial color={westWallColor} />
      </mesh>
      {westWindows}

      {/* East and south sides remain open for isometric camera visibility */}

      {/* Door frame on east side at x=20, z=6 */}
      <mesh position={[20, 1.2, 5.4]} castShadow>
        <boxGeometry args={[0.15, 2.4, 0.15]} />
        <meshStandardMaterial color="#4a3525" />
      </mesh>
      <mesh position={[20, 1.2, 6.6]} castShadow>
        <boxGeometry args={[0.15, 2.4, 0.15]} />
        <meshStandardMaterial color="#4a3525" />
      </mesh>
      <mesh position={[20, 2.45, 6]} castShadow>
        <boxGeometry args={[0.15, 0.15, 1.35]} />
        <meshStandardMaterial color="#4a3525" />
      </mesh>
      <Html position={[20, 2.7, 6]} center>
        <div style={{
          fontFamily: 'monospace',
          fontSize: '8px',
          fontWeight: 700,
          color: '#00ffcc',
          textShadow: '0 0 6px #00ffcc',
          letterSpacing: '2px',
          userSelect: 'none',
          pointerEvents: 'none',
        }}>
          ENTRANCE
        </div>
      </Html>
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
      {/* Base frame */}
      <mesh position={[0, 0.12, 0]} castShadow receiveShadow>
        <boxGeometry args={[1.8, 0.12, 0.9]} />
        <meshStandardMaterial color="#2d1f3d" />
      </mesh>
      {/* Seat cushion left */}
      <mesh position={[-0.42, 0.28, 0.05]} castShadow>
        <boxGeometry args={[0.82, 0.14, 0.72]} />
        <meshStandardMaterial color="#4a3560" />
      </mesh>
      {/* Seat cushion right */}
      <mesh position={[0.42, 0.28, 0.05]} castShadow>
        <boxGeometry args={[0.82, 0.14, 0.72]} />
        <meshStandardMaterial color="#4a3560" />
      </mesh>
      {/* Back cushion left */}
      <mesh position={[-0.42, 0.5, -0.3]} castShadow>
        <boxGeometry args={[0.78, 0.32, 0.2]} />
        <meshStandardMaterial color="#3d2850" />
      </mesh>
      {/* Back cushion right */}
      <mesh position={[0.42, 0.5, -0.3]} castShadow>
        <boxGeometry args={[0.78, 0.32, 0.2]} />
        <meshStandardMaterial color="#3d2850" />
      </mesh>
      {/* Left arm */}
      <mesh position={[-0.85, 0.35, 0]} castShadow>
        <boxGeometry args={[0.12, 0.35, 0.85]} />
        <meshStandardMaterial color="#3d2850" />
      </mesh>
      {/* Right arm */}
      <mesh position={[0.85, 0.35, 0]} castShadow>
        <boxGeometry args={[0.12, 0.35, 0.85]} />
        <meshStandardMaterial color="#3d2850" />
      </mesh>
      {/* Throw pillow left */}
      <mesh position={[-0.6, 0.42, -0.15]} rotation={[0, 0, 0.15]} castShadow>
        <boxGeometry args={[0.22, 0.22, 0.08]} />
        <meshStandardMaterial color="#6a4f8a" />
      </mesh>
      {/* Throw pillow right */}
      <mesh position={[0.6, 0.42, -0.15]} rotation={[0, 0, -0.15]} castShadow>
        <boxGeometry args={[0.22, 0.22, 0.08]} />
        <meshStandardMaterial color="#8a6f4f" />
      </mesh>
      {/* Legs */}
      <mesh position={[-0.8, 0.03, -0.35]} castShadow>
        <boxGeometry args={[0.06, 0.06, 0.06]} />
        <meshStandardMaterial color="#1a1a2a" />
      </mesh>
      <mesh position={[0.8, 0.03, -0.35]} castShadow>
        <boxGeometry args={[0.06, 0.06, 0.06]} />
        <meshStandardMaterial color="#1a1a2a" />
      </mesh>
      <mesh position={[-0.8, 0.03, 0.35]} castShadow>
        <boxGeometry args={[0.06, 0.06, 0.06]} />
        <meshStandardMaterial color="#1a1a2a" />
      </mesh>
      <mesh position={[0.8, 0.03, 0.35]} castShadow>
        <boxGeometry args={[0.06, 0.06, 0.06]} />
        <meshStandardMaterial color="#1a1a2a" />
      </mesh>
    </group>
  );
}

// ---------------------------------------------------------------------------
// Coffee Table
// ---------------------------------------------------------------------------

function CoffeeTable({ position }: { position: [number, number, number] }): React.ReactElement {
  const [px, py, pz] = position;
  return (
    <group position={[px, py, pz]}>
      <mesh position={[0, 0.3, 0]} castShadow receiveShadow>
        <boxGeometry args={[0.8, 0.04, 0.5]} />
        <meshStandardMaterial color="#6B5535" />
      </mesh>
      {/* Legs */}
      <mesh position={[-0.35, 0.15, -0.2]} castShadow>
        <boxGeometry args={[0.04, 0.3, 0.04]} />
        <meshStandardMaterial color="#4a3a25" />
      </mesh>
      <mesh position={[0.35, 0.15, -0.2]} castShadow>
        <boxGeometry args={[0.04, 0.3, 0.04]} />
        <meshStandardMaterial color="#4a3a25" />
      </mesh>
      <mesh position={[-0.35, 0.15, 0.2]} castShadow>
        <boxGeometry args={[0.04, 0.3, 0.04]} />
        <meshStandardMaterial color="#4a3a25" />
      </mesh>
      <mesh position={[0.35, 0.15, 0.2]} castShadow>
        <boxGeometry args={[0.04, 0.3, 0.04]} />
        <meshStandardMaterial color="#4a3a25" />
      </mesh>
      {/* Coffee cups */}
      <mesh position={[-0.15, 0.34, 0]} castShadow>
        <cylinderGeometry args={[0.04, 0.03, 0.06, 8]} />
        <meshStandardMaterial color="#f5f0e8" />
      </mesh>
      <mesh position={[0.15, 0.34, 0.05]} castShadow>
        <cylinderGeometry args={[0.04, 0.03, 0.06, 8]} />
        <meshStandardMaterial color="#f5f0e8" />
      </mesh>
    </group>
  );
}

// ---------------------------------------------------------------------------
// Desk items — role-specific props on each desk surface (y ≈ 0.7 above floor)
// Groups are placed at the same world position + rotation as their desk.
// ---------------------------------------------------------------------------

function renderDeskItems(role: string): React.ReactElement | null {
  switch (role) {
    case "coo":
      return (
        <>
          {/* Gold nameplate */}
          <mesh position={[0.35, 0.72, 0.28]} castShadow>
            <boxGeometry args={[0.28, 0.07, 0.06]} />
            <meshStandardMaterial color="#c4a040" />
          </mesh>
          {/* Nameplate text stand legs */}
          <mesh position={[0.28, 0.69, 0.28]} castShadow>
            <boxGeometry args={[0.02, 0.04, 0.02]} />
            <meshStandardMaterial color="#8a7030" />
          </mesh>
          <mesh position={[0.42, 0.69, 0.28]} castShadow>
            <boxGeometry args={[0.02, 0.04, 0.02]} />
            <meshStandardMaterial color="#8a7030" />
          </mesh>
          {/* Extra wide monitor (second screen) */}
          <mesh position={[-0.3, 0.9, 0.0]} castShadow>
            <boxGeometry args={[0.5, 0.3, 0.03]} />
            <meshStandardMaterial color="#1a1a2e" />
          </mesh>
          <mesh position={[-0.3, 0.9, 0.0]}>
            <boxGeometry args={[0.44, 0.24, 0.02]} />
            <meshStandardMaterial color="#0a2040" emissive="#1a4080" emissiveIntensity={0.6} />
          </mesh>
          <mesh position={[-0.3, 0.72, 0.02]} castShadow>
            <boxGeometry args={[0.04, 0.04, 0.04]} />
            <meshStandardMaterial color="#333344" />
          </mesh>
        </>
      );

    case "planner":
      return (
        <>
          {/* Sticky note 1 — yellow */}
          <mesh position={[-0.3, 0.695, 0.1]} rotation={[-Math.PI / 2, 0, 0.15]} castShadow>
            <boxGeometry args={[0.14, 0.14, 0.008]} />
            <meshStandardMaterial color="#f5e642" />
          </mesh>
          {/* Sticky note 2 — green */}
          <mesh position={[-0.15, 0.695, 0.22]} rotation={[-Math.PI / 2, 0, -0.1]} castShadow>
            <boxGeometry args={[0.13, 0.13, 0.008]} />
            <meshStandardMaterial color="#5de86a" />
          </mesh>
          {/* Sticky note 3 — pink */}
          <mesh position={[-0.38, 0.695, 0.28]} rotation={[-Math.PI / 2, 0, 0.05]} castShadow>
            <boxGeometry args={[0.12, 0.12, 0.008]} />
            <meshStandardMaterial color="#f56fa0" />
          </mesh>
          {/* Notebook — dark cover */}
          <mesh position={[0.3, 0.695, 0.2]} rotation={[-Math.PI / 2, 0, 0.0]} castShadow>
            <boxGeometry args={[0.18, 0.24, 0.018]} />
            <meshStandardMaterial color="#2a2a4a" />
          </mesh>
          {/* Notebook pages edge */}
          <mesh position={[0.3, 0.704, 0.2]} rotation={[-Math.PI / 2, 0, 0.0]}>
            <boxGeometry args={[0.16, 0.22, 0.003]} />
            <meshStandardMaterial color="#f0f0e8" />
          </mesh>
        </>
      );

    case "engineer":
      return (
        <>
          {/* Energy drink can */}
          <mesh position={[0.38, 0.76, 0.22]} castShadow>
            <cylinderGeometry args={[0.04, 0.04, 0.12, 12]} />
            <meshStandardMaterial color="#e8e030" metalness={0.7} roughness={0.3} />
          </mesh>
          {/* Can top ring */}
          <mesh position={[0.38, 0.83, 0.22]} castShadow>
            <cylinderGeometry args={[0.035, 0.04, 0.01, 12]} />
            <meshStandardMaterial color="#c0c020" metalness={0.8} roughness={0.2} />
          </mesh>
          {/* Extra monitor — second screen */}
          <mesh position={[-0.3, 0.9, 0.0]} castShadow>
            <boxGeometry args={[0.46, 0.28, 0.03]} />
            <meshStandardMaterial color="#1a1a2e" />
          </mesh>
          <mesh position={[-0.3, 0.9, 0.0]}>
            <boxGeometry args={[0.4, 0.22, 0.02]} />
            <meshStandardMaterial color="#0a1a10" emissive="#00ff44" emissiveIntensity={0.3} />
          </mesh>
          {/* Monitor stand */}
          <mesh position={[-0.3, 0.72, 0.02]} castShadow>
            <boxGeometry args={[0.04, 0.04, 0.04]} />
            <meshStandardMaterial color="#333344" />
          </mesh>
        </>
      );

    case "qa":
      return (
        <>
          {/* Checklist block — white base */}
          <mesh position={[0.25, 0.705, 0.2]} rotation={[-Math.PI / 2, 0, 0.0]} castShadow>
            <boxGeometry args={[0.16, 0.2, 0.02]} />
            <meshStandardMaterial color="#f0f0f0" />
          </mesh>
          {/* Checklist stripes — green checked */}
          <mesh position={[0.25, 0.716, 0.14]} rotation={[-Math.PI / 2, 0, 0.0]}>
            <boxGeometry args={[0.12, 0.02, 0.002]} />
            <meshStandardMaterial color="#40c060" />
          </mesh>
          <mesh position={[0.25, 0.716, 0.2]} rotation={[-Math.PI / 2, 0, 0.0]}>
            <boxGeometry args={[0.12, 0.02, 0.002]} />
            <meshStandardMaterial color="#40c060" />
          </mesh>
          {/* Checklist stripe — red unchecked */}
          <mesh position={[0.25, 0.716, 0.26]} rotation={[-Math.PI / 2, 0, 0.0]}>
            <boxGeometry args={[0.12, 0.02, 0.002]} />
            <meshStandardMaterial color="#c04040" />
          </mesh>
          {/* Magnifying glass handle */}
          <mesh position={[-0.2, 0.74, 0.3]} rotation={[0, 0, -0.6]} castShadow>
            <cylinderGeometry args={[0.015, 0.015, 0.18, 8]} />
            <meshStandardMaterial color="#8a6030" />
          </mesh>
          {/* Magnifying glass lens ring */}
          <mesh position={[-0.28, 0.79, 0.2]} castShadow>
            <torusGeometry args={[0.055, 0.012, 6, 16]} />
            <meshStandardMaterial color="#888888" metalness={0.6} roughness={0.3} />
          </mesh>
          {/* Lens glass */}
          <mesh position={[-0.28, 0.79, 0.2]}>
            <circleGeometry args={[0.043, 12]} />
            <meshStandardMaterial color="#aaddff" transparent opacity={0.5} />
          </mesh>
        </>
      );

    case "security":
      return (
        <>
          {/* Red lock body */}
          <mesh position={[0.0, 0.76, 0.2]} castShadow>
            <boxGeometry args={[0.1, 0.09, 0.05]} />
            <meshStandardMaterial color="#c03030" />
          </mesh>
          {/* Lock shackle (U-shape approximated as two cylinders + top) */}
          <mesh position={[-0.025, 0.825, 0.2]} castShadow>
            <cylinderGeometry args={[0.012, 0.012, 0.055, 8]} />
            <meshStandardMaterial color="#888888" metalness={0.7} roughness={0.3} />
          </mesh>
          <mesh position={[0.025, 0.825, 0.2]} castShadow>
            <cylinderGeometry args={[0.012, 0.012, 0.055, 8]} />
            <meshStandardMaterial color="#888888" metalness={0.7} roughness={0.3} />
          </mesh>
          <mesh position={[0.0, 0.853, 0.2]} castShadow>
            <boxGeometry args={[0.062, 0.014, 0.024]} />
            <meshStandardMaterial color="#888888" metalness={0.7} roughness={0.3} />
          </mesh>
          {/* Shield — triangle-ish using a flat box pair */}
          <mesh position={[-0.32, 0.78, 0.18]} castShadow>
            <boxGeometry args={[0.1, 0.12, 0.03]} />
            <meshStandardMaterial color="#3050c0" />
          </mesh>
          {/* Shield top rounded cap */}
          <mesh position={[-0.32, 0.84, 0.18]} castShadow>
            <cylinderGeometry args={[0.05, 0.05, 0.03, 16, 1, false, 0, Math.PI]} />
            <meshStandardMaterial color="#3050c0" />
          </mesh>
          {/* Shield emblem */}
          <mesh position={[-0.32, 0.795, 0.2]}>
            <boxGeometry args={[0.03, 0.05, 0.005]} />
            <meshStandardMaterial color="#80aaff" emissive="#4060cc" emissiveIntensity={0.5} />
          </mesh>
        </>
      );

    case "reviewer":
      return (
        <>
          {/* Red marker/pen body */}
          <mesh position={[0.1, 0.73, 0.28]} rotation={[0, 0, Math.PI / 2]} castShadow>
            <cylinderGeometry args={[0.018, 0.015, 0.22, 8]} />
            <meshStandardMaterial color="#dd2020" />
          </mesh>
          {/* Pen cap */}
          <mesh position={[0.22, 0.73, 0.28]} rotation={[0, 0, Math.PI / 2]} castShadow>
            <cylinderGeometry args={[0.019, 0.019, 0.04, 8]} />
            <meshStandardMaterial color="#aa1010" />
          </mesh>
          {/* Glasses — left lens ring */}
          <mesh position={[-0.2, 0.73, 0.2]} castShadow>
            <torusGeometry args={[0.055, 0.012, 6, 16]} />
            <meshStandardMaterial color="#2a2a3a" />
          </mesh>
          {/* Glasses — right lens ring */}
          <mesh position={[-0.32, 0.73, 0.2]} castShadow>
            <torusGeometry args={[0.055, 0.012, 6, 16]} />
            <meshStandardMaterial color="#2a2a3a" />
          </mesh>
          {/* Glasses bridge */}
          <mesh position={[-0.26, 0.73, 0.2]} castShadow>
            <boxGeometry args={[0.016, 0.008, 0.01]} />
            <meshStandardMaterial color="#2a2a3a" />
          </mesh>
          {/* Glasses — left temple */}
          <mesh position={[-0.145, 0.73, 0.2]} rotation={[0, 0.3, 0]} castShadow>
            <boxGeometry args={[0.07, 0.006, 0.006]} />
            <meshStandardMaterial color="#2a2a3a" />
          </mesh>
          {/* Glasses — right temple */}
          <mesh position={[-0.375, 0.73, 0.2]} rotation={[0, -0.3, 0]} castShadow>
            <boxGeometry args={[0.07, 0.006, 0.006]} />
            <meshStandardMaterial color="#2a2a3a" />
          </mesh>
        </>
      );

    case "product":
      return (
        <>
          {/* Phone — dark block */}
          <mesh position={[0.32, 0.71, 0.22]} rotation={[-Math.PI / 2, 0, 0.15]} castShadow>
            <boxGeometry args={[0.07, 0.13, 0.015]} />
            <meshStandardMaterial color="#1a1a2a" />
          </mesh>
          {/* Phone screen glow */}
          <mesh position={[0.32, 0.712, 0.22]} rotation={[-Math.PI / 2, 0, 0.15]}>
            <boxGeometry args={[0.056, 0.11, 0.003]} />
            <meshStandardMaterial color="#2040a0" emissive="#3060ff" emissiveIntensity={0.7} />
          </mesh>
          {/* Bar chart — 3 bars of different heights */}
          <mesh position={[-0.35, 0.73, 0.15]} castShadow>
            <boxGeometry args={[0.04, 0.04, 0.04]} />
            <meshStandardMaterial color="#4080ff" />
          </mesh>
          <mesh position={[-0.29, 0.74, 0.15]} castShadow>
            <boxGeometry args={[0.04, 0.06, 0.04]} />
            <meshStandardMaterial color="#40c080" />
          </mesh>
          <mesh position={[-0.23, 0.755, 0.15]} castShadow>
            <boxGeometry args={[0.04, 0.09, 0.04]} />
            <meshStandardMaterial color="#ff8040" />
          </mesh>
          {/* Chart base line */}
          <mesh position={[-0.29, 0.702, 0.15]}>
            <boxGeometry args={[0.18, 0.006, 0.04]} />
            <meshStandardMaterial color="#555566" />
          </mesh>
        </>
      );

    case "investigator":
      return (
        <>
          {/* File stack — 3 layered blocks */}
          <mesh position={[0.25, 0.698, 0.2]} rotation={[-Math.PI / 2, 0, 0.0]} castShadow>
            <boxGeometry args={[0.18, 0.22, 0.016]} />
            <meshStandardMaterial color="#e8e0d0" />
          </mesh>
          <mesh position={[0.245, 0.714, 0.195]} rotation={[-Math.PI / 2, 0, 0.05]} castShadow>
            <boxGeometry args={[0.18, 0.22, 0.016]} />
            <meshStandardMaterial color="#f0e8d8" />
          </mesh>
          <mesh position={[0.24, 0.73, 0.205]} rotation={[-Math.PI / 2, 0, -0.04]} castShadow>
            <boxGeometry args={[0.18, 0.22, 0.016]} />
            <meshStandardMaterial color="#e8dcc8" />
          </mesh>
          {/* Magnifying glass handle */}
          <mesh position={[-0.2, 0.74, 0.3]} rotation={[0, 0, -0.6]} castShadow>
            <cylinderGeometry args={[0.015, 0.015, 0.18, 8]} />
            <meshStandardMaterial color="#8a6030" />
          </mesh>
          {/* Magnifying glass lens ring */}
          <mesh position={[-0.28, 0.79, 0.2]} castShadow>
            <torusGeometry args={[0.055, 0.012, 6, 16]} />
            <meshStandardMaterial color="#888888" metalness={0.6} roughness={0.3} />
          </mesh>
          {/* Lens glass */}
          <mesh position={[-0.28, 0.79, 0.2]}>
            <circleGeometry args={[0.043, 12]} />
            <meshStandardMaterial color="#aaddff" transparent opacity={0.5} />
          </mesh>
        </>
      );

    case "documentation":
      return (
        <>
          {/* Book stack — 3 books in different colors */}
          <mesh position={[0.0, 0.698, 0.2]} rotation={[-Math.PI / 2, 0, 0.0]} castShadow>
            <boxGeometry args={[0.2, 0.14, 0.022]} />
            <meshStandardMaterial color="#c04040" />
          </mesh>
          <mesh position={[0.0, 0.72, 0.2]} rotation={[-Math.PI / 2, 0, 0.03]} castShadow>
            <boxGeometry args={[0.18, 0.13, 0.022]} />
            <meshStandardMaterial color="#4040c0" />
          </mesh>
          <mesh position={[0.0, 0.742, 0.2]} rotation={[-Math.PI / 2, 0, -0.02]} castShadow>
            <boxGeometry args={[0.17, 0.12, 0.02]} />
            <meshStandardMaterial color="#40a040" />
          </mesh>
          {/* Pen resting on top */}
          <mesh position={[0.0, 0.754, 0.28]} rotation={[0, 0, Math.PI / 2]} castShadow>
            <cylinderGeometry args={[0.01, 0.008, 0.2, 8]} />
            <meshStandardMaterial color="#e8e0a0" />
          </mesh>
        </>
      );

    case "devops":
      return (
        <>
          {/* Server rack front panel */}
          <mesh position={[0.0, 0.82, 0.15]} castShadow>
            <boxGeometry args={[0.24, 0.22, 0.14]} />
            <meshStandardMaterial color="#1a1a2a" />
          </mesh>
          {/* Server unit 1 */}
          <mesh position={[0.0, 0.86, 0.09]}>
            <boxGeometry args={[0.2, 0.04, 0.01]} />
            <meshStandardMaterial color="#2a2a3a" />
          </mesh>
          {/* Server unit 2 */}
          <mesh position={[0.0, 0.82, 0.09]}>
            <boxGeometry args={[0.2, 0.04, 0.01]} />
            <meshStandardMaterial color="#2a2a3a" />
          </mesh>
          {/* Server unit 3 */}
          <mesh position={[0.0, 0.78, 0.09]}>
            <boxGeometry args={[0.2, 0.04, 0.01]} />
            <meshStandardMaterial color="#2a2a3a" />
          </mesh>
          {/* LED indicators — green */}
          <mesh position={[-0.08, 0.862, 0.088]}>
            <boxGeometry args={[0.012, 0.012, 0.002]} />
            <meshStandardMaterial color="#00ff44" emissive="#00ff44" emissiveIntensity={1.5} />
          </mesh>
          <mesh position={[-0.04, 0.862, 0.088]}>
            <boxGeometry args={[0.012, 0.012, 0.002]} />
            <meshStandardMaterial color="#00ff44" emissive="#00ff44" emissiveIntensity={1.5} />
          </mesh>
          {/* LED indicator — orange (busy) */}
          <mesh position={[-0.08, 0.822, 0.088]}>
            <boxGeometry args={[0.012, 0.012, 0.002]} />
            <meshStandardMaterial color="#ff8800" emissive="#ff8800" emissiveIntensity={1.5} />
          </mesh>
          <mesh position={[-0.04, 0.822, 0.088]}>
            <boxGeometry args={[0.012, 0.012, 0.002]} />
            <meshStandardMaterial color="#00ff44" emissive="#00ff44" emissiveIntensity={1.5} />
          </mesh>
          <mesh position={[-0.08, 0.782, 0.088]}>
            <boxGeometry args={[0.012, 0.012, 0.002]} />
            <meshStandardMaterial color="#00ff44" emissive="#00ff44" emissiveIntensity={1.5} />
          </mesh>
        </>
      );

    case "monitor":
      return (
        <>
          {/* Extra small dashboard monitor */}
          <mesh position={[-0.32, 0.85, 0.04]} castShadow>
            <boxGeometry args={[0.3, 0.18, 0.025]} />
            <meshStandardMaterial color="#1a1a2e" />
          </mesh>
          {/* Dashboard screen with graphs */}
          <mesh position={[-0.32, 0.85, 0.03]}>
            <boxGeometry args={[0.26, 0.14, 0.005]} />
            <meshStandardMaterial color="#002218" emissive="#004432" emissiveIntensity={0.8} />
          </mesh>
          {/* Graph line accent */}
          <mesh position={[-0.38, 0.855, 0.026]}>
            <boxGeometry args={[0.1, 0.005, 0.002]} />
            <meshStandardMaterial color="#00ff99" emissive="#00ff99" emissiveIntensity={1.0} />
          </mesh>
          <mesh position={[-0.32, 0.845, 0.026]}>
            <boxGeometry args={[0.1, 0.005, 0.002]} />
            <meshStandardMaterial color="#ffaa00" emissive="#ffaa00" emissiveIntensity={1.0} />
          </mesh>
          {/* Monitor stand */}
          <mesh position={[-0.32, 0.72, 0.04]} castShadow>
            <boxGeometry args={[0.03, 0.03, 0.03]} />
            <meshStandardMaterial color="#333344" />
          </mesh>
        </>
      );

    case "observer":
      return (
        <>
          {/* Binoculars — left barrel */}
          <mesh position={[-0.06, 0.75, 0.2]} rotation={[Math.PI / 2, 0, 0]} castShadow>
            <cylinderGeometry args={[0.04, 0.04, 0.14, 12]} />
            <meshStandardMaterial color="#2a2a3a" />
          </mesh>
          {/* Binoculars — right barrel */}
          <mesh position={[0.06, 0.75, 0.2]} rotation={[Math.PI / 2, 0, 0]} castShadow>
            <cylinderGeometry args={[0.04, 0.04, 0.14, 12]} />
            <meshStandardMaterial color="#2a2a3a" />
          </mesh>
          {/* Binoculars bridge */}
          <mesh position={[0.0, 0.75, 0.2]} castShadow>
            <boxGeometry args={[0.05, 0.03, 0.07]} />
            <meshStandardMaterial color="#3a3a4a" />
          </mesh>
          {/* Lens gleam — left */}
          <mesh position={[-0.06, 0.75, 0.14]}>
            <circleGeometry args={[0.032, 12]} />
            <meshStandardMaterial color="#5599ff" transparent opacity={0.7} />
          </mesh>
          {/* Lens gleam — right */}
          <mesh position={[0.06, 0.75, 0.14]}>
            <circleGeometry args={[0.032, 12]} />
            <meshStandardMaterial color="#5599ff" transparent opacity={0.7} />
          </mesh>
        </>
      );

    case "researcher":
      return (
        <>
          {/* Book stack — 2 books */}
          <mesh position={[0.28, 0.698, 0.18]} rotation={[-Math.PI / 2, 0, 0.0]} castShadow>
            <boxGeometry args={[0.18, 0.14, 0.022]} />
            <meshStandardMaterial color="#8040c0" />
          </mesh>
          <mesh position={[0.28, 0.72, 0.18]} rotation={[-Math.PI / 2, 0, 0.04]} castShadow>
            <boxGeometry args={[0.16, 0.13, 0.02]} />
            <meshStandardMaterial color="#c08040" />
          </mesh>
          {/* Globe — sphere on a small stand */}
          <mesh position={[-0.22, 0.75, 0.2]} castShadow>
            <sphereGeometry args={[0.065, 12, 12]} />
            <meshStandardMaterial color="#2060c0" />
          </mesh>
          {/* Globe land masses (lighter color band) */}
          <mesh position={[-0.22, 0.75, 0.2]}>
            <sphereGeometry args={[0.067, 8, 4]} />
            <meshStandardMaterial color="#40a040" transparent opacity={0.35} wireframe />
          </mesh>
          {/* Globe stand */}
          <mesh position={[-0.22, 0.695, 0.2]} castShadow>
            <cylinderGeometry args={[0.012, 0.02, 0.025, 8]} />
            <meshStandardMaterial color="#8a7040" />
          </mesh>
        </>
      );

    default:
      return null;
  }
}

function DeskItems(): React.ReactElement {
  return (
    <group>
      {Object.entries(AGENT_DESKS).map(([role, [x, z]]) => (
        <group key={`items-${role}`} position={[x, 0, z]} rotation={[0, Math.PI, 0]}>
          {renderDeskItems(role)}
        </group>
      ))}
      {/* COO desk items — no rotation, matching desk orientation */}
      <group position={[COO_DESK[0], 0, COO_DESK[1]]} rotation={[0, 0, 0]}>
        {renderDeskItems("coo")}
      </group>
    </group>
  );
}

// ---------------------------------------------------------------------------
// Scene furniture layer
// ---------------------------------------------------------------------------

function FurnitureLayer(): React.ReactElement {
  return (
    <group>
      {/* Permanent desks for all agent roles */}
      {Object.entries(AGENT_DESKS).map(([role, [x, z]]) => (
        <group key={`desk-${role}`}>
          <group position={[x, 0, z]} rotation={[0, Math.PI, 0]}>
            <Desk3D position={[0, 0, 0]} />
          </group>
          <Chair3D position={[x, 0, z - 0.9]} rotation={0} />
        </group>
      ))}

      {/* COO desk — always visible, rotated 180° so COO faces team (-z) */}
      <group>
        <group position={[COO_DESK[0], 0, COO_DESK[1]]} rotation={[0, 0, 0]}>
          <Desk3D position={[0, 0, 0]} />
        </group>
        <Chair3D position={[COO_DESK[0], 0, COO_DESK[1] + 0.9]} rotation={Math.PI} />
      </group>

      {/* Role-specific desk items */}
      <DeskItems />

      {/* Couches — Row 1 at z=1.5 */}
      <Couch position={[3, 0, 1.5]} />
      <Couch position={[8, 0, 1.5]} />
      <Couch position={[14, 0, 1.5]} />
      {/* Couches — Row 2 at z=3.0 */}
      <Couch position={[3, 0, 3.0]} />
      <Couch position={[8, 0, 3.0]} />
      <Couch position={[14, 0, 3.0]} />

      {/* Coffee tables */}
      <CoffeeTable position={[5.5, 0, 1.5]} />
      <CoffeeTable position={[11, 0, 1.5]} />
      <CoffeeTable position={[5.5, 0, 3.0]} />
      <CoffeeTable position={[11, 0, 3.0]} />

      {/* Plants */}
      {PLANT_POSITIONS.map(([x, z], i) => (
        <Plant3D key={`plant-${i}`} position={[x, 0, z]} />
      ))}

      {/* Welcome mat at entrance */}
      <mesh position={[19.5, 0.005, 6]} rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
        <planeGeometry args={[1.0, 1.2]} />
        <meshStandardMaterial color="#3a5540" />
      </mesh>

      {/* Coffee machines */}
      <CoffeeMachine3D position={[1.5, 0, 2]} />

      {/* Whiteboard on west wall */}
      <mesh position={[0.25, 2.2, 4]} castShadow>
        <boxGeometry args={[0.05, 1.2, 1.8]} />
        <meshStandardMaterial color="#e8e8e0" />
      </mesh>
      {/* Whiteboard frame */}
      <mesh position={[0.26, 2.2, 4]}>
        <boxGeometry args={[0.02, 1.3, 1.9]} />
        <meshStandardMaterial color="#666666" />
      </mesh>

      {/* Bookshelf on west wall */}
      <group position={[0.3, 0, 8]}>
        {/* Shelf body */}
        <mesh position={[0, 1.0, 0]} castShadow>
          <boxGeometry args={[0.4, 2.0, 1.2]} />
          <meshStandardMaterial color="#5a4530" />
        </mesh>
        {/* Books */}
        <mesh position={[0.05, 1.6, -0.3]} castShadow>
          <boxGeometry args={[0.15, 0.25, 0.12]} />
          <meshStandardMaterial color="#c44040" />
        </mesh>
        <mesh position={[0.05, 1.6, -0.1]} castShadow>
          <boxGeometry args={[0.15, 0.22, 0.1]} />
          <meshStandardMaterial color="#4060c4" />
        </mesh>
        <mesh position={[0.05, 1.6, 0.1]} castShadow>
          <boxGeometry args={[0.15, 0.28, 0.11]} />
          <meshStandardMaterial color="#40c460" />
        </mesh>
        <mesh position={[0.05, 1.6, 0.3]} castShadow>
          <boxGeometry args={[0.15, 0.2, 0.13]} />
          <meshStandardMaterial color="#c4a040" />
        </mesh>
        <mesh position={[0.05, 1.1, -0.2]} castShadow>
          <boxGeometry args={[0.15, 0.24, 0.14]} />
          <meshStandardMaterial color="#8040c4" />
        </mesh>
        <mesh position={[0.05, 1.1, 0.1]} castShadow>
          <boxGeometry args={[0.15, 0.26, 0.12]} />
          <meshStandardMaterial color="#c47040" />
        </mesh>
      </group>
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
  facingMonitor: boolean;
  faceRotation: number;
}

// Track last known positions per agent role to enable walking animation
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

  const newLastKnown = new Map<string, [number, number, number]>();
  const newLastStatuses = new Map<string, string>();

  // Working agents go to their assigned desk
  for (const [role, agent] of working) {
    const deskPos = AGENT_DESKS[role];
    const avatar = generateAvatar(role);

    let target: [number, number, number];
    let facingMonitor = false;

    if (deskPos) {
      const [dx, dz] = deskPos;
      // Agent sits at chair position (-z from desk, facing toward monitor)
      target = charWorld(dx, dz - 0.9);
      facingMonitor = true;
    } else {
      // Fallback: first available lounge spot
      target = charWorld(LOUNGE_SPOTS[0][0], LOUNGE_SPOTS[0][1]);
    }

    const prevPos = lastKnownPositions.get(role);
    const prevStatus = lastKnownStatuses.get(role);

    let startPos: [number, number, number];
    if (!prevPos) {
      startPos = ENTRANCE_POS;
    } else if (prevStatus !== agent.status) {
      startPos = prevPos;
    } else {
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
      facingMonitor,
      faceRotation: 0,
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
      startPos = ENTRANCE_POS;
    } else if (prevStatus !== agent.status) {
      startPos = prevPos;
    } else {
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
      facingMonitor: false,
      faceRotation: 0,
    });
  }

  // COO
  const cooAgent = byRole.get("coo");
  if (cooAgent) {
    const [cx, cz] = COO_DESK;
    const avatar = generateAvatar("coo");
    const target = charWorld(cx, cz + 0.9);

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
      facingMonitor: true,
      faceRotation: Math.PI,
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
          facingMonitor={p.facingMonitor}
          faceRotation={p.faceRotation}
        />
      ))}
    </group>
  );
}

// ---------------------------------------------------------------------------
// Lights
// ---------------------------------------------------------------------------

function Lighting(): React.ReactElement {
  return (
    <>
      <ambientLight intensity={1.5} />
      <hemisphereLight args={["#e0ecff", "#2a2a40", 0.8]} />
      <directionalLight
        position={[12, 18, 8]}
        intensity={1.6}
        castShadow
        shadow-mapSize-width={2048}
        shadow-mapSize-height={2048}
        shadow-camera-far={50}
        shadow-camera-left={-15}
        shadow-camera-right={25}
        shadow-camera-top={18}
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
  return (
    <Canvas
      shadows
      style={{ width: "100%", height: "100%", background: "#1a1a2e" }}
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
        target={[10, 0, 7]}
      />

      <Lighting />

      <FloorZones />
      <Walls />
      <LEDSign />

      {/* Grid helper */}
      <Grid
        position={[10, 0, 7]}
        args={[20, 14]}
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

      <FurnitureLayer />
      <AgentLayer agents={agents} />

      {/* Zone labels */}
      <ZoneLabel position={[10, 0.01, 2]} text="LOUNGE" />
      <ZoneLabel position={[10, 0.01, 5]} text="CORRIDOR" />
      <ZoneLabel position={[10, 0.01, 10]} text="WORKSPACE" />
    </Canvas>
  );
}
