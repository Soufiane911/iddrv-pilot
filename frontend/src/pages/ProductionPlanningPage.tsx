import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useApi } from '../App';
import { ApiRequestError, authRoleForSite, type Machine, type PlanningSlot, type PlanningWeek } from '../lib/api';
import { StatePanel } from '../components/Ui';
import { ProductionAssignmentEditor } from '../components/planning/ProductionAssignmentEditor';
import { ProductionPlanningGrid } from '../components/planning/ProductionPlanningGrid';
import { ProductionWeekToolbar, type PlanningFilters } from '../components/planning/ProductionWeekToolbar';
import './productionPlanning.css';

function monday(value: Date): Date { const result = new Date(value); result.setHours(12, 0, 0, 0); const day = result.getDay() || 7; result.setDate(result.getDate() - day + 1); return result; }
function isoWeek(value: Date): string { const current = monday(value); const thursday = new Date(current); thursday.setDate(current.getDate() + 3); const first = new Date(thursday.getFullYear(), 0, 4); const firstMonday = monday(first); const number = Math.round((current.getTime() - firstMonday.getTime()) / 604800000) + 1; return `${thursday.getFullYear()}-W${String(number).padStart(2, '0')}`; }
function readable(error: unknown) { if (error instanceof ApiRequestError) { const labels: Record<string, string> = { week_start_required: 'La semaine sélectionnée est invalide.', press_slot_conflict: 'Un autre OF occupe déjà cette presse sur cet intervalle.', stale_row_version: 'Ce créneau a été modifié. Actualisez avant de réessayer.', slot_cancelled: 'Ce créneau est déjà annulé.', site_not_found: 'Ce site n’est plus disponible.' }; return labels[error.code] ?? error.message; } return error instanceof Error ? error.message : 'Le planning est indisponible.'; }

export function ProductionPlanningPage() {
  const { siteId: siteIdParam } = useParams();
  const siteId = Number(siteIdParam);
  const api = useApi();
  const navigate = useNavigate();
  const cache = useQueryClient();
  const [params, setParams] = useSearchParams();
  const initialWeek = params.get('week') ?? isoWeek(new Date());
  const [week, setWeek] = useState(initialWeek);
  const [filters, setFilters] = useState<PlanningFilters>({ machineId: '', order: '', collection: '', erp: '' });
  const [editorOpen, setEditorOpen] = useState(false);
  const [editing, setEditing] = useState<PlanningSlot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshedAt, setRefreshedAt] = useState<Date>();
  const [visible, setVisible] = useState(() => typeof document === 'undefined' || document.visibilityState === 'visible');
  const auth = useQuery({ queryKey: ['auth-me'], queryFn: api.getCurrentUser });
  const site = useQuery({ queryKey: ['site', siteId], queryFn: () => api.getSite(siteId), enabled: Number.isFinite(siteId) });
  const role = authRoleForSite(auth.data, Number.isFinite(siteId) ? siteId : undefined);
  const siteArchived = site.data?.status === 'archived';
  const canPlan = !siteArchived && (role === 'supervisor' || role === 'admin');
  const canImport = !siteArchived && (role === 'analyst' || canPlan);
  const planning = useQuery({ queryKey: ['planning', siteId, week], queryFn: () => api.getPlanning(siteId, { week }), enabled: Number.isFinite(siteId) && visible && !siteArchived, refetchInterval: visible && !siteArchived ? 3000 : false, retry: false });
  const machinesQuery = useQuery({ queryKey: ['machines', siteId], queryFn: () => api.getMachines(siteId), enabled: Number.isFinite(siteId) && !siteArchived, retry: false });
  useEffect(() => { const onVisibility = () => setVisible(document.visibilityState === 'visible'); document.addEventListener('visibilitychange', onVisibility); return () => document.removeEventListener('visibilitychange', onVisibility); }, []);
  useEffect(() => { if (planning.data) setRefreshedAt(new Date()); }, [planning.data]);
  useEffect(() => { if (params.get('week') !== week) { const next = new URLSearchParams(params); next.set('week', week); setParams(next, { replace: true }); } }, [params, setParams, week]);
  const cancel = useMutation({ mutationFn: (slot: PlanningSlot) => api.cancelPlanningSlot(slot.id, slot.rowVersion), onSuccess: async () => { setError(null); await cache.invalidateQueries({ queryKey: ['planning', siteId] }); }, onError: value => setError(readable(value)) });
  const activeMachines = useMemo(() => (machinesQuery.data ?? []).filter(machine => machine.lifecycleStatus !== 'archived'), [machinesQuery.data]);
  const items = useMemo(() => (planning.data?.items ?? []).filter(item => (!filters.machineId || String(item.machineId) === filters.machineId) && (!filters.order || item.orderNumber.toLowerCase().includes(filters.order.toLowerCase())) && (!filters.collection || item.collectionStatus === filters.collection) && (!filters.erp || item.erpStatus === filters.erp)), [filters, planning.data?.items]);
  function shift(delta: number) { const parsed = /^([0-9]{4})-W([0-9]{2})$/.exec(week); if (!parsed) return; const base = new Date(Number(parsed[1]), 0, 4); const current = monday(base); current.setDate(current.getDate() + (Number(parsed[2]) - 1 + delta) * 7); const next = isoWeek(current); setWeek(next); }
  function currentWeek() { setWeek(isoWeek(new Date())); }
  function cancelSlot(slot: PlanningSlot) { if (window.confirm(`Annuler le créneau OF ${slot.orderNumber} sur ${slot.machineName ?? `la presse ${slot.machineId}`} ?`)) cancel.mutate(slot); }
  if (!Number.isFinite(siteId)) return <section className="page"><StatePanel tone="error" title="Site invalide" text="L’identifiant du site n’est pas reconnu." action="Retour aux sites" onAction={() => navigate('/sites')} /></section>;
  if (site.data?.status === 'archived') return <section className="page page-wide planning-page"><div className="page-intro"><div><p className="eyebrow">ATELIER · PLANNING PRODUCTION</p><h2>{site.data.name}</h2></div><button className="button-secondary" type="button" onClick={() => navigate('/sites')}>Retour aux sites</button></div><StatePanel tone="warning" title="Site archivé" text="Le planning et les imports sont désactivés pour un site archivé. Les données historiques restent consultables dans les vues dédiées." /></section>;
  return <section className="page page-wide planning-page"><div className="page-intro"><div><p className="eyebrow">ATELIER · PLANNING PRODUCTION</p><h2>{site.data?.name ?? 'Planning hebdomadaire'}</h2><p className="muted">Une ligne par créneau OF-presse. Les cycles machine, la collecte et l’ERP restent des états indépendants.</p></div><button className="button-secondary" type="button" onClick={() => navigate(`/sites/${siteId}/workshop`)}>Retour à l’atelier</button></div>{site.isError && <StatePanel tone="error" title="Site indisponible" text={readable(site.error)} action="Réessayer" onAction={() => site.refetch()} />}<PlanningContent timezone={planning.data?.timezone ?? site.data?.timezone ?? 'UTC'} week={week} filters={filters} setFilters={setFilters} machines={activeMachines} machinesError={machinesQuery.isError} canPlan={canPlan} canImport={canImport} onWeekChange={shift} onCurrentWeek={currentWeek} onImport={() => navigate(`/imports?siteId=${siteId}`)} onCreate={() => { setEditing(null); setEditorOpen(true); }} refreshedAt={refreshedAt} loading={planning.isFetching} planning={planning} items={items} onEdit={slot => { setEditing(slot); setEditorOpen(true); }} onCancel={cancelSlot} error={error} onRetry={() => planning.refetch()} /><ProductionAssignmentEditor siteId={siteId} timezone={planning.data?.timezone ?? site.data?.timezone ?? 'UTC'} machines={activeMachines} slot={editing} open={editorOpen} canPlan={canPlan} onClose={() => setEditorOpen(false)} onSaved={async () => { setEditorOpen(false); setError(null); await cache.invalidateQueries({ queryKey: ['planning', siteId] }); }} /></section>;
}

function PlanningContent({ timezone, week, filters, setFilters, machines, machinesError, canPlan, canImport, onWeekChange, onCurrentWeek, onImport, onCreate, refreshedAt, loading, planning, items, onEdit, onCancel, error, onRetry }: { timezone: string; week: string; filters: PlanningFilters; setFilters: (value: PlanningFilters) => void; machines: Machine[]; machinesError: boolean; canPlan: boolean; canImport: boolean; onWeekChange: (delta: number) => void; onCurrentWeek: () => void; onImport: () => void; onCreate: () => void; refreshedAt?: Date; loading: boolean; planning: { isPending: boolean; isError: boolean; error: unknown; data?: PlanningWeek; refetch: () => unknown }; items: PlanningSlot[]; onEdit: (slot: PlanningSlot) => void; onCancel: (slot: PlanningSlot) => void; error: string | null; onRetry: () => void }) {
  if (planning.isPending) return <StatePanel tone="loading" title="Chargement du planning" text="Lecture des créneaux OF-presse de la semaine." />;
  if (planning.isError) return <StatePanel tone="error" title="Planning indisponible" text={readable(planning.error)} action="Réessayer" onAction={onRetry} />;
  return <><ProductionWeekToolbar weekStart={planning.data?.weekStart ?? week} timezone={timezone} filters={filters} machines={machines} refreshedAt={refreshedAt} onWeekChange={onWeekChange} onCurrentWeek={onCurrentWeek} onFiltersChange={setFilters} onCreate={onCreate} onImport={onImport} canPlan={canPlan} canImport={canImport} loading={loading} />{machinesError && <p className="helper-error" role="alert">Les filtres presse sont indisponibles. Les lignes restent affichées.</p>}{error && <p className="helper-error" role="alert">{error}</p>}<ProductionPlanningGrid items={items} timezone={timezone} canPlan={canPlan} onEdit={onEdit} onCancel={onCancel} />{!canPlan && <p className="planning-readonly" role="note">Lecture seule : seuls les superviseurs et administrateurs peuvent créer, modifier ou annuler un créneau.</p>}</>;
}
