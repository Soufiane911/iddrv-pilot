import { ArchiveIcon } from '@phosphor-icons/react/Archive';
import { ArrowDownIcon } from '@phosphor-icons/react/ArrowDown';
import { HourglassIcon } from '@phosphor-icons/react/Hourglass';
import { WarningIcon } from '@phosphor-icons/react/Warning';
import { useQuery } from '@tanstack/react-query';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useApi } from '../App';
import { ShowroomInspector } from '../features/showroom/ShowroomInspector';
import { ShowroomTour } from '../features/showroom/ShowroomTour';
import { ShowroomWorkshop, type ShowroomViewMode } from '../features/showroom/ShowroomWorkshop';
import { guidedTourSteps, SHOWROOM_REPLAY_START, SHOWROOM_SIMULATED_AS_OF } from '../features/showroom/showroomModel';
import type { Incident, Machine } from '../lib/api';
import '../features/showroom/showroom.css';

function resolveScenarioMachine(machines: Machine[], incidents: Incident[]): { machine?: Machine; incident?: Incident; fallback: boolean } {
  const incident = incidents.find((item) => item.id.toLowerCase().includes('s001') || (item.production_order_id === 'OF-2025-0012' && item.defect_type === 'short_shot'));
  if (!incident) return { machine: machines[0], fallback: Boolean(machines[0]) };
  const linked = machines.find((machine) => machine.id === incident.machine_id || machine.erpRef === incident.machine_erp_ref);
  return { machine: linked ?? machines[0], incident, fallback: !linked && Boolean(machines[0]) };
}

export function ShowroomPage() {
  const api = useApi();
  const [selectedMachineId, setSelectedMachineId] = useState<number>();
  const [tourActive, setTourActive] = useState(false);
  const [tourPaused, setTourPaused] = useState(false);
  const [tourStep, setTourStep] = useState(0);
  const [viewMode, setViewMode] = useState<ShowroomViewMode>(() => window.matchMedia?.('(max-width: 780px)').matches ? '2d' : 'iso');
  const [mobile, setMobile] = useState(() => window.matchMedia?.('(max-width: 780px)').matches ?? false);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [focusRequest, setFocusRequest] = useState(0);
  const lastMachineTrigger = useRef<HTMLElement | null>(null);
  const manualSelection = useRef(false);

  useEffect(() => {
    const query = window.matchMedia?.('(max-width: 780px)');
    if (!query) return;
    const change = (event: MediaQueryListEvent) => { setMobile(event.matches); if (event.matches) setViewMode('2d'); else setSheetOpen(false); };
    query.addEventListener?.('change', change);
    return () => query.removeEventListener?.('change', change);
  }, []);

  const sites = useQuery({ queryKey: ['showroom-sites'], queryFn: () => api.getSites(), retry: false });
  const site = sites.data?.[0];
  const machines = useQuery({ queryKey: ['showroom-machines', site?.id], queryFn: () => api.getMachines(site!.id), enabled: Boolean(site), retry: false });
  const incidents = useQuery({ queryKey: ['showroom-incidents', site?.id], queryFn: () => api.getIncidents({ siteId: site!.id }), enabled: Boolean(site), retry: false });
  const machineList = useMemo(() => machines.data ?? [], [machines.data]);
  const scenario = useMemo(() => resolveScenarioMachine(machineList, incidents.data ?? []), [machineList, incidents.data]);
  const selected = machineList.find((machine) => machine.id === selectedMachineId) ?? scenario.machine;

  useEffect(() => {
    if (!manualSelection.current && scenario.machine) setSelectedMachineId(scenario.machine.id);
  }, [scenario.machine]);

  const simulatedAsOf = tourActive ? SHOWROOM_SIMULATED_AS_OF[Math.min(Math.max(tourStep, 0), SHOWROOM_SIMULATED_AS_OF.length - 1)] : undefined;
  const machineStatus = useQuery({
    queryKey: ['showroom-machine-status', selected?.id, simulatedAsOf],
    queryFn: () => api.getMachineStatus(selected!.id, simulatedAsOf),
    enabled: Boolean(selected),
    retry: false,
    staleTime: 30_000,
  });
  const historicalIncidents = useQuery({
    queryKey: ['showroom-incidents-replay', site?.id, simulatedAsOf],
    queryFn: () => api.getIncidents({ siteId: site!.id, from: SHOWROOM_REPLAY_START, to: simulatedAsOf }),
    enabled: Boolean(site && simulatedAsOf),
    retry: false,
  });
  const historicalRequested = Boolean(simulatedAsOf);
  const statusAligned = Boolean(simulatedAsOf && machineStatus.data?.asOf === simulatedAsOf);
  const statusLoading = historicalRequested && !statusAligned && !machineStatus.isError;
  const presentedMachine = selected && machineStatus.data && (!historicalRequested || statusAligned)
    ? { ...selected, status: machineStatus.data.status, asOf: machineStatus.data.asOf, freshnessS: machineStatus.data.freshnessS, metrics: machineStatus.data.metrics }
    : selected;
  const timestampOrigin = historicalRequested ? (statusAligned ? 'historical' : 'source') : (presentedMachine?.asOf ? 'source' : 'simulated');
  const historicalIncidentsUnavailable = historicalRequested && historicalIncidents.isError;
  const displayedIncidents = historicalRequested && !historicalIncidentsUnavailable ? (historicalIncidents.data ?? []) : historicalRequested ? [] : (incidents.data ?? []);
  const selectedIncidents = displayedIncidents.filter((incident) => incident.machine_id === selected?.id || incident.machine_erp_ref === selected?.erpRef);
  const linkedScenarioMachineId = scenario.fallback ? undefined : scenario.machine?.id;
  const scenarioEvidenceAvailable = !historicalIncidentsUnavailable && (!historicalRequested || Boolean(scenario.incident && displayedIncidents.some((incident) => incident.id === scenario.incident?.id)));
  const scenarioMachineLabel = scenario.fallback ? 'Fallback de démonstration · aucune preuve S001 liée' : scenario.machine ? `${scenario.machine.name} · ERP ${scenario.machine.erpRef ?? 'non renseigné'}` : undefined;
  const tourFocus = guidedTourSteps[Math.min(Math.max(tourStep, 0), guidedTourSteps.length - 1)].focus;

  useEffect(() => {
    if (!mobile || !sheetOpen) return;
    const regions = Array.from(document.querySelectorAll<HTMLElement>('.sidebar, .showroom-hero, .showroom-workshop, .showroom-tour-rail, .showroom-data-note'));
    const previous = regions.map((region) => ({ region, ariaHidden: region.getAttribute('aria-hidden'), inert: region.hasAttribute('inert') }));
    regions.forEach((region) => { region.setAttribute('inert', ''); region.setAttribute('aria-hidden', 'true'); });
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { previous.forEach(({ region, ariaHidden, inert }) => { if (!inert) region.removeAttribute('inert'); if (ariaHidden === null) region.removeAttribute('aria-hidden'); else region.setAttribute('aria-hidden', ariaHidden); }); document.body.style.overflow = previousOverflow; };
  }, [mobile, sheetOpen]);

  useEffect(() => {
    if (!mobile || !tourActive || !['impact', 'investigation', 'action', 'estimate'].includes(tourFocus)) return;
    setSheetOpen(true);
  }, [mobile, tourActive, tourFocus]);

  const selectMachine = (machine: Machine, trigger: HTMLElement) => {
    manualSelection.current = true;
    lastMachineTrigger.current = trigger;
    setSelectedMachineId(machine.id);
    setFocusRequest((value) => value + 1);
    if (mobile) setSheetOpen(true);
  };
  const retry = () => { void sites.refetch(); if (site) { void machines.refetch(); void incidents.refetch(); } };
  const error = sites.error ?? machines.error ?? incidents.error;
  const pending = sites.isPending || (Boolean(site) && (machines.isPending || incidents.isPending));
  const startTour = () => { manualSelection.current = false; if (scenario.machine) setSelectedMachineId(scenario.machine.id); setTourStep(0); setTourPaused(false); setTourActive(true); };
  const exploreWorkshop = () => document.getElementById('atelier-panel')?.scrollIntoView({ behavior: 'smooth', block: 'start' });

  return <div className="showroom-page">
    <header className="showroom-hero" id="atelier">
      <div className="showroom-hero-copy"><div className="showroom-hero-meta"><span className="showroom-demo-label">Données fictives</span><span className="showroom-site-context">Site courant · {site?.name ?? 'chargement'}</span></div><p className="showroom-kicker">IDDRV · Démonstrateur industriel</p><h1>Du signal machine à la preuve exploitable</h1><p className="showroom-hero-description">Rejouez un incident, comparez la baseline et vérifiez chaque hypothèse avant toute décision.</p></div>
      <div className="showroom-hero-actions"><button type="button" className="showroom-primary" onClick={startTour}>Démarrer la visite</button><button type="button" className="showroom-secondary-link" onClick={exploreWorkshop}>Explorer l’atelier <ArrowDownIcon size={18} aria-hidden="true" /></button><span className="showroom-hero-step">7 étapes · scénario S001</span></div>
    </header>
    {pending && <div className="showroom-state-panel" role="status"><span className="state-mark" aria-hidden="true"><HourglassIcon size={18} /></span><div><strong>Préparation de l’atelier</strong><p>Chargement du site courant, du catalogue et des incidents associés.</p></div></div>}
    {error && <div className="showroom-state-panel showroom-error" role="alert"><span className="state-mark" aria-hidden="true"><WarningIcon size={18} /></span><div><strong>Données indisponibles</strong><p>{error instanceof Error ? error.message : 'Impossible de charger la démonstration.'}</p><button type="button" onClick={retry}>Réessayer</button></div></div>}
    {!pending && !error && !site && <div className="showroom-state-panel"><span className="state-mark" aria-hidden="true"><ArchiveIcon size={18} /></span><div><strong>Aucun site disponible</strong><p>Ajoutez un site pour préparer le showroom.</p></div></div>}
    {!pending && !error && site && machineList.length === 0 && <div className="showroom-state-panel"><span className="state-mark" aria-hidden="true"><ArchiveIcon size={18} /></span><div><strong>Atelier vide</strong><p>Aucune machine n’est associée à {site.name}.</p></div></div>}
    {!pending && !error && machineList.length > 0 && <div className="showroom-command-center">
      <ShowroomWorkshop machines={machineList} selectedMachineId={selected?.id} scenarioMachineId={linkedScenarioMachineId} scenarioFallback={scenario.fallback} viewMode={viewMode} onViewModeChange={setViewMode} tourStepIndex={tourStep} tourActive={tourActive} onSelect={selectMachine} />
      {tourActive && <div className="showroom-tour-rail"><ShowroomTour active paused={tourPaused} stepIndex={tourStep} onActiveChange={setTourActive} onPausedChange={setTourPaused} onStepChange={setTourStep} scenarioMachineLabel={scenarioMachineLabel} /></div>}
      <ShowroomInspector machine={presentedMachine} scenarioMachineId={linkedScenarioMachineId} evidenceAvailable={scenarioEvidenceAvailable} incidents={selectedIncidents} focus={tourFocus} tourActive={tourActive} focusRequest={focusRequest} mobile={mobile} open={!mobile || sheetOpen} onClose={() => setSheetOpen(false)} restoreFocusTo={lastMachineTrigger.current} timestampOrigin={timestampOrigin} statusUnavailable={machineStatus.isError} statusLoading={statusLoading} historicalRequested={historicalRequested} incidentsUnavailable={historicalIncidentsUnavailable} />
    </div>}
    {mobile && sheetOpen && <button type="button" className="showroom-scrim" aria-label="Fermer les détails de la machine" onClick={() => setSheetOpen(false)} />}
    <footer id="donnees" className="showroom-data-note"><div><strong>Données présentées</strong><span>Provenance explicitement qualifiée</span></div><p>Catalogue machine et incidents : données fournies par l’API v1 du site courant.</p><p>OPC UA : aperçu feuille de route, non connecté. Aucune commande machine n’est envoyée.</p><p>Preuves, traces, coûts et résultats S001 : points fictifs de démonstration, sans action persistée ni gain validé.</p></footer>
  </div>;
}
