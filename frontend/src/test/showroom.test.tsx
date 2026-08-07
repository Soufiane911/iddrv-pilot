import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, test, vi } from 'vitest';
import { App } from '../App';
import { mockApiClient, type ApiClient } from '../lib/api';
import { resolveMachinePositions } from '../features/showroom/ShowroomWorkshop';
import { calculateImpactEstimate, getMachineVisualState, guidedTourSteps, SHOWROOM_COST_ASSUMPTIONS } from '../features/showroom/showroomModel';

const showroomApi: ApiClient = {
  ...mockApiClient,
  getMachines: async () => [
    { id: 2, siteId: 1, erpRef: '152', name: 'Presse 152', status: 'running', asOf: '2025-02-12T01:00:00Z', freshnessS: 45, metrics: { trs: .78, scrapRate: .346, cycleTimeS: 31.4, currentOrderId: 'OF-2025-0012' }, layout: { x: 0, y: 0, rotationDeg: 0, displayOrder: 1 } },
    { id: 3, siteId: 1, erpRef: '153', name: 'Presse 153', status: 'running', layout: { x: 1, y: 0, rotationDeg: 0, displayOrder: 2 } },
    { id: 4, siteId: 1, erpRef: '154', name: 'Presse 154', status: 'offline', layout: null },
  ],
  getIncidents: async () => [{ ...(await mockApiClient.getIncidents())[0], machine_id: 2, machine_erp_ref: '152' }],
  getMachineStatus: async (machineId, asOf) => ({ machineId, status: machineId === 2 ? 'running' : 'offline', asOf: asOf ?? '2025-02-12T01:00:00Z', freshnessS: 45, metrics: machineId === 2 ? { trs: .78, scrapRate: .346, cycleTimeS: 31.4, currentOrderId: 'OF-2025-0012' } : {} }),
};

const originalMatchMedia = window.matchMedia;
afterEach(() => { window.matchMedia = originalMatchMedia; document.body.style.overflow = ''; });

function renderShowroom(path = '/showroom', api = showroomApi) {
  window.history.pushState({}, '', path);
  return render(<App api={api} />);
}

describe('modèle showroom', () => {
  test('conserve les sept étapes et ne hardcode pas une machine S001', () => {
    expect(guidedTourSteps).toHaveLength(7);
    expect(guidedTourSteps.every((step) => step.scenarioId === 'S001')).toBe(true);
    expect(getMachineVisualState(2, 2, 2)).toBe('watch');
    expect(getMachineVisualState(2, 3, 2)).toBe('incident');
    expect(getMachineVisualState(3, 6, 2)).toBe('stable');
    expect(getMachineVisualState(2, 6)).toBe('stable');
  });

  test('calcule les coûts fictifs sans les présenter comme des gains', () => {
    const estimate = calculateImpactEstimate(SHOWROOM_COST_ASSUMPTIONS);
    expect(estimate.total).toBe(405);
    expect(estimate.disclaimer).toMatch(/coûts fictifs/i);
  });

  test('produit un placement déterministe sans superposition pour layout null, zéros et doublons', () => {
    const positions = resolveMachinePositions([
      { id: 1, name: 'A', layout: { x: 0, y: 0 } },
      { id: 2, name: 'B', layout: { x: 0, y: 0 } },
      { id: 3, name: 'C', layout: null },
      { id: 4, name: 'D' },
    ]);
    expect(positions.size).toBe(4);
    expect(new Set([...positions.values()].map((position) => `${position.left}:${position.top}`)).size).toBe(4);
    expect([...positions.values()].every((position) => position.source === 'auto')).toBe(true);
  });
});

describe('showroom industriel', () => {
  test('affiche le site courant, la scène 2D et la presse issue de l’incident API', async () => {
    renderShowroom();
    expect(await screen.findByRole('heading', { name: /du signal machine à la preuve exploitable/i })).toBeInTheDocument();
    expect(screen.getByText('Données fictives')).toBeInTheDocument();
    const scene = await screen.findByRole('group', { name: /plan technique spatial/i });
    expect(within(scene).getByRole('button', { name: /Presse 152.*En production/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Presse 152' })).toBeInTheDocument();
    expect(screen.getByText('OF-2025-0012')).toBeInTheDocument();
  });

  test('ne lie pas les preuves S001 à une autre machine', async () => {
    renderShowroom();
    const other = within(await screen.findByRole('group', { name: /plan technique spatial/i })).getByRole('button', { name: /Presse 153.*En production/i });
    fireEvent.click(other);
    expect(await screen.findByText(/Aucune preuve S001 liée à cette machine/i)).toBeInTheDocument();
    expect(screen.queryByText('Température zone 2 trop basse')).not.toBeInTheDocument();
  });

  test('recalibre la visite sur la machine du scénario après une exploration libre', async () => {
    renderShowroom();
    const scene = await screen.findByRole('group', { name: /plan technique spatial/i });
    fireEvent.click(within(scene).getByRole('button', { name: /Presse 153.*En production/i }));
    expect(await screen.findByRole('heading', { name: 'Presse 153' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /démarrer la visite/i }));
    expect(await screen.findByRole('heading', { name: 'Presse 152' })).toBeInTheDocument();
  });

  test('ouvre les sections secondaires à la demande et expose une alternative tabulaire', async () => {
    renderShowroom();
    const evidence = await screen.findByText('Preuves observées');
    expect(evidence.closest('details')).not.toHaveAttribute('open');
    fireEvent.click(evidence);
    expect(await screen.findByText('Température zone 2')).toBeInTheDocument();
    const signals = screen.getByText('Signaux synchronisés');
    fireEvent.click(signals);
    expect(screen.getByRole('table', { name: /traces fictives/i })).toBeInTheDocument();
  });

  test('guide les sept étapes manuellement avec pause et progression visible', async () => {
    renderShowroom();
    await screen.findByRole('group', { name: /plan technique spatial/i });
    fireEvent.click(screen.getByRole('button', { name: /démarrer la visite/i }));
    expect(screen.getByText(/Étape 1 sur 7/i)).toBeInTheDocument();
    expect(screen.queryByText(/Parcours manuel, sans auto-avancement/i)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /mettre en pause/i }));
    expect(screen.getByRole('button', { name: /reprendre la visite/i })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /reprendre la visite/i }));
    fireEvent.click(screen.getByRole('button', { name: /étape suivante/i }));
    expect(screen.getByText(/Étape 2 sur 7/i)).toBeInTheDocument();
  });

  test('masque les preuves S001 avant la fenêtre de l’incident', async () => {
    const incident = (await showroomApi.getIncidents())[0];
    const api: ApiClient = { ...showroomApi, getIncidents: async (filters) => filters?.to ? [] : [incident] };
    renderShowroom('/showroom', api);
    await screen.findByRole('group', { name: /plan technique spatial/i });
    fireEvent.click(screen.getByRole('button', { name: /démarrer la visite/i }));
    expect(await screen.findByRole('heading', { name: /Aucune preuve liée à cet instant/i })).toBeInTheDocument();
    expect(screen.queryByText('Température zone 2 trop basse')).not.toBeInTheDocument();
  });

  test('signale une panne des incidents historiques sans conclure à une absence de preuve', async () => {
    const api: ApiClient = { ...showroomApi, getIncidents: async (filters) => { if (filters?.to) throw new Error('historique indisponible'); return showroomApi.getIncidents(filters); } };
    renderShowroom('/showroom', api);
    await screen.findByRole('group', { name: /plan technique spatial/i });
    fireEvent.click(screen.getByRole('button', { name: /démarrer la visite/i }));
    expect(await screen.findByRole('heading', { name: /Preuves historiques indisponibles/i })).toBeInTheDocument();
    expect(screen.getByText(/Incidents historiques indisponibles · aucune absence de preuve n’est déduite/i)).toBeInTheDocument();
  });

  test('affiche un statut inconnu au lieu de déduire un état hors ligne', async () => {
    const machines = await showroomApi.getMachines(1);
    const api: ApiClient = { ...showroomApi, getMachines: async () => machines.map((machine) => machine.erpRef === '152' ? { ...machine, status: null } : machine), getMachineStatus: async () => { throw new Error('statut indisponible'); } };
    renderShowroom('/showroom', api);
    const map = await screen.findByRole('group', { name: /plan technique spatial/i });
    expect(within(map).getByRole('button', { name: /Presse 152.*Statut inconnu/i })).toBeInTheDocument();
    expect(screen.getAllByText('Statut inconnu').length).toBeGreaterThan(0);
  });

  test('filtre les incidents avec la même fenêtre temporelle que le replay', async () => {
    const getIncidents = vi.fn(showroomApi.getIncidents);
    renderShowroom('/showroom', { ...showroomApi, getIncidents });
    await screen.findByRole('group', { name: /plan technique spatial/i });
    fireEvent.click(screen.getByRole('button', { name: /démarrer la visite/i }));
    await waitFor(() => expect(getIncidents).toHaveBeenCalledWith(expect.objectContaining({ from: expect.any(String), to: expect.any(String) })));
  });

  test('conserve les états partiels, anciens et sans replay', async () => {
    const api: ApiClient = { ...showroomApi, getMachines: async () => [{ id: 4, siteId: 1, erpRef: '154', name: 'Presse 154', status: 'offline', freshnessS: 9999, metrics: {}, layout: null }], getIncidents: async () => [], getMachineStatus: async () => { throw new Error('statut indisponible'); } };
    renderShowroom('/showroom', api);
    expect(await screen.findByText(/Plan spatial de secours actif/i)).toBeInTheDocument();
    expect(screen.getByText(/Couverture partielle/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Données anciennes/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/Replay indisponible/i)).toBeInTheDocument();
  });

  test('affiche une seule entrée nav active selon le hash', async () => {
    renderShowroom('/showroom#donnees');
    await screen.findByText(/Données présentées/i);
    const active = document.querySelectorAll('.nav-link.active');
    expect(active).toHaveLength(1);
    expect(active[0]).toHaveTextContent('Démonstration');
    expect(active[0]).toHaveAttribute('aria-current', 'page');
  });

  test('ouvre une feuille mobile avec scrim, verrouillage, Escape et restitution du focus', async () => {
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({ matches: query.includes('780px'), media: query, onchange: null, addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: () => true }));
    renderShowroom();
    const machine = within(await screen.findByRole('group', { name: /plan technique spatial/i })).getByRole('button', { name: /Presse 152.*En production/i });
    fireEvent.click(machine);
    expect(await screen.findByRole('dialog', { name: /Détails de Presse 152/i })).toHaveAttribute('aria-modal', 'true');
    expect(screen.getByRole('button', { name: /Fermer les détails de la machine/i })).toBeInTheDocument();
    expect(document.body.style.overflow).toBe('hidden');
    expect(document.querySelector('.showroom-scrim')).toBeInTheDocument();
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    await waitFor(() => expect(machine).toHaveFocus());
  });

  test('récupère après une erreur API', async () => {
    const api: ApiClient = { ...showroomApi, getSites: async () => { throw new Error('Service indisponible'); } };
    renderShowroom('/showroom', api);
    expect(await screen.findByRole('alert')).toHaveTextContent('Service indisponible');
    expect(screen.getByRole('button', { name: /réessayer/i })).toBeInTheDocument();
  });
});
