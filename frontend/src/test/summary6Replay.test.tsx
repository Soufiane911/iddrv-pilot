import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { mockApiClient, type Summary6Current } from '../lib/api';
import { RuntimeBoundary } from '../components/monitoring/RuntimeBoundary';

const api = { ...mockApiClient, getSummary6Current: vi.fn(), getSites: vi.fn(), getSummary6Datasets: vi.fn(), replaySummary6: vi.fn(), predictProcessDrift: vi.fn() };
vi.mock('../App', () => ({ useApi: () => api }));
const current: Summary6Current = { selected_package_id: 'summary6-test', loaded_package_id: 'summary6-test', active_mode: 'summary6_replay', readiness: 'ready', replay_enabled: true, live_enabled: false, reasons: [] };
function Legacy() { api.predictProcessDrift(); return <p>Legacy mounted</p>; }
function mount() { render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><RuntimeBoundary><Legacy /></RuntimeBoundary></QueryClientProvider>); }
beforeEach(() => {
  vi.clearAllMocks();
  api.getSummary6Current.mockResolvedValue(current);
  api.getSites.mockResolvedValue([{ id: 7, name: 'Site sept' }]);
  api.getSummary6Datasets.mockResolvedValue({ dataset_id: 'demo', synthetic: true, lots: [{ lot_id: 'M1-R1-L15', count: 400 }] });
  api.replaySummary6.mockResolvedValue({ package_id: 'summary6-test', site_id: 7, through_cycle: 84, input_count: 85, latest: { status: 'abstained', reason: 'anchor_out_of_guard', alert: null } });
});
async function calculate() {
  await screen.findByRole('option', { name: 'Site sept' });
  fireEvent.change(await screen.findByLabelText('Site autorisé'), { target: { value: '7' } });
  await screen.findByRole('option', { name: 'M1-R1-L15' });
  fireEvent.change(screen.getByLabelText('Lot synthétique'), { target: { value: 'M1-R1-L15' } });
  fireEvent.click(screen.getByRole('button', { name: 'Calculer le replay' }));
}
describe('Summary6 profile', () => {
  it('does not mount legacy or share its cache and preserves abstention', async () => {
    localStorage.setItem('iddrv:hdt-history', '[{"alert":true}]');
    mount(); await calculate();
    expect(await screen.findByText(/Abstention : anchor_out_of_guard/)).toBeInTheDocument();
    expect(api.predictProcessDrift).not.toHaveBeenCalled();
    expect(api.replaySummary6).toHaveBeenCalledWith({ site_id: 7, expected_package_id: 'summary6-test', source: { kind: 'demo_dataset', dataset_id: 'demo', lot_id: 'M1-R1-L15', through_cycle: 84 } });
    fireEvent.change(screen.getByLabelText(/Dernier compteur/), { target: { value: '59' } });
    expect(screen.queryByText(/Abstention :/)).not.toBeInTheDocument();
  });
  it('fails closed on current error', async () => {
    api.getSummary6Current.mockRejectedValue(new Error('503')); mount();
    expect(await screen.findByRole('alert')).toHaveTextContent('Aucun fallback');
    expect(api.predictProcessDrift).not.toHaveBeenCalled();
  });
  it('rejects mismatched identity without displaying stale scores', async () => {
    api.replaySummary6.mockResolvedValue({ package_id: 'other', site_id: 7, through_cycle: 84 }); mount(); await calculate();
    expect(await screen.findByRole('alert')).toHaveTextContent('Identité');
    expect(screen.queryByText(/Paquet réellement/)).not.toBeInTheDocument();
  });
  it('preserves explicit legacy rollback', async () => {
    api.getSummary6Current.mockResolvedValue({ ...current, active_mode: 'historical' }); mount();
    await waitFor(() => expect(api.predictProcessDrift).toHaveBeenCalled());
  });
});
