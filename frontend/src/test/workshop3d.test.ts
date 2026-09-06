import { describe, expect, test } from 'vitest';
import { machineLabelVisible, scenePosition, scenePositionFromWorkshop } from '../components/Workshop3D';
import { formatWorkshopDate } from '../components/WorkshopWorkspace';
import { resolveWorkshopLayouts, workshopLayoutSource, WORKSHOP_SIZE } from '../components/workshopLayout';

describe('placement du parc machine 2D', () => {
  test('normalise les petites coordonnées API dans le plan visible', () => {
    const layouts = resolveWorkshopLayouts([
      { id: 1, name: 'A', layout: { x: 0, y: 0 } },
      { id: 2, name: 'B', layout: { x: 1, y: 0 } },
      { id: 3, name: 'C', layout: { x: .5, y: 1 } },
    ]);
    expect(layouts.every(({ x, y }) => x >= 120 && x <= 700 && y >= 110 && y <= 320)).toBe(true);
    expect(new Set(layouts.map(({ x, y }) => `${x}:${y}`)).size).toBe(3);
  });

  test('utilise un placement de secours pour les coordonnées dupliquées', () => {
    const machines = [
      { id: 1, name: 'A', layout: { x: 0, y: 0 } },
      { id: 2, name: 'B', layout: { x: 0, y: 0 } },
    ];
    const layouts = resolveWorkshopLayouts(machines);
    expect(workshopLayoutSource(machines)).toBe('suggested');
    expect(new Set(layouts.map(({ x, y }) => `${x}:${y}`)).size).toBe(2);
  });

  test.each([7, 12, 50])('garde %i presses suggérées dans le plan', (machineCount) => {
    const layouts = resolveWorkshopLayouts(Array.from({ length: machineCount }, (_, index) => ({ id: index + 1, name: `Presse ${index + 1}` })));
    expect(layouts).toHaveLength(machineCount);
    expect(new Set(layouts.map(({ x, y }) => `${x}:${y}`)).size).toBe(machineCount);
    expect(layouts.every(({ x, y, width, height }) => x - width / 2 >= 0 && x + width / 2 <= WORKSHOP_SIZE.width && y - height / 2 >= 0 && y + height / 2 <= WORKSHOP_SIZE.height)).toBe(true);
  });

  test('centre un plan source réduit à une presse', () => {
    const [layout] = resolveWorkshopLayouts([{ id: 1, name: 'A', layout: { x: 12, y: 4 } }]);
    expect(layout.x).toBe(410);
    expect(layout.y).toBe(215);
  });

  test('centre un axe constant et conserve les proportions', () => {
    const horizontal = resolveWorkshopLayouts([
      { id: 1, name: 'A', layout: { x: 0, y: 3 } },
      { id: 2, name: 'B', layout: { x: 10, y: 3 } },
    ]);
    expect(horizontal[0].y).toBe(215);
    expect(horizontal[1].y).toBe(215);

    const proportional = resolveWorkshopLayouts([
      { id: 1, name: 'A', layout: { x: 0, y: 0 } },
      { id: 2, name: 'B', layout: { x: 10, y: 1 } },
    ]);
    const deltaX = proportional[1].x - proportional[0].x;
    const deltaY = proportional[1].y - proportional[0].y;
    expect(deltaX / deltaY).toBeCloseTo(10);
  });
});

describe('placement du parc machine 3D', () => {
  test('préserve les relations spatiales du plan 2D', () => {
    const layouts = resolveWorkshopLayouts([
      { id: 1, name: 'A', layout: { x: 0, y: 0 } },
      { id: 2, name: 'B', layout: { x: 2, y: 0 } },
      { id: 3, name: 'C', layout: { x: 0, y: 1 } },
    ]);
    const [a, b, c] = layouts.map(scenePositionFromWorkshop);
    expect(b[0]).toBeGreaterThan(a[0]);
    expect(c[1]).toBeLessThan(a[1]);
  });

  test('répartit les presses de part et d’autre de l’allée', () => {
    const positions = Array.from({ length: 6 }, (_, index) => scenePosition(index, 6));
    expect(positions.slice(0, 3).every(([, y]) => y < 0)).toBe(true);
    expect(positions.slice(3).every(([, y]) => y > 0)).toBe(true);
  });

  test('produit des positions distinctes et déterministes', () => {
    const positions = Array.from({ length: 7 }, (_, index) => scenePosition(index, 7));
    expect(new Set(positions.map(([x, y]) => `${x}:${y}`)).size).toBe(7);
    expect(scenePosition(2, 7)).toEqual(scenePosition(2, 7));
  });

  test('limite les repères sans masquer la sélection ni les anomalies', () => {
    expect(machineLabelVisible(false, 0, false)).toBe(false);
    expect(machineLabelVisible(false, 0, true)).toBe(true);
    expect(machineLabelVisible(true, 0, false)).toBe(true);
    expect(machineLabelVisible(false, 2, false)).toBe(true);
  });
});

describe('horodatage du poste Atelier', () => {
  test('utilise le fuseau annoncé par le site', () => {
    const timestamp = '2025-01-15T12:00:00Z';
    expect(formatWorkshopDate(timestamp, 'UTC')).toContain('12:00');
    expect(formatWorkshopDate(timestamp, 'Europe/Paris')).toContain('13:00');
    expect(formatWorkshopDate(timestamp)).toContain('12:00');
    expect(formatWorkshopDate(timestamp, 'Fuseau/Invalide')).toContain('12:00');
  });
});
