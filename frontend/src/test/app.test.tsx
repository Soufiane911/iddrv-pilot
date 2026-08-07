import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { vi } from 'vitest';
import { App } from '../App';
import { ApiRequestError, mockApiClient } from '../lib/api';

// Disable 3D view in test environment to prevent WebGL context errors and test 2D layout
import.meta.env.VITE_ENABLE_3D = 'false';

// Session-redirect tests mount the whole App and wait for a full navigation
// cycle; give them a generous timeout so a loaded CI runner cannot flake them.
const NAV_TIMEOUT = 4000;

test('redirige une session absente vers la connexion au lieu d’afficher des sites indisponibles', async () => {
  window.history.pushState({}, '', '/overview');
  render(<App api={{ ...mockApiClient, getCurrentUser: async () => { throw new ApiRequestError(401, 'Session expirée.', 'session_revoked'); } }} />);
  expect(await screen.findByRole('heading', { name: /Reprendre la supervision/i }, { timeout: NAV_TIMEOUT })).toBeInTheDocument();
  expect(screen.queryByText(/Sites indisponibles/i)).not.toBeInTheDocument();
});

test('redirige immédiatement vers la connexion lorsqu’une requête signale une session expirée', async () => {
  window.history.pushState({}, '', '/overview');
  render(<App api={mockApiClient} />);
  expect(await screen.findByRole('heading', { name: /Vue d’ensemble/i, level: 2 }, { timeout: NAV_TIMEOUT })).toBeInTheDocument();
  act(() => window.dispatchEvent(new Event('iddrv:unauthorized')));
  expect(await screen.findByRole('heading', { name: /Reprendre la supervision/i }, { timeout: NAV_TIMEOUT })).toBeInTheDocument();
});

test('ouvre la vue d’ensemble comme accueil opérationnel', async () => {
  window.history.pushState({}, '', '/overview');
  render(<App api={mockApiClient} />);
  expect(await screen.findByRole('heading', { name: /Vue d’ensemble/i, level: 2 })).toBeInTheDocument();
  expect(screen.getByText(/Sites industriels/i)).toBeInTheDocument();
  expect(screen.getByRole('link', { name: /Atelier, Sites & machines/i })).toBeInTheDocument();
});

test('affiche le shell multi-site et le catalogue atelier', async () => {
  window.history.pushState({}, '', '/sites');
  render(<App api={mockApiClient} />);
  expect(await screen.findByText('IDDRV')).toBeInTheDocument();
  expect(await screen.findByRole('heading', { name: /Vos ateliers/i })).toBeInTheDocument();
  await waitFor(() => expect(screen.getByText('Usine Principale')).toBeInTheDocument());
  expect(screen.getByRole('button', { name: /Ouvrir l’atelier/i })).toBeInTheDocument();
});

test('ancre le replay sur les données source et filtre les signaux côté client', async () => {
  const getIncidents = vi.fn(mockApiClient.getIncidents);
  const getMachineQuality = vi.fn(mockApiClient.getMachineQuality);
  window.history.pushState({}, '', '/sites/1/workshop');
  render(<App api={{ ...mockApiClient, getIncidents, getMachineQuality }} />);
  await screen.findByRole('radiogroup', { name: /Plan 2D de l’atelier/i });
  expect(screen.getByRole('region', { name: /Poste de supervision de l’atelier/i })).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: /État des presses/i })).toBeInTheDocument();
  const summary = screen.getByRole('region', { name: /Résumé du parc/i });
  expect(within(summary).getByText(/^EN PRODUCTION$/i)).toBeInTheDocument();
  await waitFor(() => expect(getIncidents).toHaveBeenCalledWith({ siteId: 1 }));
  await waitFor(() => expect(getMachineQuality).toHaveBeenCalledWith(expect.any(Number), expect.any(String), expect.any(String)));
});

test('conserve un signal commencé avant la fenêtre lorsqu’il la recouvre encore', async () => {
  const incident = { ...(await mockApiClient.getIncidents())[0], machine_id: (await mockApiClient.getMachines(1))[0].id, started_at: '2025-02-11T20:00:00Z', ended_at: null, data_cutoff: '2025-02-12T02:00:00Z' };
  window.history.pushState({}, '', '/sites/1/workshop');
  render(<App api={{ ...mockApiClient, getIncidents: async () => [incident] }} />);
  const map = await screen.findByRole('radiogroup', { name: /Plan 2D de l’atelier/i });
  await waitFor(() => expect(within(map).getByRole('radio', { name: /Presse 151.*1 anomalie reconstruite/i })).toBeInTheDocument());
  expect(await screen.findByText(/Hausse des pièces incomplètes/i)).toBeInTheDocument();
});

test('masque un signal lorsque le replay dépasse son cutoff de données', async () => {
  const incident = { ...(await mockApiClient.getIncidents())[0], machine_id: (await mockApiClient.getMachines(1))[0].id, started_at: '2025-02-11T20:00:00Z', ended_at: null, data_cutoff: '2025-02-12T02:00:00Z' };
  window.history.pushState({}, '', '/sites/1/workshop');
  render(<App api={{
    ...mockApiClient,
    getSite: async () => ({ ...(await mockApiClient.getSite(1)), lastImportAt: '2025-02-12T04:00:00Z' }),
    getIncidents: async () => [incident],
    getMachineStatus: async (id, asOf) => ({ machineId: id, status: 'running', asOf: asOf ?? '2025-02-12T04:00:00Z', lastCycleAt: asOf ?? '2025-02-12T04:00:00Z', metrics: { cycleCount24h: 1200 } }),
    getMachineTimeline: async () => ({ from: '2025-02-12T00:00:00Z', to: '2025-02-12T04:00:00Z', points: [] }),
  }} />);
  await screen.findByRole('radiogroup', { name: /Plan 2D de l’atelier/i });
  expect(await screen.findByText(/Hausse des pièces incomplètes/i)).toBeInTheDocument();
  const replay = screen.getByLabelText(/Position dans la période historique/i);
  fireEvent.change(replay, { target: { value: '100' } });
  await waitFor(() => expect(screen.queryByText(/Hausse des pièces incomplètes/i)).not.toBeInTheDocument());
  expect(screen.getByText(/Aucune anomalie reconstruite à cet horodatage/i)).toBeInTheDocument();
});

test('alimente HDT avec les cycles bruts et jamais avec les points agrégés', async () => {
  const getMachineCycles = vi.fn(mockApiClient.getMachineCycles);
  const predictProcessDrift = vi.fn(mockApiClient.predictProcessDrift);
  window.history.pushState({}, '', '/sites/1/workshop');
  render(<App api={{
    ...mockApiClient,
    getMachineCycles,
    predictProcessDrift,
    getMachineTimeline: async () => ({ from: '2025-02-11T21:00:00Z', to: '2025-02-12T01:00:00Z', points: [{ timestamp: '2025-02-12T01:00:00Z', metric: 'scrap_rate', value: 0.99 }] }),
  }} />);
  await screen.findByRole('radiogroup', { name: /Plan 2D de l’atelier/i });
  await waitFor(() => expect(getMachineCycles).toHaveBeenCalledWith(1, expect.any(String), 20));
  await waitFor(() => expect(predictProcessDrift).toHaveBeenCalled());
  const input = predictProcessDrift.mock.calls[0][0];
  expect(input.cycles.length).toBeGreaterThan(0);
  expect(input.cycles[0]).toHaveProperty('barrel_temp_zone2_c');
  expect(input.cycles.some((cycle: Record<string, unknown>) => cycle.metric === 'scrap_rate')).toBe(false);
});

test('ancre la fenêtre sur le dernier cycle source plutôt que sur l’heure d’import', async () => {
  const getMachineTimeline = vi.fn(mockApiClient.getMachineTimeline);
  const sourceStatus = await mockApiClient.getMachineStatus(1, '2026-07-13T00:00:00Z');
  window.history.pushState({}, '', '/sites/1/workshop');
  render(<App api={{
    ...mockApiClient,
    getSite: async () => ({ ...(await mockApiClient.getSite(1)), lastImportAt: '2026-07-13T00:00:00Z' }),
    getIncidents: async () => [],
    getMachineStatus: async (id, asOf) => ({ ...sourceStatus, machineId: id, asOf: asOf ?? sourceStatus.asOf, lastCycleAt: '2025-02-12T02:00:00Z' }),
    getMachineTimeline,
  }} />);
  await screen.findByRole('radiogroup', { name: /Plan 2D de l’atelier/i });
  await waitFor(() => expect(getMachineTimeline).toHaveBeenCalledWith(expect.any(Number), expect.stringContaining('2025-02-11'), expect.stringContaining('2025-02-12')));
});

test('affiche les métriques réellement fournies par le contrat statut backend', async () => {
  window.history.pushState({}, '', '/sites/1/workshop');
  render(<App api={{
    ...mockApiClient,
    getIncidents: async () => [],
    getMachineStatus: async (id, asOf) => ({ machineId: id, status: 'running', asOf: asOf ?? '2025-02-12T02:00:00Z', lastCycleAt: asOf ?? '2025-02-12T02:00:00Z', metrics: { cycleCount24h: 1200, scrapRate: 0.03, currentOrderId: 'OF-1' } }),
  }} />);
  await screen.findByRole('radiogroup', { name: /Plan 2D de l’atelier/i });
  expect(await screen.findByText(/Cycles sur 24 h/i)).toBeInTheDocument();
  expect(await screen.findByText('Dernier cycle', { exact: true })).toBeInTheDocument();
});

test('synchronise la qualité avec la presse sélectionnée', async () => {
  const getMachineQuality = vi.fn(mockApiClient.getMachineQuality);
  window.history.pushState({}, '', '/sites/1/workshop');
  render(<App api={{ ...mockApiClient, getMachineQuality }} />);
  const map = await screen.findByRole('radiogroup', { name: /Plan 2D de l’atelier/i });
  expect((await screen.findAllByText('2,8 %')).length).toBeGreaterThan(0);
  fireEvent.click(within(map).getByRole('radio', { name: /Presse 152/i }));
  await waitFor(() => expect(screen.getAllByText('34,6 %').length).toBeGreaterThan(0));
  expect(getMachineQuality).toHaveBeenCalledWith(1, expect.any(String), expect.any(String));
  expect(getMachineQuality).toHaveBeenCalledWith(2, expect.any(String), expect.any(String));
});

test('distingue une fenêtre qualité vide d’une métrique calculée', async () => {
  window.history.pushState({}, '', '/sites/1/workshop');
  render(<App api={{ ...mockApiClient, getMachineQuality: async () => ({ total: 0, good: 0, scrap: 0, scrapRate: null }) }} />);
  await screen.findByRole('radiogroup', { name: /Plan 2D de l’atelier/i });
  expect(await screen.findByText(/Aucune observation qualité dans cette période/i)).toBeInTheDocument();
});

test('n’interprète pas une panne de statut comme un état hors ligne', async () => {
  window.history.pushState({}, '', '/sites/1/workshop');
  render(<App api={{ ...mockApiClient, getMachineStatus: async () => { throw new Error('statut indisponible'); } }} />);
  expect(await screen.findByText(/Statut historique indisponible pour une partie du parc/i)).toBeInTheDocument();
  expect(screen.getAllByText(/Statut inconnu/i).length).toBeGreaterThan(0);
});

test('écarte un dernier cycle postérieur à la borne demandée', async () => {
  window.history.pushState({}, '', '/sites/1/workshop');
  render(<App api={{
    ...mockApiClient,
    getMachineStatus: async (id, asOf) => asOf === '2025-02-12T01:00:00Z'
      ? { machineId: id, status: 'running', asOf, lastCycleAt: asOf, metrics: { cycleCount24h: 1200 } }
      : { machineId: id, status: 'running', asOf: asOf ?? '2025-02-12T00:00:00Z', lastCycleAt: '2030-01-01T00:00:00Z', metrics: { cycleCount24h: 1200 } },
  }} />);
  expect(await screen.findByText(/Réponse temporelle incohérente/i)).toBeInTheDocument();
  expect(screen.getAllByText(/Statut inconnu/i).length).toBeGreaterThan(0);
  expect(screen.queryByText(/2030/)).not.toBeInTheDocument();
});

test('refuse d’afficher un run appartenant à un autre incident', async () => {
  window.history.pushState({}, '', '/incidents/s001-demo?run=run-other');
  render(<App api={{ ...mockApiClient, getInvestigation: async () => ({ run_id: 'run-other', incident_id: 'another-incident', hypotheses: [{ cause_code: 'wrong', label: 'Hypothèse étrangère', confidence: 1, supporting_evidence_ids: [], contradicting_evidence_ids: [], missing_data: [] }], evidence: [] }) }} />);
  expect(await screen.findByText('Run incompatible')).toBeInTheDocument();
  expect(screen.queryByText('Hypothèse étrangère')).not.toBeInTheDocument();
});

test('reprend un workspace depuis son identifiant dans l’URL', async () => {
  const getImportSession = vi.fn(mockApiClient.getImportSession);
  window.history.pushState({}, '', '/workspace?session=session-1');
  render(<App api={{ ...mockApiClient, getImportSession }} />);
  expect(await screen.findByRole('heading', { name: /Déposer les sources/i })).toBeInTheDocument();
  expect(getImportSession).toHaveBeenCalledWith('session-1');
  expect(screen.getByText(/Session reprise par l’URL/i)).toBeInTheDocument();
});

test('ouvre le plan 2D et expose les presses au clavier', async () => {
  window.history.pushState({}, '', '/sites/1/workshop');
  render(<App api={mockApiClient} />);
  const map = await screen.findByRole('radiogroup', { name: /Plan 2D de l’atelier/i });
  const firstMachine = within(map).getByRole('radio', { name: /Presse 151/i });
  fireEvent.keyDown(firstMachine, { key: 'ArrowRight' });
  const secondMachine = within(map).getByRole('radio', { name: /Presse 152/i });
  expect(secondMachine).toHaveAttribute('aria-checked', 'true');
  fireEvent.keyDown(secondMachine, { key: 'ArrowDown' });
  expect(within(map).getByRole('radio', { name: /Presse 155/i })).toHaveAttribute('aria-checked', 'true');
  expect(screen.getByLabelText(/Position dans la période historique/i)).toHaveAttribute('aria-valuetext');
});
