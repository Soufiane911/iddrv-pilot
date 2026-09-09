import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { AppTestShell } from '../App';
import { mockApiClient, type ApiClient, type HdtControl } from '../lib/api';
import { WorkshopPage } from '../pages/WorkshopPage';

const stopped: HdtControl = { machineId: 8, desiredState: 'stopped', effectiveState: 'stopped', blockingReasons: [], modelProfile: null };
function fixture(): ApiClient {
  return {
    ...mockApiClient,
    getSite: async () => ({ id: 7, name: 'Atelier sept', timezone: 'UTC' }),
    getMachines: async () => [{ id: 8, siteId: 7, name: 'Presse sept', workshopCode: 'P7', lifecycleStatus: 'active' }],
    getCurrentUser: async () => ({ id: 'u', email: 's@test', role: 'supervisor', siteIds: [7], siteRoles: { 7: 'supervisor' } }),
    getHdtControl: vi.fn(async () => stopped),
    activateHdt: vi.fn(async () => ({ ...stopped, desiredState: 'active', effectiveState: 'blocked', blockingReasons: ['model_profile_not_enabled'] })),
    stopHdt: vi.fn(async () => stopped),
  };
}
function mount(api: ApiClient) {
  return render(<AppTestShell api={api}><MemoryRouter initialEntries={['/sites/7/workshop']}><Routes><Route path="/sites/:siteId/workshop" element={<WorkshopPage />} /></Routes></MemoryRouter></AppTestShell>);
}

describe('atelier réel sans replay implicite', () => {
  it('affiche un état HDT arrêté sans inventer de score', async () => {
    const api = fixture();
    mount(api);
    expect(await screen.findByText('Arrêté', { selector: 'b' })).toBeInTheDocument();
    expect(screen.queryByText(/Calculer le replay/i)).not.toBeInTheDocument();
  });

  it('envoie les actions HDT au contrat API et garde le statut retourné', async () => {
    const api = fixture();
    const user = userEvent.setup();
    mount(api);
    await screen.findByText('Arrêté', { selector: 'b' });
    await user.click(screen.getByRole('button', { name: 'Activer HDT' }));
    await waitFor(() => expect(api.activateHdt).toHaveBeenCalledWith(8));
    expect(await screen.findByText('Bloqué', { selector: 'b' })).toBeInTheDocument();
  });
});
