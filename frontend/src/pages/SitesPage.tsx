import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { useApi } from '../App';
import { EmptyPanel, formatDate, MetricCard, SectionTitle, StatePanel } from '../components/Ui';

export function SitesPage() {
  const api = useApi();
  const navigate = useNavigate();
  const query = useQuery({ queryKey: ['sites'], queryFn: api.getSites });
  const sites = query.data ?? [];
  const machineCount = sites.reduce((total, site) => total + (site.machineCount ?? 0), 0);
  const openIncidentCount = sites.reduce((total, site) => total + (site.openIncidentCount ?? 0), 0);
  return <section className="page page-wide">
    <div className="page-intro"><div><p className="eyebrow">ORGANISATION MULTI-SITE</p><h2>Vos ateliers, en un coup d’œil</h2><p className="muted">Choisissez un site pour ouvrir le plan des presses et reprendre un incident depuis son contexte temporel.</p></div><button className="button-primary" type="button" onClick={() => query.refetch()} disabled={query.isFetching}>{query.isFetching ? 'Actualisation…' : 'Actualiser'}</button></div>
    {query.isPending && <StatePanel tone="loading" title="Chargement des sites" text="Le catalogue des ateliers est en cours de récupération." />}
    {query.isError && <StatePanel tone="error" title="Catalogue indisponible" text={query.error instanceof Error ? query.error.message : 'Impossible de récupérer les sites.'} action="Réessayer" onAction={() => query.refetch()} />}
    {!query.isPending && !query.isError && sites.length === 0 && <EmptyPanel title="Aucun site configuré" text="Ajoutez un site côté API pour commencer la supervision." />}
    {!query.isPending && !query.isError && sites.length > 0 && <>
      <div className="metric-grid metric-grid-three"><MetricCard label="Sites suivis" value={sites.length} detail="périmètre courant" tone="good" /><MetricCard label="Presses référencées" value={machineCount || '—'} detail="catalogue machine" /><MetricCard label="Incidents ouverts" value={openIncidentCount || '—'} detail="à examiner" tone={openIncidentCount ? 'warning' : 'good'} /></div>
      <SectionTitle eyebrow="PÉRIMÈTRE OPÉRATIONNEL" title="Sites industriels" />
      <div className="site-grid">{sites.map((site) => <article className="site-card" key={site.id}>
        <div className="site-card-head"><div><span className={`site-status site-status-${site.status ?? 'online'}`}><span aria-hidden="true" />{site.status === 'offline' ? 'Hors ligne' : site.status === 'degraded' ? 'À surveiller' : 'Opérationnel'}</span><h3>{site.name}</h3><p>{site.timezone ?? 'Fuseau non renseigné'}</p></div><span className="site-index" aria-hidden="true">{String(site.id).padStart(2, '0')}</span></div>
        <div className="site-card-stats"><div><strong>{site.machineCount ?? '—'}</strong><span>presses</span></div><div><strong>{site.openIncidentCount ?? 0}</strong><span>incidents ouverts</span></div><div><strong>{formatDate(site.lastImportAt, false)}</strong><span>dernier import</span></div></div>
        <button className="button-secondary site-open" type="button" onClick={() => navigate(`/sites/${site.id}/workshop`)}>Ouvrir l’atelier <span aria-hidden="true">→</span></button>
      </article>)}</div>
    </>}
  </section>;
}
