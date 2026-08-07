import { ContactShadows, Grid } from '@react-three/drei';
import { DataTexture, DoubleSide, LinearFilter, RedFormat, RepeatWrapping, UnsignedByteType } from 'three';
import { PALETTE, shade, sharedMaterial, tint } from './palette';

/**
 * Workshop shell: concrete floor with a technical grid, aisle markings,
 * perimeter curbs, corner pillars and static high-bay fixtures. Everything is
 * procedural and palette-derived; no texture files or external assets.
 */

const createConcreteTexture = () => {
  const size = 128;
  const data = new Uint8Array(size * size);
  for (let y = 0; y < size; y += 1) {
    for (let x = 0; x < size; x += 1) {
      const grain = ((x * 37 + y * 61 + x * y * 7) % 29) - 14;
      const broadVariation = Math.sin(x * 0.17) * 8 + Math.cos(y * 0.13) * 7;
      data[y * size + x] = Math.max(116, Math.min(220, Math.round(172 + grain + broadVariation)));
    }
  }
  const texture = new DataTexture(data, size, size, RedFormat, UnsignedByteType);
  texture.wrapS = RepeatWrapping;
  texture.wrapT = RepeatWrapping;
  texture.repeat.set(8, 5);
  texture.minFilter = LinearFilter;
  texture.magFilter = LinearFilter;
  texture.needsUpdate = true;
  return texture;
};

const concreteTexture = createConcreteTexture();
const floorSlab = () => sharedMaterial('floorSlab', { color: PALETTE.border, metalness: 0.05, roughness: 0.82, roughnessMap: concreteTexture, bumpMap: concreteTexture, bumpScale: 0.014 });
const curb = () => sharedMaterial('curb', { color: shade(PALETTE.secondary, 0.15), metalness: 0.2, roughness: 0.7 });
const pillar = () => sharedMaterial('pillar', { color: tint(PALETTE.primary, 0.12), metalness: 0.3, roughness: 0.55 });
const pillarBase = () => sharedMaterial('pillarBase', { color: PALETTE.secondary, metalness: 0.3, roughness: 0.6 });
const aislePaint = () => sharedMaterial('aislePaint', { color: PALETTE.background, metalness: 0, roughness: 0.85 });
const fixtureHousing = () => sharedMaterial('fixtureHousing', { color: PALETTE.primary, metalness: 0.5, roughness: 0.4 });
const fixtureStem = () => sharedMaterial('fixtureStem', { color: PALETTE.secondary, metalness: 0.5, roughness: 0.45 });
const wallPanel = () => sharedMaterial('wallPanel', { color: tint(PALETTE.border, 0.22), metalness: 0.06, roughness: 0.78 });
const wallJoint = () => sharedMaterial('wallJoint', { color: PALETTE.mutedForeground, metalness: 0.18, roughness: 0.62 });
const conduit = () => sharedMaterial('conduit', { color: tint(PALETTE.secondary, 0.35), metalness: 0.72, roughness: 0.3 });
const cabinet = () => sharedMaterial('environmentCabinet', { color: PALETTE.primary, metalness: 0.28, roughness: 0.52 });

export interface WorkshopEnvironmentProps {
  width?: number;
  depth?: number;
}

function AisleMarkings({ width, depth }: { width: number; depth: number }) {
  const dashes: Array<[number, number]> = [];
  const aisleY = depth * 0.16;
  for (let x = -width / 2 + 1; x <= width / 2 - 1; x += 1.05) {
    dashes.push([x, -aisleY], [x, aisleY]);
  }
  return <>
    {dashes.map(([x, y]) => <mesh key={`${x}:${y}`} position={[x, y, -0.005]} material={aislePaint()} receiveShadow>
      <boxGeometry args={[0.55, 0.07, 0.008]} />
    </mesh>)}
  </>;
}

function HighBayFixture({ x, y }: { x: number; y: number }) {
  return <group position={[x, y, 0]}>
    <mesh position={[0, 0, 3.28]} rotation={[Math.PI / 2, 0, 0]} material={fixtureStem()}>
      <cylinderGeometry args={[0.025, 0.025, 0.35, 8]} />
    </mesh>
    <mesh position={[0, 0, 3.02]} rotation={[Math.PI / 2, 0, 0]} material={fixtureHousing()}>
      <cylinderGeometry args={[0.06, 0.3, 0.16, 16]} />
    </mesh>
    <mesh position={[0, 0, 2.91]} rotation={[Math.PI / 2, 0, 0]}>
      <cylinderGeometry args={[0.27, 0.27, 0.03, 16]} />
      <meshStandardMaterial color={PALETTE.background} emissive={PALETTE.background} emissiveIntensity={1.4} toneMapped={false} metalness={0} roughness={0.6} />
    </mesh>
    <pointLight position={[0, 0, 2.78]} color={PALETTE.card} intensity={13} distance={6.5} decay={2} />
  </group>;
}

export function WorkshopEnvironment({ width = 14, depth = 9 }: WorkshopEnvironmentProps) {
  const halfW = width / 2;
  const halfD = depth / 2;
  const corners: Array<[number, number]> = [[-halfW + 0.3, -halfD + 0.3], [-halfW + 0.3, halfD - 0.3], [halfW - 0.3, -halfD + 0.3], [halfW - 0.3, halfD - 0.3]];
  const fixtures: Array<[number, number]> = [[-3.4, -2.3], [-3.4, 2.3], [3.4, -2.3], [3.4, 2.3]];
  const wallPanels = Array.from({ length: 7 }, (_, index) => -6 + index * 2);

  return <group>
    <mesh position={[0, 0, -0.12]} material={floorSlab()} receiveShadow>
      <boxGeometry args={[width, depth, 0.22]} />
    </mesh>
    {/* drei Grid is authored on the local XZ plane; rotated once for the Z-up scene. */}
    <Grid
      position={[0, 0, -0.007]}
      rotation={[Math.PI / 2, 0, 0]}
      args={[width, depth]}
      cellSize={0.5}
      sectionSize={2}
      cellColor={tint(PALETTE.mutedForeground, 0.55)}
      sectionColor={PALETTE.mutedForeground}
      cellThickness={0.6}
      sectionThickness={1.1}
      fadeDistance={34}
      fadeStrength={1.2}
      infiniteGrid={false}
      followCamera={false}
      side={DoubleSide}
    />
    <AisleMarkings width={width} depth={depth} />
    {/* Sparse expansion joints break the perfectly uniform floor without obscuring the operational grid. */}
    {[-4.65, 0, 4.65].map((x) => <mesh key={`joint-x-${x}`} position={[x, 0, 0.001]} material={wallJoint()} receiveShadow>
      <boxGeometry args={[0.018, depth - 0.3, 0.004]} />
    </mesh>)}
    {[-2.95, 2.95].map((y) => <mesh key={`joint-y-${y}`} position={[0, y, 0.001]} material={wallJoint()} receiveShadow>
      <boxGeometry args={[width - 0.3, 0.018, 0.004]} />
    </mesh>)}
    <mesh position={[0, -halfD + 0.07, 0.07]} material={curb()} castShadow receiveShadow>
      <boxGeometry args={[width, 0.14, 0.14]} />
    </mesh>
    <mesh position={[0, halfD - 0.07, 0.07]} material={curb()} castShadow receiveShadow>
      <boxGeometry args={[width, 0.14, 0.14]} />
    </mesh>
    <mesh position={[-halfW + 0.07, 0, 0.07]} material={curb()} castShadow receiveShadow>
      <boxGeometry args={[0.14, depth, 0.14]} />
    </mesh>
    <mesh position={[halfW - 0.07, 0, 0.07]} material={curb()} castShadow receiveShadow>
      <boxGeometry args={[0.14, depth, 0.14]} />
    </mesh>
    {corners.map(([x, y]) => <group key={`${x}:${y}`} position={[x, y, 0]}>
      <mesh position={[0, 0, 0.03]} material={pillarBase()} castShadow>
        <boxGeometry args={[0.5, 0.5, 0.06]} />
      </mesh>
      <mesh position={[0, 0, 1.75]} material={pillar()} castShadow>
        <boxGeometry args={[0.34, 0.34, 3.5]} />
      </mesh>
    </group>)}
    {/* A restrained service wall gives the scene depth while leaving the operator side open. */}
    {wallPanels.map((x) => <mesh key={`wall-${x}`} position={[x, halfD - 0.2, 1.48]} material={wallPanel()} receiveShadow>
      <boxGeometry args={[1.92, 0.08, 2.72]} />
    </mesh>)}
    <mesh position={[-4.9, halfD - 0.11, 1.05]} material={cabinet()} castShadow>
      <boxGeometry args={[1.05, 0.18, 1.72]} />
    </mesh>
    {[-5.15, -4.9, -4.65].map((x) => <mesh key={`vent-${x}`} position={[x, halfD - 0.005, 1.25]} material={wallJoint()}>
      <boxGeometry args={[0.13, 0.015, 0.55]} />
    </mesh>)}
    {[2.15, 2.42].map((z) => <mesh key={`conduit-${z}`} position={[0, halfD - 0.08, z]} rotation={[0, 0, Math.PI / 2]} material={conduit()} castShadow>
      <cylinderGeometry args={[0.035, 0.035, width - 1, 12]} />
    </mesh>)}
    {/* Overhead frame connects the pillars and gives the static high-bay fixtures a credible support. */}
    <mesh position={[0, -halfD + 0.3, 3.45]} material={pillar()}><boxGeometry args={[width - 0.6, 0.18, 0.18]} /></mesh>
    <mesh position={[0, halfD - 0.3, 3.45]} material={pillar()}><boxGeometry args={[width - 0.6, 0.18, 0.18]} /></mesh>
    <mesh position={[-halfW + 0.3, 0, 3.45]} material={pillar()}><boxGeometry args={[0.18, depth - 0.6, 0.18]} /></mesh>
    <mesh position={[halfW - 0.3, 0, 3.45]} material={pillar()}><boxGeometry args={[0.18, depth - 0.6, 0.18]} /></mesh>
    {[-3.4, 3.4].map((x) => <mesh key={x} position={[x, 0, 3.45]} material={fixtureStem()}><boxGeometry args={[0.16, depth - 0.6, 0.14]} /></mesh>)}
    {fixtures.map(([x, y]) => <HighBayFixture key={`${x}:${y}`} x={x} y={y} />)}
    {/* ContactShadows defaults to Y-up. Rx(π) keeps the plane on XY and points its capture camera toward +Z. */}
    <ContactShadows position={[0, 0, -0.0005]} rotation-x={Math.PI} scale={Math.max(width, depth)} far={2.6} resolution={512} frames={1} opacity={0.28} blur={2.2} color={PALETTE.foreground} />
  </group>;
}

/** Neutral daylight industrial rig; no bloom, no colored glow. */
export function WorkshopLighting() {
  return <>
    <hemisphereLight args={[PALETTE.card, PALETTE.secondary, 0.78]} />
    <directionalLight
      position={[4, -6, 12]}
      intensity={1.55}
      castShadow
      shadow-mapSize={[1024, 1024]}
      shadow-bias={-0.0002}
      shadow-normalBias={0.025}
      shadow-camera-left={-8}
      shadow-camera-right={8}
      shadow-camera-top={6}
      shadow-camera-bottom={-6}
      shadow-camera-near={2}
      shadow-camera-far={30}
    />
    <directionalLight position={[-6, 4, 8]} intensity={0.28} />
  </>;
}
