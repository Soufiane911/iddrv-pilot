import { useQuery } from '@tanstack/react-query';
import { useApi } from '../App';
import { formatDate, MetricCard, SectionTitle, StatePanel } from '../components/Ui';

export function HealthPage() {
  const api = useApi();
  const query = useQuery({ queryKey: ['health'], queryFn: api.getHealth });
  const readinessQuery = useQuery({ queryKey: ['readiness'], queryFn: api.getReadiness });

  function refresh() {
    void query.refetch();
    void readinessQuery.refetch();
  }

  return <section className="page page-wide">
    <div className="page-intro">
      <div><p className="eyebrow">CONNECTIVITÉ</p><h2>Santé des services</h2><p className="muted">Un point de contrôle avant de lancer une investigation ou un import.</p></div>
      <button className="button-primary" type="button" onClick={refresh} disabled={query.isFetching || readinessQuery.isFetching}>{query.isFetching || readinessQuery.isFetching ? 'Vérification…' : 'Vérifier maintenant'}</button>
    </div>
    {query.isPending && <StatePanel tone="loading" title="Connexion à l’API" text="La disponibilité du service est en cours de vérification." />}
    {query.isError && <StatePanel tone="error" title="API indisponible" text={query.error instanceof Error ? query.error.message : 'Impossible de joindre le backend.'} action="Réessayer" onAction={refresh} />}
    {query.data && !query.isError && <>
      <StatePanel tone={query.data.status === 'ok' && query.data.database === 'ok' ? 'success' : 'warning'} title={query.data.status === 'ok' ? 'API opérationnelle' : 'API à surveiller'} text={query.data.message ?? 'Réponse reçue du service.'} />
      <div className="metric-grid metric-grid-three">
        <MetricCard label="Service" value={query.data.service ?? 'N/D'} detail={`version ${query.data.version ?? 'N/D'}`} />
        <MetricCard label="Base de données" value={query.data.database === 'ok' ? 'Disponible' : 'Indisponible'} detail="contrôle health" tone={query.data.database === 'ok' ? 'good' : 'danger'} />
        <MetricCard label="Dernier contrôle" value={formatDate(query.data.checkedAt)} detail="horodatage local" />
      </div>
    </>}
    {readinessQuery.isError && <StatePanel tone="error" title="Prêt à servir : non" text="La readiness est indisponible ou une dépendance est défaillante." action="Réessayer" onAction={() => void readinessQuery.refetch()} />}
    {readinessQuery.data && <section className="surface-card">
      <SectionTitle eyebrow="READINESS" title="Dépendances sondées" />
      <div className="metric-grid metric-grid-three">
        <MetricCard label="État" value={readinessQuery.data.status === 'ready' ? 'Prêt' : 'Non prêt'} detail="contrôle readiness" tone={readinessQuery.data.status === 'ready' ? 'good' : 'danger'} />
        <MetricCard label="Base de données" value={readinessQuery.data.database === 'ok' ? 'Disponible' : 'Indisponible'} detail="requêtes métier" tone={readinessQuery.data.database === 'ok' ? 'good' : 'danger'} />
        <MetricCard label="Redis" value={readinessQuery.data.redis === 'ok' ? 'Disponible' : 'Indisponible'} detail="session et throttling" tone={readinessQuery.data.redis === 'ok' ? 'good' : 'danger'} />
        <MetricCard label="Modèle HDT" value={readinessQuery.data.model === 'ok' ? 'Chargeable' : 'Indisponible'} detail="artefact runtime" tone={readinessQuery.data.model === 'ok' ? 'good' : 'danger'} />
      </div>
    </section>}
    <section className="surface-card health-card">
      <SectionTitle eyebrow="CONTRATS ATTENDUS" title="Flux de supervision" />
      <p className="muted small">Ces éléments décrivent les contrats fonctionnels ; leur présence ne remplace pas le sondage readiness ci-dessus.</p>
      <ul className="health-list">
        <li><span className="health-check" aria-hidden="true" /><div><strong>Lecture sites vers atelier</strong><p>Contrat applicatif : le frontend interroge l’API, jamais les CSV.</p></div></li>
        <li><span className="health-check" aria-hidden="true" /><div><strong>Diagnostic vers preuves</strong><p>Contrat applicatif : les chiffres viennent d’une investigation persistée.</p></div></li>
        <li><span className="health-check" aria-hidden="true" /><div><strong>Replay historique</strong><p>Contrat applicatif : chaque écran conserve le cutoff de l’événement.</p></div></li>
      </ul>
    </section>
  </section>;
}
