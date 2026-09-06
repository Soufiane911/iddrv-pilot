import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { ErpImportWizard } from '../components/imports/ErpImportWizard';
import { useQuery } from '@tanstack/react-query';
import { useApi } from '../App';
import { formatDate, MetricCard, SectionTitle, StatePanel } from '../components/Ui';

function importStatusLabel(status: string): string {
  return ({
    completed: 'Terminé',
    discovered: 'Découvert',
    processing: 'En cours',
    retry_wait: 'Nouvelle tentative planifiée',
    quarantined: 'En quarantaine',
    failed: 'Échec, à retenter',
    pending: 'En attente',
    queued: 'En attente',
  } as Record<string, string>)[status] ?? status.split('_').join(' ');
}

function importStatusTone(status: string): 'completed' | 'pending' | 'failed' {
  if (status === 'completed') return 'completed';
  if (status === 'quarantined') return 'failed';
  return 'pending';
}

export function ImportsPage() {
  const api = useApi();
  const [searchParams] = useSearchParams();
  const requestedSite = Number(searchParams.get('site'));
  const [selectedSite, setSelectedSite] = useState<number | null>(Number.isFinite(requestedSite) ? requestedSite : null);
  const sites = useQuery({ queryKey: ['sites'], queryFn: () => api.getSites() });
  const auth = useQuery({ queryKey: ['auth-me'], queryFn: () => api.getCurrentUser() });
  const site = sites.data?.find(item => item.id === selectedSite) ?? sites.data?.[0];
  const role = site ? auth.data?.siteRoles?.[site.id] ?? auth.data?.role : undefined;
  const query = useQuery({ queryKey: ['imports'], queryFn: () => api.getImports() });
  const imports = query.data ?? [];
  const completed = imports.filter((item) => item.status === 'completed').length;
  const knownRejected = imports.filter((item) => item.rowCountRejected !== undefined);
  const rejected = knownRejected.reduce((sum, item) => sum + (item.rowCountRejected ?? 0), 0);
  const quarantined = imports.filter((item) => item.status === 'quarantined').length;

  return <section className="page page-wide">
    <div className="page-intro">
      <div><p className="eyebrow">TRAÇABILITÉ DES DONNÉES</p><h2>Historique des imports</h2><p className="muted">Le journal suit chaque fichier, ses tentatives et son passage éventuel en quarantaine.</p></div>
      <button className="button-primary" type="button" onClick={() => query.refetch()} disabled={query.isFetching}>{query.isFetching ? 'Actualisation…' : 'Actualiser'}</button>
    </div>

    {sites.isError && <StatePanel tone="error" title="Sites indisponibles" text="Impossible de choisir un site pour l’import." />}
    {site && <>
      <label className="erp-import-site">Site de l’import<select value={site.id} onChange={event => setSelectedSite(Number(event.target.value))}>{sites.data?.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
      <ErpImportWizard key={site.id} siteId={site.id} timezone={site.timezone ?? 'UTC'} canImport={role === 'analyst' || role === 'supervisor' || role === 'admin'} canConfigure={role === 'supervisor' || role === 'admin'} />
    </>}

    {query.isPending && <StatePanel tone="loading" title="Chargement du journal" text="Les traitements d’import sont en cours de récupération." />}
    {query.isError && <StatePanel tone="error" title="Journal indisponible" text={query.error instanceof Error ? query.error.message : 'Impossible de lire les imports.'} action="Réessayer" onAction={() => query.refetch()} />}

    {!query.isPending && !query.isError && imports.length > 0 && <>
      <div className="metric-grid metric-grid-three">
        <MetricCard label="Fichiers suivis" value={imports.length} detail="traitements" />
        <MetricCard label="Terminés" value={completed} detail="imports achevés" tone="good" />
        <MetricCard
          label={knownRejected.length ? 'Lignes rejetées' : 'Fichiers en quarantaine'}
          value={knownRejected.length ? rejected : quarantined}
          detail={knownRejected.length ? 'sur les imports renseignés' : 'état terminal du worker'}
          tone={(knownRejected.length ? rejected : quarantined) ? 'danger' : 'good'}
        />
      </div>
      <section className="surface-card import-table-card">
        <SectionTitle eyebrow="JOBS D’IMPORT" title="Fichiers traités" />
        <div className="incident-table-wrap">
          <table className="incident-table import-table">
            <caption className="visually-hidden">Journal des traitements d’import</caption>
            <thead><tr><th scope="col">Fichier</th><th scope="col">Source</th><th scope="col">Statut</th><th scope="col">Traitement</th><th scope="col">Horodatage</th></tr></thead>
            <tbody>{imports.map((item) => {
              const hasRows = item.rowCountAccepted !== undefined || item.rowCountTotal !== undefined;
              return <tr key={item.id}>
                <td data-label="Fichier"><strong>{item.fileName ?? item.id}</strong><small>{item.id.slice(0, 12)}</small></td>
                <td data-label="Source">{item.parserType ?? item.sourceKind ?? 'N/D'}</td>
                <td data-label="Statut">
                  <span className={`status-label status-label-${importStatusTone(item.status)}`}>{importStatusLabel(item.status)}</span>
                  {item.errorLog && <small className="helper-error">{item.errorCode ? `${item.errorCode} · ` : ''}{item.errorLog}</small>}
                </td>
                <td data-label="Traitement">
                  {hasRows ? <><span className="number-cell">{item.rowCountAccepted ?? 'N/D'}</span><small>/ {item.rowCountTotal ?? 'N/D'} lignes acceptées</small></> : <><span className="number-cell">{item.attemptCount ?? 0}</span><small>/ {item.maxAttempts ?? 'N/D'} tentatives</small></>}
                </td>
                <td data-label="Horodatage">{formatDate(item.importedAt)}</td>
              </tr>;
            })}</tbody>
          </table>
        </div>
      </section>
    </>}
  </section>;
}
