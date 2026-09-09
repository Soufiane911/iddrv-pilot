import { render, screen, waitFor, within } from '@testing-library/react';
import { vi } from 'vitest';
import { App } from '../App';
import { ApiRequestError, mockApiClient } from '../lib/api';

import.meta.env.VITE_ENABLE_3D = 'false';
const NAV_TIMEOUT = 4000;

test('redirige une session absente vers la connexion', async () => {
  window.history.pushState({}, '', '/overview');
  render(<App api={{ ...mockApiClient, getCurrentUser: async () => { throw new ApiRequestError(401, 'Session expirée.', 'session_revoked'); } }} />);
  expect(await screen.findByRole('heading', { name: /Reprendre la supervision/i }, { timeout: NAV_TIMEOUT })).toBeInTheDocument();
  expect(screen.queryByText(/Sites indisponibles/i)).not.toBeInTheDocument();
});

test('redirige lorsqu’une requête signale une session expirée', async () => {
  window.history.pushState({}, '', '/overview');
  render(<App api={mockApiClient} />);
  expect(await screen.findByRole('heading', { name: /Vue d’ensemble/i, level: 2 }, { timeout: NAV_TIMEOUT })).toBeInTheDocument();
  window.dispatchEvent(new Event('iddrv:unauthorized'));
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

test('atelier vide: plan sans données fictives et aucune requête de replay ou de score', async () => {
  const getIncidents = vi.fn(async () => []);
  const getMachineStatus = vi.fn(mockApiClient.getMachineStatus);
  const getMachineTimeline = vi.fn(mockApiClient.getMachineTimeline);
  const getMachineCycles = vi.fn(mockApiClient.getMachineCycles);
  const getMachineQuality = vi.fn(mockApiClient.getMachineQuality);
  window.history.pushState({}, '', '/sites/1/workshop');
  render(<App api={{ ...mockApiClient, getMachines: async () => [], getIncidents, getMachineStatus, getMachineTimeline, getMachineCycles, getMachineQuality }} />);
  expect(await screen.findByRole('heading', { name: 'Préparer cet atelier' })).toBeInTheDocument();
  expect(screen.getByRole('radiogroup', { name: /Plan 2D de l’atelier/i })).toBeInTheDocument();
  expect(screen.getByText(/Aucune presse configurée/i)).toBeInTheDocument();
  expect(getIncidents).not.toHaveBeenCalled();
  expect(getMachineStatus).not.toHaveBeenCalled();
  expect(getMachineTimeline).not.toHaveBeenCalled();
  expect(getMachineCycles).not.toHaveBeenCalled();
  expect(getMachineQuality).not.toHaveBeenCalled();
});

test('atelier équipé garde le plan, la fiche de presse et ne lance pas de score implicite', async () => {
  const calls = {
    incidents: vi.fn(async () => []), status: vi.fn(mockApiClient.getMachineStatus), timeline: vi.fn(mockApiClient.getMachineTimeline), cycles: vi.fn(mockApiClient.getMachineCycles), quality: vi.fn(mockApiClient.getMachineQuality),
  };
  window.history.pushState({}, '', '/sites/1/workshop');
  render(<App api={{ ...mockApiClient, getIncidents: calls.incidents, getMachineStatus: calls.status, getMachineTimeline: calls.timeline, getMachineCycles: calls.cycles, getMachineQuality: calls.quality }} />);
  const map = await screen.findByRole('radiogroup', { name: /Plan 2D de l’atelier/i });
  expect(screen.getByRole('heading', { name: /Catalogue des presses/i })).toBeInTheDocument();
  expect(within(map).getByRole('radio', { name: /Presse 151/i })).toBeInTheDocument();
  expect(screen.queryByText(/Position dans la période historique/i)).not.toBeInTheDocument();
  expect(calls.incidents).not.toHaveBeenCalled();
  expect(calls.status).not.toHaveBeenCalled();
  expect(calls.timeline).not.toHaveBeenCalled();
  expect(calls.cycles).not.toHaveBeenCalled();
  expect(calls.quality).not.toHaveBeenCalled();
});

test('le plan 2D expose les presses au clavier', async () => {
  window.history.pushState({}, '', '/sites/1/workshop');
  render(<App api={mockApiClient} />);
  const map = await screen.findByRole('radiogroup', { name: /Plan 2D de l’atelier/i });
  const firstMachine = within(map).getByRole('radio', { name: /Presse 151/i });
  firstMachine.focus();
  firstMachine.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }));
  await waitFor(() => expect(within(map).getByRole('radio', { name: /Presse 152/i })).toHaveAttribute('aria-checked', 'true'));
});
