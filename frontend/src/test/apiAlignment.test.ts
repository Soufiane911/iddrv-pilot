import { afterEach, describe, expect, it, vi } from 'vitest';
import { createApiClient } from '../lib/api';

afterEach(() => vi.restoreAllMocks());

describe('API alignment mappings', () => {
  it('keeps lifecycle status separate from operational status', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ items: [{ id: 4, site_id: 2, name: 'Presse archivée', workshop_code: 'P-4', lifecycle_status: 'archived', status: 'offline' }], next_cursor: null }), { status: 200 }));
    const machine = (await createApiClient().getMachines(2))[0];
    expect(machine.lifecycleStatus).toBe('archived');
    expect(machine.status).toBe('offline');
  });

  it('enregistre une référence ERP par PATCH machine', async () => {
    const fetch = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ id: 8, site_id: 2, name: 'Presse 608', workshop_code: 'P-608', erp_ref: 'ERP-608' }), { status: 200 }));
    const machine = await createApiClient().updateMachine(8, { erp_ref: 'ERP-608' });
    expect(machine.erpRef).toBe('ERP-608');
    expect(fetch.mock.calls[0][0]).toMatch(/\/machines\/8$/);
    expect(fetch.mock.calls[0][1]?.method).toBe('PATCH');
    expect(JSON.parse(String(fetch.mock.calls[0][1]?.body))).toEqual({ erp_ref: 'ERP-608' });
  });

  it('reads existing site sources with GET', async () => {
    const fetch = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ items: [{ id: 'source-1', site_id: 2, name: 'Gateway', status: 'active' }] }), { status: 200 }));
    const sources = await createApiClient().getSources(2);
    expect(sources[0].id).toBe('source-1');
    expect(fetch.mock.calls[0][0]).toMatch(/\/sites\/2\/sources$/);
    expect(fetch.mock.calls[0][1]?.method ?? 'GET').toBe('GET');
  });

  it('mappe les cinq champs OF du payload réel backend sans inventer de totaux', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ site_id: 2, timezone: 'Europe/Paris', week_start: '2026-09-07', items: [{ id: 'slot', site_id: 2, machine_id: 4, work_order_id: 'order', order_number: '000123', starts_at: '2026-09-07T06:00:00Z', ends_at: '2026-09-07T08:00:00Z', erp_status: 'matched', produced_parts: 120, good_parts: 116, scrap_parts: 4, cycle_count: 20, order_total_produced_parts: 240, order_total_good_parts: 232, order_total_scrap_parts: 8, order_total_cycles: 40, erp_order_status: 'released' }] }), { status: 200 }));
    const slot = (await createApiClient().getPlanning(2, { week: '2026-W37' })).items[0];
    expect(slot.producedPartsErp).toBe(120);
    expect(slot.goodPartsErp).toBe(116);
    expect(slot.orderProducedPartsErp).toBe(240);
    expect(slot.orderGoodPartsErp).toBe(232);
    expect(slot.orderScrapPartsErp).toBe(8);
    expect(slot.orderCyclesErp).toBe(40);
    expect(slot.orderErpStatus).toBe('released');
  });
});
