import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { vi } from 'vitest';
import { AppTestShell } from '../App';
import { mockApiClient, type ApiClient, type Machine } from '../lib/api';
import { WorkshopPage } from '../pages/WorkshopPage';

function renderWorkshop(api: ApiClient) {
  return render(<AppTestShell api={api}><MemoryRouter initialEntries={['/sites/2/workshop']}><Routes><Route path="/sites/:siteId/workshop" element={<WorkshopPage />} /><Route path="/imports" element={<p>Import ERP</p>} /></Routes></MemoryRouter></AppTestShell>);
}

test('présente la checklist et ajoute une presse depuis un atelier vide', async () => {
  const user = userEvent.setup();
  const machines: Machine[] = [];
  const createMachine = vi.fn(async (siteId: number, input: NonNullable<Parameters<ApiClient['createMachine']>[1]>) => {
    const machine: Machine = { id: 7, siteId, name: input.name, workshopCode: input.workshop_code, erpRef: input.erp_ref, brand: input.brand, model: input.model, status: 'offline' };
    machines.push(machine);
    return machine;
  });
  const api: ApiClient = {
    ...mockApiClient,
    getSite: async () => ({ id: 2, name: 'Atelier vide', timezone: 'Europe/Paris' }),
    getMachines: async () => machines,
    getIncidents: async () => [],
    getCurrentUser: async () => ({ id: 'u1', email: 'supervisor@test', role: 'supervisor', siteIds: [2], siteRoles: { 2: 'supervisor' } }),
    createMachine,
  };
  renderWorkshop(api);

  expect(await screen.findByRole('heading', { name: 'Préparer cet atelier' })).toBeInTheDocument();
  expect(screen.getAllByRole('button', { name: 'Configurer la passerelle' })[0]).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Importer l’ERP' })).toBeInTheDocument();
  await user.click(screen.getAllByRole('button', { name: 'Ajouter une presse' })[0]);
  await user.type(screen.getByLabelText('Nom de la presse'), 'Presse 606');
  await user.type(screen.getByLabelText('Code atelier'), 'P-606');
  await user.click(screen.getByRole('button', { name: 'Ajouter la presse' }));
  await waitFor(() => expect(createMachine).toHaveBeenCalledWith(2, expect.objectContaining({ name: 'Presse 606', workshop_code: 'P-606', erp_ref: null, brand: null, model: null })));
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
});

test('un atelier équipé garde l’accès à la passerelle et permet d’associer une référence ERP', async () => {
  const user = userEvent.setup();
  const machine: Machine = { id: 8, siteId: 2, name: 'Presse sans ERP', workshopCode: 'P-608', erpRef: null, status: 'offline', lifecycleStatus: 'active' };
  const updateMachine = vi.fn(async (_machineId: number, input: NonNullable<Parameters<ApiClient['updateMachine']>[1]>) => ({ ...machine, erpRef: input.erp_ref ?? null }));
  const api: ApiClient = {
    ...mockApiClient,
    getSite: async () => ({ id: 2, name: 'Atelier équipé', timezone: 'Europe/Paris' }),
    getMachines: async () => [machine],
    getIncidents: async () => [],
    getCurrentUser: async () => ({ id: 'u1', email: 'supervisor@test', role: 'supervisor', siteIds: [2], siteRoles: { 2: 'supervisor' } }),
    updateMachine,
  };
  renderWorkshop(api);
  expect(await screen.findByRole('heading', { name: 'Catalogue des presses' })).toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: 'Configurer passerelle et mapping' }));
  expect(await screen.findByRole('heading', { name: 'Passerelle locale' })).toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: 'Modifier' }));
  await user.clear(screen.getByLabelText('Référence ERP (facultative)'));
  await user.type(screen.getByLabelText('Référence ERP (facultative)'), 'ERP-608');
  await user.click(screen.getByRole('button', { name: 'Enregistrer les modifications' }));
  await waitFor(() => expect(updateMachine).toHaveBeenCalledWith(8, expect.objectContaining({ erp_ref: 'ERP-608' })));
});

test('la checklist reste en lecture seule pour un viewer', async () => {
  const api: ApiClient = {
    ...mockApiClient,
    getSite: async () => ({ id: 2, name: 'Atelier', timezone: 'Europe/Paris' }),
    getMachines: async () => [],
    getIncidents: async () => [],
    getCurrentUser: async () => ({ id: 'u1', email: 'viewer@test', role: 'viewer', siteIds: [2], siteRoles: { 2: 'viewer' } }),
  };
  renderWorkshop(api);
  await screen.findByRole('heading', { name: 'Préparer cet atelier' });
  expect(screen.getAllByRole('button', { name: 'Ajouter une presse' })[0]).toBeDisabled();
  expect(screen.getByText(/pas sa configuration/i)).toBeInTheDocument();
});
