import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { createApiClient, ApiRequestError, canWriteSite } from '../lib/api';

describe('runInvestigation', () => {
  const api = createApiClient('http://test/api/v1');
  const mockIncident = {
    id: 'inc-1', site_id: 1, machine_id: 2, status: 'open', severity: 'high',
    symptom: 'short_shot_increase', started_at: '2025-01-01T00:00:00Z',
    created_at: '2025-01-01T00:00:00Z', data_cutoff: '2025-01-01T01:00:00Z',
  };
  const mockResponse = {
    incident: mockIncident,
    run_id: 'run-1',
    hypotheses: [{
      cause_code: 'low_barrel_temperature_zone_2',
      label: 'Température zone 2 trop basse',
      confidence: 0.87,
      supporting_evidence_ids: ['ev-1'],
      contradicting_evidence_ids: [],
      missing_data: [],
      next_check: 'inspect_barrel_zone_2_heating',
    }],
    evidence: [{
      id: 'ev-1', source_kind: 'cycle_aggregate', source_ref: 'ref-1',
      metric: 'scrap_rate', window: { start: '2025-01-01T00:00:00Z', end: '2025-01-01T01:00:00Z' },
      observation: { value: 0.346, unit: 'fraction' },
      baseline: { value: 0.028, unit: 'fraction' },
      delta: 0.318, supports: true,
    }],
  };

  beforeEach(() => {
    globalThis.fetch = vi.fn();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('utilise POST avec credentials include sur la bonne URL avec as_of encodé', async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true, status: 200,
      text: async () => JSON.stringify(mockResponse),
    });

    await api.runInvestigation('inc-1', '2025-01-01T00:00:00Z');

    expect(globalThis.fetch).toHaveBeenCalledTimes(1);
    const [url, opts] = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe('http://test/api/v1/incidents/inc-1/investigations?as_of=2025-01-01T00%3A00%3A00Z');
    expect(opts.method).toBe('POST');
    expect(opts.credentials).toBe('include');
    expect(opts.cache).toBe('no-store');
    expect(opts.headers).toBeUndefined();
    expect(opts.body).toBeUndefined();
  });

  it('n\'ajoute pas ?as_of quand le paramètre est absent', async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true, status: 200,
      text: async () => JSON.stringify(mockResponse),
    });

    await api.runInvestigation('inc-1');

    const [url, opts] = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe('http://test/api/v1/incidents/inc-1/investigations');
    expect(opts.method).toBe('POST');
    expect(opts.body).toBeUndefined();
  });

  it('mappe correctement les hypothèses et les preuves', async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true, status: 200,
      text: async () => JSON.stringify(mockResponse),
    });

    const result = await api.runInvestigation('inc-1');

    expect(result.incident.id).toBe('inc-1');
    expect(result.run_id).toBe('run-1');
    expect(result.hypotheses).toHaveLength(1);
    expect(result.hypotheses[0].cause_code).toBe('low_barrel_temperature_zone_2');
    expect(result.hypotheses[0].confidence).toBe(0.87);
    expect(result.hypotheses[0].supporting_evidence_ids).toEqual(['ev-1']);
    expect(result.evidence).toHaveLength(1);
    expect(result.evidence[0].metric).toBe('scrap_rate');
    expect(result.evidence[0].supports).toBe(true);
    expect(result.evidence[0].baseline).toEqual({ value: 0.028, unit: 'fraction' });
  });

  it('relit un run persisté sans relancer le moteur', async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true, status: 200,
      text: async () => JSON.stringify({ id: 'run-1', incident_id: 'inc-1', status: 'completed', data_cutoff: '2025-01-01T01:00:00Z', result: { hypotheses: mockResponse.hypotheses, evidence: mockResponse.evidence } }),
    });

    const result = await api.getInvestigation('run-1');
    expect(result).toMatchObject({ run_id: 'run-1', incident_id: 'inc-1', status: 'completed' });
    expect(result.hypotheses[0].cause_code).toBe('low_barrel_temperature_zone_2');
    expect(result.evidence[0].metric).toBe('scrap_rate');
    expect((globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0]).toBe('http://test/api/v1/investigations/run-1');
  });

  it('lance une erreur API exploitable avec code et message', async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: false, status: 400,
      text: async () => JSON.stringify({
        error: { code: 'bad_request', message: 'Paramètre as_of requis', details: {} },
      }),
    });

    try {
      await api.runInvestigation('inc-1');
      expect.unreachable('Should have thrown');
    } catch (error) {
      expect(error).toBeInstanceOf(ApiRequestError);
      const apiError = error as ApiRequestError;
      expect(apiError.status).toBe(400);
      expect(apiError.message).toBe('Paramètre as_of requis');
      expect(apiError.code).toBe('bad_request');
    }
  });
});

describe('scrap-risk model frontend client', () => {
  it('POSTe le contrat de features et retourne le score versionné', async () => {
    const api = createApiClient('http://test/api/v1');
    globalThis.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      status: 200,
      text: async () => JSON.stringify({ model_version: 'rebut-risk-logistic-v1', risk_probability: 0.08, predicted_scrap: false, threshold: 0.5 }),
    });

    const result = await api.predictScrapRisk({ site_id: 1, machine_erp_ref: '1003', previous_scrap_flag: 0, rolling_scrap_rate_20: 0.02 });
    const [url, opts] = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];

    expect(result.model_version).toBe('rebut-risk-logistic-v1');
    expect(url).toBe('http://test/api/v1/scrap-risk');
    expect(opts.method).toBe('POST');
    expect(opts.credentials).toBe('include');
    expect(JSON.parse(opts.body)).toMatchObject({ site_id: 1, machine_erp_ref: '1003', rolling_scrap_rate_20: 0.02 });
  });
});

describe('process-drift model frontend client', () => {
  it('POSTe les cycles bruts vers le contrat HDT et retourne la prédiction versionnée', async () => {
    const api = createApiClient('http://test/api/v1');
    globalThis.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      status: 200,
      text: async () => JSON.stringify({
        model_version: 'hdt-process-drift-iforest-v1',
        machine_erp_ref: '152',
        anomaly_score: 0.73,
        predicted_instability_next_20_cycles: true,
        threshold: 0.41,
        horizon_cycles: 20,
        signals: [{ feature: 'cycle_time_s_volatility_20', value: 0.48 }],
      }),
    });

    const cycles = [{ timestamp: '2025-02-12T01:00:00Z', machine_erp_ref: '152', cycle_time_s: 8.2 }];
    const result = await api.predictProcessDrift({ site_id: 1, cycles });
    const [url, opts] = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];

    expect(result).toMatchObject({ model_version: 'hdt-process-drift-iforest-v1', machine_erp_ref: '152', predicted_instability_next_20_cycles: true, horizon_cycles: 20 });
    expect(url).toBe('http://test/api/v1/process-drift');
    expect(opts.method).toBe('POST');
    expect(opts.credentials).toBe('include');
    expect(JSON.parse(opts.body)).toEqual({ site_id: 1, cycles });
  });
});

describe('cycles bruts frontend', () => {
  it('GETe les cycles bornés par to et limit et mappe les features process', async () => {
    const api = createApiClient('http://test/api/v1');
    globalThis.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      status: 200,
      text: async () => JSON.stringify([{
        timestamp: '2025-02-12T00:59:30Z',
        machine_erp_ref: '152',
        cycle_time_s: 30.2,
        dosing_time_s: 7.2,
        injection_time_s: 5.8,
        cooling_time_s: 12.4,
        cushion_mm: 4.3,
        switchover_position_mm: 18.2,
        switchover_pressure_bar: 620,
        peak_pressure_bar: 1380,
        clamp_force_kn: 450,
        mold_temperature_c: 62,
        barrel_temp_zone1_c: 208,
        barrel_temp_zone2_c: 220,
        barrel_temp_zone3_c: 224,
        oil_temperature_c: 42,
        energy_kwh: 0.42,
      }]),
    });

    const result = await api.getMachineCycles(2, '2025-02-12T01:00:00Z', 20);
    const [url, opts] = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe('http://test/api/v1/machines/2/cycles?to=2025-02-12T01%3A00%3A00Z&limit=20');
    expect(opts.method).toBe('GET');
    expect(result[0]).toMatchObject({ machine_erp_ref: '152', cycle_time_s: 30.2, barrel_temp_zone2_c: 220, energy_kwh: 0.42 });
  });
});

describe('session cookie frontend', () => {
  beforeEach(() => { globalThis.fetch = vi.fn(); });
  afterEach(() => { vi.restoreAllMocks(); });

  it('signale une session expirée sur toute réponse métier 401', async () => {
    const unauthorized = vi.fn();
    window.addEventListener('iddrv:unauthorized', unauthorized, { once: true });
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: false, status: 401,
      text: async () => JSON.stringify({ detail: 'session_revoked' }),
    });
    await expect(createApiClient('http://test/api/v1').getSites()).rejects.toBeInstanceOf(ApiRequestError);
    expect(unauthorized).toHaveBeenCalledTimes(1);
  });

  it('mappe la réponse cookie sans attendre de jeton navigateur', async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true, status: 200,
      text: async () => JSON.stringify({ user: { id: 'user-1', email: 'analyst@iddrv.local', display_name: 'Analyste', role: 'analyst', site_ids: [2], site_roles: { 2: 'viewer' } }, expires_at: '2026-07-14T00:00:00Z' }),
    });
    const result = await createApiClient('http://test/api/v1').login('analyst@iddrv.local', 'secret');
    expect(result.user).toMatchObject({ id: 'user-1', role: 'analyst', siteIds: [2], siteRoles: { 2: 'viewer' } });
    expect(result.expiresAt).toBe('2026-07-14T00:00:00Z');
    expect(canWriteSite(result.user, 2)).toBe(false);
    expect((globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0][1].credentials).toBe('include');
  });
});

describe('contrat du journal d’import', () => {
  beforeEach(() => { globalThis.fetch = vi.fn(); });
  afterEach(() => { vi.restoreAllMocks(); });

  it('mappe les jobs worker et expose clairement la quarantaine', async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true, status: 200,
      text: async () => JSON.stringify({ items: [{
        id: 'job-1', source_kind: 'quality', file_name: 'quality.csv', status: 'quarantined',
        attempt_count: 3, max_attempts: 3, last_error_code: 'parse_failed', last_error: 'Colonne absente',
        discovered_at: '2025-02-12T00:00:00Z', completed_at: '2025-02-12T01:00:00Z',
      }], next_cursor: null }),
    });
    const result = await createApiClient('http://test/api/v1').getImports();
    expect(result[0]).toMatchObject({ status: 'quarantined', sourceKind: 'quality', attemptCount: 3, maxAttempts: 3, errorCode: 'parse_failed', errorLog: 'Colonne absente', importedAt: '2025-02-12T01:00:00Z' });
  });

  it('normalise un profil workspace encore vide', async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true, status: 200,
      text: async () => JSON.stringify({ id: 'session-1', site_id: 2, name: 'Projet', status: 'collecting', files: [{ id: 'file-1', file_name: 'cycles.csv', source_kind: 'machines', size_bytes: 12, status: 'pending', profile: {} }], summary: {}, created_at: '2025-02-12T00:00:00Z', updated_at: '2025-02-12T00:00:00Z' }),
    });
    const result = await createApiClient('http://test/api/v1').getImportSession('session-1');
    expect(result.files[0].profile).toEqual({ columns: [], recognized: [], unknown: [], confidence: 0, message: undefined });
  });

  it('refuse un cycle de curseur plutôt que de livrer une liste tronquée', async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce({ ok: true, status: 200, text: async () => JSON.stringify({ items: [{ id: 'job-1', status: 'completed' }], next_cursor: 'page-2' }) })
      .mockResolvedValueOnce({ ok: true, status: 200, text: async () => JSON.stringify({ items: [{ id: 'job-2', status: 'completed' }], next_cursor: 'page-2' }) });
    await expect(createApiClient('http://test/api/v1').getImports()).rejects.toMatchObject({ code: 'pagination_cursor_cycle', status: 502 });
  });

  it('suit next_cursor au lieu de masquer les pages suivantes', async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce({ ok: true, status: 200, text: async () => JSON.stringify({ items: [{ id: 'job-1', status: 'completed' }], next_cursor: 'page-2' }) })
      .mockResolvedValueOnce({ ok: true, status: 200, text: async () => JSON.stringify({ items: [{ id: 'job-2', status: 'completed' }], next_cursor: null }) });
    const result = await createApiClient('http://test/api/v1').getImports();
    expect(result.map((item) => item.id)).toEqual(['job-1', 'job-2']);
    expect((globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[1][0]).toContain('cursor=page-2');
  });
});

describe('santé du service', () => {
  beforeEach(() => { globalThis.fetch = vi.fn(); });
  afterEach(() => { vi.restoreAllMocks(); });

  it('utilise /api/health sans masquer la route SPA /health', async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true, status: 200,
      text: async () => JSON.stringify({ status: 'ok', service: 'iddrv', database: 'ok' }),
    });
    const api = createApiClient('/api/v1');
    const health = await api.getHealth();
    expect((globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0]).toBe('/api/health');
    expect(health.database).toBe('ok');
  });
});

describe('adaptation stricte du contrat statut et layout', () => {
  it('préserve layout null, coordonnées zéro et champs rotation/display_order', async () => {
    const api = createApiClient('http://test/api/v1');
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true, status: 200,
      text: async () => JSON.stringify({ items: [
        { id: 2, site_id: 1, erp_ref: '152', name: 'Presse 152', layout: { x: 0, y: 0, z: 0, rotation_deg: 15, display_order: 2 } },
        { id: 3, site_id: 1, erp_ref: '153', name: 'Presse 153', layout: null },
      ] }),
    });

    const machines = await api.getMachines(1);
    expect(machines[0].layout).toMatchObject({ x: 0, y: 0, z: 0, rotationDeg: 15, displayOrder: 2 });
    expect(machines[1].layout).toBeNull();
  });

  it('associe chaque point de timeline à la valeur agrégée réellement présente', async () => {
    const api = createApiClient('http://test/api/v1');
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true, status: 200,
      text: async () => JSON.stringify({ items: [{ timestamp: '2025-02-12T01:00:00Z', scrap_rate: null, avg_zone2_temperature_c: 174.5 }] }),
    });

    const timeline = await api.getMachineTimeline(2, '2025-02-12T00:00:00Z', '2025-02-12T02:00:00Z');
    expect(timeline.points[0]).toMatchObject({ metric: 'barrel_temp_zone2_c', value: 174.5, avgZone2TemperatureC: 174.5, scrapRate: null });
  });

  it('préserve le code et le message des erreurs FastAPI structurées', async () => {
    const api = createApiClient('http://test/api/v1');
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: false, status: 422,
      text: async () => JSON.stringify({ detail: { code: 'insufficient_data', message: 'Fenêtre incomplète' } }),
    });

    await expect(api.runInvestigation('incident-1')).rejects.toMatchObject({ status: 422, code: 'insufficient_data', message: 'Fenêtre incomplète' });
  });

  it('mappe le payload statut plat sans inventer TRS ou cycle', async () => {
    const api = createApiClient('http://test/api/v1');
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true, status: 200,
      text: async () => JSON.stringify({ machine_id: 2, status: 'warning', as_of: '2026-07-13T01:00:00Z', last_cycle_at: '2025-02-12T01:00:00Z', freshness_s: 45, current_order_id: 'OF-2025-0012', cycle_count_24h: 1200, scrap_rate_24h: .346, data_quality_status: 'complete' }),
    });

    const status = await api.getMachineStatus(2, '2025-02-12T01:00:00Z');
    expect(status.metrics).toMatchObject({ currentOrderId: 'OF-2025-0012', scrapRate: .346, cycleCount24h: 1200 });
    expect(status.lastCycleAt).toBe('2025-02-12T01:00:00Z');
    expect(status.metrics?.trs).toBeUndefined();
    expect(status.metrics?.cycleTimeS).toBeUndefined();
  });
});
