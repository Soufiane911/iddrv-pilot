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
  cycleCount24h?: number | null;
  currentOrderId?: string | null;
}

export interface MachineLayout {
  x?: number | null;
  y?: number | null;
  z?: number | null;
  rotation?: number | null;
  rotationDeg?: number | null;
  displayOrder?: number | null;
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
  lastCycleAt?: string | null;
  metrics?: MachineMetrics;
  layout?: MachineLayout | null;
}

export interface MachineStatus {
  machineId: number;
  status: MachineState;
  asOf: string;
  freshnessS?: number | null;
  lastCycleAt?: string | null;
  metrics?: MachineMetrics;
}

export interface ScrapRiskInput {
  site_id: number;
  machine_erp_ref: string;
  cycle_time_s?: number | null;
  dosing_time_s?: number | null;
  injection_time_s?: number | null;
  cooling_time_s?: number | null;
  cushion_mm?: number | null;
  switchover_position_mm?: number | null;
  switchover_pressure_bar?: number | null;
  peak_pressure_bar?: number | null;
  clamp_force_kn?: number | null;
  mold_temperature_c?: number | null;
  barrel_temp_zone1_c?: number | null;
  barrel_temp_zone2_c?: number | null;
  barrel_temp_zone3_c?: number | null;
  oil_temperature_c?: number | null;
  energy_kwh?: number | null;
  previous_scrap_flag?: number | null;
  rolling_scrap_rate_20?: number | null;
}

export interface ScrapRisk {
  model_version: string;
  risk_probability: number;
  predicted_scrap: boolean;
  threshold: number;
}

/** Raw cycle payload accepted by the HDT process-drift endpoint. */
export interface ProcessDriftCycle {
  timestamp?: string;
  machine_erp_ref?: string;
  [feature: string]: unknown;
}

/** A raw machine-cycle response, with the process features consumed by HDT. */
export interface MachineCycle {
  timestamp: string;
  machine_erp_ref: string;
  cycle_time_s?: number | null;
  dosing_time_s?: number | null;
  injection_time_s?: number | null;
  cooling_time_s?: number | null;
  cushion_mm?: number | null;
  switchover_position_mm?: number | null;
  switchover_pressure_bar?: number | null;
  peak_pressure_bar?: number | null;
  clamp_force_kn?: number | null;
  mold_temperature_c?: number | null;
  barrel_temp_zone1_c?: number | null;
  barrel_temp_zone2_c?: number | null;
  barrel_temp_zone3_c?: number | null;
  oil_temperature_c?: number | null;
  energy_kwh?: number | null;
  [feature: string]: unknown;
}

export interface ProcessDriftInput {
  site_id: number;
  cycles: ProcessDriftCycle[];
}

export interface ProcessDriftSignal {
  feature: string;
  volatility: number;
}

export interface ProcessDriftPrediction {
  model_version: string;
  machine_erp_ref: string;
  anomaly_score: number;
  predicted_instability_next_20_cycles: boolean;
  threshold: number;
  horizon_cycles: number;
  signals: ProcessDriftSignal[];
}

export interface TimelinePoint {
  timestamp: string;
  metric?: string;
  value?: number | null;
  cycleCount?: number | null;
  avgCycleTimeS?: number | null;
  scrapRate?: number | null;
  avgZone2TemperatureC?: number | null;
  productionOrderId?: string | null;
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

export interface InvestigationRun {
  run_id: string;
  incident_id: string;
  status?: string;
  dataCutoff?: string;
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
  sourceKind?: string;
  status: string;
  importedAt?: string | null;
  rowCountTotal?: number;
  rowCountAccepted?: number;
  rowCountRejected?: number;
  attemptCount?: number;
  maxAttempts?: number;
  errorLog?: string | null;
  errorCode?: string | null;
}

export type ImportSourceKind = 'erp' | 'machines' | 'quality' | 'maintenance' | 'layout' | 'unknown';
export interface ImportSessionFile {
  id: string;
  file_name: string;
  source_kind: ImportSourceKind;
  mime_type?: string | null;
  size_bytes: number;
  file_hash?: string | null;
  status: string;
  profile: { columns: string[]; recognized: string[]; unknown: string[]; confidence: number; message?: string };
}
export interface ImportSession {
  id: string;
  site_id: number;
  name: string;
  status: 'collecting' | 'profiling' | 'needs_review' | 'validated' | 'integrated' | 'failed';
  summary: { recognizedColumns?: number; unknownColumns?: number; confidence?: number };
  files: ImportSessionFile[];
  created_at: string;
  updated_at: string;
}

export type AuthRole = 'viewer' | 'analyst' | 'supervisor' | 'admin';

export interface AuthUser {
  id: string;
  email: string;
  displayName?: string;
  role: AuthRole;
  siteIds: number[];
  siteRoles?: Record<number, AuthRole>;
}

export function authRoleForSite(user: AuthUser | undefined, siteId: number | undefined): AuthRole | undefined {
  if (!user) return undefined;
  const scopedRoles = user.siteRoles ?? {};
  if (siteId !== undefined && Object.keys(scopedRoles).length > 0) return scopedRoles[siteId];
  return user.role;
}

export function canWriteSite(user: AuthUser | undefined, siteId: number | undefined): boolean {
  if (!user) return true;
  const role = authRoleForSite(user, siteId);
  return role === 'analyst' || role === 'supervisor' || role === 'admin';
}

export interface LoginResponse {
  user: AuthUser;
  expiresAt?: string;
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
  getMachineCycles(machineId: number, asOf: string, limit?: number): Promise<MachineCycle[]>;
  getMachineQuality(machineId: number, from?: string, to?: string): Promise<QualitySummary>;
  getMachineDiagnostics(machineId: number, asOf?: string): Promise<Incident[]>;
  getIncidents(filters?: { siteId?: number; machineId?: number; from?: string; to?: string; status?: IncidentStatus }): Promise<Incident[]>;
  getIncident(incidentId: string): Promise<Incident>;
  getEvidence(incidentId: string): Promise<Evidence[]>;
  getInvestigation(runId: string): Promise<InvestigationRun>;
  runInvestigation(incidentId: string, asOf?: string): Promise<Investigation>;
  predictScrapRisk(input: ScrapRiskInput): Promise<ScrapRisk>;
  predictProcessDrift(input: ProcessDriftInput): Promise<ProcessDriftPrediction>;
  submitFeedback(incidentId: string, verdict: string, comment?: string): Promise<Feedback>;
  getImports(): Promise<ImportPassport[]>;
  createImportSession(siteId: number, name: string): Promise<ImportSession>;
  getImportSession(sessionId: string): Promise<ImportSession>;
  registerImportFile(sessionId: string, file: { file_name: string; source_kind: ImportSourceKind; mime_type?: string; size_bytes: number; file_hash?: string }): Promise<ImportSession>;
  validateImportSession(sessionId: string): Promise<ImportSession>;
  login(email: string, password: string): Promise<LoginResponse>;
  getCurrentUser(): Promise<AuthUser>;
  logout(): Promise<void>;
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

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
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
  const metrics = isRecord(pick(record, 'metrics')) ? pick(record, 'metrics') as Record<string, unknown> : {};
  const rawLayout = pick(record, 'layout');
  const layout = isRecord(rawLayout) ? rawLayout : undefined;
  const hasMetrics = Object.keys(metrics).length > 0;
  return {
    id: Number(record.id),
    siteId: numberOrNull(pick(record, 'siteId', 'site_id')),
    lineId: numberOrNull(pick(record, 'lineId', 'line_id')),
    erpRef: (pick(record, 'erpRef', 'erp_ref') as string | null | undefined) ?? null,
    name: String(record.name ?? record.erpRef ?? record.erp_ref ?? `Machine ${record.id ?? ''}`).trim(),
    brand: (record.brand as string | null | undefined) ?? null,
    model: (record.model as string | null | undefined) ?? null,
    status: (record.status as MachineState | null | undefined) ?? null,
    asOf: (pick(record, 'asOf', 'as_of') as string | null | undefined) ?? null,
    freshnessS: numberOrNull(pick(record, 'freshnessS', 'freshness_s')),
    metrics: hasMetrics ? {
      trs: numberOrNull(pick(metrics, 'trs', 'oee', 'erp_trs')),
      oee: numberOrNull(pick(metrics, 'oee', 'trs', 'erp_trs')),
      scrapRate: numberOrNull(pick(metrics, 'scrapRate', 'scrap_rate')),
      cycleTimeS: numberOrNull(pick(metrics, 'cycleTimeS', 'cycle_time_s')),
      goodParts: numberOrNull(pick(metrics, 'goodParts', 'good_parts')),
      scrapParts: numberOrNull(pick(metrics, 'scrapParts', 'scrap_parts')),
      currentOrderId: (pick(metrics, 'currentOrderId', 'current_order_id', 'production_order_id') as string | null | undefined) ?? null,
    } : undefined,
    layout: layout ? {
      x: numberOrNull(pick(layout, 'x', 'layout_x', 'layoutX')),
      y: numberOrNull(pick(layout, 'y', 'layout_y', 'layoutY')),
      z: numberOrNull(pick(layout, 'z')),
      rotation: numberOrNull(pick(layout, 'rotation', 'rotation_deg', 'rotationDeg')),
      rotationDeg: numberOrNull(pick(layout, 'rotation_deg', 'rotationDeg', 'rotation')),
      displayOrder: numberOrNull(pick(layout, 'display_order', 'displayOrder')),
      width: numberOrNull(pick(layout, 'width')) ?? undefined,
      height: numberOrNull(pick(layout, 'height')) ?? undefined,
    } : null,
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

function mapHypothesis(value: unknown): Hypothesis {
  const hypothesis = (value ?? {}) as Record<string, unknown>;
  return {
    cause_code: String(hypothesis.cause_code ?? ''),
    label: String(hypothesis.label ?? hypothesis.cause_code ?? ''),
    confidence: Number(hypothesis.confidence ?? 0),
    supporting_evidence_ids: listPayload<string>(hypothesis.supporting_evidence_ids),
    contradicting_evidence_ids: listPayload<string>(hypothesis.contradicting_evidence_ids),
    missing_data: listPayload<unknown>(hypothesis.missing_data),
    next_check: (hypothesis.next_check as string | null | undefined) ?? null,
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

function mapMachineCycle(value: unknown): MachineCycle {
  const record = (value ?? {}) as Record<string, unknown>;
  return {
    timestamp: String(record.timestamp ?? record.time ?? record.ts ?? ''),
    machine_erp_ref: String(record.machine_erp_ref ?? record.machineErpRef ?? ''),
    cycle_time_s: numberOrNull(record.cycle_time_s),
    dosing_time_s: numberOrNull(record.dosing_time_s),
    injection_time_s: numberOrNull(record.injection_time_s),
    cooling_time_s: numberOrNull(record.cooling_time_s),
    cushion_mm: numberOrNull(record.cushion_mm),
    switchover_position_mm: numberOrNull(record.switchover_position_mm),
    switchover_pressure_bar: numberOrNull(record.switchover_pressure_bar),
    peak_pressure_bar: numberOrNull(record.peak_pressure_bar),
    clamp_force_kn: numberOrNull(record.clamp_force_kn),
    mold_temperature_c: numberOrNull(record.mold_temperature_c),
    barrel_temp_zone1_c: numberOrNull(record.barrel_temp_zone1_c),
    barrel_temp_zone2_c: numberOrNull(record.barrel_temp_zone2_c),
    barrel_temp_zone3_c: numberOrNull(record.barrel_temp_zone3_c),
    oil_temperature_c: numberOrNull(record.oil_temperature_c),
    energy_kwh: numberOrNull(record.energy_kwh),
  };
}

function mapTimeline(value: unknown): MachineTimeline {
  const points = listPayload<Record<string, unknown>>(value).map((point) => {
    let metric = typeof point.metric === 'string' ? point.metric : undefined;
    let rawValue = point.value;
    if (rawValue === null || rawValue === undefined) {
      const aggregate = [
        ['scrap_rate', 'scrap_rate'],
        ['avg_zone2_temperature_c', 'barrel_temp_zone2_c'],
        ['avg_cycle_time_s', 'cycle_time_s'],
        ['cycle_count', 'cycle_count'],
      ].find(([key]) => point[key] !== null && point[key] !== undefined);
      if (aggregate) { metric = aggregate[1]; rawValue = point[aggregate[0]]; }
    }
    return {
      timestamp: String(point.timestamp ?? point.time ?? point.ts ?? point.bucket),
      metric,
      value: numberOrNull(rawValue),
      cycleCount: numberOrNull(point.cycle_count),
      avgCycleTimeS: numberOrNull(point.avg_cycle_time_s),
      scrapRate: numberOrNull(point.scrap_rate),
      avgZone2TemperatureC: numberOrNull(point.avg_zone2_temperature_c),
      productionOrderId: (point.production_order_id as string | null | undefined) ?? null,
      status: (point.status as string | undefined) ?? null,
      label: (point.label as string | undefined) ?? null,
    };
  });
  const record = (value && !Array.isArray(value) ? value : {}) as Record<string, unknown>;
  return { points, from: record.from as string | undefined, to: record.to as string | undefined };
}

function mapImport(value: unknown): ImportPassport {
  const record = (value ?? {}) as Record<string, unknown>;
  return {
    id: String(record.id),
    fileName: (record.fileName ?? record.file_name) as string | undefined,
    parserType: (record.parserType ?? record.parser_type) as string | undefined,
    sourceKind: (record.sourceKind ?? record.source_kind) as string | undefined,
    status: String(record.status ?? 'pending'),
    importedAt: (record.importedAt ?? record.imported_at ?? record.completed_at ?? record.discovered_at) as string | null | undefined,
    rowCountTotal: numberOrNull(pick(record, 'rowCountTotal', 'row_count_total')) ?? undefined,
    rowCountAccepted: numberOrNull(pick(record, 'rowCountAccepted', 'row_count_accepted')) ?? undefined,
    rowCountRejected: numberOrNull(pick(record, 'rowCountRejected', 'row_count_rejected')) ?? undefined,
    attemptCount: numberOrNull(record.attemptCount ?? record.attempt_count) ?? undefined,
    maxAttempts: numberOrNull(record.maxAttempts ?? record.max_attempts) ?? undefined,
    errorLog: (record.errorLog ?? record.error_log ?? record.last_error) as string | null | undefined,
    errorCode: (record.errorCode ?? record.error_code ?? record.last_error_code) as string | null | undefined,
  };
}

function mapAuthUser(value: unknown): AuthUser {
  if (!value || typeof value !== 'object') throw new Error('Réponse d’authentification invalide.');
  const user = value as Record<string, unknown>;
  const id = String(user.id ?? '');
  const email = String(user.email ?? '');
  const role = String(user.role ?? '');
  if (!id || !email || !['viewer', 'analyst', 'supervisor', 'admin'].includes(role)) throw new Error('Réponse d’authentification incomplète.');
  const rawSiteRoles = user.site_roles ?? user.siteRoles;
  const siteRoles = rawSiteRoles && typeof rawSiteRoles === 'object'
    ? Object.fromEntries(Object.entries(rawSiteRoles as Record<string, unknown>).filter(([siteId, siteRole]) => Number.isFinite(Number(siteId)) && ['viewer', 'analyst', 'supervisor', 'admin'].includes(String(siteRole))).map(([siteId, siteRole]) => [Number(siteId), String(siteRole) as AuthRole]))
    : {};
  return { id, email, displayName: (user.display_name ?? user.displayName) as string | undefined, role: role as AuthUser['role'], siteIds: listPayload<number>(user.site_ids ?? user.siteIds), siteRoles };
}

function mapImportSession(value: unknown): ImportSession {
  const record = (value ?? {}) as Record<string, unknown>;
  const files = listPayload<Record<string, unknown>>(record.files).map((file) => {
    const profile = (file.profile && typeof file.profile === 'object' ? file.profile : {}) as Record<string, unknown>;
    return {
      id: String(file.id), file_name: String(file.file_name ?? file.fileName ?? ''),
      source_kind: (file.source_kind ?? 'unknown') as ImportSourceKind,
      mime_type: (file.mime_type ?? file.mimeType) as string | null | undefined,
      size_bytes: Number(file.size_bytes ?? file.sizeBytes ?? 0), file_hash: (file.file_hash ?? file.fileHash) as string | null | undefined,
      status: String(file.status ?? 'queued'),
      profile: { columns: listPayload<string>(profile.columns), recognized: listPayload<string>(profile.recognized), unknown: listPayload<string>(profile.unknown), confidence: Number(profile.confidence ?? 0), message: profile.message as string | undefined },
    };
  });
  return { id: String(record.id), site_id: Number(record.site_id ?? record.siteId), name: String(record.name ?? 'Projet usine'),
    status: (record.status ?? 'collecting') as ImportSession['status'], summary: (record.summary ?? {}) as ImportSession['summary'], files,
    created_at: String(record.created_at ?? record.createdAt ?? ''), updated_at: String(record.updated_at ?? record.updatedAt ?? '') };
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
      cache: 'no-store',
    });
    const payload = await readPayload(response);
    if (!response.ok) {
      const authProbe = path.startsWith('/auth/login') || path.startsWith('/auth/me');
      if (response.status === 401 && !authProbe && typeof window !== 'undefined') window.dispatchEvent(new Event('iddrv:unauthorized'));
      const error = payload && typeof payload === 'object' && 'error' in payload ? (payload as { error: ApiErrorPayload }).error : undefined;
      const detail = payload && typeof payload === 'object' && 'detail' in payload ? (payload as { detail?: unknown }).detail : undefined;
      const detailRecord = detail && typeof detail === 'object' ? detail as Record<string, unknown> : undefined;
      const detailCode = typeof detailRecord?.code === 'string' ? detailRecord.code : undefined;
      const detailMessage = typeof detail === 'string'
        ? ({ invalid_credentials: 'Identifiants invalides.', authentication_required: 'Authentification requise.', invalid_token: 'Session invalide.', session_revoked: 'Session expirée.' } as Record<string, string>)[detail] ?? detail.split('_').join(' ')
        : typeof detailRecord?.message === 'string' ? detailRecord.message : undefined;
      const message = error?.message ?? detailMessage ?? (typeof payload === 'string' ? payload : `API indisponible (${response.status})`);
      throw new ApiRequestError(response.status, message, error?.code ?? detailCode ?? `http_${response.status}`, error?.details ?? detailRecord ?? {});
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

  async function requestAllPages(path: string): Promise<unknown[]> {
    const items: unknown[] = [];
    const seenCursors = new Set<string>();
    let cursor: string | undefined;
    let hasNextPage = true;
    while (hasNextPage) {
      const params = new URLSearchParams();
      params.set('limit', '500');
      if (cursor) params.set('cursor', cursor);
      const separator = path.includes('?') ? '&' : '?';
      const payload = await requestWithLegacyFallback<unknown>(`${path}${separator}${params.toString()}`);
      items.push(...listPayload<unknown>(payload));
      if (Array.isArray(payload) || !payload || typeof payload !== 'object') break;
      const next = (payload as Record<string, unknown>).next_cursor ?? (payload as Record<string, unknown>).nextCursor;
      if (typeof next !== 'string' || !next) {
        hasNextPage = false;
      } else if (seenCursors.has(next)) {
        throw new ApiRequestError(502, 'Pagination API incohérente.', 'pagination_cursor_cycle');
      } else {
        seenCursors.add(next);
        cursor = next;
      }
    }
    return items;
  }

  return {
    async getHealth() {
      const healthRoot = import.meta.env.VITE_HEALTH_URL ? normaliseBaseUrl(import.meta.env.VITE_HEALTH_URL) : apiBase.replace(/\/api(?:\/v1)?$/, '') || '/api';
      const payload = await request<Record<string, unknown>>('/health', {}, healthRoot);
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
      return (await requestAllPages('/sites')).map(mapSite);
    },
    async getSite(siteId) {
      return mapSite(await requestWithLegacyFallback(`/sites/${siteId}`));
    },
    async getMachines(siteId) {
      return (await requestAllPages(`/sites/${siteId}/machines`)).map(mapMachine);
    },
    async getMachine(machineId) {
      return mapMachine(await requestWithLegacyFallback(`/machines/${machineId}`));
    },
    async getMachineStatus(machineId, asOf) {
      const query = asOf ? `?as_of=${encodeURIComponent(asOf)}` : '';
      const record = (await requestWithLegacyFallback(`/machines/${machineId}/status${query}`)) as Record<string, unknown>;
      const statusMetrics = {
        // The v1 contract exposes these fields at the root. Do not fill the
        // missing TRS/cycle values from the catalogue: their time origins differ.
        trs: numberOrNull(record.trs),
        oee: numberOrNull(record.oee),
        scrapRate: numberOrNull(record.scrap_rate_24h ?? record.scrapRate),
        cycleTimeS: numberOrNull(record.cycle_time_s ?? record.cycleTimeS),
        goodParts: numberOrNull(record.good_parts ?? record.goodParts),
        scrapParts: numberOrNull(record.scrap_parts ?? record.scrapParts),
        cycleCount24h: numberOrNull(record.cycle_count_24h ?? record.cycleCount24h),
        currentOrderId: (record.current_order_id ?? record.currentOrderId ?? null) as string | null,
      } satisfies MachineMetrics;
      return {
        machineId: Number(record.machine_id ?? record.machineId ?? machineId),
        status: (record.status ?? 'offline') as MachineState,
        asOf: String(record.as_of ?? record.asOf ?? asOf ?? ''),
        freshnessS: numberOrNull(record.freshness_s ?? record.freshnessS),
        lastCycleAt: (record.last_cycle_at ?? record.lastCycleAt) as string | null | undefined,
        metrics: statusMetrics,
      };
    },
    async getMachineTimeline(machineId, from, to) {
      const params = new URLSearchParams();
      if (from) params.set('from', from);
      if (to) params.set('to', to);
      const suffix = params.toString() ? `?${params.toString()}` : '';
      return mapTimeline(await requestWithLegacyFallback(`/machines/${machineId}/timeline${suffix}`));
    },
    async getMachineCycles(machineId, asOf, limit) {
      const params = new URLSearchParams({ to: asOf });
      if (limit !== undefined) params.set('limit', String(limit));
      return listPayload<unknown>(await requestWithLegacyFallback(`/machines/${machineId}/cycles?${params.toString()}`)).map(mapMachineCycle);
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
      return (await requestAllPages(`/incidents${query}`)).map(mapIncident);
    },
    async getIncident(incidentId) {
      return mapIncident(await requestWithLegacyFallback(`/incidents/${encodeURIComponent(incidentId)}`));
    },
    async getEvidence(incidentId) {
      return listPayload<unknown>(await requestWithLegacyFallback(`/incidents/${encodeURIComponent(incidentId)}/evidence`)).map(mapEvidence);
    },
    async getInvestigation(runId) {
      const payload = await requestWithLegacyFallback<Record<string, unknown>>(`/investigations/${encodeURIComponent(runId)}`);
      const result = payload.result && typeof payload.result === 'object' ? payload.result as Record<string, unknown> : {};
      return {
        run_id: String(payload.id ?? runId),
        incident_id: String(payload.incident_id ?? payload.incidentId ?? ''),
        status: payload.status as string | undefined,
        dataCutoff: (payload.data_cutoff ?? payload.dataCutoff) as string | undefined,
        hypotheses: listPayload<unknown>(result.hypotheses).map(mapHypothesis),
        evidence: listPayload<unknown>(result.evidence).map(mapEvidence),
      };
    },
    async runInvestigation(incidentId, asOf) {
      const query = asOf ? `?as_of=${encodeURIComponent(asOf)}` : '';
      const payload = await request<Record<string, unknown>>(`/incidents/${encodeURIComponent(incidentId)}/investigations${query}`, {
        method: 'POST',
      });
      return {
        incident: mapIncident(payload.incident),
        run_id: (payload.run_id ?? payload.runId) as string | null | undefined,
        hypotheses: listPayload<unknown>(payload.hypotheses).map(mapHypothesis),
        evidence: listPayload<unknown>(payload.evidence).map(mapEvidence),
      };
    },
    async predictScrapRisk(input) {
      return request<ScrapRisk>('/scrap-risk', { method: 'POST', body: input });
    },
    async predictProcessDrift(input) {
      return request<ProcessDriftPrediction>('/process-drift', { method: 'POST', body: input });
    },
    async submitFeedback(incidentId, verdict, comment) {
      const payload = await request<Record<string, unknown>>(`/incidents/${encodeURIComponent(incidentId)}/feedback`, { method: 'POST', body: { verdict, comment } });
      return { id: String(payload.id), incident_id: String(payload.incident_id ?? payload.incidentId ?? incidentId), verdict: String(payload.verdict ?? verdict), comment: (payload.comment as string | null | undefined) ?? null };
    },
    async getImports() {
      return (await requestAllPages('/imports')).map(mapImport);
    },
    async createImportSession(siteId, name) {
      return mapImportSession(await request(`/sites/${siteId}/import-sessions`, { method: 'POST', body: { name } }));
    },
    async getImportSession(sessionId) {
      return mapImportSession(await request(`/import-sessions/${encodeURIComponent(sessionId)}`));
    },
    async registerImportFile(sessionId, file) {
      return mapImportSession(await request(`/import-sessions/${encodeURIComponent(sessionId)}/files`, { method: 'POST', body: file }));
    },
    async validateImportSession(sessionId) {
      return mapImportSession(await request(`/import-sessions/${encodeURIComponent(sessionId)}/validate`, { method: 'POST' }));
    },
    async login(email, password) {
      const payload = await request<Record<string, unknown>>('/auth/login', { method: 'POST', body: { email, password } });
      return {
        user: mapAuthUser(payload.user),
        expiresAt: (payload.expires_at ?? payload.expiresAt) as string | undefined,
      };
    },
    async getCurrentUser() {
      return mapAuthUser(await request<unknown>('/auth/me'));
    },
    async logout() {
      await request<null>('/auth/logout', { method: 'POST' });
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
  metrics: { trs: 0.78 - index * 0.02, scrapRate: index === 1 ? 0.346 : 0.028, cycleCount24h: 1180 + index * 10, currentOrderId: index === 1 ? 'OF-2025-0012' : `OF-2025-${String(index + 1).padStart(4, '0')}` },
  layout: { x: 90 + (index % 3) * 190, y: 75 + Math.floor(index / 3) * 145, width: 125, height: 78 },
}));
const DEMO_INCIDENT: Incident = { id: 's001-demo', site_id: 1, machine_id: 2, machine_erp_ref: '152', production_order_id: 'OF-2025-0012', status: 'open', severity: 'high', symptom: 'short_shot_increase', defect_type: 'short_shot', started_at: '2025-02-12T00:21:43Z', ended_at: '2025-02-12T01:52:40Z', created_at: '2025-02-12T02:00:00Z', data_cutoff: '2025-02-12T02:00:00Z', confidence: 'high' };

function demoMachineCycles(machineId: number, asOf?: string, limit = 20): MachineCycle[] {
  const parsedAsOf = asOf ? new Date(asOf).getTime() : Number.NaN;
  const end = Number.isFinite(parsedAsOf) ? parsedAsOf : new Date(DEMO_DATE).getTime();
  const count = Math.max(0, Math.floor(limit));
  const machine = DEMO_MACHINES.find((item) => item.id === machineId) ?? DEMO_MACHINES[0];
  const machineErpRef = machine.erpRef ?? String(151 + machineId - 1);
  return Array.from({ length: count }, (_, index) => {
    const unstable = machineId === 2 && index >= count - 6;
    const variation = unstable ? (index - Math.max(0, count - 6)) * 0.55 : (index % 4) * 0.04;
    return {
      timestamp: new Date(end - (count - index - 1) * 30_000).toISOString(),
      machine_erp_ref: machineErpRef,
      cycle_time_s: 30.2 + variation,
      dosing_time_s: 7.2 + variation * 0.08,
      injection_time_s: 5.8 + variation * 0.12,
      cooling_time_s: 12.4 + variation * 0.1,
      cushion_mm: 4.3 - variation * 0.02,
      switchover_position_mm: 18.2 + variation * 0.05,
      switchover_pressure_bar: 620 + variation * 4,
      peak_pressure_bar: 1380 + variation * 12,
      clamp_force_kn: 450 + (index % 3) * 1.5,
      mold_temperature_c: 62 + (index % 5) * 0.15,
      barrel_temp_zone1_c: 208 + (index % 4) * 0.2,
      barrel_temp_zone2_c: unstable ? 216 - variation * 2.8 : 220 + (index % 3) * 0.2,
      barrel_temp_zone3_c: 224 + (index % 4) * 0.2,
      oil_temperature_c: 42 + (index % 3) * 0.1,
      energy_kwh: 0.42 + variation * 0.006,
    };
  });
}

/** A deterministic client used by component tests and an explicit demo mode. */
export const mockApiClient: ApiClient = {
  getHealth: async () => ({ status: 'ok', service: 'iddrv-demo', database: 'ok', checkedAt: DEMO_DATE, message: 'API de démonstration connectée.' }),
  getSites: async () => DEMO_SITES,
  getSite: async (id) => DEMO_SITES.find((site) => site.id === id) ?? DEMO_SITES[0],
  getMachines: async () => DEMO_MACHINES,
  getMachine: async (id) => DEMO_MACHINES.find((machine) => machine.id === id) ?? DEMO_MACHINES[0],
  getMachineStatus: async (id, asOf) => {
    const requestedAt = asOf && Number.isFinite(new Date(asOf).getTime()) ? new Date(asOf).getTime() : new Date(DEMO_DATE).getTime();
    const sourceAt = new Date(DEMO_DATE).getTime();
    return { machineId: id, status: DEMO_MACHINES.find((machine) => machine.id === id)?.status ?? 'offline', asOf: new Date(requestedAt).toISOString(), lastCycleAt: new Date(Math.min(requestedAt, sourceAt)).toISOString(), metrics: DEMO_MACHINES.find((machine) => machine.id === id)?.metrics };
  },
  getMachineTimeline: async (id, from, to) => {
    const start = new Date(from ?? '2025-02-11T21:00:00Z').getTime();
    const end = new Date(to ?? DEMO_DATE).getTime();
    const anomaly = id === 2;
    const points = Array.from({ length: 8 }, (_, index) => ({ timestamp: new Date(start + ((end - start) * index) / 7).toISOString(), metric: 'scrap_rate', value: anomaly && index > 3 ? 0.08 + index * 0.038 : 0.028 + index * 0.001 }));
    return { from: new Date(start).toISOString(), to: new Date(end).toISOString(), points };
  },
  getMachineCycles: async (id, asOf, limit) => demoMachineCycles(id, asOf, limit),
  getMachineQuality: async (id, from, to) => {
    const start = new Date(from ?? '').getTime();
    const end = new Date(to ?? '').getTime();
    if (!Number.isFinite(start) || !Number.isFinite(end) || start >= end) return { total: 0, good: 0, scrap: 0, scrapRate: null, defects: [] };
    return id === 2
      ? { total: 1200, good: 785, scrap: 415, scrapRate: 0.346, defects: [{ type: 'short_shot', count: 73 }, { type: 'flash', count: 12 }] }
      : { total: 1200, good: 1166, scrap: 34, scrapRate: 0.028, defects: [{ type: 'short_shot', count: 11 }, { type: 'flash', count: 6 }] };
  },
  getMachineDiagnostics: async () => [DEMO_INCIDENT],
  getIncidents: async () => [DEMO_INCIDENT],
  getIncident: async () => DEMO_INCIDENT,
  getEvidence: async () => [
    { id: 'ev-scrap', source_kind: 'cycle_aggregate', source_ref: '152:OF-2025-0012:scrap_rate', metric: 'scrap_rate', window: { start: DEMO_INCIDENT.started_at, end: DEMO_INCIDENT.ended_at ?? DEMO_DATE }, observation: { value: 0.346, unit: 'fraction', n: 1200 }, baseline: { value: 0.028, unit: 'fraction', n: 1180 }, delta: 0.318, supports: true },
    { id: 'ev-temp', source_kind: 'cycle_aggregate', source_ref: '152:OF-2025-0012:zone2', metric: 'barrel_temp_zone2_c', window: { start: DEMO_INCIDENT.started_at, end: DEMO_INCIDENT.ended_at ?? DEMO_DATE }, observation: { value: 194.9, unit: 'C', n: 217 }, baseline: { value: 210.1, unit: 'C', n: 216 }, delta: -15.2, supports: true },
    { id: 'ev-note', source_kind: 'operator_note', source_ref: 'note-152-01', metric: 'operator_note', window: { start: DEMO_INCIDENT.started_at, end: DEMO_INCIDENT.ended_at ?? DEMO_DATE }, observation: { value: 1, unit: 'note' }, supports: true, excerpt: 'Température zone 2 instable après changement de matière.' },
  ],
  getInvestigation: async (runId) => ({ run_id: runId, incident_id: DEMO_INCIDENT.id, status: 'completed', dataCutoff: DEMO_INCIDENT.data_cutoff, hypotheses: [{ cause_code: 'low_barrel_temperature_zone_2', label: 'Température zone 2 trop basse', confidence: 0.87, supporting_evidence_ids: ['ev-scrap', 'ev-temp', 'ev-note'], contradicting_evidence_ids: [], missing_data: [], next_check: 'inspect_barrel_zone_2_heating' }], evidence: await mockApiClient.getEvidence(DEMO_INCIDENT.id) }),
  runInvestigation: async () => ({ incident: DEMO_INCIDENT, run_id: 'run-s001-demo', hypotheses: [{ cause_code: 'low_barrel_temperature_zone_2', label: 'Température zone 2 trop basse', confidence: 0.87, supporting_evidence_ids: ['ev-scrap', 'ev-temp', 'ev-note'], contradicting_evidence_ids: [], missing_data: [], next_check: 'inspect_barrel_zone_2_heating' }], evidence: await mockApiClient.getEvidence('s001-demo') }),
  predictScrapRisk: async () => ({ model_version: 'rebut-risk-logistic-v1', risk_probability: 0.08, predicted_scrap: false, threshold: 0.5 }),
  predictProcessDrift: async (input) => {
    const machineErpRef = String(input.cycles.find((cycle) => typeof cycle.machine_erp_ref === 'string')?.machine_erp_ref ?? '152');
    const driftDetected = machineErpRef === '152';
    return {
      model_version: 'hdt-process-drift-iforest-v1',
      machine_erp_ref: machineErpRef,
      anomaly_score: driftDetected ? 0.73 : 0.18,
      predicted_instability_next_20_cycles: driftDetected,
      threshold: 0.41,
      horizon_cycles: 20,
      signals: driftDetected
        ? [{ feature: 'barrel_temp_zone2_c_volatility_20', volatility: 0.72 }, { feature: 'cycle_time_s_volatility_20', volatility: 0.48 }]
        : [{ feature: 'barrel_temp_zone2_c_volatility_20', volatility: 0.16 }, { feature: 'cycle_time_s_volatility_20', volatility: 0.11 }],
    };
  },
  submitFeedback: async (incidentId, verdict, comment) => ({ id: 'feedback-demo', incident_id: incidentId, verdict, comment }),
  getImports: async () => [{ id: 'import-demo', fileName: 'machine_cycles_152.csv', parserType: 'csv_machine_cycles', status: 'completed', importedAt: DEMO_DATE, rowCountTotal: 12500, rowCountAccepted: 12500, rowCountRejected: 0 }],
  createImportSession: async (siteId, name) => ({ id: 'session-demo', site_id: siteId, name, status: 'collecting', summary: {}, files: [], created_at: DEMO_DATE, updated_at: DEMO_DATE }),
  getImportSession: async () => ({ id: 'session-demo', site_id: 1, name: 'Projet usine pilote', status: 'profiling', summary: { recognizedColumns: 18, unknownColumns: 2, confidence: .91 }, files: [], created_at: DEMO_DATE, updated_at: DEMO_DATE }),
  registerImportFile: async (sessionId, file) => ({ id: sessionId, site_id: 1, name: 'Projet usine pilote', status: 'profiling', summary: { recognizedColumns: 6, unknownColumns: 1, confidence: .84 }, files: [{ id: `file-${file.file_name}`, ...file, status: 'needs_review', profile: { columns: ['machine_id', 'timestamp', 'cycle_time_s'], recognized: ['machine_id', 'timestamp'], unknown: ['cycle_time_s'], confidence: .84 } }], created_at: DEMO_DATE, updated_at: DEMO_DATE }),
  validateImportSession: async (sessionId) => ({ id: sessionId, site_id: 1, name: 'Projet usine pilote', status: 'validated', summary: { recognizedColumns: 18, unknownColumns: 0, confidence: .96 }, files: [], created_at: DEMO_DATE, updated_at: DEMO_DATE }),
  login: async (email) => ({ user: { id: 'demo-user', email, role: 'analyst', siteIds: [1], siteRoles: { 1: 'analyst' } }, expiresAt: DEMO_DATE }),
  getCurrentUser: async () => ({ id: 'demo-user', email: 'demo@iddrv.local', role: 'analyst', siteIds: [1], siteRoles: { 1: 'analyst' } }),
  logout: async () => undefined,
};

export const apiClient = createApiClient();
