import React from "react";

interface Props {
  position: [number, number, number];
}

export function Plant3D({ position }: Props): React.ReactElement {
  const [px, py, pz] = position;

  return (
    <group position={[px, py, pz]}>
      {/* Pot */}
      <mesh position={[0, 0.09, 0]} castShadow receiveShadow>
        <cylinderGeometry args={[0.12, 0.15, 0.18, 8]} />
        <meshStandardMaterial color="#c4703a" />
      </mesh>

      {/* Soil top */}
      <mesh position={[0, 0.185, 0]}>
        <cylinderGeometry args={[0.115, 0.115, 0.02, 8]} />
        <meshStandardMaterial color="#3a2a1a" />
      </mesh>

      {/* Stem */}
      <mesh position={[0, 0.32, 0]} castShadow>
        <cylinderGeometry args={[0.02, 0.025, 0.22, 6]} />
        <meshStandardMaterial color="#2d5a1a" />
      </mesh>

      {/* Foliage */}
      <mesh position={[0, 0.52, 0]} castShadow>
        <sphereGeometry args={[0.22, 8, 6]} />
        <meshStandardMaterial color="#2d6a1f" transparent opacity={0.9} />
      </mesh>

      {/* Secondary foliage — offset slightly */}
      <mesh position={[0.1, 0.48, 0.05]} castShadow>
        <sphereGeometry args={[0.15, 7, 5]} />
        <meshStandardMaterial color="#3a7a28" transparent opacity={0.85} />
      </mesh>
    </group>
  );
}
