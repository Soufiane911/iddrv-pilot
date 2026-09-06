import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import { App } from '../App';
import { createApiClient, mockApiClient } from '../lib/api';

const body = { base_url: 'http://machine.test', external_machine_id: '606', secret_ref: null, poll_interval_s: 1, enabled: false, mapping_profile: 'iddrv-cycle-v1' as const };

function setup(viewer = false) {
  const save = vi.fn().mockResolvedValue({ ...body, id: 'c1', site_id: 1, machine_id: 606, state: 'disabled' });
  const test = vi.fn().mockResolvedValue({ ok: true, state: 'reachable', source_state: 'unknown', oldest_available_at: '2026-09-04T00:00:00Z' });
  window.history.pushState({}, '', '/sites/1/workshop');
  render(<App api={{ ...mockApiClient,
    getMachines: async () => [{ id: 606, siteId: 1, erpRef: '606', name: 'Presse 606' }],
    getIncidents: async () => [],
    getMachineStatus: async id => ({ machineId: id, status: 'offline', asOf: '9999-12-31T23:59:59Z', lastCycleAt: null }),
    getCurrentUser: async () => ({ id: 'u', email: 'test@example.com', role: viewer ? 'viewer' : 'supervisor', siteIds: [1] }),
    getMachineConnection: async () => null, saveMachineConnection: save, testMachineConnection: test,
  }} />);
  return { save, test };
}

it('affiche une presse sans télémétrie et ouvre la connexion avec mesures inconnues', async () => {
  const { save, test } = setup();
  expect(await screen.findByRole('heading', { name: 'Presse 606' })).toBeInTheDocument();
  fireEvent.click(screen.getByText('Connexion de la presse'));
  fireEvent.change(await screen.findByLabelText('Adresse API'), { target: { value: body.base_url } });
  fireEvent.click(screen.getByRole('button', { name: 'Tester la connexion' }));
  expect(await screen.findByText(/API joignable/)).toBeInTheDocument();
  expect(screen.getByLabelText('Collecte active')).not.toBeChecked();
  expect(save).not.toHaveBeenCalled();
  expect(test).toHaveBeenCalledWith(606, body);
  expect(screen.getByText('Aucun cycle reçu')).toBeInTheDocument();
  expect(screen.queryByRole('slider')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Enregistrer la connexion' }));
  await waitFor(() => expect(save).toHaveBeenCalledWith(606, body));
});

it('réserve la configuration aux superviseurs et administrateurs', async () => {
  setup(true);
  fireEvent.click(await screen.findByText('Connexion de la presse'));
  expect(await screen.findByLabelText('Adresse API')).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Tester la connexion' })).toBeDisabled();
});

it('utilise les routes réelles et remonte les erreurs serveur', async () => {
  const fetch = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ detail: 'continuity_review_required' }), { status: 409 }));
  try {
    await expect(createApiClient().saveMachineConnection(606, body)).rejects.toThrow();
    expect(fetch.mock.calls[0][0]).toMatch(/\/machines\/606\/connection$/);
    expect(fetch.mock.calls[0][1]?.method).toBe('PUT');
  } finally { fetch.mockRestore(); }
});
