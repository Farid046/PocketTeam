import React from "react";

interface Props {
  position: [number, number, number];
  rotation?: number;
}

export function Chair3D({ position, rotation = 0 }: Props): React.ReactElement {
  const [px, py, pz] = position;

  return (
    <group position={[px, py, pz]} rotation={[0, rotation, 0]}>
      {/* Seat */}
      <mesh position={[0, 0.5, 0]} castShadow receiveShadow>
        <boxGeometry args={[0.45, 0.04, 0.45]} />
        <meshStandardMaterial color="#1a2a4a" />
      </mesh>

      {/* Seat cushion */}
      <mesh position={[0, 0.53, 0]} castShadow>
        <boxGeometry args={[0.4, 0.04, 0.4]} />
        <meshStandardMaterial color="#243560" />
      </mesh>

      {/* Back rest */}
      <mesh position={[0, 0.8, -0.21]} castShadow>
        <boxGeometry args={[0.45, 0.35, 0.04]} />
        <meshStandardMaterial color="#1a2a4a" />
      </mesh>

      {/* Pedestal */}
      <mesh position={[0, 0.25, 0]} castShadow>
        <cylinderGeometry args={[0.04, 0.06, 0.5, 8]} />
        <meshStandardMaterial color="#333333" />
      </mesh>

      {/* Base star */}
      <mesh position={[0, 0.02, 0]} castShadow>
        <cylinderGeometry args={[0.22, 0.22, 0.03, 5]} />
        <meshStandardMaterial color="#282828" />
      </mesh>
    </group>
  );
}
