import { ArrowRightIcon } from '@phosphor-icons/react/ArrowRight';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { useApi } from '../App';
import { formatDate, incidentSeverityLabel, incidentSymptomLabel, StatePanel } from '../components/Ui';

export function OverviewPage() {
  const api = useApi();
  const sitesQuery = useQuery({ queryKey: ['overview-sites'], queryFn: api.getSites });
  const incidentsQuery = useQuery({ queryKey: ['overview-incidents'], queryFn: () => api.getIncidents({ status: 'open' }) });
  const importsQuery = useQuery({ queryKey: ['overview-imports'], queryFn: api.getImports });
  const sites = sitesQuery.data ?? [];
  const incidents = incidentsQuery.data ?? [];
  const imports = importsQuery.data ?? [];
  const machines = sites.reduce((total, site) => total + (site.machineCount ?? 0), 0);
  const completedImports = imports.filter((item) => item.status === 'completed').length;
  const critical = incidents.filter((item) => item.severity === 'critical' || item.severity === 'high').length;
  const latestDataAt = [...sites.map((site) => site.lastImportAt), ...incidents.map((incident) => incident.created_at), ...imports.map((item) => item.importedAt)].filter((value): value is string => Boolean(value)).sort().slice(-1)[0];
  const importsUnavailable = importsQuery.isPending || importsQuery.isError;
  const importCount = importsUnavailable ? 'N/D' : completedImports;
  const siteCount = sitesQuery.isError ? 'N/D' : sites.length.toString().padStart(2, '0');
  const machineCount = sitesQuery.isError ? 'N/D' : machines;
  const incidentCount = incidentsQuery.isError ? 'N/D' : incidents.length;
  const criticalDetail = incidentsQuery.isError ? 'File indisponible' : `${critical} de priorité haute`;

  if (sitesQuery.isPending || incidentsQuery.isPending) return <section className="page"><StatePanel tone="loading" title="Préparation de la vue d’ensemble" text="Le périmètre industriel est en cours de lecture." /></section>;

  return <section className="page page-wide overview-page">
    <header className="editorial-heading"><div><p className="eyebrow">SITUATION INDUSTRIELLE</p><h2>Vue d’ensemble</h2><p>État consolidé du parc, des incidents et des dernières données disponibles.</p></div><div className="editorial-date"><span>DERNIÈRE LECTURE</span><strong>{formatDate(latestDataAt)}</strong></div></header>

    <section className="overview-ledger" aria-label="Indicateurs principaux">
      <div><span>SITES SUIVIS</span><strong>{siteCount}</strong><small>{sitesQuery.isError ? 'Périmètre indisponible' : 'Périmètre autorisé'}</small></div>
      <div><span>MACHINES RÉFÉRENCÉES</span><strong>{machineCount}</strong><small>{sitesQuery.isError ? 'Catalogue indisponible' : 'Catalogue actif'}</small></div>
      <div><span>INCIDENTS OUVERTS</span><strong>{incidentCount}</strong><small>{criticalDetail}</small></div>
      <div><span>IMPORTS TERMINÉS</span><strong>{importCount}</strong><small>{importsQuery.isPending ? 'Chargement du journal' : importsQuery.isError ? 'Journal indisponible' : `sur ${imports.length} passeports`}</small></div>
    </section>

    <div className="overview-composition">
      <section className="overview-panel overview-sites"><header><div><h3>Sites industriels</h3></div><Link to="/sites">Voir tous les sites <ArrowRightIcon size={16} aria-hidden="true" /></Link></header>
        {sitesQuery.isError ? <StatePanel tone="error" title="Sites indisponibles" text="Impossible de charger le périmètre." /> : <div className="overview-site-list">{sites.slice(0, 5).map((site, index) => <Link to={`/sites/${site.id}/workshop`} key={site.id}><span className="row-index">{String(index + 1).padStart(2, '0')}</span><span><strong>{site.name}</strong><small>{site.timezone ?? 'Fuseau non renseigné'}</small></span><span className={`site-status site-status-${site.status ?? 'unknown'}`}><i />{site.status === 'offline' ? 'Hors ligne' : site.status === 'degraded' ? 'À surveiller' : site.status === 'online' ? 'Opérationnel' : 'Non communiqué'}</span><b>{site.machineCount ?? 'N/D'} <small>presses</small></b></Link>)}</div>}
      </section>

      <section className="overview-panel overview-priority"><header><div><h3>Incidents prioritaires</h3></div><Link to="/incidents">Ouvrir la file <ArrowRightIcon size={16} aria-hidden="true" /></Link></header>
        {incidentsQuery.isError ? <StatePanel tone="error" title="Incidents indisponibles" text="Impossible de lire la file." /> : incidents.length === 0 ? <p className="overview-empty">Aucun incident ouvert sur le périmètre.</p> : <div className="priority-list">{incidents.slice(0, 5).map((incident) => <Link to={`/incidents/${incident.id}`} key={incident.id}><i className={`priority-rule priority-${incident.severity}`} /><span><strong>{incidentSymptomLabel(incident.symptom)}</strong><small>{incident.machine_erp_ref ? `Presse ${incident.machine_erp_ref}` : `Machine ${incident.machine_id}`} · {formatDate(incident.started_at)}</small></span><b>{incidentSeverityLabel(incident.severity)}</b></Link>)}</div>}
      </section>

      <section className="overview-panel overview-ingestion"><header><div><h3>Dernières données</h3></div><Link to="/imports">Journal complet <ArrowRightIcon size={16} aria-hidden="true" /></Link></header><div className="ingestion-summary"><div className="ingestion-gauge"><strong>{importsUnavailable ? 'N/D' : `${imports.length ? Math.round((completedImports / imports.length) * 100) : 0}%`}</strong><span>imports terminés</span></div><div><p><span>Terminés</span><strong>{importsUnavailable ? 'N/D' : completedImports}</strong></p><p><span>À traiter</span><strong>{importsUnavailable ? 'N/D' : Math.max(0, imports.length - completedImports)}</strong></p><p><span>Dernier passage</span><strong>{importsUnavailable ? 'N/D' : formatDate(imports[0]?.importedAt, false)}</strong></p></div></div></section>
    </div>
  </section>;
}
