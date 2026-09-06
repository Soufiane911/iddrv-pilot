import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { AppTestShell } from '../App';
import { mockApiClient, type ApiClient, type Site } from '../lib/api';
import { SitesPage } from '../pages/SitesPage';

function renderSites(api: ApiClient) {
  return render(
    <AppTestShell api={api}>
      <MemoryRouter initialEntries={['/sites']}>
        <Routes><Route path="/sites" element={<SitesPage />} /></Routes>
      </MemoryRouter>
    </AppTestShell>,
  );
}

test('crée un site vide depuis le catalogue', async () => {
  const user = userEvent.setup();
  const sites: Site[] = [{ id: 1, name: 'Usine', timezone: 'Europe/Paris', status: 'online' }];
  const api: ApiClient = {
    ...mockApiClient,
    getSites: async () => sites,
    getCurrentUser: async () => ({ id: 'u1', email: 'supervisor@test', role: 'supervisor', siteIds: [1], siteRoles: { 1: 'supervisor' } }),
    createSite: async (input) => { const site = { id: 2, name: input.name, timezone: input.timezone, status: 'offline' as const }; sites.push(site); return site; },
  };
  renderSites(api);
  await user.click(await screen.findByRole('button', { name: 'Nouveau site' }));
  await user.type(screen.getByLabelText('Nom du site'), 'Atelier Lyon');
  await user.click(screen.getByRole('button', { name: 'Créer le site' }));
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  expect(await screen.findByText('Atelier Lyon')).toBeInTheDocument();
});

test('demande le nom exact avant une suppression administrateur', async () => {
  const user = userEvent.setup();
  const api: ApiClient = {
    ...mockApiClient,
    getSites: async () => [{ id: 1, name: 'Usine', timezone: 'Europe/Paris', status: 'online' }],
    getCurrentUser: async () => ({ id: 'u1', email: 'admin@test', role: 'admin', siteIds: [1], siteRoles: { 1: 'admin' } }),
    deleteSite: async () => undefined,
  };
  renderSites(api);
  await user.click(await screen.findByRole('button', { name: 'Supprimer' }));
  const submit = screen.getByRole('button', { name: 'Supprimer définitivement' });
  expect(submit).toBeDisabled();
  await user.type(screen.getByLabelText(/nom du site pour confirmer/i), 'Usine');
  expect(submit).toBeEnabled();
});

test('envoie l’ERP facultatif après la création du site', async () => {
  const user = userEvent.setup();
  const calls: string[] = [];
  const api: ApiClient = {
    ...mockApiClient,
    getSites: async () => [{ id: 1, name: 'Usine', timezone: 'Europe/Paris', status: 'online' }],
    getCurrentUser: async () => ({ id: 'u1', email: 'supervisor@test', role: 'supervisor', siteIds: [1], siteRoles: { 1: 'supervisor' } }),
    createSite: async (input) => { calls.push('create'); return { id: 2, name: input.name, timezone: input.timezone, status: 'offline' as const }; },
    uploadERP: async (siteId) => { calls.push(`upload:${siteId}`); return { id: 'erp-1', site_id: siteId, original_name: 'atelier.xlsx', state: 'uploaded', preview_version: 0 }; },
  };
  renderSites(api);
  await user.click(await screen.findByRole('button', { name: 'Nouveau site' }));
  await user.type(screen.getByLabelText('Nom du site'), 'Atelier ERP');
  await user.upload(screen.getByLabelText(/ERP initial/i), new File(['data'], 'atelier.xlsx', { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' }));
  await user.click(screen.getByRole('button', { name: 'Créer le site' }));
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  expect(calls).toEqual(['create', 'upload:2']);
});
