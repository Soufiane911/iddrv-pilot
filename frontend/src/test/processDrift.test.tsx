import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ProcessDriftPanel } from '../components/ProcessDriftPanel';
import type { ProcessDriftCycle, ProcessDriftPrediction } from '../lib/api';

function renderPanel(prediction: ProcessDriftPrediction | Error, cycles: ProcessDriftCycle[] | undefined = [
  { timestamp: '2025-02-12T01:00:00Z', machine_erp_ref: '152' },
  { timestamp: '2025-02-12T01:01:00Z', machine_erp_ref: '152' },
  { timestamp: '2025-02-12T01:02:00Z', machine_erp_ref: '152' },
]) {
  const api = { predictProcessDrift: vi.fn(async () => {
    if (prediction instanceof Error) throw prediction;
    return prediction;
  }) };
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={queryClient}><ProcessDriftPanel api={api} siteId={1} cycles={cycles} machineName="Presse 152" /></QueryClientProvider>);
  return api;
}

function renderPanelWithMissingCycles(prediction: ProcessDriftPrediction | Error) {
  const api = { predictProcessDrift: vi.fn(async () => {
    if (prediction instanceof Error) throw prediction;
    return prediction;
  }) };
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={queryClient}><ProcessDriftPanel api={api} siteId={1} cycles={undefined as unknown as ProcessDriftCycle[]} machineName="Presse 152" /></QueryClientProvider>);
  return api;
}

const normal: ProcessDriftPrediction = {
  model_version: 'hdt-process-drift-iforest-v1', machine_erp_ref: '152', anomaly_score: 0.18,
  predicted_instability_next_20_cycles: false, threshold: 0.41, horizon_cycles: 20,
  signals: [{ feature: 'cycle_time_s_volatility_20', volatility: 0.11 }],
};

const drift: ProcessDriftPrediction = {
  ...normal, anomaly_score: 0.73, predicted_instability_next_20_cycles: true,
};

describe('ProcessDriftPanel', () => {
  it('affiche l’absence de cycles sans appeler le modèle', () => {
    const api = renderPanel(normal, []);
    expect(screen.getByText('Historique process insuffisant')).toBeInTheDocument();
    expect(api.predictProcessDrift).not.toHaveBeenCalled();
  });

  it('refuse une fenêtre de un ou deux cycles sans appeler le modèle', () => {
    const api = renderPanel(normal, [
      { timestamp: '2025-02-12T01:00:00Z', machine_erp_ref: '152' },
      { timestamp: '2025-02-12T01:01:00Z', machine_erp_ref: '152' },
    ]);
    expect(screen.getByText('Historique process insuffisant')).toBeInTheDocument();
    expect(api.predictProcessDrift).not.toHaveBeenCalled();
  });

  it('traite une fenêtre de cycles absente comme indisponible', () => {
    const api = renderPanelWithMissingCycles(normal);
    expect(screen.getByText('Historique process insuffisant')).toBeInTheDocument();
    expect(api.predictProcessDrift).not.toHaveBeenCalled();
  });

  it('affiche un état normal et le disclaimer de décision', async () => {
    renderPanel(normal);
    expect(await screen.findByText('État normal')).toBeInTheDocument();
    expect(screen.getByText(/priorité d’inspection, pas une décision automatique/i)).toBeInTheDocument();
    expect(screen.getByText(/Aucune dérive détectée/i)).toBeInTheDocument();
  });

  it('affiche une dérive détectée avec le score et ses signaux', async () => {
    renderPanel(drift);
    expect(await screen.findByText('Dérive détectée')).toBeInTheDocument();
    expect(screen.getByText('0,73')).toBeInTheDocument();
    expect(screen.getByText(/cycle time s · variabilité 20 cycles/i)).toBeInTheDocument();
  });

  it('affiche une erreur récupérable', async () => {
    renderPanel(new Error('API HDT indisponible'));
    expect(await screen.findByText('Score HDT indisponible')).toBeInTheDocument();
    expect(screen.getByText('API HDT indisponible')).toBeInTheDocument();
  });
});
