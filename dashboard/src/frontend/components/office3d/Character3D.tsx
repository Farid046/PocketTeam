import React, { useRef, useState, useEffect } from "react";
import { useFrame } from "@react-three/fiber";
import { Html } from "@react-three/drei";
import type * as THREE from "three";

interface Props {
  position: [number, number, number];
  targetPosition: [number, number, number];
  role: string;
  status: string;
  description: string;
  shirtColor: string;
  skinColor: string;
  hairColor: string;
  facingMonitor?: boolean;
  faceRotation?: number;
}

// Desaturate a hex color by multiplying all channels by a factor (0-1)
function desaturateColor(hex: string | undefined, factor: number): string {
  if (!hex) return "#888888";
  const c = parseInt(hex.replace("#", ""), 16);
  const r = Math.floor(((c >> 16) & 0xff) * factor);
  const g = Math.floor(((c >> 8) & 0xff) * factor);
  const b = Math.floor((c & 0xff) * factor);
  return `#${r.toString(16).padStart(2, "0")}${g.toString(16).padStart(2, "0")}${b.toString(16).padStart(2, "0")}`;
}

export function Character3D({
  position,
  targetPosition,
  role,
  status,
  description,
  shirtColor,
  skinColor,
  hairColor,
  facingMonitor = false,
  faceRotation = 0,
}: Props): React.ReactElement {
  const groupRef = useRef<THREE.Group>(null!);
  const upperBodyRef = useRef<THREE.Group>(null!);
  const bodyRef = useRef<THREE.Mesh>(null!);
  const leftArmRef = useRef<THREE.Mesh>(null!);
  const rightArmRef = useRef<THREE.Mesh>(null!);
  const leftLegRef = useRef<THREE.Mesh>(null!);
  const rightLegRef = useRef<THREE.Mesh>(null!);

  // FIX 1: Tooltip with 150ms delay to prevent rapid toggling / flicker
  const [hovered, setHovered] = useState(false);
  const [showTooltip, setShowTooltip] = useState(false);
  const [pinned, setPinned] = useState(false);
  const hoverTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (hovered) {
      hoverTimerRef.current = setTimeout(() => setShowTooltip(true), 150);
    } else {
      if (hoverTimerRef.current) {
        clearTimeout(hoverTimerRef.current);
        hoverTimerRef.current = null;
      }
      setShowTooltip(false);
    }
    return () => {
      if (hoverTimerRef.current) clearTimeout(hoverTimerRef.current);
    };
  }, [hovered]);

  const showBubble = showTooltip || pinned;

  const currentPos = useRef<[number, number, number]>([...position]);
  const isWalking = useRef(false);
  const walkPhase = useRef(0);

  const isWorking = status === "working";
  const isIdle = status === "idle" || status === "done";

  // FIX 3: Desaturated colors for idle agents
  const effectiveShirtColor = isIdle ? desaturateColor(shirtColor, 0.5) : shirtColor;
  const effectiveSkinColor = isIdle ? desaturateColor(skinColor, 0.5) : skinColor;
  const effectiveHairColor = isIdle ? desaturateColor(hairColor, 0.5) : hairColor;

  useFrame((_state, delta) => {
    if (!groupRef.current) return;

    const [cx, cy, cz] = currentPos.current;
    const [tx, ty, tz] = targetPosition;

    const dx = tx - cx;
    const dy = ty - cy;
    const dz = tz - cz;
    const dist = Math.sqrt(dx * dx + dy * dy + dz * dz);

    if (dist > 0.05) {
      isWalking.current = true;
      // Time-based walking speed (not frame-rate dependent)
      const speed = Math.min(delta * 2.0, dist);
      currentPos.current = [
        cx + (dx / dist) * speed,
        cy + (dy / dist) * speed,
        cz + (dz / dist) * speed,
      ];
      groupRef.current.position.set(...currentPos.current);

      // Face direction of travel
      if (Math.abs(dx) > 0.01 || Math.abs(dz) > 0.01) {
        groupRef.current.rotation.y = Math.atan2(dx, dz);
      }
    } else {
      isWalking.current = false;
      currentPos.current = [tx, ty, tz];
      groupRef.current.position.set(tx, ty, tz);

      // When at rest, face the monitor direction if at a desk
      if (facingMonitor) {
        groupRef.current.rotation.y = faceRotation;
      } else if (isIdle) {
        groupRef.current.rotation.y = 0;
      }
    }

    walkPhase.current += delta * (isWalking.current ? 8 : 5);
    const phase = walkPhase.current;

    // Detect sitting: on couch OR at desk (facingMonitor and at rest)
    const currentCz = currentPos.current[2];
    const onCouch = isIdle && (Math.abs(currentCz - 1.5) < 0.3 || Math.abs(currentCz - 3.0) < 0.3);
    const atDesk = facingMonitor && !isWalking.current;
    const isSitting = onCouch || atDesk;

    if (isSitting) {
      // Lower the upper body group for sitting pose
      if (upperBodyRef.current) upperBodyRef.current.position.y = -0.25;
      // Legs stretched forward
      if (leftLegRef.current) {
        leftLegRef.current.rotation.x = -1.2;
        leftLegRef.current.position.y = 0.55;
      }
      if (rightLegRef.current) {
        rightLegRef.current.rotation.x = -1.2;
        rightLegRef.current.position.y = 0.55;
      }
      // Reset body lean
      if (bodyRef.current) bodyRef.current.rotation.x = 0;
      // Arms: typing if working, relaxed if idle
      if (isWorking) {
        const leftType = Math.sin(phase * 3) * 0.12;
        const rightType = Math.sin(phase * 3 + 1.5) * 0.12;
        if (leftArmRef.current) leftArmRef.current.rotation.x = -0.5 + leftType;
        if (rightArmRef.current) rightArmRef.current.rotation.x = -0.5 + rightType;
      } else {
        if (leftArmRef.current) leftArmRef.current.rotation.x = -0.3;
        if (rightArmRef.current) rightArmRef.current.rotation.x = -0.3;
      }
    } else if (isWalking.current) {
      // Reset upper body position when walking
      if (upperBodyRef.current) upperBodyRef.current.position.y = 0;
      // Reset leg positions
      if (leftLegRef.current) leftLegRef.current.position.y = 0.4;
      if (rightLegRef.current) rightLegRef.current.position.y = 0.4;
      // More pronounced walking arm swing (0.9) and leg swing (0.6)
      const swing = Math.sin(phase) * 0.9;
      if (leftArmRef.current) leftArmRef.current.rotation.x = swing;
      if (rightArmRef.current) rightArmRef.current.rotation.x = -swing;
      if (leftLegRef.current) leftLegRef.current.rotation.x = -Math.sin(phase) * 0.6;
      if (rightLegRef.current) rightLegRef.current.rotation.x = Math.sin(phase) * 0.6;
      // Reset body lean when walking
      if (bodyRef.current) bodyRef.current.rotation.x = 0;
    } else {
      // Standing idle (not on couch, not at desk)
      if (upperBodyRef.current) upperBodyRef.current.position.y = 0;
      // Reset leg positions
      if (leftLegRef.current) leftLegRef.current.position.y = 0.4;
      if (rightLegRef.current) rightLegRef.current.position.y = 0.4;
      // Breathing animation for standing idle agents
      if (isIdle && bodyRef.current) {
        bodyRef.current.position.y = 1.1 + Math.sin(phase * 0.3) * 0.02;
      }
      if (leftArmRef.current) leftArmRef.current.rotation.x = 0;
      if (rightArmRef.current) rightArmRef.current.rotation.x = 0;
      if (leftLegRef.current) leftLegRef.current.rotation.x = 0;
      if (rightLegRef.current) rightLegRef.current.rotation.x = 0;
      if (bodyRef.current) bodyRef.current.rotation.x = 0;
    }
  });

  const roleLabel = role.toUpperCase();

  return (
    <group ref={groupRef} position={position}>
      {/* Working status light */}
      {isWorking && (
        <pointLight
          color="#FFD700"
          intensity={0.5}
          distance={3}
          position={[0, 2.5, 0]}
        />
      )}

      {/* Tighter hit-box for hover */}
      <mesh
        position={[0, 1.0, 0]}
        onPointerEnter={() => setHovered(true)}
        onPointerLeave={() => setHovered(false)}
        onClick={() => setPinned((p) => !p)}
      >
        <boxGeometry args={[0.5, 1.8, 0.4]} />
        <meshStandardMaterial transparent opacity={0} />
      </mesh>

      {/* Upper body group — lowered when sitting */}
      <group ref={upperBodyRef}>
        {/* Hair */}
        <mesh position={[0, 1.82, 0]} castShadow>
          <boxGeometry args={[0.34, 0.1, 0.34]} />
          <meshStandardMaterial color={effectiveHairColor} />
        </mesh>

        {/* Head */}
        <mesh position={[0, 1.6, 0]} castShadow>
          <boxGeometry args={[0.32, 0.32, 0.32]} />
          <meshStandardMaterial color={effectiveSkinColor} />
        </mesh>

        {/* Eyes */}
        <mesh position={[-0.08, 1.64, 0.161]}>
          <boxGeometry args={[0.05, 0.04, 0.01]} />
          <meshStandardMaterial color="#1a1a1a" />
        </mesh>
        <mesh position={[0.08, 1.64, 0.161]}>
          <boxGeometry args={[0.05, 0.04, 0.01]} />
          <meshStandardMaterial color="#1a1a1a" />
        </mesh>

        {/* Body */}
        <mesh ref={bodyRef} position={[0, 1.1, 0]} castShadow>
          <boxGeometry args={[0.35, 0.6, 0.22]} />
          <meshStandardMaterial color={effectiveShirtColor} />
        </mesh>

        {/* Left arm */}
        <mesh
          ref={leftArmRef}
          position={[-0.28, 1.1, 0]}
          castShadow
        >
          <boxGeometry args={[0.12, 0.5, 0.12]} />
          <meshStandardMaterial color={effectiveShirtColor} />
        </mesh>

        {/* Right arm */}
        <mesh
          ref={rightArmRef}
          position={[0.28, 1.1, 0]}
          castShadow
        >
          <boxGeometry args={[0.12, 0.5, 0.12]} />
          <meshStandardMaterial color={effectiveShirtColor} />
        </mesh>
      </group>

      {/* Left leg */}
      <mesh
        ref={leftLegRef}
        position={[-0.1, 0.4, 0]}
        castShadow
      >
        <boxGeometry args={[0.16, 0.5, 0.16]} />
        <meshStandardMaterial color="#2a2a3a" />
      </mesh>

      {/* Right leg */}
      <mesh
        ref={rightLegRef}
        position={[0.1, 0.4, 0]}
        castShadow
      >
        <boxGeometry args={[0.16, 0.5, 0.16]} />
        <meshStandardMaterial color="#2a2a3a" />
      </mesh>

      {/* FIX 6: Permanent role label above agent — fixed pixel size */}
      <Html position={[0, 2.4, 0]} center sprite zIndexRange={[0, 0]}>
        <div
          style={{
            background: "rgba(10,10,20,0.75)",
            color: "#c0c0e0",
            fontSize: "8px",
            fontFamily: "monospace",
            fontWeight: 700,
            padding: "1px 4px",
            borderRadius: "2px",
            whiteSpace: "nowrap",
            pointerEvents: "none",
            userSelect: "none",
            letterSpacing: "0.5px",
          }}
        >
          {roleLabel}
        </div>
      </Html>

      {/* FIX 1: Tooltip — pointer-events-none, shown with delay */}
      {showBubble && (
        <Html position={[0, 2.2, 0]} center distanceFactor={10}>
          <div
            className="bg-gray-900 border border-gray-700 rounded px-3 py-2 text-xs text-gray-200 max-w-[200px] whitespace-pre-wrap pointer-events-none"
            style={{ minWidth: "80px" }}
          >
            <div className="font-bold text-yellow-400 mb-1">{roleLabel}</div>
            <div>{description || "Idle"}</div>
            {pinned && (
              <div className="mt-1 text-gray-500 text-[10px]">click to unpin</div>
            )}
          </div>
        </Html>
      )}
    </group>
  );
}
