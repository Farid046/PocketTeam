import React, { useRef } from "react";
import type * as THREE from "three";

interface Props {
  position: [number, number, number];
}

export function Desk3D({ position }: Props): React.ReactElement {
  const [px, py, pz] = position;

  return (
    <group position={[px, py, pz]}>
      {/* Table top */}
      <mesh position={[0, 0.64, 0]} castShadow receiveShadow>
        <boxGeometry args={[2, 0.08, 1]} />
        <meshStandardMaterial color="#8B7355" />
      </mesh>

      {/* Table legs */}
      <mesh position={[-0.9, 0.32, -0.4]} castShadow>
        <boxGeometry args={[0.06, 0.64, 0.06]} />
        <meshStandardMaterial color="#6B5535" />
      </mesh>
      <mesh position={[0.9, 0.32, -0.4]} castShadow>
        <boxGeometry args={[0.06, 0.64, 0.06]} />
        <meshStandardMaterial color="#6B5535" />
      </mesh>
      <mesh position={[-0.9, 0.32, 0.4]} castShadow>
        <boxGeometry args={[0.06, 0.64, 0.06]} />
        <meshStandardMaterial color="#6B5535" />
      </mesh>
      <mesh position={[0.9, 0.32, 0.4]} castShadow>
        <boxGeometry args={[0.06, 0.64, 0.06]} />
        <meshStandardMaterial color="#6B5535" />
      </mesh>

      {/* Monitor 1 - main */}
      {/* Stand */}
      <mesh position={[-0.2, 0.8, -0.3]} castShadow>
        <boxGeometry args={[0.04, 0.12, 0.04]} />
        <meshStandardMaterial color="#222222" />
      </mesh>
      {/* Screen frame */}
      <mesh position={[-0.2, 0.985, -0.32]} castShadow>
        <boxGeometry args={[0.5, 0.35, 0.04]} />
        <meshStandardMaterial color="#1a1a1a" />
      </mesh>
      {/* Screen face - emissive blue */}
      <mesh position={[-0.2, 0.985, -0.30]}>
        <boxGeometry args={[0.44, 0.29, 0.01]} />
        <meshStandardMaterial color="#0a1628" emissive="#1a3a5c" emissiveIntensity={0.8} />
      </mesh>

      {/* Monitor 2 - smaller, offset */}
      <mesh position={[0.45, 0.84, -0.32]} castShadow>
        <boxGeometry args={[0.04, 0.08, 0.04]} />
        <meshStandardMaterial color="#222222" />
      </mesh>
      <mesh position={[0.45, 0.97, -0.34]} castShadow>
        <boxGeometry args={[0.35, 0.26, 0.04]} />
        <meshStandardMaterial color="#1a1a1a" />
      </mesh>
      <mesh position={[0.45, 0.97, -0.32]}>
        <boxGeometry args={[0.3, 0.21, 0.01]} />
        <meshStandardMaterial color="#0a1628" emissive="#1a3a5c" emissiveIntensity={0.6} />
      </mesh>

      {/* Keyboard */}
      <mesh position={[0, 0.69, 0.15]} castShadow>
        <boxGeometry args={[0.35, 0.02, 0.12]} />
        <meshStandardMaterial color="#2a2a2a" />
      </mesh>
    </group>
  );
}
