import { MinusIcon } from '@phosphor-icons/react/Minus';
import { PlusIcon } from '@phosphor-icons/react/Plus';
import { Canvas, useThree } from '@react-three/fiber';
import { Environment, Html, Lightformer, OrbitControls, PerspectiveCamera } from '@react-three/drei';
import { useLayoutEffect, useRef, useState } from 'react';
import { ACESFilmicToneMapping, PCFSoftShadowMap, SRGBColorSpace } from 'three';
import type { KeyboardEvent, MutableRefObject } from 'react';
import type * as THREE from 'three';
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib';
import type { Machine } from '../lib/api';
import { machineStatusLabel } from './Ui';
import { InjectionPress } from './three/InjectionPress';
import { WorkshopEnvironment, WorkshopLighting } from './three/WorkshopEnvironment';
import { PALETTE } from './three/palette';
import { resolveWorkshopLayouts, WORKSHOP_SIZE, type WorkshopLayout } from './workshopLayout';

const SCENE_WIDTH = 14;
const SCENE_DEPTH = 9;
const CAMERA_HOME: [number, number, number] = [9.4, -12.8, 7.2];
const CAMERA_MIN_DISTANCE = 7;
const CAMERA_MAX_DISTANCE = 22;

export function scenePositionFromWorkshop(layout: WorkshopLayout): [number, number, number] {
  return [((layout.x / WORKSHOP_SIZE.width) - .5) * 10.5, -((layout.y / WORKSHOP_SIZE.height) - .5) * 6.2, 0];
}

/** A deterministic two-row layout remains available when no workshop layout exists. */
export function scenePosition(index: number, machineCount: number): [number, number, number] {
  const leftCount = Math.ceil(machineCount / 2);
  const left = index < leftCount;
  const rowIndex = left ? index : index - leftCount;
  const rowCount = left ? leftCount : Math.max(1, machineCount - leftCount);
  const spacing = Math.min(2.3, 9.5 / Math.max(1, rowCount));
  const x = (rowIndex - (rowCount - 1) / 2) * spacing;
  return [x, left ? -2.55 : 2.55, 0];
}

function handleMachineRadioKey(event: KeyboardEvent<HTMLButtonElement>, index: number, machines: Machine[], onSelect: (machine: Machine) => void) {
  if (!['ArrowRight', 'ArrowDown', 'ArrowLeft', 'ArrowUp'].includes(event.key)) return;
  event.preventDefault();
  const direction = event.key === 'ArrowRight' || event.key === 'ArrowDown' ? 1 : -1;
  const nextIndex = (index + direction + machines.length) % machines.length;
  onSelect(machines[nextIndex]);
  const radios = event.currentTarget.closest('[role="radiogroup"]')?.querySelectorAll<HTMLButtonElement>('[role="radio"]');
  window.setTimeout(() => radios?.[nextIndex]?.focus(), 0);
}

export function machineLabelVisible(selected: boolean, signalCount: number, showLabels: boolean): boolean {
  return selected || signalCount > 0 || showLabels;
}

function MachineMesh({ machine, index, machineCount, layout, selected, signalCount, showLabels, onSelect }: { machine: Machine; index: number; machineCount: number; layout?: WorkshopLayout; selected: boolean; signalCount: number; showLabels: boolean; onSelect: (machine: Machine) => void }) {
  const [x, y] = layout ? scenePositionFromWorkshop(layout) : scenePosition(index, machineCount);
  const rowCount = Math.ceil(machineCount / 2);
  const machineScale = Math.min(1, 5.2 / Math.max(1, rowCount));

  return <group position={[x, y, 0]} scale={machineScale} rotation={[0, 0, layout ? -(layout.rotation * Math.PI) / 180 : y > 0 ? Math.PI : 0]} onClick={(event) => { event.stopPropagation(); onSelect(machine); }}>
    <InjectionPress status={machine.status} selected={selected} signalCount={signalCount} />
    {machineLabelVisible(selected, signalCount, showLabels) ? <Html center distanceFactor={selected ? 11 : 7} position={selected ? [0, -.55, 2.05] : [0, 0, 1.88]}>
      <div className={`three-label${selected ? ' selected' : ' compact'}`} aria-hidden="true">
        <strong>{selected ? machine.name : machine.erpRef ? `ERP ${machine.erpRef}` : machine.name}</strong>
        {selected ? <span className={`status-${machine.status ?? 'unknown'}`}><i />{machineStatusLabel(machine.status)}</span> : null}
        {signalCount > 0 ? <small className="three-label-signal">{signalCount} {signalCount > 1 ? 'anomalies' : 'anomalie'}</small> : null}
      </div>
    </Html> : null}
  </group>;
}

function WebGLContextGuard({ onUnavailable }: { onUnavailable?: () => void }) {
  const gl = useThree((state) => state.gl);

  useLayoutEffect(() => {
    const canvas = gl.domElement;
    const handleContextLost = (event: Event) => {
      event.preventDefault();
      onUnavailable?.();
    };
    canvas.addEventListener('webglcontextlost', handleContextLost);
    return () => canvas.removeEventListener('webglcontextlost', handleContextLost);
  }, [gl, onUnavailable]);

  return null;
}

function FactoryScene({ machines, selectedMachineId, signalCounts, showLabels, onSelect, cameraRef, controlsRef }: { machines: Machine[]; selectedMachineId?: number; signalCounts: Record<number, number>; showLabels: boolean; onSelect: (machine: Machine) => void; cameraRef: MutableRefObject<THREE.PerspectiveCamera | null>; controlsRef: MutableRefObject<OrbitControlsImpl | null> }) {
  const layouts = resolveWorkshopLayouts(machines);
  return <>
    <color attach="background" args={['#F2F3F4']} />
    <fog attach="fog" args={['#F2F3F4', 21, 34]} />
    <PerspectiveCamera ref={cameraRef} makeDefault position={CAMERA_HOME} up={[0, 0, 1]} fov={42} />
    <Environment resolution={128} background={false}>
      <Lightformer form="rect" intensity={1.8} color={PALETTE.card} position={[0, -5, 7]} rotation={[Math.PI / 2, 0, 0]} scale={[9, 3, 1]} />
      <Lightformer form="rect" intensity={1.15} color={PALETTE.background} position={[-6, 2, 5]} rotation={[0, Math.PI / 2, 0]} scale={[5, 2, 1]} />
      <Lightformer form="rect" intensity={0.75} color={PALETTE.border} position={[6, 1, 4]} rotation={[0, -Math.PI / 2, 0]} scale={[4, 2, 1]} />
    </Environment>
    <WorkshopLighting />
    <WorkshopEnvironment width={SCENE_WIDTH} depth={SCENE_DEPTH} />
    {machines.map((machine, index) => <MachineMesh key={machine.id} machine={machine} index={index} machineCount={machines.length} layout={layouts[index]} selected={machine.id === selectedMachineId} signalCount={signalCounts[machine.id] ?? 0} showLabels={showLabels} onSelect={onSelect} />)}
    <OrbitControls ref={controlsRef} makeDefault target={[0, 0, .68]} enableDamping dampingFactor={.08} enablePan enableZoom enableRotate minDistance={CAMERA_MIN_DISTANCE} maxDistance={CAMERA_MAX_DISTANCE} minPolarAngle={.58} maxPolarAngle={Math.PI / 2.18} />
  </>;
}

/** Opt-in Three.js view; the SVG workshop remains the operational fallback. */
export function Workshop3D({ machines, selectedMachineId, signalCounts = {}, onSelect, onUnavailable }: { machines: Machine[]; selectedMachineId?: number; signalCounts?: Record<number, number>; onSelect: (machine: Machine) => void; onUnavailable?: () => void }) {
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const controlsRef = useRef<OrbitControlsImpl | null>(null);
  const [showLabels, setShowLabels] = useState(false);

  if (import.meta.env.VITE_ENABLE_3D !== 'true') return <div className="three-fallback" role="note"><strong>Vue 3D désactivée</strong><span>Activez <code>VITE_ENABLE_3D=true</code> pour le prévisualiseur Three.js. La vue 2D reste la référence opérationnelle.</span></div>;

  const zoom = (factor: number) => {
    const camera = cameraRef.current;
    if (!camera) return;
    const target = controlsRef.current?.target;
    const offset = target ? camera.position.clone().sub(target) : camera.position.clone();
    offset.setLength(Math.min(CAMERA_MAX_DISTANCE, Math.max(CAMERA_MIN_DISTANCE, offset.length() * factor)));
    camera.position.copy(target ? target.clone().add(offset) : offset);
    camera.updateProjectionMatrix();
    controlsRef.current?.update();
  };
  const reset = () => {
    const camera = cameraRef.current;
    if (camera) { camera.position.set(...CAMERA_HOME); camera.updateProjectionMatrix(); }
    controlsRef.current?.reset();
  };

  return <div className="three-viewer">
    <div className="three-canvas-wrap">
      <Canvas
        role="group"
        aria-label="Vue spatiale du parc machine. Les positions reprennent les coordonnées affichées en 2D."
        shadows
        dpr={[1, 1.6]}
        frameloop="demand"
        camera={{ position: CAMERA_HOME }}
        gl={{ antialias: true, alpha: false, powerPreference: 'high-performance' }}
        onCreated={({ gl }) => {
          gl.toneMapping = ACESFilmicToneMapping;
          gl.toneMappingExposure = .92;
          gl.outputColorSpace = SRGBColorSpace;
          gl.shadowMap.type = PCFSoftShadowMap;
        }}
      >
        <WebGLContextGuard onUnavailable={onUnavailable} />
        <FactoryScene machines={machines} selectedMachineId={selectedMachineId} signalCounts={signalCounts} showLabels={showLabels} onSelect={onSelect} cameraRef={cameraRef} controlsRef={controlsRef} />
      </Canvas>
      <div className="three-toolbar" role="group" aria-label="Contrôles de la vue 3D">
        <button type="button" onClick={() => zoom(.86)} aria-label="Zoomer"><PlusIcon size={18} aria-hidden="true" /></button>
        <button type="button" onClick={() => zoom(1.16)} aria-label="Dézoomer"><MinusIcon size={18} aria-hidden="true" /></button>
        <button type="button" className="three-reset" onClick={reset}>Recentrer</button>
        <button type="button" className={`three-label-toggle${showLabels ? ' active' : ''}`} aria-pressed={showLabels} aria-label={showLabels ? 'Masquer les repères des machines' : 'Afficher les repères des machines'} onClick={() => setShowLabels((visible) => !visible)}>Repères</button>
      </div>
    </div>
    <div className="three-accessible-machines" role="radiogroup" aria-label="Sélection clavier des presses">
      {machines.map((machine, index) => { const signalCount = signalCounts[machine.id] ?? 0; return <button key={machine.id} type="button" role="radio" className={machine.id === selectedMachineId ? 'active' : ''} tabIndex={machine.id === selectedMachineId ? 0 : -1} aria-checked={machine.id === selectedMachineId} aria-label={`${machine.name}, ${machineStatusLabel(machine.status)}${signalCount > 0 ? `, ${signalCount} ${signalCount > 1 ? 'anomalies reconstruites' : 'anomalie reconstruite'}` : ''}`} onClick={() => onSelect(machine)} onKeyDown={(event) => handleMachineRadioKey(event, index, machines, onSelect)}>{machine.name}</button>; })}
    </div>
    <p className="muted three-note">Glisser pour orienter · clic droit pour déplacer · molette ou pincement pour zoomer.</p>
  </div>;
}
