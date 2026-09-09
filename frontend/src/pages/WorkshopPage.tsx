import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useApi } from '../App';
import { authRoleForSite, type Machine } from '../lib/api';
import { StatePanel } from '../components/Ui';
import { WorkshopMap } from '../components/WorkshopMap';
import { Workshop3D } from '../components/Workshop3D';
import { GatewayCard } from '../components/workshop/GatewayCard';
import { MachineConnectionPanel } from '../components/workshop/MachineConnectionPanel';
import { PressCatalogTable } from '../components/workshop/PressCatalogTable';
import { PressFormDrawer } from '../components/workshop/PressFormDrawer';
import { SiteSetupChecklist } from '../components/workshop/SiteSetupChecklist';

const effectiveLabels: Record<string, string> = {
  stopped: 'Arrêté', starting: 'Démarrage', active: 'Actif', blocked: 'Bloqué',
};
const desiredLabels: Record<string, string> = { stopped: 'arrêt demandé', active: 'activation demandée' };

export function WorkshopPage() {
  const { siteId: rawSiteId } = useParams();
  const siteId = Number(rawSiteId);
  const api = useApi();
  const navigate = useNavigate();
  const cache = useQueryClient();
  const [selectedMachineId, setSelectedMachineId] = useState<number>();
  const [editingMachine, setEditingMachine] = useState<Machine | null>(null);
  const [pressFormOpen, setPressFormOpen] = useState(false);
  const [gatewayOpen, setGatewayOpen] = useState(false);

  const site = useQuery({ queryKey: ['site', siteId], queryFn: () => api.getSite(siteId), enabled: Number.isFinite(siteId) });
  const machinesQuery = useQuery({ queryKey: ['machines', siteId], queryFn: () => api.getMachines(siteId), enabled: Number.isFinite(siteId) });
  const auth = useQuery({ queryKey: ['auth-me'], queryFn: api.getCurrentUser });
  const role = authRoleForSite(auth.data, Number.isFinite(siteId) ? siteId : undefined);
  const canConfigure = role === 'supervisor' || role === 'admin';
  const canImport = role === 'analyst' || canConfigure;
  const machines = machinesQuery.data ?? [];
  const activeMachines = machines.filter(machine => machine.lifecycleStatus !== 'archived');
  const selected = activeMachines.find(machine => machine.id === selectedMachineId) ?? activeMachines[0];
  const hdt = useQuery({
    queryKey: ['hdt-control', selected?.id],
    queryFn: () => api.getHdtControl(selected!.id),
    enabled: selected !== undefined,
    retry: false,
  });
  const [hdtError, setHdtError] = useState<string | null>(null);
  const hdtAction = useMutation({
    mutationFn: (action: 'activate' | 'stop') => action === 'activate' ? api.activateHdt(selected!.id) : api.stopHdt(selected!.id),
    onMutate: () => setHdtError(null),
    onSuccess: value => { setHdtError(null); cache.setQueryData(['hdt-control', selected?.id], value); },
    onError: error => setHdtError(error instanceof Error ? error.message : 'Action HDT refusée par l’API.'),
  });

  if (!Number.isFinite(siteId)) return <section className="page"><StatePanel tone="error" title="Site invalide" text="L’identifiant du site n’est pas reconnu." action="Retour aux sites" onAction={() => navigate('/sites')} /></section>;
  if (site.isError) return <section className="page"><StatePanel tone="error" title="Site indisponible" text={site.error instanceof Error ? site.error.message : 'Impossible de charger ce site.'} action="Réessayer" onAction={() => site.refetch()} /></section>;
  if (machinesQuery.isPending) return <section className="page"><StatePanel tone="loading" title="Chargement de l’atelier" text="Lecture du catalogue des presses." /></section>;
  if (machinesQuery.isError) return <section className="page"><StatePanel tone="error" title="Atelier indisponible" text="Impossible de récupérer les presses." action="Réessayer" onAction={() => machinesQuery.refetch()} /></section>;

  const openNewPress = () => { setEditingMachine(null); setPressFormOpen(true); };
  const openEditPress = (machine: Machine) => { setSelectedMachineId(machine.id); setEditingMachine(machine); setPressFormOpen(true); };
  const refreshMachines = () => { setPressFormOpen(false); setEditingMachine(null); void cache.invalidateQueries({ queryKey: ['machines', siteId] }); };

  return <section className={`page page-wide workshop-page${activeMachines.length ? ' workshop-page-ready' : ''}`}>
    <div className="page-intro workshop-intro"><div><Link className="back-link" to="/sites">Tous les sites</Link><p className="eyebrow">ATELIER · {site.data?.timezone ?? 'UTC'}</p><h2>{site.data?.name ?? 'Atelier'}</h2><p className="muted">Parc et configuration des presses. Les données apparaissent uniquement après raccordement d’une source réelle.</p></div></div>
    <section className="workshop-visual" aria-label="Plan 2D de l’atelier"><WorkshopMap machines={activeMachines} selectedMachineId={selected?.id} signalCounts={{}} onSelect={machine => setSelectedMachineId(machine.id)} /></section>
    <section className="workshop-visual workshop-visual-3d" aria-label="Vue 3D de l’atelier"><Workshop3D machines={activeMachines} selectedMachineId={selected?.id} signalCounts={{}} onSelect={machine => setSelectedMachineId(machine.id)} /></section>
    {activeMachines.length === 0 ? <><p className="workshop-empty-note" role="status">Aucune presse configurée. Le plan reste vide jusqu’à l’ajout d’une presse réelle.</p><SiteSetupChecklist hasPresses={false} canConfigure={canConfigure} canImport={canImport} onAddPress={openNewPress} onConfigureGateway={() => setGatewayOpen(true)} onImportErp={() => navigate(`/imports?siteId=${siteId}`)} /></> : <>
      <section className="workshop-configuration-access" aria-label="Configuration de l’atelier"><div><p className="eyebrow">CONFIGURATION ATELIER</p><strong>Passerelle et mapping des presses</strong><p className="muted">Les identifiants et cycles sont lus depuis la passerelle configurée, jamais depuis une fixture d’interface.</p></div><button className="button-secondary" type="button" aria-expanded={gatewayOpen} aria-controls="workshop-gateway-panel" onClick={() => setGatewayOpen(open => !open)}>{gatewayOpen ? 'Masquer la configuration' : 'Configurer passerelle et mapping'}</button></section>
      {gatewayOpen && <div id="workshop-gateway-panel"><GatewayCard siteId={siteId} machines={activeMachines} canConfigure={canConfigure} /></div>}
      <PressCatalogTable machines={machines} canConfigure={canConfigure} onAddPress={openNewPress} onEditPress={openEditPress} />
      {selected && <section className="workshop-machine-sheet" aria-labelledby="selected-press-title"><h3 id="selected-press-title">{selected.name}</h3><p className="muted">Configuration de la presse et état HDT.</p><MachineConnectionPanel api={api} machine={selected} /><HdtControlPanel control={hdt.data} loading={hdt.isPending} error={hdtError} readError={hdt.isError} canConfigure={canConfigure} busy={hdtAction.isPending} onAction={action => hdtAction.mutate(action)} /></section>}
    </>}
    <PressFormDrawer api={api} siteId={siteId} machine={editingMachine} open={pressFormOpen} onClose={() => setPressFormOpen(false)} onSaved={refreshMachines} />
  </section>;
}

function HdtControlPanel({ control, loading, error, readError, canConfigure, busy, onAction }: { control?: import('../lib/api').HdtControl; loading: boolean; error: string | null; readError: boolean; canConfigure: boolean; busy: boolean; onAction: (action: 'activate' | 'stop') => void }) {
  if (loading) return <section className="hdt-control-summary" aria-label="Contrôle HDT"><strong>HDT</strong><span role="status">Lecture du statut HDT…</span></section>;
  if (readError || !control) return <section className="hdt-control-summary" aria-label="Contrôle HDT"><strong>HDT</strong><span role="alert">Statut HDT indisponible.</span></section>;
  const blocked = control.effectiveState === 'blocked';
  return <section className="hdt-control-summary" aria-label="Contrôle HDT" aria-live="polite"><strong>HDT</strong><span>Demande : {desiredLabels[control.desiredState] ?? control.desiredState}</span><span>État effectif : <b>{effectiveLabels[control.effectiveState] ?? control.effectiveState}</b></span>{blocked && <ul aria-label="Motifs de blocage">{control.blockingReasons.map(reason => <li key={reason}>{reason}</li>)}</ul>}<div><button className="button-secondary" type="button" disabled={!canConfigure || busy || control.effectiveState === 'active'} onClick={() => onAction('activate')}>Activer HDT</button><button className="button-ghost" type="button" disabled={!canConfigure || busy || control.effectiveState === 'stopped'} onClick={() => onAction('stop')}>Arrêter HDT</button></div>{error && <span role="alert">{error}</span>}{!canConfigure && <small>Commande réservée aux superviseurs et administrateurs.</small>}</section>;
}
