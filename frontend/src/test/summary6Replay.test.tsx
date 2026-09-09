import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { ApiRequestError, mockApiClient, type Summary6Current } from '../lib/api';
import { RuntimeBoundary } from '../components/monitoring/RuntimeBoundary';

const api = { ...mockApiClient, getSummary6Current: vi.fn(), getSites: vi.fn(), getSummary6Datasets: vi.fn(), replaySummary6: vi.fn(), predictProcessDrift: vi.fn() };
vi.mock('../App', () => ({ useApi: () => api }));
const current: Summary6Current = { selected_package_id: 'summary6-test', loaded_package_id: 'summary6-test', active_mode: 'summary6_replay', readiness: 'ready', replay_enabled: true, live_enabled: false, reasons: [] };
function Legacy() { api.predictProcessDrift(); return <p>Legacy mounted</p>; }
function mount(client = new QueryClient({ defaultOptions: { queries: { retry: false } } })) { render(<QueryClientProvider client={client}><RuntimeBoundary><Legacy /></RuntimeBoundary></QueryClientProvider>); }
beforeEach(() => {
  vi.clearAllMocks();
  api.getSummary6Current.mockResolvedValue(current);
  api.getSites.mockResolvedValue([{ id: 7, name: 'Site sept' }]);
  api.getSummary6Datasets.mockResolvedValue({ dataset_id: 'demo', synthetic: true, lots: [{ lot_id: 'M1-R1-L15', count: 400 }] });
  api.replaySummary6.mockResolvedValue({ package_id: 'summary6-test', site_id: 7, through_cycle: 84, input_count: 85, latest: { status: 'abstained', reason: 'anchor_out_of_guard', alert: null } });
});
async function calculate() {
  await screen.findByRole('option', { name: 'Site sept' });
  fireEvent.change(await screen.findByLabelText(/Site autorisé/), { target: { value: '7' } });
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
  it('never mounts cached historical children before current confirmation', async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    client.setQueryData(['summary6', 'current'], { ...current, active_mode: 'historical' });
    let resolve!: (value: Summary6Current) => void;
    api.getSummary6Current.mockReturnValue(new Promise<Summary6Current>(r => { resolve = r; }));
    mount(client);
    expect(screen.getByRole('status')).toHaveTextContent('Vérification');
    expect(api.predictProcessDrift).not.toHaveBeenCalled();
    await act(async () => resolve(current));
    await screen.findByText(/SYNTHÉTIQUE REPLAY PAS LIVE/);
    expect(api.predictProcessDrift).not.toHaveBeenCalled();
  });
  it('fails closed on refetch failure with cached historical data', async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    client.setQueryData(['summary6', 'current'], { ...current, active_mode: 'historical' });
    api.getSummary6Current.mockRejectedValue(new Error('refetch failed'));
    mount(client);
    expect(await screen.findByRole('alert')).toHaveTextContent('refetch failed');
    expect(api.predictProcessDrift).not.toHaveBeenCalled();
    expect(screen.queryByText('Legacy mounted')).not.toBeInTheDocument();
  });
  it.each([403, 409, 503, 429])('renders replay HTTP %s without a historical fallback', async status => {
    api.replaySummary6.mockRejectedValue(new ApiRequestError(status, 'server', 'test', { retryAfter: '30' }));
    mount(); await calculate();
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent(({ 403: 'Accès refusé', 409: 'Le paquet a changé', 503: 'runtime non prêt', 429: 'Retry-After' })[status]!);
    expect(api.predictProcessDrift).not.toHaveBeenCalled();
  });
  it('does not offer calculation if readiness is false even when replay flag is true', async () => {
    api.getSummary6Current.mockResolvedValue({ ...current, readiness: 'not_ready' });
    mount(); await screen.findByRole('alert');
    expect(screen.queryByRole('button', { name: 'Calculer le replay' })).not.toBeInTheDocument();
    expect(api.getSummary6Datasets).not.toHaveBeenCalled();
  });
  it('resets lot and response on site change and partitions dataset cache by package', async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    api.getSites.mockResolvedValue([{ id: 7, name: 'Site sept' }, { id: 8, name: 'Site huit' }]);
    mount(client); await calculate();
    await screen.findByText(/Abstention/);
    fireEvent.change(screen.getByLabelText(/Site autorisé/), { target: { value: '8' } });
    await waitFor(() => expect(api.getSummary6Datasets).toHaveBeenCalledWith(8));
    expect(screen.queryByText(/Abstention/)).not.toBeInTheDocument();
    expect(screen.getByLabelText('Lot synthétique')).toHaveValue('');
    api.getSummary6Current.mockResolvedValue({ ...current, loaded_package_id: 'new-package' });
    await act(async () => { await client.invalidateQueries({ queryKey: ['summary6', 'current'] }); });
    // Runtime revalidation remounts the form, deliberately discarding prior site selection.
    fireEvent.change(await screen.findByLabelText(/Site autorisé/), { target: { value: '8' } });
    await waitFor(() => expect(client.getQueryData(['summary6', 8, 'new-package', 'datasets'])).toBeDefined());
    expect(client.getQueryData(['summary6', 7, 'summary6-test', 'datasets'])).toBeDefined();
    expect(screen.queryByText(/Abstention/)).not.toBeInTheDocument();
  });
  it('disables controls while pending and bounds the cutoff to 400 observations', async () => {
    api.replaySummary6.mockReturnValue(new Promise(() => {}));
    mount();
    await screen.findByRole('option', { name: 'Site sept' });
    fireEvent.change(screen.getByLabelText(/Site autorisé/), { target: { value: '7' } });
    await screen.findByRole('option', { name: 'M1-R1-L15' });
    fireEvent.change(screen.getByLabelText('Lot synthétique'), { target: { value: 'M1-R1-L15' } });
    fireEvent.change(screen.getByLabelText(/Dernier compteur/), { target: { value: '400' } });
    expect(screen.getByRole('button', { name: 'Calculer le replay' })).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/Dernier compteur/), { target: { value: '399' } });
    fireEvent.click(screen.getByRole('button', { name: 'Calculer le replay' }));
    expect(api.replaySummary6).toHaveBeenCalledWith(expect.objectContaining({ source: expect.objectContaining({ through_cycle: 399 }) }));
    expect(screen.getByLabelText('Lot synthétique')).toBeDisabled();
    expect(screen.getByLabelText(/Dernier compteur/)).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Calculer le replay' })).toBeDisabled();
  });
  it('preserves explicit legacy rollback', async () => {
    api.getSummary6Current.mockResolvedValue({ ...current, active_mode: 'historical' }); mount();
    await waitFor(() => expect(api.predictProcessDrift).toHaveBeenCalled());
  });
});
