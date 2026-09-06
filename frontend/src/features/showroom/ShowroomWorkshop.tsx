import { ArrowDownIcon } from '@phosphor-icons/react/ArrowDown';
import { ArrowLeftIcon } from '@phosphor-icons/react/ArrowLeft';
import { ArrowRightIcon } from '@phosphor-icons/react/ArrowRight';
import { ArrowUpIcon } from '@phosphor-icons/react/ArrowUp';
import { CaretRightIcon } from '@phosphor-icons/react/CaretRight';
import { CornersOutIcon } from '@phosphor-icons/react/CornersOut';
import { CrosshairIcon } from '@phosphor-icons/react/Crosshair';
import { MinusIcon } from '@phosphor-icons/react/Minus';
import { PathIcon } from '@phosphor-icons/react/Path';
import { PlusIcon } from '@phosphor-icons/react/Plus';
import { WarningIcon } from '@phosphor-icons/react/Warning';
import { useEffect, useMemo, useState, type CSSProperties, type MouseEvent } from 'react';
import type { Machine, MachineState } from '../../lib/api';
import { getMachineVisualState } from './showroomModel';

type DisplayState = 'stable' | 'watch' | 'incident' | 'stopped' | 'offline' | 'unknown';
export type ShowroomViewMode = 'iso' | '2d';

const stateLabels: Record<DisplayState, string> = {
  stable: 'En production',
  watch: 'À surveiller',
  incident: 'Incident détecté',
  stopped: 'Arrêtée',
  offline: 'Hors ligne',
  unknown: 'Statut inconnu',
};

const apiState: Record<MachineState, DisplayState> = {
  running: 'stable',
  warning: 'watch',
  stopped: 'stopped',
  offline: 'offline',
};

const mobileQuery = '(max-width: 780px)';

export interface ResolvedMachinePosition {
  left: number;
  top: number;
  rotation: number;
  source: 'api' | 'auto';
}

function finite(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

/**
 * Turns nullable, differently scaled database coordinates into stable scene
 * positions. Duplicate or incomplete coordinates intentionally use a local
 * grid so a small 0..3 seed can never stack every press on one point.
 */
export function resolveMachinePositions(machines: Machine[]): Map<number, ResolvedMachinePosition> {
  const ordered = [...machines].sort((a, b) => {
    const orderA = finite(a.layout?.displayOrder) ? a.layout!.displayOrder! : Number.POSITIVE_INFINITY;
    const orderB = finite(b.layout?.displayOrder) ? b.layout!.displayOrder! : Number.POSITIVE_INFINITY;
    return orderA - orderB || a.id - b.id;
  });
  const coordinateKeys = ordered.map((machine) => `${machine.layout?.x ?? 'none'}:${machine.layout?.y ?? 'none'}`);
  const canUseApiLayout = ordered.length > 0
    && ordered.every((machine) => finite(machine.layout?.x) && finite(machine.layout?.y))
    && new Set(coordinateKeys).size === ordered.length;
  const xs = canUseApiLayout ? ordered.map((machine) => machine.layout!.x as number) : [];
  const ys = canUseApiLayout ? ordered.map((machine) => machine.layout!.y as number) : [];
  const minX = canUseApiLayout ? Math.min(...xs) : 0;
  const maxX = canUseApiLayout ? Math.max(...xs) : 1;
  const minY = canUseApiLayout ? Math.min(...ys) : 0;
  const maxY = canUseApiLayout ? Math.max(...ys) : 1;
  const rangeX = Math.max(1, maxX - minX);
  const rangeY = Math.max(1, maxY - minY);
  const positions = new Map<number, ResolvedMachinePosition>();

  ordered.forEach((machine, index) => {
    if (canUseApiLayout) {
      positions.set(machine.id, {
        left: 16 + (((machine.layout!.x as number) - minX) / rangeX) * 68,
        top: 18 + (((machine.layout!.y as number) - minY) / rangeY) * 60,
        rotation: finite(machine.layout?.rotationDeg) ? machine.layout!.rotationDeg! : finite(machine.layout?.rotation) ? machine.layout!.rotation! : 0,
        source: 'api',
      });
      return;
    }
    const column = index % 3;
    const row = Math.floor(index / 3);
    positions.set(machine.id, {
      left: 18 + column * 32,
      top: 22 + row * 27,
      rotation: column === 1 ? -1 : column === 2 ? 1 : 0,
      source: 'auto',
    });
  });
  return positions;
}

function Icon({ name }: { name: 'center' | 'fit' | 'plus' | 'minus' | 'chevron' | 'route' }) {
  const icons = { center: CrosshairIcon, fit: CornersOutIcon, plus: PlusIcon, minus: MinusIcon, chevron: CaretRightIcon, route: PathIcon };
  const Glyph = icons[name];
  return <Glyph className="showroom-icon" size={20} aria-hidden="true" />;
}

function MachineSilhouette() {
  return <span className="machine-silhouette" aria-hidden="true"><i /><b /><em /></span>;
}

export function ShowroomWorkshop({
  machines,
  selectedMachineId,
  scenarioMachineId,
  scenarioFallback,
  viewMode,
  onViewModeChange,
  tourStepIndex,
  tourActive,
  onSelect,
}: {
  machines: Machine[];
  selectedMachineId?: number;
  scenarioMachineId?: number;
  scenarioFallback: boolean;
  viewMode: ShowroomViewMode;
  onViewModeChange: (mode: ShowroomViewMode) => void;
  tourStepIndex: number;
  tourActive: boolean;
  onSelect: (machine: Machine, trigger: HTMLElement) => void;
}) {
  const positions = useMemo(() => resolveMachinePositions(machines), [machines]);
  const layoutAvailable = machines.length > 0 && machines.every((machine) => finite(machine.layout?.x) && finite(machine.layout?.y));
  const [mobile, setMobile] = useState(() => window.matchMedia?.(mobileQuery).matches ?? false);
  const [camera, setCamera] = useState({ x: 0, y: 0, zoom: 1 });
  const initialCamera = { x: 0, y: 0, zoom: 1 };

  useEffect(() => {
    const query = window.matchMedia?.(mobileQuery);
    if (!query) return;
    const change = (event: MediaQueryListEvent) => {
      setMobile(event.matches);
      if (event.matches) onViewModeChange('2d');
    };
    query.addEventListener?.('change', change);
    return () => query.removeEventListener?.('change', change);
  }, [onViewModeChange]);

  useEffect(() => {
    if (!layoutAvailable && viewMode === 'iso') onViewModeChange('2d');
  }, [layoutAvailable, onViewModeChange, viewMode]);

  const displayState = (machine: Machine): DisplayState => {
    if (tourActive && scenarioMachineId !== undefined && machine.id === scenarioMachineId) {
      return getMachineVisualState(machine.id, tourStepIndex, scenarioMachineId);
    }
    return machine.status ? apiState[machine.status] : 'unknown';
  };

  const activate = (machine: Machine, event: MouseEvent<HTMLButtonElement>) => onSelect(machine, event.currentTarget);
  const recenter = () => setCamera(initialCamera);
  const fitWorkshop = () => setCamera({ x: 0, y: 0, zoom: layoutAvailable ? 1 : .92 });

  const machineButton = (machine: Machine) => {
    const state = displayState(machine);
    const position = positions.get(machine.id) ?? { left: 50, top: 50, rotation: 0, source: 'auto' as const };
    const style = {
      '--machine-left': `${position.left}%`,
      '--machine-top': `${position.top}%`,
      '--machine-rotation': `${position.rotation}deg`,
      '--machine-order': machines.indexOf(machine),
    } as CSSProperties;
    return <button
      key={machine.id}
      type="button"
      className={`showroom-machine-node state-${state}${selectedMachineId === machine.id ? ' selected' : ''}`}
      style={style}
      aria-pressed={selectedMachineId === machine.id}
      aria-label={`${machine.name}, ${stateLabels[state]}`}
      onClick={(event) => activate(machine, event)}
    >
      <MachineSilhouette />
      <span className="machine-node-code">{machine.erpRef ?? `ID ${machine.id}`}</span>
      <strong>{machine.name}</strong>
      <span className="machine-node-status"><span className="status-shape" aria-hidden="true" />{stateLabels[state]}</span>
      {scenarioMachineId === machine.id && (tourStepIndex >= 2 && tourActive) && <span className="incident-marker"><WarningIcon size={14} aria-hidden="true" /><span className="visually-hidden">Incident</span></span>}
    </button>;
  };

  return <section className="showroom-workshop" id="atelier-panel" aria-labelledby="showroom-workshop-title">
    <div className="showroom-section-heading">
      <div>
        <p className="showroom-kicker">Atelier reconstitué</p>
        <h2 id="showroom-workshop-title">Une vue commune, du signal à l’action</h2>
        <p className="showroom-section-meta">Plan spatial de démonstration · {machines.length} presses · données de catalogue</p>
      </div>
      <div className="showroom-legend" aria-label="Légende des états machine">
        <span className="legend-item legend-stable"><i aria-hidden="true" />En production</span>
        <span className="legend-item legend-watch"><i aria-hidden="true" />À surveiller</span>
        <span className="legend-item legend-incident"><i aria-hidden="true" />Incident</span>
        <span className="legend-item legend-offline"><i aria-hidden="true" />Hors ligne</span>
      </div>
    </div>
    {tourActive && <p className="showroom-scenario-state"><span className="status-shape" aria-hidden="true" />État scénarisé de démonstration · scénario S001 · horodatage partagé avec l’inspecteur</p>}
    {scenarioFallback && <p className="showroom-fallback" role="status"><strong>Fallback de démonstration.</strong> L’incident API ne résout pas de machine correspondante ; aucune preuve S001 n’est liée à cette sélection.</p>}
    <div className="showroom-viewbar">
      <div className="showroom-view-switch" role="group" aria-label="Mode de représentation">
        <button type="button" aria-pressed={viewMode === 'iso'} disabled={!layoutAvailable || mobile} onClick={() => onViewModeChange('iso')}>Vue isométrique</button>
        <button type="button" aria-pressed={viewMode === '2d'} onClick={() => onViewModeChange('2d')}>Plan technique 2D</button>
      </div>
      <div className="showroom-camera-actions" role="group" aria-label="Cadrage de l’atelier">
        <button type="button" aria-label="Recentrer l’atelier" title="Recentrer l’atelier" onClick={recenter}><Icon name="center" /><span>Recentrer</span></button>
        <button type="button" aria-label="Ajuster l’atelier" title="Ajuster l’atelier" onClick={fitWorkshop}><Icon name="fit" /><span>Ajuster</span></button>
        {viewMode === 'iso' && <><button type="button" aria-label="Zoom avant" title="Zoom avant" onClick={() => setCamera((value) => ({ ...value, zoom: Math.min(1.4, value.zoom + .1) }))}><Icon name="plus" /><span className="visually-hidden">Zoom avant</span></button><button type="button" aria-label="Zoom arrière" title="Zoom arrière" onClick={() => setCamera((value) => ({ ...value, zoom: Math.max(.8, value.zoom - .1) }))}><Icon name="minus" /><span className="visually-hidden">Zoom arrière</span></button></>}
      </div>
    </div>
    {(!layoutAvailable || !positions.size) && <p className="showroom-fallback" role="status"><strong>Plan spatial de secours actif.</strong> Le layout API est absent ou incomplet ; les presses sont placées selon un ordre déterministe, sans inventer de coordonnées source.</p>}
    <details className="showroom-camera-advanced">
      <summary>Déplacement clavier de la caméra</summary>
      <div className="camera-keyboard-controls" role="group" aria-label="Déplacement et zoom au clavier">
        <button type="button" aria-label="Déplacer à gauche" onClick={() => setCamera((value) => ({ ...value, x: value.x - 18 }))}><ArrowLeftIcon size={18} aria-hidden="true" /></button>
        <button type="button" aria-label="Déplacer vers le haut" onClick={() => setCamera((value) => ({ ...value, y: value.y - 18 }))}><ArrowUpIcon size={18} aria-hidden="true" /></button>
        <button type="button" aria-label="Déplacer vers le bas" onClick={() => setCamera((value) => ({ ...value, y: value.y + 18 }))}><ArrowDownIcon size={18} aria-hidden="true" /></button>
        <button type="button" aria-label="Déplacer à droite" onClick={() => setCamera((value) => ({ ...value, x: value.x + 18 }))}><ArrowRightIcon size={18} aria-hidden="true" /></button>
        <button type="button" aria-label="Réinitialiser la vue" onClick={recenter}>Réinitialiser</button>
      </div>
    </details>
    <div className={`showroom-scene scene-${viewMode}${mobile ? ' is-mobile' : ''}`} role="group" aria-label={viewMode === '2d' ? 'Plan technique spatial de l’atelier' : 'Vue isométrique accessible de l’atelier'}>
      <svg className="showroom-scene-backdrop" viewBox="0 0 1000 580" aria-hidden="true" focusable="false">
        <defs>
          <pattern id="showroom-plan-grid" width="36" height="36" patternUnits="userSpaceOnUse"><path d="M36 0H0V36" fill="none" stroke="#E6E8EA" strokeWidth="1" /></pattern>
          <marker id="flow-arrow" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto"><path d="M0 0 8 4 0 8Z" fill="#059669" /></marker>
        </defs>
        <rect width="1000" height="580" fill="url(#showroom-plan-grid)" />
        <rect x="22" y="22" width="956" height="536" rx="2" fill="none" stroke="#334155" strokeWidth="2" />
        <path d="M70 185H930M70 390H930M325 70V510M675 70V510" stroke="#FFFFFF" strokeWidth="52" opacity=".72" />
        <path d="M70 185H930M70 390H930M325 70V510M675 70V510" stroke="#E6E8EA" strokeWidth="2" strokeDasharray="10 9" />
        <path d="M95 185H285M355 185H635M705 185H905M95 390H285M355 390H635M705 390H905" stroke="#059669" strokeWidth="3" strokeDasharray="9 11" markerEnd="url(#flow-arrow)" />
        <g className="scene-zone-labels" fill="#334155" fontSize="13" fontWeight="700" letterSpacing="1.2"><text x="54" y="62">MATIÈRE</text><text x="368" y="62">INJECTION</text><text x="711" y="62">MAINTENANCE</text><text x="54" y="548">CONTRÔLE QUALITÉ</text></g>
        <g className="scene-wayfinding" fill="#64748B" fontSize="12"><text x="44" y="145">A01 · ALLÉE PRINCIPALE</text><text x="44" y="350">A02 · FLUX PIÉTON</text><text x="850" y="542">SORTIE →</text><text x="50" y="104">ENTRÉE →</text></g>
      </svg>
      <div className="showroom-scene-camera" style={{ transform: viewMode === 'iso' ? `translate(${camera.x}px, ${camera.y}px) scale(${camera.zoom})` : undefined }}>
        {machines.map(machineButton)}
      </div>
      <div className="scene-caption"><Icon name="route" /> Flux de circulation · repères de démonstration</div>
    </div>
    <details className="machine-list-disclosure">
      <summary>Machines de l’atelier <span>({machines.length})</span><Icon name="chevron" /></summary>
      <ul aria-label="Liste accessible des machines">
        {machines.map((machine) => {
          const state = displayState(machine);
          return <li key={machine.id}><button type="button" aria-pressed={selectedMachineId === machine.id} onClick={(event) => activate(machine, event)}><span><strong>{machine.name}</strong><small>ERP {machine.erpRef ?? 'non renseigné'}</small></span><span className={`list-state state-${state}`}><span className="status-shape" aria-hidden="true" />{stateLabels[state]}</span><Icon name="chevron" /></button></li>;
        })}
      </ul>
    </details>
  </section>;
}
