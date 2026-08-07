import { ArrowLeftIcon } from '@phosphor-icons/react/ArrowLeft';
import { useQueries, useQuery } from '@tanstack/react-query';
import { Component, lazy, Suspense, useEffect, useMemo, useState, type ReactNode } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useApi } from '../App';
import type { Machine, MachineStatus } from '../lib/api';
import { WorkshopMap } from '../components/WorkshopMap';
import { WorkshopWorkspace, type WorkshopViewMode } from '../components/WorkshopWorkspace';
import { EmptyPanel, StatePanel } from '../components/Ui';

const EMPTY_REPLAY_END = '1970-01-01T04:00:00Z';
const SOURCE_DISCOVERY_AS_OF = '9999-12-31T23:59:59Z';
const REPLAY_WINDOW_MS = 4 * 60 * 60 * 1000;
const EMPTY_TIMELINE: Array<{ timestamp: string }> = [];
const EMPTY_MACHINES: Machine[] = [];
const Workshop3D = lazy(() => import('../components/Workshop3D').then((module) => ({ default: module.Workshop3D })));

class Workshop3DErrorBoundary extends Component<{ children: ReactNode; fallback: ReactNode; onError: () => void }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() { return { failed: true }; }

  componentDidCatch() { this.props.onError(); }

  render() { return this.state.failed ? this.props.fallback : this.props.children; }
}

function isoAtPercent(start: string, end: string, percent: number): string {
  const startMs = new Date(start).getTime();
  const endMs = new Date(end).getTime();
  return new Date(startMs + ((endMs - startMs) * percent) / 100).toISOString();
}

function statusResponseIsConsistent(response: MachineStatus, machineId: number, requestedAt: string): boolean {
  const requestedAtMs = new Date(requestedAt).getTime();
  const responseAtMs = new Date(response.asOf).getTime();
  const lastCycleAtMs = response.lastCycleAt ? new Date(response.lastCycleAt).getTime() : Number.NaN;
  if (response.machineId !== machineId || !Number.isFinite(requestedAtMs) || !Number.isFinite(responseAtMs) || responseAtMs > requestedAtMs + 1000) return false;
  if (response.lastCycleAt && !Number.isFinite(lastCycleAtMs)) return false;
  return !response.lastCycleAt || lastCycleAtMs <= responseAtMs + 1000;
}

function replayWindow(cutoff?: string | null): { start: string; end: string } {
  const parsed = cutoff ? new Date(cutoff).getTime() : Number.NaN;
  const endMs = Number.isFinite(parsed) ? parsed : new Date(EMPTY_REPLAY_END).getTime();
  return {
    start: new Date(endMs - REPLAY_WINDOW_MS).toISOString(),
    end: new Date(endMs).toISOString(),
  };
}

export function WorkshopPage() {
  const { siteId: siteIdParam } = useParams();
  const siteId = Number(siteIdParam);
  const api = useApi();
  const navigate = useNavigate();
  const [selectedMachineId, setSelectedMachineId] = useState<number>();
  const [replayPercent, setReplayPercent] = useState(50);
  const feature3dEnabled = import.meta.env.VITE_ENABLE_3D === 'true';
  const [viewMode, setViewMode] = useState<WorkshopViewMode>(feature3dEnabled ? '3d' : '2d');
  const [threeDUnavailable, setThreeDUnavailable] = useState(false);

  const siteQuery = useQuery({
    queryKey: ['site', siteId],
    queryFn: async () => {
      try {
        return await api.getSite(siteId);
      } catch {
        const sites = await api.getSites();
        const site = sites.find((item) => item.id === siteId);
        if (!site) throw new Error('Site introuvable.');
        return site;
      }
    },
    enabled: Number.isFinite(siteId),
  });
  const machinesQuery = useQuery({
    queryKey: ['machines', siteId],
    queryFn: () => api.getMachines(siteId),
    enabled: Number.isFinite(siteId),
  });
  const machines = machinesQuery.data ?? EMPTY_MACHINES;
  const activeMachineId = selectedMachineId ?? machines[0]?.id;

  useEffect(() => {
    if (selectedMachineId !== undefined && machinesQuery.isSuccess && !machines.some((machine) => machine.id === selectedMachineId)) {
      setSelectedMachineId(undefined);
    }
  }, [machines, machinesQuery.isSuccess, selectedMachineId]);

  const incidentsQuery = useQuery({
    queryKey: ['site-incidents', siteId],
    queryFn: () => api.getIncidents({ siteId }),
    enabled: Number.isFinite(siteId),
    retry: false,
  });
  const discoveryAsOf = siteQuery.data?.lastImportAt ?? SOURCE_DISCOVERY_AS_OF;
  const sourceCutoffQueries = useQueries({
    queries: machines.map((machine) => ({
      queryKey: ['machine-source-cutoff', machine.id, discoveryAsOf],
      queryFn: () => api.getMachineStatus(machine.id, discoveryAsOf),
      enabled: machinesQuery.isSuccess,
      retry: false,
      staleTime: 60_000,
    })),
  });
  const sourceCandidates = [
    ...sourceCutoffQueries.flatMap((query, index) => query.data && statusResponseIsConsistent(query.data, machines[index].id, discoveryAsOf) && query.data.lastCycleAt ? [query.data.lastCycleAt] : []),
    ...(incidentsQuery.data ?? []).map((incident) => incident.data_cutoff ?? incident.ended_at ?? incident.started_at),
  ].filter((value): value is string => typeof value === 'string' && Number.isFinite(new Date(value).getTime()));
  sourceCandidates.sort((left, right) => new Date(left).getTime() - new Date(right).getTime());
  const sourceAnchor = sourceCandidates[sourceCandidates.length - 1];
  const sourceDiscoveryLoading = machines.length > 0 && (sourceCutoffQueries.some((query) => query.isPending) || incidentsQuery.isPending);
  const sourceStatusDiscoveryPartial = sourceCutoffQueries.some((query, index) => query.isError || Boolean(query.data && !statusResponseIsConsistent(query.data, machines[index].id, discoveryAsOf)));
  const sourceDiscoveryUnavailable = machines.length > 0 && !sourceDiscoveryLoading && !sourceAnchor;
  const replayReady = Boolean(sourceAnchor) && !sourceDiscoveryLoading;
  const requestedRange = useMemo(() => replayWindow(sourceAnchor), [sourceAnchor]);

  const timelineQuery = useQuery({
    queryKey: ['machine-timeline', activeMachineId, requestedRange.start, requestedRange.end],
    queryFn: () => api.getMachineTimeline(activeMachineId as number, requestedRange.start, requestedRange.end),
    enabled: activeMachineId !== undefined && replayReady,
  });
  const rawTimeline = timelineQuery.data?.points ?? EMPTY_TIMELINE;
  const range = useMemo(() => {
    const requestedStartMs = new Date(requestedRange.start).getTime();
    const requestedEndMs = new Date(requestedRange.end).getTime();
    const responseStartMs = new Date(timelineQuery.data?.from ?? requestedRange.start).getTime();
    const responseEndMs = new Date(timelineQuery.data?.to ?? requestedRange.end).getTime();
    const startMs = Math.max(requestedStartMs, Number.isFinite(responseStartMs) ? responseStartMs : requestedStartMs);
    const endMs = Math.min(requestedEndMs, Number.isFinite(responseEndMs) ? responseEndMs : requestedEndMs);
    return startMs < endMs ? { start: new Date(startMs).toISOString(), end: new Date(endMs).toISOString() } : requestedRange;
  }, [requestedRange, timelineQuery.data?.from, timelineQuery.data?.to]);
  const timeline = useMemo(() => {
    const startMs = new Date(range.start).getTime();
    const endMs = new Date(range.end).getTime();
    return rawTimeline.filter((point) => {
      const timestamp = new Date(point.timestamp).getTime();
      return Number.isFinite(timestamp) && timestamp >= startMs && timestamp <= endMs;
    });
  }, [range.end, range.start, rawTimeline]);
  const replayAt = isoAtPercent(range.start, range.end, replayPercent);
  const selectedReplayAt = replayAt;
  const processDriftQuery = useQuery({
    queryKey: ['machine-cycles', activeMachineId, selectedReplayAt, 20],
    queryFn: () => api.getMachineCycles(activeMachineId as number, selectedReplayAt, 20),
    enabled: activeMachineId !== undefined && replayReady,
    retry: false,
  });
  // Timeline points are aggregates and stay confined to the trend chart. HDT
  // receives only the raw-cycle response, or abstains when it is empty.
  const processDriftCycles = processDriftQuery.data ?? [];
  const [statusAt, setStatusAt] = useState(replayAt);

  useEffect(() => {
    const timeout = window.setTimeout(() => setStatusAt(replayAt), 180);
    return () => window.clearTimeout(timeout);
  }, [replayAt]);

  const statusAtMs = new Date(statusAt).getTime();
  const statusInsideRange = statusAtMs >= new Date(range.start).getTime() && statusAtMs <= new Date(range.end).getTime();
  const statusQueries = useQueries({
    queries: machines.map((machine) => ({
      queryKey: ['machine-status', machine.id, statusAt],
      queryFn: () => api.getMachineStatus(machine.id, statusAt),
      enabled: replayReady && statusInsideRange,
      retry: false,
    })),
  });
  const statusDataInconsistent = replayReady && statusQueries.some((query, index) => query.data && !statusResponseIsConsistent(query.data, machines[index].id, statusAt));
  const historicalMachines = machines.map((machine, index) => {
    const query = statusQueries[index];
    if (query?.data && statusResponseIsConsistent(query.data, machine.id, statusAt)) {
      return { ...machine, status: query.data.status, metrics: query.data.metrics, asOf: query.data.asOf, freshnessS: query.data.freshnessS, lastCycleAt: query.data.lastCycleAt };
    }
    return { ...machine, status: undefined, metrics: undefined, lastCycleAt: undefined };
  });
  const replayMachine = historicalMachines.find((machine) => machine.id === activeMachineId);
  const statusUnavailable = replayReady && (statusQueries.some((query) => query.isError) || statusDataInconsistent);
  const statusLoading = replayReady && statusQueries.some((query) => query.isPending);
  const replayPending = replayAt !== statusAt || statusLoading;

  const hasQualityWindow = replayReady && statusInsideRange && statusAt === replayAt && statusAtMs > new Date(range.start).getTime();
  const qualityQuery = useQuery({
    queryKey: ['machine-quality', activeMachineId, range.start, statusAt],
    queryFn: () => api.getMachineQuality(activeMachineId as number, range.start, statusAt),
    enabled: activeMachineId !== undefined && hasQualityWindow,
    retry: false,
  });
  const rangeStartMs = new Date(range.start).getTime();
  const rangeEndMs = new Date(range.end).getTime();
  const windowIncidents = useMemo(() => {
    if (!replayReady) return [];
    return (incidentsQuery.data ?? []).filter((incident) => {
      const startedAt = new Date(incident.started_at).getTime();
      const endedAt = incident.ended_at ? new Date(incident.ended_at).getTime() : Number.POSITIVE_INFINITY;
      const dataCutoffAt = new Date(incident.data_cutoff).getTime();
      const reconstructedUntil = Math.min(endedAt, Number.isFinite(dataCutoffAt) ? dataCutoffAt : endedAt);
      return startedAt <= rangeEndMs && reconstructedUntil >= rangeStartMs;
    });
  }, [incidentsQuery.data, rangeEndMs, rangeStartMs, replayReady]);
  const visibleIncidents = useMemo(() => {
    if (!replayReady) return [];
    return (incidentsQuery.data ?? []).filter((incident) => {
      const startedAt = new Date(incident.started_at).getTime();
      const endedAt = incident.ended_at ? new Date(incident.ended_at).getTime() : Number.POSITIVE_INFINITY;
      const dataCutoffAt = new Date(incident.data_cutoff).getTime();
      const observableUntil = Math.min(endedAt, Number.isFinite(dataCutoffAt) ? dataCutoffAt : endedAt);
      return startedAt <= statusAtMs && observableUntil >= rangeStartMs && statusAtMs <= observableUntil;
    }).sort((left, right) => new Date(right.started_at).getTime() - new Date(left.started_at).getTime());
  }, [incidentsQuery.data, rangeStartMs, replayReady, statusAtMs]);
  const machineIncidents = visibleIncidents.filter((incident) => incident.machine_id === activeMachineId);
  const machineTimelineIncidents = windowIncidents.filter((incident) => incident.machine_id === activeMachineId);
  const signalCounts = useMemo(() => visibleIncidents.reduce<Record<number, number>>((counts, incident) => {
    counts[incident.machine_id] = (counts[incident.machine_id] ?? 0) + 1;
    return counts;
  }, {}), [visibleIncidents]);

  if (!Number.isFinite(siteId)) {
    return <section className="page"><StatePanel tone="error" title="Site invalide" text="L’identifiant du site n’est pas reconnu." action="Retour aux sites" onAction={() => navigate('/sites')} /></section>;
  }

  const map = <WorkshopMap machines={historicalMachines} selectedMachineId={activeMachineId} signalCounts={signalCounts} onSelect={(machine) => setSelectedMachineId(machine.id)} />;
  const threeDReady = feature3dEnabled && !threeDUnavailable;
  const handle3DUnavailable = () => { setThreeDUnavailable(true); setViewMode('2d'); };
  const visualization = viewMode === '3d' && threeDReady
    ? <Workshop3DErrorBoundary fallback={map} onError={handle3DUnavailable}>
        <Suspense fallback={<StatePanel tone="loading" title="Préparation de la vue spatiale" text="Chargement du rendu 3D local." />}>
          <Workshop3D machines={historicalMachines} selectedMachineId={activeMachineId} signalCounts={signalCounts} onSelect={(machine) => setSelectedMachineId(machine.id)} onUnavailable={handle3DUnavailable} />
        </Suspense>
      </Workshop3DErrorBoundary>
    : map;
  const workspaceReady = replayReady && siteQuery.isSuccess && machinesQuery.isSuccess && machines.length > 0;

  return <section className={`page page-wide workshop-page${workspaceReady ? ' workshop-page-ready' : ''}`}>
    {!workspaceReady ? <div className="page-intro workshop-intro"><div><Link className="back-link" to="/sites"><ArrowLeftIcon size={17} aria-hidden="true" />Tous les sites</Link><p className="eyebrow">ATELIER · {siteQuery.data?.timezone ?? 'UTC'}</p><h2>{siteQuery.data?.name ?? 'Chargement du site…'}</h2><p className="muted">Le plan, les statuts et le replay sont préparés à partir des dernières données source disponibles.</p></div></div> : null}

    {siteQuery.isError ? <StatePanel tone="error" title="Site indisponible" text={siteQuery.error instanceof Error ? siteQuery.error.message : 'Impossible de charger ce site.'} action="Réessayer" onAction={() => siteQuery.refetch()} /> : null}
    {machinesQuery.isPending ? <StatePanel tone="loading" title="Chargement des presses" text="Le plan atelier est en cours de préparation." /> : null}
    {machinesQuery.isError ? <StatePanel tone="error" title="Machines indisponibles" text={machinesQuery.error instanceof Error ? machinesQuery.error.message : 'Impossible de récupérer les machines.'} action="Réessayer" onAction={() => machinesQuery.refetch()} /> : null}
    {sourceDiscoveryLoading ? <StatePanel tone="loading" title="Recherche de la borne source" text="Le dernier horodatage des cycles et incidents est en cours de lecture." /> : null}
    {sourceDiscoveryUnavailable ? <StatePanel tone="warning" title="Replay indisponible" text="Aucun horodatage de donnée source n’est disponible. L’heure d’import n’est pas utilisée comme substitut." action="Réessayer" onAction={() => { sourceCutoffQueries.forEach((query) => query.refetch()); incidentsQuery.refetch(); }} /> : null}
    {!machinesQuery.isPending && !machinesQuery.isError && machines.length === 0 ? <EmptyPanel title="Aucune presse sur ce site" text="Le catalogue machine est vide pour ce périmètre." /> : null}

    {workspaceReady ? <WorkshopWorkspace
      site={siteQuery.data}
      machines={historicalMachines}
      activeMachine={replayMachine}
      machineIncidents={machineIncidents}
      timelineIncidents={machineTimelineIncidents}
      siteIncidentCount={visibleIncidents.length}
      incidentsUnavailable={incidentsQuery.isError}
      statusUnavailable={statusUnavailable}
      statusLoading={statusLoading}
      statusDataInconsistent={statusDataInconsistent}
      sourceCutoffPartial={sourceStatusDiscoveryPartial}
      threeDUnavailable={threeDUnavailable}
      qualityUnavailable={qualityQuery.isError}
      qualityLoading={qualityQuery.isPending}
      hasQualityWindow={hasQualityWindow}
      timelineUnavailable={timelineQuery.isError}
      timelineLoading={timelineQuery.isPending}
      status={replayMachine?.status}
      scrapRate={qualityQuery.data?.scrapRate}
      scrap={qualityQuery.data?.scrap}
      qualityTotal={qualityQuery.data?.total}
      replayAt={statusAt}
      selectedReplayAt={selectedReplayAt}
      replayPending={replayPending}
      range={range}
      replayPercent={replayPercent}
      timeline={timeline}
      processDriftApi={api}
      processDriftSiteId={siteId}
      processDriftCycles={processDriftCycles}
      processDriftCyclesLoading={processDriftQuery.isPending}
      processDriftCyclesError={processDriftQuery.isError ? (processDriftQuery.error instanceof Error ? processDriftQuery.error : new Error('Impossible de récupérer les cycles bruts.')) : null}
      onProcessDriftCyclesRetry={() => processDriftQuery.refetch()}
      viewMode={viewMode}
      feature3dEnabled={threeDReady}
      visualization={visualization}
      onReplayChange={setReplayPercent}
      onViewModeChange={setViewMode}
    /> : null}
  </section>;
}
