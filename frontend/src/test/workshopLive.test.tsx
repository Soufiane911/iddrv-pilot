import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi } from 'vitest';
import { AppTestShell } from '../App';
import { MachineSourceStatus } from '../components/workshop/MachineSourceStatus';
import { WorkshopTimeControls } from '../components/workshop/WorkshopTimeControls';
import { ProcessDriftPanel } from '../components/ProcessDriftPanel';
import { workshopSourceState } from '../components/WorkshopWorkspace';

describe('atelier live', () => {
  it('sépare les états de la source, des cycles, de l’ERP et du HDT', () => {
    render(<MachineSourceStatus sourceState="reachable" cycleState="waiting" erpState="pending" hdtState="building" />);
    expect(screen.getByText('Source joignable')).toBeInTheDocument();
    expect(screen.getByText('En attente de cycles')).toBeInTheDocument();
    expect(screen.getByText('Bilan ERP en attente')).toBeInTheDocument();
    expect(screen.getByText('Historique HDT en constitution')).toBeInTheDocument();
  });

  it('traite une collecte désactivée comme une source non connectée', () => {
    expect(workshopSourceState(true, true, 'disabled')).toBe('disconnected');
    expect(workshopSourceState(true, true, 'collecting')).toBe('reachable');
    expect(workshopSourceState(true, true, 'gap_detected')).toBe('interrupted');
  });

  it('rafraîchit le mode direct mais laisse le rejeu borné', () => {
    vi.useFakeTimers();
    const onRefresh = vi.fn();
    const { rerender } = render(<AppTestShell><WorkshopTimeControls mode="direct" selectedAt="2026-09-05T09:00:00Z" onModeChange={vi.fn()} onSelectedAtChange={vi.fn()} onRefresh={onRefresh} /></AppTestShell>);
    vi.advanceTimersByTime(2000);
    expect(onRefresh).toHaveBeenCalled();
    onRefresh.mockClear();
    rerender(<AppTestShell><WorkshopTimeControls mode="replay" selectedAt="2026-09-05T09:00:00Z" onModeChange={vi.fn()} onSelectedAtChange={vi.fn()} onRefresh={onRefresh} /></AppTestShell>);
    vi.advanceTimersByTime(4000);
    expect(onRefresh).not.toHaveBeenCalled();
    vi.useRealTimers();
  });

  it('ne lance aucune inférence lorsque le Direct n’a pas encore de score persistant', () => {
    const predictProcessDrift = vi.fn();
    render(<QueryClientProvider client={new QueryClient()}><ProcessDriftPanel api={{ predictProcessDrift }} siteId={1} readOnly cycles={[{ timestamp: '2026-09-05T09:00:00Z', machine_erp_ref: '606' }, { timestamp: '2026-09-05T09:01:00Z', machine_erp_ref: '606' }, { timestamp: '2026-09-05T09:02:00Z', machine_erp_ref: '606' }]} /></QueryClientProvider>);
    expect(screen.getByText('Score HDT en attente')).toBeInTheDocument();
    expect(predictProcessDrift).not.toHaveBeenCalled();
  });
});
