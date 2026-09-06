import type { ThreeEvent } from '@react-three/fiber';
import { RoundedBoxGeometry } from 'three/examples/jsm/geometries/RoundedBoxGeometry.js';
import { PALETTE, shade, sharedMaterial, statusColor, tint } from './palette';

/**
 * Stylistically restrained but recognizable horizontal injection molding press.
 * Local frame: Z up, machine axis along X (injection unit at -X, clamping at
 * +X), origin at floor center. Footprint stays within about 2.1 by 1.2 scene units
 * so the press remains registered with the shared 2D/3D workshop layout.
 */

const frame = () => sharedMaterial('frame', { color: shade(PALETTE.primary, 0.18), metalness: 0.35, roughness: 0.5 });
const footPad = () => sharedMaterial('footPad', { color: shade(PALETTE.primary, 0.45), metalness: 0.3, roughness: 0.65 });
const steel = () => sharedMaterial('steel', { color: tint(PALETTE.secondary, 0.45), metalness: 0.8, roughness: 0.25 });
const steelDark = () => sharedMaterial('steelDark', { color: PALETTE.secondary, metalness: 0.6, roughness: 0.35 });
const platen = () => sharedMaterial('platen', { color: PALETTE.border, metalness: 0.5, roughness: 0.35 });
const moldSteel = () => sharedMaterial('moldSteel', { color: tint(PALETTE.secondary, 0.3), metalness: 0.8, roughness: 0.22 });
const barrelSteel = () => sharedMaterial('barrelSteel', { color: tint(PALETTE.secondary, 0.35), metalness: 0.8, roughness: 0.22 });
const heaterBand = () => sharedMaterial('heaterBand', { color: PALETTE.primary, metalness: 0.5, roughness: 0.4 });
const hopperPaint = () => sharedMaterial('hopperPaint', { color: PALETTE.border, metalness: 0.4, roughness: 0.4 });
const cabinetPaint = () => sharedMaterial('cabinetPaint', { color: PALETTE.secondary, metalness: 0.3, roughness: 0.5 });
const guardPanel = () => sharedMaterial('guardPanel', { color: tint(PALETTE.secondary, 0.55), metalness: 0.1, roughness: 0.28, transparent: true, opacity: 0.24, depthWrite: false });
const fixturePaint = () => sharedMaterial('fixturePaint', { color: PALETTE.primary, metalness: 0.4, roughness: 0.5 });
const rubber = () => sharedMaterial('rubber', { color: PALETTE.foreground, metalness: 0.05, roughness: 0.88 });

// Shared chamfered geometries catch highlights without multiplying geometry allocations per press.
const BED_GEOMETRY = new RoundedBoxGeometry(2, 1, 0.3, 2, 0.035);
const CLAMP_GEOMETRY = new RoundedBoxGeometry(0.3, 0.52, 0.56, 2, 0.025);
const CABINET_GEOMETRY = new RoundedBoxGeometry(0.8, 0.24, 1.1, 2, 0.028);
const SCREEN_GEOMETRY = new RoundedBoxGeometry(0.36, 0.05, 0.28, 2, 0.025);

/** Cylinders are authored along their local Y; these rotations align them with the scene axes. */
const ALONG_X: [number, number, number] = [0, 0, -Math.PI / 2];
const ALONG_Z: [number, number, number] = [Math.PI / 2, 0, 0];

export interface InjectionPressProps {
  status?: string | null;
  selected?: boolean;
  signalCount?: number;
  onSelect?: (event: ThreeEvent<MouseEvent>) => void;
}

export function InjectionPress({ status, selected = false, signalCount = 0, onSelect }: InjectionPressProps) {
  const color = statusColor(status);
  const beaconSegments: Array<{ key: string; hex: string; z: number }> = [
    { key: 'running', hex: PALETTE.accent, z: 1.58 },
    { key: 'warning', hex: PALETTE.secondary, z: 1.67 },
    { key: 'stopped', hex: PALETTE.destructive, z: 1.76 },
  ];

  return <group onClick={onSelect}>
    {selected ? <mesh position={[0, 0, -0.005]}>
      <boxGeometry args={[2.1, 1.46, 0.008]} />
      <meshStandardMaterial color={PALETTE.accent} emissive={PALETTE.accent} emissiveIntensity={0.35} />
    </mesh> : null}

    {/* Foundation pads and machine bed */}
    {[[-0.82, -0.4], [-0.82, 0.4], [0.82, -0.4], [0.82, 0.4]].map(([x, y]) => <mesh key={`${x}:${y}`} position={[x, y, 0.05]} material={footPad()} castShadow>
      <boxGeometry args={[0.22, 0.22, 0.1]} />
    </mesh>)}
    <mesh position={[0, 0, 0.23]} geometry={BED_GEOMETRY} material={frame()} castShadow receiveShadow />
    {[-0.335, 0.335].map((y) => <mesh key={y} position={[0, y, 0.405]} material={steel()}>
      <boxGeometry args={[1.86, 0.07, 0.05]} />
    </mesh>)}

    {/* Clamping unit: tie bars, platens, mold, clamp housing */}
    {[[-0.3, 0.62], [-0.3, 1.02], [0.3, 0.62], [0.3, 1.02]].map(([y, z]) => <mesh key={`${y}:${z}`} position={[0.6, y, z]} rotation={ALONG_X} material={steel()} castShadow>
      <cylinderGeometry args={[0.032, 0.032, 0.8, 12]} />
    </mesh>)}
    <mesh position={[0.86, 0, 0.82]} material={platen()} castShadow receiveShadow>
      <boxGeometry args={[0.1, 0.74, 0.8]} />
    </mesh>
    <mesh position={[0.38, 0, 0.82]} material={platen()} castShadow receiveShadow>
      <boxGeometry args={[0.1, 0.74, 0.8]} />
    </mesh>
    {[0.5, 0.68].map((x) => <mesh key={x} position={[x, 0, 0.82]} material={moldSteel()} castShadow>
      <boxGeometry args={[0.1, 0.52, 0.54]} />
    </mesh>)}
    <mesh position={[0.12, 0, 0.82]} geometry={CLAMP_GEOMETRY} material={steelDark()} castShadow />

    {/* Injection unit: barrel, heater bands, nozzle, hopper */}
    <mesh position={[-0.52, 0, 0.82]} rotation={ALONG_X} material={barrelSteel()} castShadow>
      <cylinderGeometry args={[0.11, 0.11, 1, 20]} />
    </mesh>
    {[-0.28, -0.52, -0.76].map((x) => <mesh key={x} position={[x, 0, 0.82]} rotation={ALONG_X} material={heaterBand()}>
      <cylinderGeometry args={[0.125, 0.125, 0.07, 20]} />
    </mesh>)}
    <mesh position={[-1.06, 0, 0.82]} rotation={ALONG_X} material={steelDark()}>
      <cylinderGeometry args={[0.05, 0.075, 0.14, 14]} />
    </mesh>
    <mesh position={[-0.78, 0, 0.98]} material={steelDark()}>
      <boxGeometry args={[0.14, 0.14, 0.1]} />
    </mesh>
    <mesh position={[-0.78, 0, 1.14]} rotation={ALONG_Z} material={hopperPaint()} castShadow>
      <cylinderGeometry args={[0.07, 0.2, 0.26, 16]} />
    </mesh>
    <mesh position={[-0.78, 0, 1.285]} rotation={ALONG_Z} material={steelDark()}>
      <cylinderGeometry args={[0.21, 0.21, 0.03, 16]} />
    </mesh>

    {/* Control cabinet at the back and HMI screen facing the aisle */}
    <mesh position={[0.3, 0.56, 0.72]} geometry={CABINET_GEOMETRY} material={cabinetPaint()} castShadow receiveShadow />
    <mesh position={[0.62, 0.36, 1.02]} material={fixturePaint()}>
      <boxGeometry args={[0.06, 0.18, 0.06]} />
    </mesh>
    <mesh position={[0.62, 0.24, 1.1]} geometry={SCREEN_GEOMETRY} material={frame()} />
    <mesh position={[0.62, 0.212, 1.1]}>
      <boxGeometry args={[0.3, 0.02, 0.22]} />
      <meshStandardMaterial color={PALETTE.foreground} emissive={color} emissiveIntensity={0.28} metalness={0.2} roughness={0.55} />
    </mesh>
    {[-0.14, -0.05, 0.04, 0.13].map((x) => <mesh key={x} position={[x, 0.425, 0.83]} material={rubber()}>
      <boxGeometry args={[0.025, 0.012, 0.46]} />
    </mesh>)}

    {/* Status beacon tower: active segment matches the machine status */}
    <mesh position={[0.55, 0.56, 1.42]} rotation={ALONG_Z} material={steelDark()}>
      <cylinderGeometry args={[0.018, 0.018, 0.3, 10]} />
    </mesh>
    {beaconSegments.map(({ key, hex, z }) => {
      const active = status === key;
      return <mesh key={key} position={[0.55, 0.56, z]} rotation={ALONG_Z}>
        <cylinderGeometry args={[0.05, 0.05, 0.08, 14]} />
        <meshStandardMaterial color={active ? hex : tint(hex, 0.55)} emissive={active ? hex : PALETTE.foreground} emissiveIntensity={active ? 1.15 : 0} metalness={0.2} roughness={0.4} />
      </mesh>;
    })}

    {/* Safety guarding along the aisle side, cable tray, status strip */}
    <mesh position={[0.42, -0.56, 0.62]} material={guardPanel()}>
      <boxGeometry args={[1.14, 0.03, 0.46]} />
    </mesh>
    <mesh position={[0, 0.475, 0.1]} material={fixturePaint()}>
      <boxGeometry args={[1.7, 0.09, 0.05]} />
    </mesh>
    <mesh position={[-0.1, -0.515, 0.3]}>
      <boxGeometry args={[1.3, 0.04, 0.07]} />
      <meshStandardMaterial color={color} emissive={color} emissiveIntensity={1} metalness={0.2} roughness={0.45} />
    </mesh>

    {signalCount > 0 ? <mesh position={[0.55, 0.56, 1.92]}>
      <sphereGeometry args={[0.12, 16, 16]} />
      <meshStandardMaterial color={PALETTE.destructive} emissive={PALETTE.destructive} emissiveIntensity={0.65} />
    </mesh> : null}
  </group>;
}
