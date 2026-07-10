import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useApi } from '../App';
import { EmptyPanel, formatDate, incidentSeverityLabel, incidentStatusLabel, SectionTitle, StatePanel } from '../components/Ui';
import type { IncidentStatus } from '../lib/api';

export function IncidentsPage() {
  const api = useApi();
  const [searchParams, setSearchParams] = useSearchParams();
  const [status, setStatus] = useState<IncidentStatus | 'all'>((searchParams.get('status') as IncidentStatus | null) ?? 'all');
  const query = useQuery({ queryKey: ['incidents', status], queryFn: () => api.getIncidents(status === 'all' ? {} : { status }) });
  const incidents = query.data ?? [];
  function changeStatus(value: IncidentStatus | 'all') { setStatus(value); if (value === 'all') searchParams.delete('status'); else searchParams.set('status', value); setSearchParams(searchParams); }
  return <section className="page page-wide">
    <div className="page-intro"><div><p className="eyebrow">DIAGNOSTIC & PREUVES</p><h2>Incidents à examiner</h2><p className="muted">Chaque signal est relié à une fenêtre temporelle, une hypothèse et des preuves persistées en base.</p></div><button type="button" className="button-primary" onClick={() => query.refetch()} disabled={query.isFetching}>{query.isFetching ? 'Actualisation…' : 'Actualiser'}</button></div>
    <div className="filter-bar" aria-label="Filtres incidents"><label htmlFor="incident-status">Statut</label><select id="incident-status" value={status} onChange={(event) => changeStatus(event.target.value as IncidentStatus | 'all')}><option value="all">Tous</option><option value="open">Ouverts</option><option value="reviewed">Revus</option><option value="closed">Clos</option></select><span className="filter-count">{query.isPending ? '…' : `${incidents.length} résultat${incidents.length > 1 ? 's' : ''}`}</span></div>
    {query.isPending && <StatePanel tone="loading" title="Chargement des incidents" text="Les signaux persistés sont en cours de récupération." />}
    {query.isError && <StatePanel tone="error" title="Incidents indisponibles" text={query.error instanceof Error ? query.error.message : 'Impossible de récupérer les incidents.'} action="Réessayer" onAction={() => query.refetch()} />}
    {!query.isPending && !query.isError && incidents.length === 0 && <EmptyPanel title="Aucun incident dans ce filtre" text="Aucun signal ne correspond à la période ou au statut sélectionné." action={status !== 'all' ? 'Afficher tous les incidents' : undefined} onAction={() => changeStatus('all')} />}
    {!query.isPending && !query.isError && incidents.length > 0 && <section className="surface-card incident-table-card"><SectionTitle eyebrow="FILE DE DIAGNOSTIC" title="Signaux récents" /><div className="incident-table-wrap"><table className="incident-table"><caption className="visually-hidden">Liste des incidents persistés</caption><thead><tr><th scope="col">Incident</th><th scope="col">Machine</th><th scope="col">Gravité</th><th scope="col">Statut</th><th scope="col">Début</th><th scope="col"><span className="visually-hidden">Action</span></th></tr></thead><tbody>{incidents.map((incident) => <tr key={incident.id}><td><Link className="incident-link" to={`/incidents/${incident.id}`}><strong>{incident.symptom.split('_').join(' ')}</strong><small>{incident.defect_type ?? 'défaut non classé'} · {incident.id.slice(0, 8)}</small></Link></td><td><span className="machine-ref">{incident.machine_erp_ref ? `Presse ${incident.machine_erp_ref}` : `Machine ${incident.machine_id}`}</span><small>Site {incident.site_id}</small></td><td><span className={`severity severity-${incident.severity}`}>{incidentSeverityLabel(incident.severity)}</span></td><td><span className={`status-label status-label-${incident.status}`}>{incidentStatusLabel(incident.status)}</span></td><td><time dateTime={incident.started_at}>{formatDate(incident.started_at)}</time></td><td><Link className="table-action" to={`/incidents/${incident.id}`}>Ouvrir →</Link></td></tr>)}</tbody></table></div></section>}
  </section>;
}
