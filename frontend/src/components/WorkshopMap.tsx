import type { KeyboardEvent } from 'react';
import type { Machine } from '../lib/api';
import { machineStatusLabel, StatusBadge } from './Ui';
import { resolveWorkshopLayouts, WORKSHOP_SIZE, type WorkshopLayout } from './workshopLayout';

function statusColor(status?: string | null): string {
  return ({ running: 'var(--color-accent)', warning: 'var(--color-secondary)', stopped: 'var(--color-destructive)', offline: 'var(--color-primary)' } as Record<string, string>)[status ?? 'unknown'] ?? 'var(--color-muted-foreground)';
}

function focusRadio(event: KeyboardEvent<Element>, nextIndex: number) {
  const radios = event.currentTarget.closest('[role="radiogroup"]')?.querySelectorAll<HTMLElement>('[role="radio"]');
  window.setTimeout(() => radios?.[nextIndex]?.focus(), 0);
}

function spatialTarget(index: number, key: string, layouts: WorkshopLayout[]): number | undefined {
  const current = layouts[index];
  const candidates = layouts.flatMap((layout, candidateIndex) => {
    if (candidateIndex === index) return [];
    const dx = layout.x - current.x;
    const dy = layout.y - current.y;
    const horizontal = key === 'ArrowRight' || key === 'ArrowLeft';
    const primary = horizontal ? Math.abs(dx) : Math.abs(dy);
    const secondary = horizontal ? Math.abs(dy) : Math.abs(dx);
    const inDirection = key === 'ArrowRight' ? dx > 0 : key === 'ArrowLeft' ? dx < 0 : key === 'ArrowDown' ? dy > 0 : dy < 0;
    return inDirection ? [{ index: candidateIndex, score: primary + secondary * 2 }] : [];
  });
  candidates.sort((left, right) => left.score - right.score);
  return candidates[0]?.index;
}

function activateMap(event: KeyboardEvent<Element>, index: number, machines: Machine[], layouts: WorkshopLayout[], onSelect: (machine: Machine) => void) {
  if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onSelect(machines[index]); return; }
  if (!['ArrowRight', 'ArrowDown', 'ArrowLeft', 'ArrowUp'].includes(event.key)) return;
  event.preventDefault();
  const nextIndex = spatialTarget(index, event.key, layouts);
  if (nextIndex === undefined) return;
  onSelect(machines[nextIndex]);
  focusRadio(event, nextIndex);
}

function activateCompactList(event: KeyboardEvent<Element>, index: number, machines: Machine[], onSelect: (machine: Machine) => void) {
  if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onSelect(machines[index]); return; }
  if (!['ArrowRight', 'ArrowDown', 'ArrowLeft', 'ArrowUp'].includes(event.key)) return;
  event.preventDefault();
  const candidate = event.key === 'ArrowRight' && index % 2 === 0 ? index + 1
    : event.key === 'ArrowLeft' && index % 2 === 1 ? index - 1
      : event.key === 'ArrowDown' ? index + 2
        : event.key === 'ArrowUp' ? index - 2
          : index;
  if (candidate < 0 || candidate >= machines.length || candidate === index) return;
  onSelect(machines[candidate]);
  focusRadio(event, candidate);
}

export function WorkshopMap({ machines, selectedMachineId, signalCounts = {}, onSelect }: { machines: Machine[]; selectedMachineId?: number; signalCounts?: Record<number, number>; onSelect: (machine: Machine) => void }) {
  const layouts = resolveWorkshopLayouts(machines);
  return <div className="workshop-map-wrap">
    <svg className="workshop-map" viewBox={`0 0 ${WORKSHOP_SIZE.width} ${WORKSHOP_SIZE.height}`} role="radiogroup" aria-labelledby="workshop-map-title workshop-map-desc">
      <title id="workshop-map-title">Plan 2D de l’atelier</title>
      <desc id="workshop-map-desc">Chaque presse est sélectionnable avec Entrée ou Espace. Les flèches déplacent la sélection selon sa position sur le plan. La couleur et le libellé indiquent son état.</desc>
      <defs><pattern id="floor-grid" width="32" height="32" patternUnits="userSpaceOnUse"><path d="M 32 0 L 0 0 0 32" fill="none" stroke="var(--color-border)" strokeWidth="1" /></pattern></defs>
      <rect width={WORKSHOP_SIZE.width} height={WORKSHOP_SIZE.height} rx="2" fill="url(#floor-grid)" />
      <rect x="20" y="20" width="780" height="390" rx="2" fill="none" stroke="var(--color-border)" strokeDasharray="7 8" />
      <text x="38" y="50" fill="var(--color-muted-foreground)" fontSize="12" fontWeight="700" letterSpacing="1.4">ZONE PRESSES · VUE DE DESSUS</text>
      {machines.map((machine, index) => {
        const layout = layouts[index];
        const width = layout.width;
        const height = layout.height;
        const selected = machine.id === selectedMachineId;
        const color = statusColor(machine.status);
        const signalCount = signalCounts[machine.id] ?? 0;
        const signalLabel = signalCount > 0 ? `, ${signalCount} ${signalCount > 1 ? 'anomalies reconstruites' : 'anomalie reconstruite'}` : '';
        return <g key={machine.id} role="radio" tabIndex={selected ? 0 : -1} aria-label={`${machine.name}, ${machineStatusLabel(machine.status)}${signalLabel}${selected ? ', sélectionnée' : ''}`} aria-checked={selected} className={`machine-node ${selected ? 'selected' : ''}${signalCount > 0 ? ' has-signal' : ''}`} transform={`translate(${layout.x},${layout.y}) rotate(${layout.rotation})`} onClick={() => onSelect(machine)} onKeyDown={(event) => activateMap(event, index, machines, layouts, onSelect)}>
          <rect x={-width / 2} y={-height / 2} width={width} height={height} rx="2" fill="var(--color-card)" stroke={selected ? 'var(--color-accent)' : 'var(--color-border)'} strokeWidth={selected ? 3 : 1.5} />
          <rect x={-width / 2} y={-height / 2} width="7" height={height} rx="1" fill={color} />
          <circle cx={-width / 2 + 25} cy={-height / 2 + 24} r="8" fill={color} opacity=".18" /><circle cx={-width / 2 + 25} cy={-height / 2 + 24} r="4" fill={color} />
          <text x={-width / 2 + 42} y={-height / 2 + 29} fill="var(--color-foreground)" fontSize="13" fontWeight="700">{machine.name}</text>
          <text x={-width / 2 + 17} y="9" fill="var(--color-muted-foreground)" fontSize="12">{machine.erpRef ? `ERP ${machine.erpRef}` : `ID ${machine.id}`}</text>
          <text x={-width / 2 + 17} y="28" fill="var(--color-primary)" fontSize="12" fontWeight="600">{machineStatusLabel(machine.status)}</text>
          {signalCount > 0 ? <g className="machine-signal" transform={`translate(${width / 2 + 6},${-height / 2 + 14})`} aria-hidden="true"><circle r="13" /><text textAnchor="middle" dominantBaseline="central">{signalCount > 9 ? '9+' : signalCount}</text></g> : null}
        </g>;
      })}
    </svg>
    <p className="workshop-mobile-note">Liste compacte, ordre catalogue. Implantation non représentée.</p>
    <div className="workshop-mobile-list" role="radiogroup" aria-label="Presses de l’atelier en liste">
      {machines.map((machine, index) => {
        const signalCount = signalCounts[machine.id] ?? 0;
        return <button key={machine.id} type="button" role="radio" className={machine.id === selectedMachineId ? 'selected' : ''} tabIndex={machine.id === selectedMachineId ? 0 : -1} aria-checked={machine.id === selectedMachineId} aria-label={`${machine.name}, ${machineStatusLabel(machine.status)}${signalCount > 0 ? `, ${signalCount} ${signalCount > 1 ? 'anomalies reconstruites' : 'anomalie reconstruite'}` : ''}`} onClick={() => onSelect(machine)} onKeyDown={(event) => activateCompactList(event, index, machines, onSelect)}><span><strong>{machine.name}</strong><small>{machine.erpRef ? `ERP ${machine.erpRef}` : `ID ${machine.id}`}</small>{signalCount > 0 ? <small className="machine-mobile-signal">{signalCount} {signalCount > 1 ? 'anomalies' : 'anomalie'}</small> : null}</span><StatusBadge value={machine.status} /></button>;
      })}
    </div>
    <div className="map-legend" aria-label="Légende des états"><StatusBadge value="running" label="En production" /><StatusBadge value="warning" label="À surveiller" /><StatusBadge value="stopped" label="Arrêtée" /><StatusBadge value="offline" label="Hors ligne" /><StatusBadge value={undefined} label="Statut inconnu" /></div>
  </div>;
}
