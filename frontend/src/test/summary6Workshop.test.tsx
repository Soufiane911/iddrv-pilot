import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Link, MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { AppTestShell } from '../App';
import { mockApiClient, type ApiClient, type Summary6Current } from '../lib/api';
import { WorkshopPage } from '../pages/WorkshopPage';

const current: Summary6Current = { selected_package_id: 'summary6-test', loaded_package_id: 'summary6-test', active_mode: 'summary6_replay', readiness: 'ready', replay_enabled: true, live_enabled: false, reasons: [] };
function fixture(runtime: () => Promise<Summary6Current>): ApiClient {
  return {
    ...mockApiClient,
    getSummary6Current: runtime,
    getSites: vi.fn(async () => [{ id: 7, name: 'Atelier sept', timezone: 'UTC' }]),
    getSite: async () => ({ id: 7, name: 'Atelier sept', timezone: 'UTC' }),
    getMachines: async () => [{ id: 8, siteId: 7, name: 'Presse sept', workshopCode: 'P7', lifecycleStatus: 'active' }],
    getIncidents: async () => [],
    getCurrentUser: async () => ({ id: 'u', email: 's@test', role: 'supervisor', siteIds: [7], siteRoles: { 7: 'supervisor' } }),
    getSummary6Datasets: vi.fn(async () => ({ dataset_id: 'source-contract', synthetic: true as const, lots: [{ lot_id: 'M1-R1-L15', count: 400 }] })),
    replaySummary6: vi.fn(),
    predictProcessDrift: vi.fn(),
    predictScrapRisk: vi.fn(),
  };
}
function mount(api: ApiClient) {
  return render(<AppTestShell api={api}><MemoryRouter initialEntries={['/sites/7/workshop']}><Routes><Route path="/sites/:siteId/workshop" element={<WorkshopPage />} /><Route path="/sites/:siteId/planning" element={<h2>Planning du site sept</h2>} /></Routes></MemoryRouter></AppTestShell>);
}
describe('vraie page atelier avec frontière scoring', () => {
  it('revalide le site URL et abandonne le lot précédent sans site de repli', async () => {
    const api = fixture(async () => current);
    api.getSites = async () => [{ id: 7, name: 'Sept', timezone: 'UTC' }, { id: 8, name: 'Huit', timezone: 'UTC' }];
    api.getSite = async id => ({ id, name: `Atelier ${id}`, timezone: 'UTC' });
    api.getMachines = async () => [];
    const user = userEvent.setup();
    render(<AppTestShell api={api}><MemoryRouter initialEntries={['/sites/7/workshop']}><Link to="/sites/8/workshop">Autre atelier</Link><Link to="/sites/99/workshop">Site interdit</Link><Routes><Route path="/sites/:siteId/workshop" element={<WorkshopPage />} /></Routes></MemoryRouter></AppTestShell>);
    await screen.findByRole('option', { name: 'M1-R1-L15' });
    await user.selectOptions(screen.getByLabelText('Lot synthétique'), 'M1-R1-L15');
    await user.click(screen.getByRole('link', { name: 'Autre atelier' }));
    await waitFor(() => expect(api.getSummary6Datasets).toHaveBeenCalledWith(8));
    expect(screen.getByLabelText('Lot synthétique')).toHaveValue('');
    await user.click(screen.getByRole('link', { name: 'Site interdit' }));
    await screen.findByText(/Site non autorisé/);
    expect(screen.queryByRole('button', { name: 'Calculer le replay' })).not.toBeInTheDocument();
    expect(api.getSummary6Datasets).not.toHaveBeenCalledWith(99);
    expect(api.getSummary6Datasets).not.toHaveBeenCalledWith(1);
    expect(api.predictProcessDrift).not.toHaveBeenCalled();
  });
  it.each(['ready', 'disabled', 'error'] as const)('conserve outils, plan 2D et navigation avec runtime %s', async mode => {
    const api = fixture(mode === 'error' ? async () => { throw new Error('503'); } : async () => mode === 'disabled' ? { ...current, active_mode: 'disabled', replay_enabled: false, readiness: 'not_ready' } : current);
    const user = userEvent.setup();
    mount(api);
    await screen.findByRole('heading', { name: 'Catalogue des presses' });
    expect(screen.getByRole('button', { name: 'Ajouter une presse' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Configurer passerelle et mapping' })).toBeInTheDocument();
    expect(screen.getByText('Plan 2D')).toBeInTheDocument();
    if (mode === 'ready') {
      await screen.findByRole('option', { name: 'M1-R1-L15' });
      expect(api.getSummary6Datasets).toHaveBeenCalledWith(7);
      expect(screen.queryByLabelText(/Site autorisé/)).not.toBeInTheDocument();
      expect(screen.getByText(/Site de l’atelier : Atelier sept/)).toBeInTheDocument();
    } else {
      await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Scoring indisponible'));
      expect(api.getSummary6Datasets).not.toHaveBeenCalled();
    }
    expect(api.predictProcessDrift).not.toHaveBeenCalled();
    expect(api.predictScrapRisk).not.toHaveBeenCalled();
    expect(api.replaySummary6).not.toHaveBeenCalled();
    await user.click(screen.getByRole('link', { name: 'Ouvrir le planning hebdomadaire' }));
    expect(await screen.findByRole('heading', { name: 'Planning du site sept' })).toBeInTheDocument();
  });
});
