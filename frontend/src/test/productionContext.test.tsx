import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ProductionContextPanel } from '../components/workshop/ProductionContextPanel';
import { createApiClient } from '../lib/api';

describe('contexte de production', () => {
  it('présente un OF une fois avec ses équipes, les inconnues et l’historique', () => {
    render(<ProductionContextPanel context={{ knownAt: '2026-09-05T09:00:00Z', importedAt: '2026-09-05T10:00:00Z', declarations: [{ id: 'd1', orderRef: 'OF-42', team: 'A', producedParts: 100, goodParts: 90, scrapParts: 10, status: 'reopened', reopenReason: '400 pièces requalifiées', history: [{ status: 'closed' }, { status: 'reopened' }] }, { id: 'd2', orderRef: 'OF-42', team: 'B', producedParts: 80, goodParts: 80, scrapParts: 0, status: 'closed', history: [] }], target: null, erpStatus: null, qualityStatus: 'unknown', coverageStatus: 'incomplete' }} />);
    expect(screen.getByText('OF-42')).toBeInTheDocument();
    expect(screen.getByText(/Équipe A/)).toBeInTheDocument();
    expect(screen.getByText(/Équipe B/)).toBeInTheDocument();
    expect(screen.getByText('Cible inconnue')).toBeInTheDocument();
    expect(screen.getByText('Statut ERP non fourni')).toBeInTheDocument();
    expect(screen.getByText('Historique incomplet')).toBeInTheDocument();
    expect(screen.getByText(/400 pièces requalifiées/)).toBeInTheDocument();
  });

  it('mappe le résumé API d’un OF vers ses équipes et son historique', async () => {
    const fetch = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({
      known_at: '2026-09-05T09:00:00Z',
      declarations: [{ id: 'd1', production_order_id: 'OF-42', shift_number: 1, good_parts: 90, produced_parts: 100, warnings: ['good_parts'] }, { id: 'd2', production_order_id: 'OF-42', shift_number: 2, good_parts: 80, produced_parts: 80, warnings: [] }],
      orders: [{ order_ref: 'OF-42', order_target_quantity: 500, order_status: 'reopened', good_parts_net: 170, remaining_quantity: null, status_history: [{ status: 'closed' }, { status: 'reopened' }], coverage: { complete: false, warnings: 1 } }],
    }), { status: 200, headers: { 'content-type': 'application/json' } }));
    try {
      const context = await createApiClient('/api/v1').getProductionContext(1, { from: '2026-09-05T00:00:00Z', to: '2026-09-05T10:00:00Z', knownAt: '2026-09-05T09:00:00Z' });
      render(<ProductionContextPanel context={context} />);
      expect(screen.getByText(/Cible 500/)).toBeInTheDocument();
      expect(screen.getByText('Statut ERP : Rouverte')).toBeInTheDocument();
      expect(screen.getByText(/Progression non certifiée/)).toBeInTheDocument();
    } finally { fetch.mockRestore(); }
  });
});
