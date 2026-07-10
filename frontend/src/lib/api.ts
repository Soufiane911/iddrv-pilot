/**
 * Frontend boundary for the IDDRV HTTP API.
 *
 * The UI never reads the scenario files directly.  This module owns the wire
 * format and keeps the rest of the application independent from fetch.
 */

export type HealthStatus = 'ok' | 'degraded' | 'unknown';
export type MachineState = 'running' | 'warning' | 'stopped' | 'offline';
export type IncidentStatus = 'open' | 'reviewed' | 'closed';
export type IncidentSeverity = 'low' | 'medium' | 'high' | 'critical';

export interface Health {
  status: HealthStatus;
  service?: string;
  version?: string;
  database?: 'ok' | 'unavailable';
  checkedAt?: string;
  message?: string;
}

export interface Site {
  id: number;
  name: string;
  timezone?: string;
  status?: 'online' | 'degraded' | 'offline';
  machineCount?: number;
  openIncidentCount?: number;
  lastImportAt?: string | null;
}

export interface MachineMetrics {
  trs?: number | null;
  oee?: number | null;
  scrapRate?: number | null;
  cycleTimeS?: number | null;
  goodParts?: number | null;
  scrapParts?: number | null;
  currentOrderId?: string | null;
}

export interface MachineLayout {
  x: number;
  y: number;
  rotation?: number;
  width?: number;
  height?: number;
}

export interface Machine {
  id: number;
  siteId?: number | null;
  lineId?: number | null;
  erpRef?: string | null;
  name: string;
  brand?: string | null;
  model?: string | null;
  status?: MachineState | null;
  asOf?: string | null;
  freshnessS?: number | null;
  metrics?: MachineMetrics;
  layout?: MachineLayout;
}

export interface MachineStatus {
  machineId: number;
  status: MachineState;
  asOf: string;
  freshnessS?: number | null;
  metrics?: MachineMetrics;
}

export interface TimelinePoint {
  timestamp: string;
  metric?: string;
  value?: number | null;
  status?: MachineState | string | null;
  label?: string | null;
}

export interface MachineTimeline {
  points: TimelinePoint[];
  from?: string;
  to?: string;
}

export interface QualitySummary {
  total?: number | null;
  good?: number | null;
  scrap?: number | null;
  scrapRate?: number | null;
  defects?: Array<{ type: string; count: number }>;
}

export interface Incident {
  id: string;
  site_id: number;
  machine_id: number;
  machine_erp_ref?: string | null;
  production_order_id?: string | null;
  status: IncidentStatus;
  severity: IncidentSeverity;
  symptom: string;
  defect_type?: string | null;
  started_at: string;
  ended_at?: string | null;
  created_at: string;
  data_cutoff: string;
  confidence?: 'low' | 'medium' | 'high' | null;
}

export interface Evidence {
  id: string;
  source_kind: string;
  source_ref: string;
  metric: string;
  window: { start?: string; end?: string };
  observation: Record<string, unknown>;
  baseline?: Record<string, unknown> | null;
  delta?: number | null;
  supports: boolean;
  excerpt?: string | null;
}

export interface Hypothesis {
  cause_code: string;
  label: string;
  confidence: number;
  supporting_evidence_ids: string[];
  contradicting_evidence_ids: string[];
  missing_data: unknown[];
  next_check?: string | null;
}

export interface Investigation {
  incident: Incident;
  run_id?: string | null;
  hypotheses: Hypothesis[];
  evidence: Evidence[];
}

export interface Feedback {
  id: string;
  incident_id: string;
  verdict: string;
  comment?: string | null;
}

export interface ImportPassport {
  id: string;
  fileName?: string;
  parserType?: string;
  status: 'pending' | 'completed' | 'failed';
  importedAt?: string | null;
  rowCountTotal?: number;
  rowCountAccepted?: number;
  rowCountRejected?: number;
  errorLog?: string | null;
}

export interface LoginResponse {
  accessToken?: string;
  user?: { id: string; email: string; role?: string };
}

export interface ApiErrorPayload {
  code: string;
  message: string;
  details?: Record<string, unknown>;
  request_id?: string;
}

export class ApiRequestError extends Error {
  status: number;
  code: string;
  details: Record<string, unknown>;

  constructor(status: number, message: string, code = 'api_error', details: Record<string, unknown> = {}) {
    super(message);
    this.name = 'ApiRequestError';
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export interface ApiClient {
  getHealth(): Promise<Health>;
  getSites(): Promise<Site[]>;
  getSite(siteId: number): Promise<Site>;
  getMachines(siteId: number): Promise<Machine[]>;
  getMachine(machineId: number): Promise<Machine>;
  getMachineStatus(machineId: number, asOf?: string): Promise<MachineStatus>;
  getMachineTimeline(machineId: number, from?: string, to?: string): Promise<MachineTimeline>;
  getMachineQuality(machineId: number, from?: string, to?: string): Promise<QualitySummary>;
  getMachineDiagnostics(machineId: number, asOf?: string): Promise<Incident[]>;
  getIncidents(filters?: { siteId?: number; machineId?: number; from?: string; to?: string; status?: IncidentStatus }): Promise<Incident[]>;
  getIncident(incidentId: string): Promise<Incident>;
  getEvidence(incidentId: string): Promise<Evidence[]>;
  runInvestigation(incidentId: string, asOf?: string): Promise<Investigation>;
  submitFeedback(incidentId: string, verdict: string, comment?: string): Promise<Feedback>;
  getImports(): Promise<ImportPassport[]>;
  login(email: string, password: string): Promise<LoginResponse>;
}

type RequestOptions = { method?: string; body?: unknown; signal?: AbortSignal };

function normaliseBaseUrl(value: string): string {
  return value.replace(/\/$/, '');
}

function listPayload<T>(payload: unknown): T[] {
  if (Array.isArray(payload)) return payload as T[];
  if (payload && typeof payload === 'object') {
    const value = payload as { items?: unknown; data?: unknown; results?: unknown };
    if (Array.isArray(value.items)) return value.items as T[];
    if (Array.isArray(value.data)) return value.data as T[];
    if (Array.isArray(value.results)) return value.results as T[];
  }
  return [];
}

function pick<T extends Record<string, unknown>>(record: T, ...keys: string[]): unknown {
  for (const key of keys) {
    if (record[key] !== undefined && record[key] !== null) return record[key];
  }
  return undefined;
}

function numberOrNull(value: unknown): number | null | undefined {
  if (value === null) return null;
  if (value === undefined || value === '') return undefined;
  const result = Number(value);
  return Number.isFinite(result) ? result : undefined;
}

function mapSite(value: unknown): Site {
  const record = (value ?? {}) as Record<string, unknown>;
  return {
    id: Number(record.id),
    name: String(record.name ?? record.label ?? `Site ${record.id ?? ''}`).trim(),
    timezone: String(record.timezone ?? 'UTC'),
    status: record.status as Site['status'],
    machineCount: numberOrNull(pick(record, 'machineCount', 'machine_count')) ?? undefined,
    openIncidentCount: numberOrNull(pick(record, 'openIncidentCount', 'open_incident_count')) ?? undefined,
    lastImportAt: (pick(record, 'lastImportAt', 'last_import_at') as string | null | undefined) ?? null,
  };
}

function mapMachine(value: unknown): Machine {
  const record = (value ?? {}) as Record<string, unknown>;
  const metrics = (pick(record, 'metrics') ?? {}) as Record<string, unknown>;
  const layout = (pick(record, 'layout') ?? {}) as Record<string, unknown>;
  return {
    id: Number(record.id),
    siteId: numberOrNull(pick(record, 'siteId', 'site_id')),
    lineId: numberOrNull(pick(record, 'lineId', 'line_id')),
    erpRef: (pick(record, 'erpRef', 'erp_ref') as string | null | undefined) ?? null,
    name: String(record.name ?? record.erp_ref ?? `Machine ${record.id ?? ''}`).trim(),
    brand: (record.brand as string | null | undefined) ?? null,
    model: (record.model as string | null | undefined) ?? null,
    status: (record.status as MachineState | null | undefined) ?? null,
    asOf: (pick(record, 'asOf', 'as_of') as string | null | undefined) ?? null,
    freshnessS: numberOrNull(pick(record, 'freshnessS', 'freshness_s')),
    metrics: {
      trs: numberOrNull(pick(metrics, 'trs', 'oee', 'erp_trs')),
      oee: numberOrNull(pick(metrics, 'oee', 'trs', 'erp_trs')),
      scrapRate: numberOrNull(pick(metrics, 'scrapRate', 'scrap_rate')),
      cycleTimeS: numberOrNull(pick(metrics, 'cycleTimeS', 'cycle_time_s')),
      goodParts: numberOrNull(pick(metrics, 'goodParts', 'good_parts')),
      scrapParts: numberOrNull(pick(metrics, 'scrapParts', 'scrap_parts')),
      currentOrderId: (pick(metrics, 'currentOrderId', 'current_order_id', 'production_order_id') as string | null | undefined) ?? null,
    },
    layout: {
      x: Number(layout.x ?? record.layout_x ?? 0),
      y: Number(layout.y ?? record.layout_y ?? 0),
      rotation: Number(layout.rotation ?? layout.rotation_deg ?? 0),
      width: Number(layout.width ?? 110),
      height: Number(layout.height ?? 70),
    },
  };
}

function mapIncident(value: unknown): Incident {
  const record = (value ?? {}) as Record<string, unknown>;
  return {
    id: String(record.id),
    site_id: Number(record.site_id ?? record.siteId),
    machine_id: Number(record.machine_id ?? record.machineId),
    machine_erp_ref: (record.machine_erp_ref ?? record.machineErpRef) as string | null | undefined,
    production_order_id: (record.production_order_id ?? record.productionOrderId) as string | null | undefined,
    status: (record.status ?? 'open') as IncidentStatus,
    severity: (record.severity ?? 'medium') as IncidentSeverity,
    symptom: String(record.symptom ?? 'incident'),
    defect_type: (record.defect_type ?? record.defectType) as string | null | undefined,
    started_at: String(record.started_at ?? record.startedAt),
    ended_at: (record.ended_at ?? record.endedAt) as string | null | undefined,
    created_at: String(record.created_at ?? record.createdAt ?? record.started_at),
    data_cutoff: String(record.data_cutoff ?? record.dataCutoff ?? record.started_at),
    confidence: (record.confidence as Incident['confidence']) ?? null,
  };
}

function mapEvidence(value: unknown): Evidence {
  const record = (value ?? {}) as Record<string, unknown>;
  const window = (record.window ?? {}) as Record<string, unknown>;
  return {
    id: String(record.id),
    source_kind: String(record.source_kind ?? record.sourceKind ?? 'cycle_aggregate'),
    source_ref: String(record.source_ref ?? record.sourceRef ?? ''),
    metric: String(record.metric ?? ''),
    window: {
      start: (window.start ?? record.window_start ?? record.windowStart) as string | undefined,
      end: (window.end ?? record.window_end ?? record.windowEnd) as string | undefined,
    },
    observation: (record.observation ?? {}) as Record<string, unknown>,
    baseline: (record.baseline ?? null) as Record<string, unknown> | null,
    delta: numberOrNull(record.delta),
    supports: Boolean(record.supports),
    excerpt: (record.excerpt as string | null | undefined) ?? null,
  };
}

function mapTimeline(value: unknown): MachineTimeline {
  const points = listPayload<Record<string, unknown>>(value).map((point) => ({
    timestamp: String(point.timestamp ?? point.time ?? point.ts ?? point.bucket),
    metric: (point.metric ?? (point.scrap_rate !== undefined ? 'scrap_rate' : point.avg_zone2_temperature_c !== undefined ? 'barrel_temp_zone2_c' : 'cycle_count')) as string | undefined,
    value: numberOrNull(point.value ?? point.scrap_rate ?? point.avg_zone2_temperature_c ?? point.avg_cycle_time_s ?? point.cycle_count),
    status: (point.status as string | undefined) ?? null,
    label: (point.label as string | undefined) ?? null,
  }));
  const record = (value && !Array.isArray(value) ? value : {}) as Record<string, unknown>;
  return { points, from: record.from as string | undefined, to: record.to as string | undefined };
}

function mapImport(value: unknown): ImportPassport {
  const record = (value ?? {}) as Record<string, unknown>;
  return {
    id: String(record.id),
    fileName: (record.fileName ?? record.file_name) as string | undefined,
    parserType: (record.parserType ?? record.parser_type) as string | undefined,
    status: (record.status ?? 'pending') as ImportPassport['status'],
    importedAt: (record.importedAt ?? record.imported_at) as string | null | undefined,
    rowCountTotal: numberOrNull(pick(record, 'rowCountTotal', 'row_count_total')) ?? undefined,
    rowCountAccepted: numberOrNull(pick(record, 'rowCountAccepted', 'row_count_accepted')) ?? undefined,
    rowCountRejected: numberOrNull(pick(record, 'rowCountRejected', 'row_count_rejected')) ?? undefined,
    errorLog: (record.errorLog ?? record.error_log) as string | null | undefined,
  };
}

async function readPayload(response: Response): Promise<unknown> {
  if (response.status === 204) return null;
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return text;
  }
}

export function createApiClient(baseUrl = import.meta.env.VITE_API_URL ?? '/api/v1'): ApiClient {
  const apiBase = normaliseBaseUrl(baseUrl);
  const fallbackBase = apiBase.endsWith('/v1') ? apiBase.slice(0, -3) : '/api';

  function url(path: string, root = apiBase): string {
    const clean = path.startsWith('/') ? path : `/${path}`;
    return `${normaliseBaseUrl(root)}${clean}`;
  }

  async function request<T>(path: string, options: RequestOptions = {}, root = apiBase): Promise<T> {
    const response = await fetch(url(path, root), {
      method: options.method ?? 'GET',
      headers: options.body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: options.signal,
      credentials: 'include',
    });
    const payload = await readPayload(response);
    if (!response.ok) {
      const error = payload && typeof payload === 'object' && 'error' in payload ? (payload as { error: ApiErrorPayload }).error : undefined;
      const message = error?.message ?? (typeof payload === 'string' ? payload : `API indisponible (${response.status})`);
      throw new ApiRequestError(response.status, message, error?.code ?? `http_${response.status}`, error?.details ?? {});
    }
    return payload as T;
  }

  async function requestWithLegacyFallback<T>(path: string): Promise<T> {
    try {
      return await request<T>(path);
    } catch (error) {
      if (!(error instanceof ApiRequestError) || error.status !== 404 || fallbackBase === apiBase) throw error;
      return request<T>(path, {}, fallbackBase);
    }
  }

  return {
    async getHealth() {
      const healthRoot = import.meta.env.VITE_HEALTH_URL ? normaliseBaseUrl(import.meta.env.VITE_HEALTH_URL) : '';
      const payload = await request<Record<string, unknown>>('/health', {}, healthRoot || apiBase.replace(/\/api(?:\/v1)?$/, '') || '');
      return {
        status: (payload.status ?? 'unknown') as HealthStatus,
        service: payload.service as string | undefined,
        version: payload.version as string | undefined,
        database: payload.database as Health['database'],
        checkedAt: new Date().toISOString(),
        message: payload.database === 'ok' ? 'API connectée et base disponible.' : 'API joignable, base à surveiller.',
      } satisfies Health;
    },
    async getSites() {
      return listPayload<unknown>(await requestWithLegacyFallback('/sites')).map(mapSite);
    },
    async getSite(siteId) {
      return mapSite(await requestWithLegacyFallback(`/sites/${siteId}`));
    },
    async getMachines(siteId) {
      return listPayload<unknown>(await requestWithLegacyFallback(`/sites/${siteId}/machines`)).map(mapMachine);
    },
    async getMachine(machineId) {
      return mapMachine(await requestWithLegacyFallback(`/machines/${machineId}`));
    },
    async getMachineStatus(machineId, asOf) {
      const query = asOf ? `?as_of=${encodeURIComponent(asOf)}` : '';
      const record = (await requestWithLegacyFallback(`/machines/${machineId}/status${query}`)) as Record<string, unknown>;
      return {
        machineId: Number(record.machine_id ?? record.machineId ?? machineId),
        status: (record.status ?? 'offline') as MachineState,
        asOf: String(record.as_of ?? record.asOf ?? asOf ?? ''),
        freshnessS: numberOrNull(record.freshness_s ?? record.freshnessS),
        metrics: mapMachine({ id: machineId, name: `Machine ${machineId}`, metrics: record.metrics ?? record }).metrics,
      };
    },
    async getMachineTimeline(machineId, from, to) {
      const params = new URLSearchParams();
      if (from) params.set('from', from);
      if (to) params.set('to', to);
      const suffix = params.toString() ? `?${params.toString()}` : '';
      return mapTimeline(await requestWithLegacyFallback(`/machines/${machineId}/timeline${suffix}`));
    },
    async getMachineQuality(machineId, from, to) {
      const params = new URLSearchParams();
      if (from) params.set('from', from);
      if (to) params.set('to', to);
      const suffix = params.toString() ? `?${params.toString()}` : '';
      const payload = (await requestWithLegacyFallback(`/machines/${machineId}/quality${suffix}`)) as Record<string, unknown>;
      const defects = listPayload<Record<string, unknown>>(payload.defects ?? payload.by_defect ?? payload.items).map((defect) => ({ type: String(defect.type ?? defect.defect_type), count: Number(defect.count ?? 0) }));
      return {
        total: numberOrNull(payload.total ?? payload.total_count ?? payload.total_checks),
        good: numberOrNull(payload.good ?? payload.good_parts ?? (Number(payload.total_checks ?? 0) - Number(payload.total_defects ?? 0))),
        scrap: numberOrNull(payload.scrap ?? payload.scrap_parts ?? payload.total_defects),
        scrapRate: numberOrNull(payload.scrapRate ?? payload.scrap_rate),
        defects,
      } satisfies QualitySummary;
    },
    async getMachineDiagnostics(machineId, asOf) {
      const params = new URLSearchParams({ machine_id: String(machineId) });
      if (asOf) params.set('as_of', asOf);
      return listPayload<unknown>(await requestWithLegacyFallback(`/machines/${machineId}/diagnostics?${params.toString()}`)).map(mapIncident);
    },
    async getIncidents(filters = {}) {
      const params = new URLSearchParams();
      if (filters.siteId !== undefined) params.set('site_id', String(filters.siteId));
      if (filters.machineId !== undefined) params.set('machine_id', String(filters.machineId));
      if (filters.from) params.set('from', filters.from);
      if (filters.to) params.set('to', filters.to);
      if (filters.status) params.set('status', filters.status);
      const query = params.toString() ? `?${params.toString()}` : '';
      return listPayload<unknown>(await requestWithLegacyFallback(`/incidents${query}`)).map(mapIncident);
    },
    async getIncident(incidentId) {
      return mapIncident(await requestWithLegacyFallback(`/incidents/${encodeURIComponent(incidentId)}`));
    },
    async getEvidence(incidentId) {
      return listPayload<unknown>(await requestWithLegacyFallback(`/incidents/${encodeURIComponent(incidentId)}/evidence`)).map(mapEvidence);
    },
    async runInvestigation(incidentId, asOf) {
      const query = asOf ? `?as_of=${encodeURIComponent(asOf)}` : '';
      const payload = (await requestWithLegacyFallback(`/incidents/${encodeURIComponent(incidentId)}/investigations${query}`,)) as Record<string, unknown>;
      return {
        incident: mapIncident(payload.incident),
        run_id: (payload.run_id ?? payload.runId) as string | null | undefined,
        hypotheses: listPayload<Hypothesis>(payload.hypotheses).map((hypothesis) => ({
          cause_code: String(hypothesis.cause_code),
          label: String(hypothesis.label),
          confidence: Number(hypothesis.confidence ?? 0),
          supporting_evidence_ids: hypothesis.supporting_evidence_ids ?? [],
          contradicting_evidence_ids: hypothesis.contradicting_evidence_ids ?? [],
          missing_data: hypothesis.missing_data ?? [],
          next_check: hypothesis.next_check ?? null,
        })),
        evidence: listPayload<unknown>(payload.evidence).map(mapEvidence),
      };
    },
    async submitFeedback(incidentId, verdict, comment) {
      const payload = await request<Record<string, unknown>>(`/incidents/${encodeURIComponent(incidentId)}/feedback`, { method: 'POST', body: { verdict, comment } });
      return { id: String(payload.id), incident_id: String(payload.incident_id ?? payload.incidentId ?? incidentId), verdict: String(payload.verdict ?? verdict), comment: (payload.comment as string | null | undefined) ?? null };
    },
    async getImports() {
      return listPayload<unknown>(await requestWithLegacyFallback('/imports')).map(mapImport);
    },
    async login(email, password) {
      return request<LoginResponse>('/auth/login', { method: 'POST', body: { email, password } });
    },
  } satisfies ApiClient;
}

const DEMO_DATE = '2025-02-12T01:00:00Z';
const DEMO_SITES: Site[] = [{ id: 1, name: 'Usine Principale', timezone: 'Europe/Paris', status: 'online', machineCount: 6, openIncidentCount: 2, lastImportAt: DEMO_DATE }];
const DEMO_MACHINES: Machine[] = Array.from({ length: 6 }, (_, index) => ({
  id: index + 1,
  siteId: 1,
  erpRef: String(151 + index),
  name: `Presse ${151 + index}`,
  status: index === 1 ? 'warning' : index === 4 ? 'stopped' : 'running',
  metrics: { trs: 0.78 - index * 0.02, scrapRate: index === 1 ? 0.346 : 0.028, currentOrderId: index === 1 ? 'OF-2025-0012' : `OF-2025-${String(index + 1).padStart(4, '0')}` },
  layout: { x: 90 + (index % 3) * 190, y: 75 + Math.floor(index / 3) * 145, width: 125, height: 78 },
}));
const DEMO_INCIDENT: Incident = { id: 's001-demo', site_id: 1, machine_id: 2, machine_erp_ref: '152', production_order_id: 'OF-2025-0012', status: 'open', severity: 'high', symptom: 'short_shot_increase', defect_type: 'short_shot', started_at: '2025-02-12T00:21:43Z', ended_at: '2025-02-12T01:52:40Z', created_at: '2025-02-12T02:00:00Z', data_cutoff: '2025-02-12T02:00:00Z', confidence: 'high' };

/** A deterministic client used by component tests and an explicit demo mode. */
export const mockApiClient: ApiClient = {
  getHealth: async () => ({ status: 'ok', service: 'iddrv-demo', database: 'ok', checkedAt: DEMO_DATE, message: 'API de démonstration connectée.' }),
  getSites: async () => DEMO_SITES,
  getSite: async (id) => DEMO_SITES.find((site) => site.id === id) ?? DEMO_SITES[0],
  getMachines: async () => DEMO_MACHINES,
  getMachine: async (id) => DEMO_MACHINES.find((machine) => machine.id === id) ?? DEMO_MACHINES[0],
  getMachineStatus: async (id, asOf) => ({ machineId: id, status: DEMO_MACHINES.find((machine) => machine.id === id)?.status ?? 'offline', asOf: asOf ?? DEMO_DATE, metrics: DEMO_MACHINES.find((machine) => machine.id === id)?.metrics }),
  getMachineTimeline: async () => ({ from: '2025-02-11T22:00:00Z', to: DEMO_DATE, points: Array.from({ length: 8 }, (_, index) => ({ timestamp: `2025-02-12T0${index}:00:00Z`, metric: 'scrap_rate', value: index > 3 ? 0.12 + index * 0.04 : 0.028 })) }),
  getMachineQuality: async () => ({ total: 1200, good: 785, scrap: 415, scrapRate: 0.346, defects: [{ type: 'short_shot', count: 73 }, { type: 'flash', count: 12 }] }),
  getMachineDiagnostics: async () => [DEMO_INCIDENT],
  getIncidents: async () => [DEMO_INCIDENT],
  getIncident: async () => DEMO_INCIDENT,
  getEvidence: async () => [
    { id: 'ev-scrap', source_kind: 'cycle_aggregate', source_ref: '152:OF-2025-0012:scrap_rate', metric: 'scrap_rate', window: { start: DEMO_INCIDENT.started_at, end: DEMO_INCIDENT.ended_at ?? DEMO_DATE }, observation: { value: 0.346, unit: 'fraction', n: 1200 }, baseline: { value: 0.028, unit: 'fraction', n: 1180 }, delta: 0.318, supports: true },
    { id: 'ev-temp', source_kind: 'cycle_aggregate', source_ref: '152:OF-2025-0012:zone2', metric: 'barrel_temp_zone2_c', window: { start: DEMO_INCIDENT.started_at, end: DEMO_INCIDENT.ended_at ?? DEMO_DATE }, observation: { value: 194.9, unit: 'C', n: 217 }, baseline: { value: 210.1, unit: 'C', n: 216 }, delta: -15.2, supports: true },
    { id: 'ev-note', source_kind: 'operator_note', source_ref: 'note-152-01', metric: 'operator_note', window: { start: DEMO_INCIDENT.started_at, end: DEMO_INCIDENT.ended_at ?? DEMO_DATE }, observation: { value: 1, unit: 'note' }, supports: true, excerpt: 'Température zone 2 instable après changement de matière.' },
  ],
  runInvestigation: async () => ({ incident: DEMO_INCIDENT, run_id: 'run-s001-demo', hypotheses: [{ cause_code: 'low_barrel_temperature_zone_2', label: 'Température zone 2 trop basse', confidence: 0.87, supporting_evidence_ids: ['ev-scrap', 'ev-temp', 'ev-note'], contradicting_evidence_ids: [], missing_data: [], next_check: 'inspect_barrel_zone_2_heating' }], evidence: await mockApiClient.getEvidence('s001-demo') }),
  submitFeedback: async (incidentId, verdict, comment) => ({ id: 'feedback-demo', incident_id: incidentId, verdict, comment }),
  getImports: async () => [{ id: 'import-demo', fileName: 'machine_cycles_152.csv', parserType: 'csv_machine_cycles', status: 'completed', importedAt: DEMO_DATE, rowCountTotal: 12500, rowCountAccepted: 12500, rowCountRejected: 0 }],
  login: async (email) => ({ user: { id: 'demo-user', email, role: 'analyst' }, accessToken: 'demo-token' }),
};

export const apiClient = createApiClient();
