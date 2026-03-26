import React from "react";

interface Props {
  position: [number, number, number];
}

export function CoffeeMachine3D({ position }: Props): React.ReactElement {
  const [px, py, pz] = position;

  return (
    <group position={[px, py, pz]}>
      {/* Main body */}
      <mesh position={[0, 0.25, 0]} castShadow receiveShadow>
        <boxGeometry args={[0.25, 0.5, 0.25]} />
        <meshStandardMaterial color="#2a2a2a" />
      </mesh>

      {/* Top panel */}
      <mesh position={[0, 0.505, 0]} castShadow>
        <boxGeometry args={[0.26, 0.02, 0.26]} />
        <meshStandardMaterial color="#1a1a1a" />
      </mesh>

      {/* Screen - emissive green */}
      <mesh position={[0, 0.35, 0.13]}>
        <boxGeometry args={[0.1, 0.08, 0.01]} />
        <meshStandardMaterial color="#002200" emissive="#00aa44" emissiveIntensity={1.0} />
      </mesh>

      {/* Button row */}
      <mesh position={[0, 0.25, 0.13]}>
        <boxGeometry args={[0.12, 0.02, 0.01]} />
        <meshStandardMaterial color="#333333" />
      </mesh>

      {/* Dispenser nozzle */}
      <mesh position={[0, 0.12, 0.1]} castShadow>
        <cylinderGeometry args={[0.015, 0.015, 0.08, 6]} />
        <meshStandardMaterial color="#444444" />
      </mesh>

      {/* Cup */}
      <mesh position={[0, 0.025, 0.1]} castShadow receiveShadow>
        <cylinderGeometry args={[0.04, 0.03, 0.05, 8]} />
        <meshStandardMaterial color="#f5f0e8" />
      </mesh>

      {/* Coffee in cup */}
      <mesh position={[0, 0.052, 0.1]}>
        <cylinderGeometry args={[0.035, 0.035, 0.005, 8]} />
        <meshStandardMaterial color="#3a1a08" />
      </mesh>

      {/* Water tank on back */}
      <mesh position={[0, 0.3, -0.1]} castShadow>
        <boxGeometry args={[0.2, 0.3, 0.08]} />
        <meshStandardMaterial color="#1a3a5c" transparent opacity={0.7} />
      </mesh>
    </group>
  );
}
