import type { KeyboardEvent } from 'react';
import type { Machine, MachineLayout } from '../lib/api';
import { machineStatusLabel, StatusBadge } from './Ui';

export const WORKSHOP_SIZE = { width: 820, height: 430 };

export function layoutForMachine(machine: Machine, index: number): MachineLayout {
  const fallback = { x: 105 + (index % 3) * 245, y: 108 + Math.floor(index / 3) * 175, width: 142, height: 88, rotation: 0 };
  const layout = machine.layout;
  return {
    x: layout?.x && layout.x > 0 ? layout.x : fallback.x,
    y: layout?.y && layout.y > 0 ? layout.y : fallback.y,
    width: layout?.width && layout.width > 0 ? layout.width : fallback.width,
    height: layout?.height && layout.height > 0 ? layout.height : fallback.height,
    rotation: layout?.rotation ?? 0,
  };
}

function statusColor(status?: string | null): string {
  return ({ running: '#28a98c', warning: '#e2a332', stopped: '#d46765', offline: '#8796a7' } as Record<string, string>)[status ?? 'offline'] ?? '#8796a7';
}

function activate(event: KeyboardEvent<SVGGElement>, callback: () => void) {
  if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); callback(); }
}

export function WorkshopMap({ machines, selectedMachineId, onSelect }: { machines: Machine[]; selectedMachineId?: number; onSelect: (machine: Machine) => void }) {
  return <div className="workshop-map-wrap">
    <svg className="workshop-map" viewBox={`0 0 ${WORKSHOP_SIZE.width} ${WORKSHOP_SIZE.height}`} role="img" aria-labelledby="workshop-map-title workshop-map-desc">
      <title id="workshop-map-title">Plan 2D de l’atelier</title>
      <desc id="workshop-map-desc">Chaque presse est sélectionnable au clavier avec Entrée ou Espace. La couleur et le libellé indiquent son état.</desc>
      <defs><pattern id="floor-grid" width="32" height="32" patternUnits="userSpaceOnUse"><path d="M 32 0 L 0 0 0 32" fill="none" stroke="#e4eaf0" strokeWidth="1" /></pattern></defs>
      <rect width={WORKSHOP_SIZE.width} height={WORKSHOP_SIZE.height} rx="14" fill="url(#floor-grid)" />
      <rect x="20" y="20" width="780" height="390" rx="11" fill="none" stroke="#cbd7e2" strokeDasharray="7 8" />
      <path d="M 30 300 H 790" stroke="#d5e0e9" strokeWidth="18" opacity=".45" /><path d="M 390 30 V 400" stroke="#d5e0e9" strokeWidth="18" opacity=".45" />
      <text x="38" y="50" fill="#72859a" fontSize="11" fontWeight="700" letterSpacing="1.4">ZONE PRESSES · VUE TOPO-DOWN</text>
      {machines.map((machine, index) => {
        const layout = layoutForMachine(machine, index);
        const width = layout.width ?? 142;
        const height = layout.height ?? 88;
        const selected = machine.id === selectedMachineId;
        const color = statusColor(machine.status);
        return <g key={machine.id} role="button" tabIndex={0} aria-label={`${machine.name}, ${machineStatusLabel(machine.status)}${selected ? ', sélectionnée' : ''}`} aria-pressed={selected} className={`machine-node ${selected ? 'selected' : ''}`} transform={`translate(${layout.x},${layout.y}) rotate(${layout.rotation ?? 0})`} onClick={() => onSelect(machine)} onKeyDown={(event) => activate(event, () => onSelect(machine))}>
          <rect x={-width / 2} y={-height / 2} width={width} height={height} rx="9" fill="#fff" stroke={selected ? '#0e7f88' : '#d5dee8'} strokeWidth={selected ? 3 : 1.5} />
          <rect x={-width / 2} y={-height / 2} width="7" height={height} rx="4" fill={color} />
          <circle cx={-width / 2 + 25} cy={-height / 2 + 24} r="8" fill={color} opacity=".18" /><circle cx={-width / 2 + 25} cy={-height / 2 + 24} r="4" fill={color} />
          <text x={-width / 2 + 42} y={-height / 2 + 29} fill="#1a3048" fontSize="13" fontWeight="700">{machine.name}</text>
          <text x={-width / 2 + 17} y="9" fill="#718298" fontSize="11">{machine.erpRef ? `ERP ${machine.erpRef}` : `ID ${machine.id}`}</text>
          <text x={-width / 2 + 17} y="28" fill={color} fontSize="11" fontWeight="600">{machineStatusLabel(machine.status)}</text>
          <text x={width / 2 - 14} y={height / 2 - 12} fill="#7d8da0" fontSize="10" textAnchor="end">{machine.metrics?.currentOrderId ?? '—'}</text>
        </g>;
      })}
    </svg>
    <div className="map-legend" aria-label="Légende des états"><StatusBadge value="running" label="En production" /><StatusBadge value="warning" label="À surveiller" /><StatusBadge value="stopped" label="Arrêtée" /><StatusBadge value="offline" label="Hors ligne" /></div>
  </div>;
}
