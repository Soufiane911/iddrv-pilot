import type { Machine } from '../lib/api';

export const WORKSHOP_SIZE = { width: 820, height: 430 } as const;

const SOURCE_BOUNDS = {
  left: 120,
  right: 700,
  top: 110,
  bottom: 320,
} as const;

const SUGGESTED_BOUNDS = {
  left: 58,
  right: 762,
  top: 92,
  bottom: 348,
} as const;

export interface WorkshopLayout {
  x: number;
  y: number;
  width: number;
  height: number;
  rotation: number;
}

export type WorkshopLayoutSource = 'source' | 'suggested';

function hasFiniteCoordinates(machine: Machine): boolean {
  return typeof machine.layout?.x === 'number'
    && Number.isFinite(machine.layout.x)
    && typeof machine.layout?.y === 'number'
    && Number.isFinite(machine.layout.y);
}

export function workshopLayoutSource(machines: Machine[]): WorkshopLayoutSource {
  if (machines.length === 0 || !machines.every(hasFiniteCoordinates)) return 'suggested';
  const coordinates = machines.map((machine) => `${machine.layout?.x}:${machine.layout?.y}`);
  return new Set(coordinates).size === machines.length ? 'source' : 'suggested';
}

function machineDimensions(machine: Machine): Pick<WorkshopLayout, 'width' | 'height' | 'rotation'> {
  return {
    width: typeof machine.layout?.width === 'number' && machine.layout.width > 0 ? machine.layout.width : 142,
    height: typeof machine.layout?.height === 'number' && machine.layout.height > 0 ? machine.layout.height : 88,
    rotation: typeof machine.layout?.rotationDeg === 'number'
      ? machine.layout.rotationDeg
      : machine.layout?.rotation ?? 0,
  };
}

function suggestedLayouts(machines: Machine[]): WorkshopLayout[] {
  if (machines.length === 0) return [];
  const usableWidth = SUGGESTED_BOUNDS.right - SUGGESTED_BOUNDS.left;
  const usableHeight = SUGGESTED_BOUNDS.bottom - SUGGESTED_BOUNDS.top;
  const aspectRatio = usableWidth / usableHeight;
  const columns = Math.max(1, Math.ceil(Math.sqrt(machines.length * aspectRatio)));
  const rows = Math.max(1, Math.ceil(machines.length / columns));
  const cellWidth = usableWidth / columns;
  const cellHeight = usableHeight / rows;

  return machines.map((machine, index) => {
    const dimensions = machineDimensions(machine);
    const column = index % columns;
    const row = Math.floor(index / columns);
    return {
      x: SUGGESTED_BOUNDS.left + cellWidth * (column + .5),
      y: SUGGESTED_BOUNDS.top + cellHeight * (row + .5),
      width: Math.min(dimensions.width, Math.max(48, cellWidth - 18)),
      height: Math.min(dimensions.height, Math.max(32, cellHeight - 18)),
      rotation: dimensions.rotation,
    };
  });
}

export function resolveWorkshopLayouts(machines: Machine[]): WorkshopLayout[] {
  if (workshopLayoutSource(machines) === 'suggested') return suggestedLayouts(machines);

  const xs = machines.map((machine) => machine.layout?.x as number);
  const ys = machines.map((machine) => machine.layout?.y as number);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const rangeX = maxX - minX;
  const rangeY = maxY - minY;
  const sourceWidth = SOURCE_BOUNDS.right - SOURCE_BOUNDS.left;
  const sourceHeight = SOURCE_BOUNDS.bottom - SOURCE_BOUNDS.top;
  const sourceCenterX = (SOURCE_BOUNDS.left + SOURCE_BOUNDS.right) / 2;
  const sourceCenterY = (SOURCE_BOUNDS.top + SOURCE_BOUNDS.bottom) / 2;
  const coordinateCenterX = (minX + maxX) / 2;
  const coordinateCenterY = (minY + maxY) / 2;
  const scaleCandidates = [
    rangeX > 0 ? sourceWidth / rangeX : Number.POSITIVE_INFINITY,
    rangeY > 0 ? sourceHeight / rangeY : Number.POSITIVE_INFINITY,
  ].filter(Number.isFinite);
  const scale = scaleCandidates.length > 0 ? Math.min(...scaleCandidates) : 1;

  return machines.map((machine) => ({
    ...machineDimensions(machine),
    x: sourceCenterX + (((machine.layout?.x as number) - coordinateCenterX) * scale),
    y: sourceCenterY + (((machine.layout?.y as number) - coordinateCenterY) * scale),
  }));
}
