import { ArrowLeftIcon } from '@phosphor-icons/react/ArrowLeft';
import { ArrowUpRightIcon } from '@phosphor-icons/react/ArrowUpRight';
import { SkipBackIcon } from '@phosphor-icons/react/SkipBack';
import { SkipForwardIcon } from '@phosphor-icons/react/SkipForward';
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import type { ApiClient, Incident, Machine, ProcessDriftCycle, Site, TimelinePoint } from '../lib/api';
import { ProcessDriftPanel } from './ProcessDriftPanel';
import {
  formatNumber,
  formatPercent,
  incidentSeverityLabel,
  incidentSymptomLabel,
  StatusBadge,
} from './Ui';
export type WorkshopViewMode = '2d' | '3d';

export function formatWorkshopDate(value?: string | null, timeZone?: string, withTime = true): string {
  if (!value) return 'N/D';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const options = (zone: string): Intl.DateTimeFormatOptions => withTime ? { dateStyle: 'medium', timeStyle: 'short', timeZone: zone } : { dateStyle: 'medium', timeZone: zone };
  try {
    return new Intl.DateTimeFormat('fr-FR', options(timeZone || 'UTC')).format(date);
  } catch {
    return new Intl.DateTimeFormat('fr-FR', options('UTC')).format(date);
  }
}

interface Props {
  site?: Site;
  machines: Machine[];
  activeMachine?: Machine;
  machineIncidents: Incident[];
  timelineIncidents: Incident[];
  siteIncidentCount: number;
  incidentsUnavailable?: boolean;
  statusUnavailable?: boolean;
  statusLoading?: boolean;
  statusDataInconsistent?: boolean;
  sourceCutoffPartial?: boolean;
  threeDUnavailable?: boolean;
  qualityUnavailable?: boolean;
  qualityLoading?: boolean;
  hasQualityWindow?: boolean;
  timelineUnavailable?: boolean;
  timelineLoading?: boolean;
  status?: string | null;
  scrapRate?: number | null;
  scrap?: number | null;
  qualityTotal?: number | null;
  replayAt: string;
  selectedReplayAt: string;
  replayPending?: boolean;
  range: { start: string; end: string };
  replayPercent: number;
  timeline: TimelinePoint[];
  processDriftApi: Pick<ApiClient, 'predictProcessDrift'>;
  processDriftSiteId: number;
  processDriftCycles: ProcessDriftCycle[];
  processDriftCyclesLoading?: boolean;
  processDriftCyclesError?: Error | null;
  onProcessDriftCyclesRetry?: () => void;
  viewMode: WorkshopViewMode;
  feature3dEnabled: boolean;
  visualization: ReactNode;
  onReplayChange: (value: number) => void;
  onViewModeChange: (mode: WorkshopViewMode) => void;
}

interface TrendSeries {
  label: string;
  points: Array<{ timestamp: string; value: number }>;
}

const TIMELINE_METRIC_LABELS: Record<string, string> = {
  scrap_rate: 'Taux de rebut',
  barrel_temp_zone2_c: 'Température zone 2',
  cycle_time_s: 'Cycle moyen',
  cycle_count: 'Cycles',
};

function metricLabel(metric?: string): string {
  if (!metric) return 'Mesure agrégée';
  return TIMELINE_METRIC_LABELS[metric] ?? metric.split('_').join(' ');
}

function timelineSeries(points: TimelinePoint[]): TrendSeries {
  const explicit = points.filter((point): point is TimelinePoint & { value: number } => typeof point.value === 'number' && Number.isFinite(point.value));
  if (explicit.length > 0) {
    const metric = explicit.find((point) => point.metric)?.metric;
    return {
      label: metricLabel(metric),
      points: explicit.filter((point) => !metric || point.metric === metric).map((point) => ({ timestamp: point.timestamp, value: point.value })).sort((left, right) => new Date(left.timestamp).getTime() - new Date(right.timestamp).getTime()),
    };
  }

  const candidates: Array<{ key: keyof TimelinePoint; label: string }> = [
    { key: 'scrapRate', label: 'taux de rebut' },
    { key: 'avgCycleTimeS', label: 'cycle moyen' },
    { key: 'cycleCount', label: 'cycles' },
    { key: 'avgZone2TemperatureC', label: 'température zone 2' },
  ];
  for (const candidate of candidates) {
    const series = points.flatMap((point) => {
      const value = point[candidate.key];
      return typeof value === 'number' && Number.isFinite(value) ? [{ timestamp: point.timestamp, value }] : [];
    });
    if (series.length > 0) return { label: candidate.label, points: series.sort((left, right) => new Date(left.timestamp).getTime() - new Date(right.timestamp).getTime()) };
  }
  return { label: 'Mesure agrégée', points: [] };
}

function percentInRange(timestamp: string, range: { start: string; end: string }): number {
  const start = new Date(range.start).getTime();
  const end = new Date(range.end).getTime();
  const value = new Date(timestamp).getTime();
  if (!Number.isFinite(value) || end <= start) return 0;
  return Math.max(0, Math.min(100, ((value - start) / (end - start)) * 100));
}

function WorkshopTrend({ points, incidents, range, replayPercent, unavailable, loading }: { points: TimelinePoint[]; incidents: Incident[]; range: { start: string; end: string }; replayPercent: number; unavailable: boolean; loading: boolean }) {
  const series = timelineSeries(points);
  const values = series.points.map((point) => point.value);
  const minimum = values.length > 0 ? Math.min(...values) : 0;
  const maximum = values.length > 0 ? Math.max(...values) : 1;
  const amplitude = maximum - minimum || 1;
  const polyline = series.points.map((point) => {
    const x = percentInRange(point.timestamp, range) * 6;
    const y = 58 - (((point.value - minimum) / amplitude) * 42);
    return `${x.toFixed(2)},${y.toFixed(2)}`;
  }).join(' ');
  const description = `${series.points.length} points pour ${series.label}. ${incidents.length} ${incidents.length > 1 ? 'anomalies reconstruites' : 'anomalie reconstruite'} dans la fenêtre.`;

  if (loading) return <div className="workshop-trend-empty" role="status">Lecture de la tendance agrégée…</div>;
  if (unavailable) return <div className="workshop-trend-empty" role="status">Tendance indisponible. La fenêtre source et le replay restent utilisables.</div>;
  if (series.points.length === 0) return <div className="workshop-trend-empty" role="status">Aucun point agrégé n’est disponible dans cette fenêtre.</div>;

  return <div className="workshop-trend" role="img" aria-label={description}>
    <svg viewBox="0 0 600 72" preserveAspectRatio="none" aria-hidden="true">
      <path className="workshop-trend-grid" d="M0 16H600 M0 37H600 M0 58H600" />
      <polyline className="workshop-trend-line" points={polyline} />
      {incidents.map((incident) => <line key={incident.id} className="workshop-trend-incident" x1={percentInRange(incident.started_at, range) * 6} x2={percentInRange(incident.started_at, range) * 6} y1="8" y2="64" />)}
      <line className="workshop-trend-cursor" x1={replayPercent * 6} x2={replayPercent * 6} y1="4" y2="68" />
    </svg>
    <span>{series.label}</span>
  </div>;
}

export function WorkshopWorkspace({ site, machines, activeMachine, machineIncidents, timelineIncidents, siteIncidentCount, incidentsUnavailable = false, statusUnavailable = false, statusLoading = false, statusDataInconsistent = false, sourceCutoffPartial = false, threeDUnavailable = false, qualityUnavailable = false, qualityLoading = false, hasQualityWindow = false, timelineUnavailable = false, timelineLoading = false, status, scrapRate, scrap, qualityTotal, replayAt, selectedReplayAt, replayPending = false, range, replayPercent, timeline, processDriftApi, processDriftSiteId, processDriftCycles, processDriftCyclesLoading = false, processDriftCyclesError = null, onProcessDriftCyclesRetry, viewMode, feature3dEnabled, visualization, onReplayChange, onViewModeChange }: Props) {
  const statusCoverageComplete = machines.every((machine) => machine.status !== undefined && machine.status !== null);
  const summaryUnavailable = statusUnavailable || statusLoading || !statusCoverageComplete;
  const running = machines.filter((machine) => machine.status === 'running').length;
  const warning = machines.filter((machine) => machine.status === 'warning').length;
  const cyclesAvailable = typeof activeMachine?.metrics?.cycleCount24h === 'number';
  const displayDate = (value?: string | null, withTime = true) => formatWorkshopDate(value, site?.timezone, withTime);

  return <section className="workshop-console" aria-label="Poste de supervision de l’atelier">
    <header className="workshop-console-bar">
      <div className="workshop-console-location">
        <Link to="/sites" aria-label="Retour aux sites"><ArrowLeftIcon size={18} aria-hidden="true" /></Link>
        <div><span>ATELIER · {site?.timezone ?? 'UTC'}</span><h2>{site?.name ?? 'Atelier'}</h2></div>
      </div>
      <div className="workshop-console-context">
        <span><small>HORODATAGE SÉLECTIONNÉ</small><strong>{displayDate(selectedReplayAt)}</strong></span>
      </div>
      {feature3dEnabled ? <div className="workshop-console-modes" role="group" aria-label="Mode de visualisation">
        <button type="button" aria-pressed={viewMode === '2d'} className={viewMode === '2d' ? 'active' : ''} onClick={() => onViewModeChange('2d')}>2D</button>
        <button type="button" aria-pressed={viewMode === '3d'} className={viewMode === '3d' ? 'active' : ''} onClick={() => onViewModeChange('3d')}>3D</button>
      </div> : <span className="workshop-console-mode-static">Plan 2D</span>}
    </header>

    <section className="workshop-console-summary" aria-label="Résumé du parc à l’horodatage choisi">
      <div><span>EN PRODUCTION</span><strong>{summaryUnavailable ? 'N/D' : <>{running}<small> / {machines.length}</small></>}</strong><i className="summary-bar summary-bar-running" aria-hidden="true" /></div>
      <div><span>À SURVEILLER</span><strong>{summaryUnavailable ? 'N/D' : warning}</strong><i className="summary-bar summary-bar-warning" aria-hidden="true" /></div>
      <div><span>ANOMALIES RECONSTRUITES</span><strong>{incidentsUnavailable ? 'N/D' : siteIncidentCount}</strong><i className="summary-bar summary-bar-signal" aria-hidden="true" /></div>
    </section>

    <div className="workshop-console-body">
      <section className="workshop-console-scene" aria-labelledby="workshop-scene-title">
        <div className="workshop-scene-heading">
          <div><span>VUE SPATIALE DU PARC</span><h3 id="workshop-scene-title">État des presses</h3></div>
          <div className={`workshop-scene-state${replayPending ? ' pending' : ''}`}><i aria-hidden="true" />{replayPending ? 'Mise à jour' : 'Lecture historique'}<strong>{displayDate(replayAt)}</strong></div>
        </div>
        <p className="visually-hidden" role="status" aria-live="polite">{replayPending ? 'Mise à jour de la borne historique.' : `Données chargées au ${displayDate(replayAt)}.`}</p>
        {sourceCutoffPartial ? <p className="workshop-inline-alert">Borne partielle : certaines presses n’ont pas fourni leur dernier cycle.</p> : null}
        {statusDataInconsistent ? <p className="workshop-inline-alert">Réponse temporelle incohérente pour une ou plusieurs presses. Les valeurs concernées restent inconnues.</p> : null}
        {threeDUnavailable ? <p className="workshop-inline-alert">Vue 3D indisponible. Le plan 2D reste actif avec la même sélection et la même borne.</p> : null}
        {timelineUnavailable ? <p className="workshop-inline-alert">La tendance agrégée est indisponible. Le replay conserve sa fenêtre source.</p> : null}
        <div className={`workshop-visual workshop-visual-${viewMode}`}>{visualization}</div>
      </section>

      <aside className="workshop-console-inspector" aria-label="Détail de la presse sélectionnée">
        <div className="workshop-inspector-kicker"><span>ÉQUIPEMENT SÉLECTIONNÉ</span><StatusBadge value={status ?? activeMachine?.status} /></div>
        <div className="workshop-inspector-title"><small>{activeMachine?.brand ?? 'Presse industrielle'}</small><h3>{activeMachine?.name ?? 'Aucune sélection'}</h3><p>{activeMachine?.erpRef ? `ERP · ${activeMachine.erpRef}` : 'Sélectionnez une presse sur le plan'}</p></div>
        {statusLoading ? <p className="helper-status">Lecture des statuts historiques…</p> : null}
        {statusUnavailable ? <p className="helper-error">Statut historique indisponible pour une partie du parc.</p> : null}
        {activeMachine ? <>
          <dl className="workshop-inspector-metrics">
            <div><dt>{cyclesAvailable ? 'Cycles sur 24 h' : 'TRS'}</dt><dd>{cyclesAvailable ? formatNumber(activeMachine.metrics?.cycleCount24h, 0) : formatPercent(activeMachine.metrics?.trs)}</dd><small>au point sélectionné</small></div>
            <div><dt>Rebuts</dt><dd>{formatPercent(scrapRate)}</dd><small>{scrap ?? 'N/D'} pièces · période</small></div>
            <div><dt>{activeMachine.lastCycleAt ? 'Dernier cycle' : 'Cycle moyen'}</dt><dd>{activeMachine.lastCycleAt ? displayDate(activeMachine.lastCycleAt) : `${formatNumber(activeMachine.metrics?.cycleTimeS, 2)} s`}</dd><small>{activeMachine.lastCycleAt ? 'dernier cycle observé' : 'au point sélectionné'}</small></div>
            <div><dt>OF courant</dt><dd>{activeMachine.metrics?.currentOrderId ?? 'N/D'}</dd><small>ordre de fabrication</small></div>
          </dl>
          <section className="workshop-inspector-section">
            <header><span>ANOMALIES RECONSTRUITES</span><strong>{incidentsUnavailable ? 'N/D' : machineIncidents.length.toString().padStart(2, '0')}</strong></header>
            {incidentsUnavailable ? <p className="helper-error">Anomalies indisponibles à cet horodatage.</p> : machineIncidents.length === 0 ? <p>Aucune anomalie reconstruite à cet horodatage.</p> : <div className="workshop-signal-list">{machineIncidents.slice(0, 4).map((incident) => <Link to={`/incidents/${incident.id}`} key={incident.id}><i className={`event-state event-state-${incident.severity}`} aria-hidden="true" /><span><strong>{incidentSymptomLabel(incident.symptom)}</strong><small>{displayDate(incident.started_at)} · {incidentSeverityLabel(incident.severity)}</small></span><ArrowUpRightIcon size={16} aria-hidden="true" /></Link>)}</div>}
          </section>
          <section className="workshop-inspector-section">
            <header><span>QUALITÉ SUR LA PÉRIODE</span></header>
            {replayPending ? <p className="helper-status">Mise à jour de la borne qualité…</p> : !hasQualityWindow ? <p>Déplacez le replay pour ouvrir une période de calcul.</p> : qualityUnavailable ? <p className="helper-error">Métriques qualité indisponibles.</p> : qualityLoading ? <p className="helper-status">Lecture de la qualité…</p> : typeof qualityTotal !== 'number' || qualityTotal <= 0 ? <p>Aucune observation qualité dans cette période.</p> : typeof scrapRate !== 'number' ? <p className="helper-error">Réponse qualité incomplète pour cette période.</p> : <div className={`workshop-quality ${scrapRate > .1 ? 'danger' : ''}`}><strong>{formatPercent(scrapRate)}</strong><span>{formatNumber(qualityTotal, 0)} observations</span></div>}
          </section>
          <ProcessDriftPanel api={processDriftApi} siteId={processDriftSiteId} cycles={processDriftCycles} cyclesLoading={processDriftCyclesLoading} cyclesError={processDriftCyclesError} onRetryCycles={onProcessDriftCyclesRetry} machineName={activeMachine.name} />
        </> : null}
      </aside>
    </div>

    <footer className="workshop-console-timeline">
      <div className="workshop-timeline-heading"><div><span>REPLAY TEMPOREL</span><strong>{displayDate(selectedReplayAt)}</strong></div><p>{replayPending ? `Données encore affichées au ${displayDate(replayAt)}.` : 'La carte, l’inspecteur et les anomalies partagent la borne chargée.'}</p></div>
      <WorkshopTrend points={timeline} incidents={timelineIncidents} range={range} replayPercent={replayPercent} unavailable={timelineUnavailable} loading={timelineLoading} />
      <p id="workshop-replay-description" className="visually-hidden">Période du {displayDate(range.start)} au {displayDate(range.end)}.</p>
      <div className="workshop-timeline-controls">
        <button type="button" aria-label="Revenir au début de la période" onClick={() => onReplayChange(0)}><SkipBackIcon size={18} aria-hidden="true" /></button>
        <time>{displayDate(range.start)}</time>
        <input type="range" min="0" max="100" value={replayPercent} onChange={(event) => onReplayChange(Number(event.target.value))} aria-label="Position dans la période historique" aria-valuetext={displayDate(selectedReplayAt)} aria-describedby="workshop-replay-description" />
        <time>{displayDate(range.end)}</time>
        <button type="button" aria-label="Aller à la fin de la période" onClick={() => onReplayChange(100)}><SkipForwardIcon size={18} aria-hidden="true" /></button>
      </div>
    </footer>
  </section>;
}
