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
  const [deleteSiteId, setDeleteSiteId] = useState<number | null>(null);
  const [name, setName] = useState('');
  const [timezone, setTimezone] = useState('Europe/Paris');
  const [erpFile, setErpFile] = useState<File | null>(null);
  const [confirmation, setConfirmation] = useState('');
  const [formError, setFormError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const selectedForDelete = sites.find((site) => site.id === deleteSiteId);

  const createMutation = useMutation({
    mutationFn: async () => {
      const site = await api.createSite({ name: name.trim(), timezone });
      let importError: string | null = null;
      if (erpFile) {
        try { await api.uploadERP(site.id, erpFile); }
        catch (error) { importError = publicError(error, 'Le fichier ERP n’a pas pu être envoyé.'); }
      }
      return { site, importError };
    },
    onSuccess: async ({ importError }) => {
      await queryClient.invalidateQueries({ queryKey: ['sites'] });
      setCreateOpen(false); setName(''); setTimezone('Europe/Paris'); setErpFile(null); setFormError(null);
      setNotice(importError ? `Site créé, mais l’import ERP a échoué : ${importError}` : 'Site créé.');
    },
    onError: (error) => setFormError(publicError(error, 'Impossible de créer le site.')),
  });
  const deleteMutation = useMutation({
    mutationFn: () => api.deleteSite(deleteSiteId as number),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['sites'] });
      setDeleteSiteId(null); setConfirmation(''); setFormError(null);
    },
    onError: (error) => setFormError(publicError(error, 'Impossible de supprimer le site.')),
  });

  function submitCreate(event: FormEvent) {
    event.preventDefault();
    setFormError(null);
    if (!name.trim()) { setFormError('Le nom du site est requis.'); return; }
    createMutation.mutate();
  }

  function submitDelete(event: FormEvent) {
    event.preventDefault();
    if (!selectedForDelete || confirmation.trim() !== selectedForDelete.name) return;
    setFormError(null);
    deleteMutation.mutate();
  }

  return <section className="page page-wide">
    <div className="page-intro">
      <div><p className="eyebrow">ORGANISATION MULTI-SITE</p><h2>Vos ateliers, en un coup d’œil</h2><p className="muted">Choisissez un site pour retrouver ses presses et ses incidents.</p></div>
      <div className="page-actions">
        {canCreate && <button className="button-primary" type="button" onClick={() => { setCreateOpen(true); setFormError(null); setNotice(null); }}>Nouveau site</button>}
        <button className="button-secondary" type="button" onClick={() => query.refetch()} disabled={query.isFetching}>{query.isFetching ? 'Actualisation…' : 'Actualiser'}</button>
      </div>
    </div>

    {notice && !createOpen && !selectedForDelete && <StatePanel tone="success" title="Opération terminée" text={notice} />}
    {formError && !createOpen && !selectedForDelete && <StatePanel tone="error" title="Action impossible" text={formError} />}
    {query.isPending && <StatePanel tone="loading" title="Chargement des sites" text="Le catalogue des ateliers est en cours de récupération." />}
    {query.isError && <StatePanel tone="error" title="Catalogue indisponible" text={query.error instanceof Error ? query.error.message : 'Impossible de récupérer les sites.'} action="Réessayer" onAction={() => query.refetch()} />}
    {!query.isPending && !query.isError && sites.length === 0 && <EmptyPanel title="Aucun site configuré" text={canCreate ? 'Créez votre premier site pour commencer la supervision.' : 'Ajoutez un site côté API pour commencer la supervision.'} />}
    {!query.isPending && !query.isError && sites.length > 0 && <>
      <SectionTitle eyebrow="PÉRIMÈTRE OPÉRATIONNEL" title="Sites industriels"><span className="muted small">{sites.length} site{sites.length > 1 ? 's' : ''}</span></SectionTitle>
      <div className="site-grid">{sites.map((site) => <article className="site-card" key={site.id}>
        <div className="site-card-head"><div><span className={`site-status site-status-${site.status ?? 'unknown'}`}><span aria-hidden="true" />{site.status === 'offline' ? 'Hors ligne' : site.status === 'degraded' ? 'À surveiller' : site.status === 'online' ? 'Opérationnel' : 'Statut non communiqué'}</span><h3>{site.name}</h3><p>{site.timezone ?? 'Fuseau non renseigné'}</p></div><span className="site-index" aria-hidden="true">{String(site.id).padStart(2, '0')}</span></div>
        <div className="site-card-stats"><div><strong>{site.machineCount ?? 'N/D'}</strong><span>presses</span></div><div><strong>{site.openIncidentCount ?? 0}</strong><span>incidents ouverts</span></div><div><strong>{formatDate(site.lastImportAt, false)}</strong><span>dernier import</span></div></div>
        <div className="site-card-actions"><button className="button-secondary site-open" type="button" onClick={() => navigate(`/sites/${site.id}/workshop`)}>Ouvrir l’atelier <ArrowRightIcon size={17} aria-hidden="true" /></button>{canDelete && <button className="button-danger" type="button" onClick={() => { setDeleteSiteId(site.id); setConfirmation(''); setFormError(null); }}>Supprimer</button>}</div>
      </article>)}</div>
    </>}

    {createOpen && <div className="site-modal-backdrop" role="presentation"><section className="site-modal" role="dialog" aria-modal="true" aria-labelledby="create-site-title">
      <p className="eyebrow">NOUVEL ATELIER</p><h2 id="create-site-title">Créer un site de production</h2><p className="muted">Le site peut être créé vide puis complété depuis l’import ERP.</p>
      <form onSubmit={submitCreate}><label htmlFor="site-name">Nom du site</label><input id="site-name" value={name} onChange={(event) => setName(event.target.value)} autoFocus required maxLength={100} placeholder="Ex. Atelier injection Lyon" />
        <label htmlFor="site-timezone">Fuseau horaire</label><select id="site-timezone" value={timezone} onChange={(event) => setTimezone(event.target.value)}><option>Europe/Paris</option><option>UTC</option><option>America/Montreal</option></select>
        <label htmlFor="site-erp">ERP initial (facultatif)</label><input id="site-erp" type="file" accept=".xlsx,.xlsm" onChange={(event) => setErpFile(event.target.files?.[0] ?? null)} /><p className="helper-text">Le fichier sera envoyé dans le parcours de prévisualisation ERP après la création.</p>
        {formError && <p className="helper-error" role="alert">{formError}</p>}<div className="site-modal-actions"><button className="button-secondary" type="button" onClick={() => setCreateOpen(false)} disabled={createMutation.isPending}>Annuler</button><button className="button-primary" type="submit" disabled={createMutation.isPending}>{createMutation.isPending ? 'Création…' : 'Créer le site'}</button></div>
      </form>
    </section></div>}

    {selectedForDelete && <div className="site-modal-backdrop" role="presentation"><section className="site-modal" role="dialog" aria-modal="true" aria-labelledby="delete-site-title"><p className="eyebrow">SUPPRESSION DU TENANT</p><h2 id="delete-site-title">Supprimer {selectedForDelete.name} ?</h2><p className="muted">Toutes les presses, OF, cycles, imports et incidents de ce site seront supprimés de la base partagée. Cette action est irréversible.</p><form onSubmit={submitDelete}><label htmlFor="site-confirmation">Saisissez le nom du site pour confirmer</label><input id="site-confirmation" value={confirmation} onChange={(event) => setConfirmation(event.target.value)} autoFocus /><p className="helper-text">{selectedForDelete.name}</p>{formError && <p className="helper-error" role="alert">{formError}</p>}<div className="site-modal-actions"><button className="button-secondary" type="button" onClick={() => setDeleteSiteId(null)} disabled={deleteMutation.isPending}>Annuler</button><button className="button-danger" type="submit" disabled={confirmation.trim() !== selectedForDelete.name || deleteMutation.isPending}>{deleteMutation.isPending ? 'Suppression…' : 'Supprimer définitivement'}</button></div></form></section></div>}
  </section>;
}
