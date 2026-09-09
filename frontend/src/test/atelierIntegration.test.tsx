import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { AppTestShell } from '../App';
import { createApiClient, type PlanningSlot } from '../lib/api';
import { ProductionPlanningGrid } from '../components/planning/ProductionPlanningGrid';

const slot: PlanningSlot = {
  id: 'slot-1', siteId: 1, allocationId: 'allocation-1', machineId: 10,
  machineName: 'Presse A', workOrderId: 'order-1', orderNumber: 'OF-1',
  startsAt: '2026-09-07T08:00:00Z', endsAt: '2026-09-07T10:00:00Z',
  status: 'planned', planningStatus: 'planned', collectionStatus: 'no_cycle',
  erpStatus: 'pending', rowVersion: 4, actualScrapCount: null,
  actualScrapRowVersion: 2, cyclesReceived: 0,
};

describe('contrat atelier-planning', () => {
  it('écrit le rebut sur POST avec le nom de champ et la version OF-presse', async () => {
    const fetch = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({
      site_id: 1, work_order_id: 'order-1', machine_id: 10, actual_scrap_count: 0, comment: null, row_version: 3,
    }), { status: 200, headers: { 'content-type': 'application/json' } }));
    const result = await createApiClient('/api/v1').updateWorkOrderScrap('order-1', {
      actual_scrap_count: 0, machine_id: 10, row_version: 2,
    });
    expect(result.actual_scrap_count).toBe(0);
    expect(fetch).toHaveBeenCalledWith('/api/v1/planning/work-orders/order-1/scrap', expect.objectContaining({
      method: 'POST', body: JSON.stringify({ actual_scrap_count: 0, machine_id: 10, row_version: 2 }),
    }));
    fetch.mockRestore();
  });

  it('sauvegarde Entrée, blur/Tab et annule Escape sans écrire une valeur invalide', async () => {
    const save = vi.fn();
    const user = userEvent.setup();
    render(<AppTestShell><ProductionPlanningGrid items={[slot]} timezone="UTC" canPlan onEdit={vi.fn()} onCancel={vi.fn()} onSaveScrap={save} /> </AppTestShell>);
    await user.click(screen.getByRole('button', { name: 'Modifier le rebut réel OF-1' }));
    const input = screen.getByRole('spinbutton', { name: 'Rebut réel OF-1' });
    await user.type(input, '0');
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(save).toHaveBeenCalledWith(slot, 0);

    await user.click(screen.getByRole('button', { name: 'Modifier le rebut réel OF-1' }));
    const second = screen.getByRole('spinbutton', { name: 'Rebut réel OF-1' });
    await user.clear(second);
    await user.type(second, '3');
    fireEvent.keyDown(second, { key: 'Escape' });
    expect(save).toHaveBeenCalledTimes(1);
  });
});
