import { Canvas } from '@react-three/fiber';
import { Html, OrbitControls, PerspectiveCamera } from '@react-three/drei';
import type { Machine } from '../lib/api';
import { layoutForMachine, WORKSHOP_SIZE } from './WorkshopMap';
import { machineStatusLabel } from './Ui';

function statusColor(status?: string | null): string {
  return ({ running: '#35b996', warning: '#e6aa42', stopped: '#d46967', offline: '#8999aa' } as Record<string, string>)[status ?? 'offline'] ?? '#8999aa';
}

function MachineMesh({ machine, index, selected, onSelect }: { machine: Machine; index: number; selected: boolean; onSelect: (machine: Machine) => void }) {
  const layout = layoutForMachine(machine, index);
  const x = (layout.x / WORKSHOP_SIZE.width - 0.5) * 10;
  const y = -(layout.y / WORKSHOP_SIZE.height - 0.5) * 5;
  const width = ((layout.width ?? 120) / WORKSHOP_SIZE.width) * 10;
  const height = ((layout.height ?? 80) / WORKSHOP_SIZE.height) * 5;
  const color = statusColor(machine.status);
  return (
    <group position={[x, y, 0.35]} rotation={[0, 0, ((layout.rotation ?? 0) * Math.PI) / 180]} onClick={() => onSelect(machine)}>
      <mesh castShadow receiveShadow>
        <boxGeometry args={[width, height, 0.55]} />
        <meshStandardMaterial color={selected ? '#0e7f88' : color} metalness={0.15} roughness={0.6} />
      </mesh>
      <mesh position={[0, 0, 0.3]}>
        <boxGeometry args={[width * 0.68, height * 0.54, 0.12]} />
        <meshStandardMaterial color="#dce7ec" roughness={0.8} />
      </mesh>
      <Html center distanceFactor={8} position={[0, 0, 0.5]}>
        <button className="three-label" type="button" onClick={() => onSelect(machine)} aria-label={`${machine.name}, ${machineStatusLabel(machine.status)}`}>
          <strong>{machine.name}</strong><span>{machineStatusLabel(machine.status)}</span>
        </button>
      </Html>
    </group>
  );
}

/** Real opt-in Three.js view. VITE_ENABLE_3D=false keeps the SVG fallback. */
export function Workshop3D({ machines, selectedMachineId, onSelect }: { machines: Machine[]; selectedMachineId?: number; onSelect: (machine: Machine) => void }) {
  if (import.meta.env.VITE_ENABLE_3D !== 'true') {
    return <div className="three-fallback" role="note"><strong>Vue 3D désactivée</strong><span>Activez <code>VITE_ENABLE_3D=true</code> pour le prévisualiseur Three.js. La vue 2D reste la référence opérationnelle.</span></div>;
  }
  return <div className="three-canvas-wrap" aria-label="Vue 3D top-down de l’atelier">
    <Canvas shadows dpr={[1, 2]}>
      <PerspectiveCamera makeDefault position={[0, 0, 9]} fov={38} />
      <ambientLight intensity={1.5} />
      <directionalLight position={[2, 4, 7]} intensity={2} castShadow />
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, -0.15]} receiveShadow>
        <planeGeometry args={[10.8, 5.8]} />
        <meshStandardMaterial color="#e9f0f2" roughness={0.95} />
      </mesh>
      {machines.map((machine, index) => <MachineMesh key={machine.id} machine={machine} index={index} selected={machine.id === selectedMachineId} onSelect={onSelect} />)}
      <OrbitControls enableRotate={false} minZoom={0.8} maxZoom={2.2} />
    </Canvas>
    <p className="muted three-note">Scène top-down légère : mêmes coordonnées, états et sélection que le plan 2D.</p>
  </div>;
}
