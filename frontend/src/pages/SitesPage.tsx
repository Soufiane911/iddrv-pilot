import { ArrowRightIcon } from '@phosphor-icons/react/ArrowRight';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApi } from '../App';
import { ApiRequestError } from '../lib/api';
import { EmptyPanel, formatDate, SectionTitle, StatePanel } from '../components/Ui';

function publicError(error: unknown, fallback: string): string {
  if (error instanceof ApiRequestError) {
    if (error.code === 'site_name_already_exists') return 'Un site porte déjà ce nom.';
    if (error.code === 'last_site_cannot_be_deleted') return 'Le dernier site ne peut pas être supprimé.';
    return error.message;
  }
  return error instanceof Error ? error.message : fallback;
}

export function SitesPage() {
  const api = useApi();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ['sites'], queryFn: api.getSites });
  const authQuery = useQuery({ queryKey: ['auth-me'], queryFn: api.getCurrentUser });
  const sites = query.data ?? [];
  const user = authQuery.data;
  const canCreate = user?.role === 'supervisor' || user?.role === 'admin';
  const canDelete = user?.role === 'admin';
  const [createOpen, setCreateOpen] = useState(false);
  const [archiveSiteId, setArchiveSiteId] = useState<number | null>(null);
  const [name, setName] = useState('');
  const [timezone, setTimezone] = useState('Europe/Paris');
  const [confirmation, setConfirmation] = useState('');
  const [formError, setFormError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const selectedForArchive = sites.find((site) => site.id === archiveSiteId);

  const createMutation = useMutation({
    mutationFn: () => api.createSite({ name: name.trim(), timezone }),
    onSuccess: async (site) => {
      setCreateOpen(false); setName(''); setTimezone('Europe/Paris'); setFormError(null);
      await queryClient.invalidateQueries({ queryKey: ['sites'] });
      // Site creation refreshes the session scope on the backend. Refetch it
      // before navigating so the protected workshop does not briefly see the
      // pre-creation site list/role.
      await queryClient.refetchQueries({ queryKey: ['auth-me'], type: 'active' });
      navigate(`/sites/${site.id}/workshop`);
    },
    onError: (error) => setFormError(publicError(error, 'Impossible de créer le site.')),
  });
  const archiveMutation = useMutation({
    mutationFn: () => api.archiveSite(archiveSiteId as number),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['sites'] });
      setArchiveSiteId(null); setConfirmation(''); setFormError(null);
    },
    onError: (error) => setFormError(publicError(error, 'Impossible d’archiver le site.')),
  });

  function submitCreate(event: FormEvent) {
    event.preventDefault();
    setFormError(null);
    if (!name.trim()) { setFormError('Le nom du site est requis.'); return; }
    createMutation.mutate();
  }

  function submitDelete(event: FormEvent) {
    event.preventDefault();
    if (!selectedForArchive || confirmation.trim() !== selectedForArchive.name) return;
    setFormError(null);
    archiveMutation.mutate();
  }

  return <section className="page page-wide">
    <div className="page-intro">
      <div><p className="eyebrow">ORGANISATION MULTI-SITE</p><h2>Vos ateliers, en un coup d’œil</h2><p className="muted">Choisissez un site pour retrouver ses presses et ses incidents.</p></div>
      <div className="page-actions">
        {canCreate && <button className="button-primary" type="button" onClick={() => { setCreateOpen(true); setFormError(null); setNotice(null); }}>Nouveau site</button>}
        <button className="button-secondary" type="button" onClick={() => query.refetch()} disabled={query.isFetching}>{query.isFetching ? 'Actualisation…' : 'Actualiser'}</button>
      </div>
    </div>

    {notice && !createOpen && !selectedForArchive && <StatePanel tone="success" title="Opération terminée" text={notice} />}
    {formError && !createOpen && !selectedForArchive && <StatePanel tone="error" title="Action impossible" text={formError} />}
    {query.isPending && <StatePanel tone="loading" title="Chargement des sites" text="Le catalogue des ateliers est en cours de récupération." />}
    {query.isError && <StatePanel tone="error" title="Catalogue indisponible" text={query.error instanceof Error ? query.error.message : 'Impossible de récupérer les sites.'} action="Réessayer" onAction={() => query.refetch()} />}
    {!query.isPending && !query.isError && sites.length === 0 && <EmptyPanel title="Aucun site configuré" text={canCreate ? 'Créez votre premier site pour commencer la supervision.' : 'Ajoutez un site côté API pour commencer la supervision.'} />}
    {!query.isPending && !query.isError && sites.length > 0 && <>
      <SectionTitle eyebrow="SITES SUIVIS" title="Sites industriels"><span className="muted small">{sites.length} site{sites.length > 1 ? 's' : ''}</span></SectionTitle>
      <div className="site-grid">{sites.map((site) => <article className="site-card" key={site.id}>
        <div className="site-card-head"><div><span className={`site-status site-status-${site.status ?? 'unknown'}`}><span aria-hidden="true" />{site.status === 'archived' ? 'Archivé' : site.status === 'offline' ? 'Hors ligne' : site.status === 'degraded' ? 'À surveiller' : site.status === 'online' || site.status === 'active' ? 'Opérationnel' : 'Statut non communiqué'}</span><h3>{site.name}</h3><p>{site.timezone ?? 'Fuseau non renseigné'}</p></div><span className="site-index" aria-hidden="true">{String(site.id).padStart(2, '0')}</span></div>
        <div className="site-card-stats"><div><strong>{site.machineCount ?? 'N/D'}</strong><span>presses référencées<span className="visually-hidden"> presses</span></span></div><div><strong>{site.openIncidentCount ?? 0}</strong><span>incidents ouverts</span></div><div><strong>{formatDate(site.lastImportAt, false)}</strong><span>dernier import</span></div></div>
        <div className="site-card-actions"><button className="button-secondary site-open" type="button" disabled={site.status === 'archived'} onClick={() => navigate(`/sites/${site.id}/workshop`)}>{site.status === 'archived' ? 'Site archivé' : <>Ouvrir l’atelier <ArrowRightIcon size={17} aria-hidden="true" /></>}</button>{canDelete && site.status !== 'archived' && <button className="button-danger" type="button" onClick={() => { setArchiveSiteId(site.id); setConfirmation(''); setFormError(null); }}>Archiver</button>}</div>
      </article>)}</div>
    </>}

    {createOpen && <div className="site-modal-backdrop" role="presentation"><section className="site-modal" role="dialog" aria-modal="true" aria-labelledby="create-site-title">
      <p className="eyebrow">NOUVEL ATELIER</p><h2 id="create-site-title">Créer un site de production</h2><p className="muted">Le site est créé vide. Vous ajouterez les presses et l’ERP depuis l’Atelier.</p>
      <form onSubmit={submitCreate}><label htmlFor="site-name">Nom du site</label><input id="site-name" value={name} onChange={(event) => setName(event.target.value)} autoFocus required maxLength={100} placeholder="Ex. Atelier injection Lyon" />
        <label htmlFor="site-timezone">Fuseau horaire</label><select id="site-timezone" value={timezone} onChange={(event) => setTimezone(event.target.value)}><option>Europe/Paris</option><option>UTC</option><option>America/Montreal</option></select>
        {formError && <p className="helper-error" role="alert">{formError}</p>}<div className="site-modal-actions"><button className="button-secondary" type="button" onClick={() => setCreateOpen(false)} disabled={createMutation.isPending}>Annuler</button><button className="button-primary" type="submit" disabled={createMutation.isPending}>{createMutation.isPending ? 'Création…' : 'Créer le site'}</button></div>
      </form>
    </section></div>}

    {selectedForArchive && <div className="site-modal-backdrop" role="presentation"><section className="site-modal" role="dialog" aria-modal="true" aria-labelledby="archive-site-title"><p className="eyebrow">CYCLE DE VIE DU SITE</p><h2 id="archive-site-title">Archiver {selectedForArchive.name} ?</h2><p className="muted">Le site ne sera plus utilisable, mais ses presses, OF, cycles, imports et incidents resteront conservés pour l’historique.</p><form onSubmit={submitDelete}><label htmlFor="site-confirmation">Saisissez le nom du site pour confirmer</label><input id="site-confirmation" value={confirmation} onChange={(event) => setConfirmation(event.target.value)} autoFocus /><p className="helper-text">{selectedForArchive.name}</p>{formError && <p className="helper-error" role="alert">{formError}</p>}<div className="site-modal-actions"><button className="button-secondary" type="button" onClick={() => setArchiveSiteId(null)} disabled={archiveMutation.isPending}>Annuler</button><button className="button-danger" type="submit" disabled={confirmation.trim() !== selectedForArchive.name || archiveMutation.isPending}>{archiveMutation.isPending ? 'Archivage…' : 'Archiver le site'}</button></div></form></section></div>}
  </section>;
}
