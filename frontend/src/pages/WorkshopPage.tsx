import { useQuery } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useApi } from '../App';
import { Workshop3D } from '../components/Workshop3D';
import { WorkshopMap } from '../components/WorkshopMap';
import { EmptyPanel, formatDate, formatNumber, formatPercent, MetricCard, SectionTitle, StatePanel, StatusBadge } from '../components/Ui';

const REPLAY_START = '2025-02-11T22:00:00Z';
const REPLAY_END = '2025-02-12T02:00:00Z';
const EMPTY_TIMELINE: Array<{ timestamp: string; status?: string | null }> = [];

function isoAtPercent(start: string, end: string, percent: number): string {
  const startMs = new Date(start).getTime();
  const endMs = new Date(end).getTime();
  return new Date(startMs + ((endMs - startMs) * percent) / 100).toISOString();
}

function closestPoint(points: Array<{ timestamp: string; status?: string | null }>, asOf: string) {
  if (!points.length) return undefined;
  const target = new Date(asOf).getTime();
  return points.reduce((closest, point) => Math.abs(new Date(point.timestamp).getTime() - target) < Math.abs(new Date(closest.timestamp).getTime() - target) ? point : closest);
}

export function WorkshopPage() {
  const { siteId: siteIdParam } = useParams();
  const siteId = Number(siteIdParam);
  const api = useApi();
  const navigate = useNavigate();
  const [selectedMachineId, setSelectedMachineId] = useState<number>();
  const [replayPercent, setReplayPercent] = useState(50);
  const [viewMode, setViewMode] = useState<'2d' | '3d'>('2d');

  const siteQuery = useQuery({ queryKey: ['site', siteId], queryFn: async () => { try { return await api.getSite(siteId); } catch { const sites = await api.getSites(); const site = sites.find((item) => item.id === siteId); if (!site) throw new Error('Site introuvable.'); return site; } }, enabled: Number.isFinite(siteId) });
  const machinesQuery = useQuery({ queryKey: ['machines', siteId], queryFn: () => api.getMachines(siteId), enabled: Number.isFinite(siteId) });
  const machines = machinesQuery.data ?? [];
  const activeMachineId = selectedMachineId ?? machines[0]?.id;
  const activeMachine = machines.find((machine) => machine.id === activeMachineId);
  const timelineQuery = useQuery({ queryKey: ['machine-timeline', activeMachineId], queryFn: () => api.getMachineTimeline(activeMachineId as number, REPLAY_START, REPLAY_END), enabled: activeMachineId !== undefined });
  const qualityQuery = useQuery({ queryKey: ['machine-quality', activeMachineId], queryFn: () => api.getMachineQuality(activeMachineId as number, REPLAY_START, REPLAY_END), enabled: activeMachineId !== undefined });
  const incidentsQuery = useQuery({ queryKey: ['site-incidents', siteId], queryFn: () => api.getIncidents({ siteId }), enabled: Number.isFinite(siteId) });
  const timeline = timelineQuery.data?.points ?? EMPTY_TIMELINE;
  const range = useMemo(() => {
    const sorted = timeline.map((point) => point.timestamp).filter(Boolean).sort();
    const start = timelineQuery.data?.from ?? sorted[0] ?? REPLAY_START;
    const end = timelineQuery.data?.to ?? sorted[sorted.length - 1] ?? REPLAY_END;
    return new Date(start).getTime() < new Date(end).getTime() ? { start, end } : { start: REPLAY_START, end: REPLAY_END };
  }, [timeline, timelineQuery.data?.from, timelineQuery.data?.to]);
  const replayAt = isoAtPercent(range.start, range.end, replayPercent);
  const replayPoint = closestPoint(timeline, replayAt);
  const machineIncidents = (incidentsQuery.data ?? []).filter((incident) => incident.machine_id === activeMachineId);
  const feature3dEnabled = import.meta.env.VITE_ENABLE_3D === 'true';

  if (!Number.isFinite(siteId)) return <section className="page"><StatePanel tone="error" title="Site invalide" text="L’identifiant du site n’est pas reconnu." action="Retour aux sites" onAction={() => navigate('/sites')} /></section>;
  return <section className="page page-wide workshop-page">
    <div className="page-intro workshop-intro"><div><Link className="back-link" to="/sites">← Tous les sites</Link><p className="eyebrow">ATELIER · {siteQuery.data?.timezone ?? 'UTC'}</p><h2>{siteQuery.data?.name ?? 'Chargement du site…'}</h2><p className="muted">Sélectionnez une presse pour consulter son contexte, ses métriques et ses incidents au temps choisi.</p></div><div className="view-switch" role="group" aria-label="Mode de visualisation">{feature3dEnabled && <><button type="button" className={viewMode === '2d' ? 'active' : ''} onClick={() => setViewMode('2d')}>Plan 2D</button><button type="button" className={viewMode === '3d' ? 'active' : ''} onClick={() => setViewMode('3d')}>Vue 3D</button></>}</div></div>
    {siteQuery.isError && <StatePanel tone="error" title="Site indisponible" text={siteQuery.error instanceof Error ? siteQuery.error.message : 'Impossible de charger ce site.'} action="Réessayer" onAction={() => siteQuery.refetch()} />}
    {machinesQuery.isPending && <StatePanel tone="loading" title="Chargement des presses" text="Le plan atelier est en cours de préparation." />}
    {machinesQuery.isError && <StatePanel tone="error" title="Machines indisponibles" text={machinesQuery.error instanceof Error ? machinesQuery.error.message : 'Impossible de récupérer les machines.'} action="Réessayer" onAction={() => machinesQuery.refetch()} />}
    {!machinesQuery.isPending && !machinesQuery.isError && machines.length === 0 && <EmptyPanel title="Aucune presse sur ce site" text="Le catalogue machine est vide pour ce périmètre." />}
    {!machinesQuery.isPending && !machinesQuery.isError && machines.length > 0 && <>
      <div className="workshop-grid"><section className="surface-card map-card"><SectionTitle eyebrow="PLAN ATELIER" title="État des presses"><span className="replay-stamp">Au {formatDate(replayAt)}</span></SectionTitle>{viewMode === '3d' ? <Workshop3D machines={machines} selectedMachineId={activeMachineId} onSelect={(machine) => setSelectedMachineId(machine.id)} /> : <WorkshopMap machines={machines} selectedMachineId={activeMachineId} onSelect={(machine) => setSelectedMachineId(machine.id)} />}</section>
        <aside className="surface-card machine-panel" aria-live="polite"><div className="machine-panel-head"><div><p className="eyebrow">PRESSE SÉLECTIONNÉE</p><h3>{activeMachine?.name ?? '—'}</h3><p className="muted">ERP {activeMachine?.erpRef ?? 'non renseigné'} · {activeMachine?.brand ?? 'marque non renseignée'}</p></div><StatusBadge value={replayPoint?.status ?? activeMachine?.status} /></div>{activeMachine ? <><div className="metric-grid metric-grid-two"><MetricCard label="TRS" value={formatPercent(activeMachine.metrics?.trs)} detail="valeur au temps choisi" tone={(activeMachine.metrics?.trs ?? 0) > .75 ? 'good' : 'warning'} /><MetricCard label="Rebuts" value={formatPercent(qualityQuery.data?.scrapRate ?? activeMachine.metrics?.scrapRate)} detail={`${qualityQuery.data?.scrap ?? '—'} pièces`} tone={(qualityQuery.data?.scrapRate ?? activeMachine.metrics?.scrapRate ?? 0) > .1 ? 'danger' : 'good'} /><MetricCard label="Cycle moyen" value={`${formatNumber(activeMachine.metrics?.cycleTimeS, 2)} s`} detail="process" /><MetricCard label="OF courant" value={activeMachine.metrics?.currentOrderId ?? '—'} detail="ordre de fabrication" /></div><div className="machine-panel-section"><h4>Incidents récents</h4>{incidentsQuery.isPending ? <p className="muted">Chargement…</p> : machineIncidents.length === 0 ? <p className="muted">Aucun incident sur cette presse.</p> : <ul className="compact-list">{machineIncidents.slice(0, 4).map((incident) => <li key={incident.id}><Link to={`/incidents/${incident.id}`}><span><strong>{incident.symptom.split('_').join(' ')}</strong><small>{formatDate(incident.started_at)}</small></span><span className={`severity severity-${incident.severity}`}>{incident.severity}</span></Link></li>)}</ul>}</div><div className="machine-panel-section"><h4>Qualité sur la période</h4>{qualityQuery.isError ? <p className="muted">Métriques qualité indisponibles.</p> : <div className="quality-inline"><strong>{formatPercent(qualityQuery.data?.scrapRate ?? activeMachine.metrics?.scrapRate)}</strong><span>taux de rebut</span></div>}</div></> : <p className="muted">Sélectionnez une presse sur le plan.</p>}</aside></div>
      <section className="surface-card replay-card"><SectionTitle eyebrow="REPLAY TEMPOREL" title="Rejouer la séquence"><span className="replay-range">{formatDate(range.start)} → {formatDate(range.end)}</span></SectionTitle><div className="replay-controls"><button type="button" aria-label="Revenir au début de la période" onClick={() => setReplayPercent(0)}>↤</button><input type="range" min="0" max="100" value={replayPercent} onChange={(event) => setReplayPercent(Number(event.target.value))} aria-label="Position dans la période historique" /><button type="button" aria-label="Aller à la fin de la période" onClick={() => setReplayPercent(100)}>↦</button></div><div className="replay-axis"><span>{formatDate(range.start)}</span><strong>{formatDate(replayAt)}</strong><span>{formatDate(range.end)}</span></div>{timelineQuery.isError && <p className="helper-error">Timeline indisponible : le curseur reste positionné sur la période de démonstration sans inventer de valeur.</p>}</section>
      {machineIncidents.length > 0 && <section className="surface-card incident-strip"><div><p className="eyebrow">À EXAMINER</p><h3>{machineIncidents.length} incident{machineIncidents.length > 1 ? 's' : ''} sur le site</h3><p className="muted">Le replay est positionné sur {formatDate(replayAt)}. Ouvrez un incident pour suivre les preuves avant / pendant / après.</p></div><Link className="button-primary" to={`/incidents/${machineIncidents[0].id}`}>Voir l’incident prioritaire →</Link></section>}
    </>}
  </section>;
}
