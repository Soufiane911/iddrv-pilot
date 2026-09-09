import { afterEach, expect, it, vi } from 'vitest';
import { ApiRequestError, createApiClient } from '../lib/api';
import { replayError } from '../components/monitoring/Summary6Replay';

afterEach(() => vi.unstubAllGlobals());
it('preserves admission Retry-After from the actual HTTP response', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ detail: 'summary6_busy' }), { status: 429, headers: { 'Retry-After': '30' } })));
  const api = createApiClient('/api/v1');
  const error = await api.replaySummary6({ site_id: 7, expected_package_id: 'package', source: { kind: 'demo_dataset', dataset_id: 'source', lot_id: 'M1-R1-L15', through_cycle: 84 } }).catch(e => e);
  expect(error).toBeInstanceOf(ApiRequestError);
  expect(error.details.retryAfter).toBe('30');
  expect(replayError(error)).toContain('Réessayer après 30 (Retry-After)');
});
