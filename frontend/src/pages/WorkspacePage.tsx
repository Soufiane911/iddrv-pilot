import { ArrowRightIcon } from '@phosphor-icons/react/ArrowRight';
import { UploadSimpleIcon } from '@phosphor-icons/react/UploadSimple';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useApi } from '../App';
import { EmptyPanel, SectionTitle, StatePanel } from '../components/Ui';
import { canWriteSite, type AuthUser, type ImportSourceKind } from '../lib/api';

const sourceOptions: Array<{ value: ImportSourceKind; label: string }> = [
  { value: 'erp', label: 'ERP / OF' },
  { value: 'machines', label: 'Machines' },
  { value: 'quality', label: 'Qualité' },
  { value: 'maintenance', label: 'Maintenance' },
  { value: 'layout', label: 'Plan atelier' },
];

function sourceLabel(value: ImportSourceKind): string {
  return sourceOptions.find((option) => option.value === value)?.label ?? 'Détection automatique';
}

function fileStatusLabel(value: string): string {
  if (value === 'needs_review') return 'À valider';
  if (value === 'profiled') return 'Profilé';
  if (value === 'validated') return 'Validé';
  if (value === 'failed') return 'En erreur';
  return 'En attente du worker';
}

export function WorkspacePage() {
  const api = useApi();
  const queryClient = useQueryClient();
  const authUser = queryClient.getQueryData<AuthUser>(['auth-me']);
  const [siteId, setSiteId] = useState<number>();
  const [searchParams, setSearchParams] = useSearchParams();
  const sessionId = searchParams.get('session') ?? undefined;
  const [projectName, setProjectName] = useState('Projet usine pilote');
  const [sourceKind, setSourceKind] = useState<ImportSourceKind>('unknown');
  const sites = useQuery({ queryKey: ['workspace-sites'], queryFn: () => api.getSites() });
  const session = useQuery({ queryKey: ['import-session', sessionId], queryFn: () => api.getImportSession(sessionId as string), enabled: Boolean(sessionId) });
  const create = useMutation({ mutationFn: () => api.createImportSession(siteId as number, projectName), onSuccess: (value) => setSearchParams({ session: value.id }, { replace: true }) });
  const register = useMutation({ mutationFn: (file: File) => api.registerImportFile(sessionId as string, { file_name: file.name, source_kind: sourceKind, mime_type: file.type, size_bytes: file.size }), onSuccess: () => session.refetch() });
  const validate = useMutation({ mutationFn: () => api.validateImportSession(sessionId as string), onSuccess: () => session.refetch() });
  const current = session.data;
  const canManageWorkspace = sessionId && !current && authUser ? false : canWriteSite(authUser, current?.site_id ?? siteId);
  const canValidate = canManageWorkspace && Boolean(current?.files.length && current.files.every((file) => file.file_hash && ['needs_review', 'profiled', 'validated'].includes(file.status)));

  useEffect(() => {
    const available = sites.data ?? [];
    if (available.length > 0 && !available.some((site) => site.id === siteId)) setSiteId(available[0].id);
  }, [siteId, sites.data]);

  return <section className="page page-wide workspace-page">
    <div className="workspace-hero">
      <div><p className="eyebrow">POSTE DE TRAVAIL INDUSTRIEL</p><h2>Préparer les sources avant l’intégration</h2><p className="muted">Référencez les métadonnées des exports et conservez un lien vers la session. Le transfert et le profilage restent séparés dans ce pilote.</p></div>
      <div className="workspace-status"><span className="status-pulse" /> Runtime local · données maîtrisées</div>
    </div>

    {!sessionId && <section className="surface-card workspace-start">
      <div><p className="eyebrow">NOUVEAU PROJET</p><h3>Commencer par un périmètre usine</h3><p className="muted">Une session garde les métadonnées enregistrées. Son identifiant reste dans l’URL pour reprendre ce même périmètre après actualisation.</p></div>
      <div className="workspace-start-form">
        <label>Nom du projet<input value={projectName} onChange={(event) => setProjectName(event.target.value)} /></label>
        <label>Site<select value={siteId ?? ''} onChange={(event) => setSiteId(Number(event.target.value))} disabled={sites.isPending || sites.isError}>{sites.isPending && <option value="">Chargement…</option>}{(sites.data ?? []).map((site) => <option key={site.id} value={site.id}>{site.name}</option>)}</select></label>
        <button className="button-primary" type="button" onClick={() => create.mutate()} disabled={!canManageWorkspace || create.isPending || siteId === undefined || !projectName.trim()}>{create.isPending ? 'Création…' : <>Ouvrir le workspace <ArrowRightIcon size={17} aria-hidden="true" /></>}</button>
      </div>
    </section>}
    {authUser && (!sessionId || current) && !canManageWorkspace && <StatePanel tone="warning" title="Workspace en lecture seule" text="Votre rôle sur ce site autorise la consultation, mais pas la création de session, l’ajout de fichier ou la validation." />}
    {sites.isError && <StatePanel tone="error" title="Sites indisponibles" text="Aucun périmètre ne peut être sélectionné." action="Réessayer" onAction={() => sites.refetch()} />}
    {create.isError && <StatePanel tone="error" title="Impossible d’ouvrir le projet" text={create.error instanceof Error ? create.error.message : 'L’API est indisponible.'} action="Réessayer" onAction={() => create.mutate()} />}

    {sessionId && <>
      <div className="workspace-stepper" role="list" aria-label="Progression du projet"><span role="listitem" aria-current={current?.status === 'validated' ? undefined : 'step'} className={current?.status === 'validated' ? 'done' : 'active'}>01 Déposer</span><i aria-hidden="true" /><span role="listitem" aria-current={current?.status === 'validated' ? 'step' : undefined} className={current?.status === 'validated' ? 'done' : ''}>02 Comprendre</span><i aria-hidden="true" /><span role="listitem">03 Atelier 2D</span><i aria-hidden="true" /><span role="listitem">04 Opportunités</span></div>
      {session.isError && <StatePanel tone="error" title="Session indisponible" text={session.error instanceof Error ? session.error.message : 'Impossible de relire le projet.'} action="Réessayer" onAction={() => session.refetch()} />}
      <div className="workspace-session-link"><span>Session reprise par l’URL · <Link to="/workspace">ouvrir un nouveau périmètre</Link></span><button type="button" className="button-secondary" onClick={() => session.refetch()} disabled={session.isFetching}>Actualiser la session</button></div>
      <div className="workspace-grid">
        <section className="surface-card dropzone-card">
          <SectionTitle eyebrow="COLLECTE DES DONNÉES" title="Déposer les sources" />
          <p className="muted">Cette prévisualisation enregistre seulement le nom, le type et la taille. Le dossier surveillé traite le binaire séparément et ne le rattache pas encore automatiquement à cette session.</p>
          <div className="dropzone"><span className="dropzone-icon"><UploadSimpleIcon size={32} aria-hidden="true" /></span><strong>Référencer plusieurs fichiers</strong><small>Prévisualisation locale · seuls le nom, le type et la taille sont transmis par cet écran</small><input aria-label="Fichiers industriels" type="file" multiple disabled={!sessionId || !canManageWorkspace} onChange={(event) => { Array.from(event.target.files ?? []).forEach((file) => register.mutate(file)); event.currentTarget.value = ''; }} /></div>
          <label className="source-select">Rôle des prochains fichiers<select value={sourceKind} disabled={!canManageWorkspace} onChange={(event) => setSourceKind(event.target.value as ImportSourceKind)}><option value="unknown">Détection automatique</option>{sourceOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
          {register.isPending && <p className="helper-status">Enregistrement des métadonnées…</p>}
          {register.isError && <p className="helper-error">Métadonnées non enregistrées. Réessayez avec le même fichier.</p>}
        </section>

        <aside className="surface-card understanding-card">
          <SectionTitle eyebrow="EXTRACTEUR" title="Ce que le système comprend" />
          {!current || current.files.length === 0 ? <EmptyPanel title="En attente de métadonnées" text="Référencez un fichier pour documenter le périmètre. Le hash et le profil worker ne sont pas encore reliés automatiquement à cet écran." /> : <>
            <div className="understanding-score"><strong>{Math.round((current.summary.confidence ?? 0) * 100)}%</strong><span>confiance globale</span></div>
            <div className="understanding-list">{current.files.map((file) => <div className="understanding-file" key={file.id}><div><strong>{file.file_name}</strong><small>{sourceLabel(file.source_kind)} · {file.profile.recognized.length} champs reconnus · {file.profile.unknown.length} à vérifier</small></div><span className={`status-label status-label-${file.status === 'failed' ? 'failed' : file.status === 'validated' ? 'completed' : 'pending'}`}>{fileStatusLabel(file.status)}</span></div>)}</div>
            <div className="workspace-callout"><strong>{canValidate ? `${current.summary.unknownColumns ?? 0} ambiguïté(s) détectée(s)` : 'Rattachement worker non connecté'}</strong><p>{canValidate ? 'Validez les mappings avant de générer l’atelier logique.' : 'Le hash et le profil doivent être fournis par une intégration worker ultérieure. Aucun résultat n’est simulé dans cet écran.'}</p></div>
            <button className="button-primary workspace-validate" type="button" onClick={() => validate.mutate()} disabled={!canManageWorkspace || !canValidate || validate.isPending || current.status === 'validated'}>{current.status === 'validated' ? 'Mapping validé' : validate.isPending ? 'Validation…' : canValidate ? <>Valider la compréhension <ArrowRightIcon size={17} aria-hidden="true" /></> : 'Validation indisponible'}</button>
            {validate.isError && <p className="helper-error">Validation refusée : le profilage ou le hash du fichier est incomplet.</p>}
          </>}
        </aside>
      </div>

      {current?.status === 'validated' && <section className="workspace-next surface-card"><div><p className="eyebrow">PROCHAINE ÉTAPE</p><h3>Votre atelier logique est prêt à être généré.</h3><p className="muted">Les positions seront présentées comme suggérées tant qu’aucun plan physique ou coordonnée fiable n’a été importé.</p></div><div className="workspace-next-actions"><Link className="button-primary" to={`/sites/${current.site_id}/workshop`}>Ouvrir l’atelier 2D <ArrowRightIcon size={17} aria-hidden="true" /></Link><Link className="button-secondary" to={`/sites/${current.site_id}/opportunities`}>Voir les opportunités</Link></div></section>}
    </>}
  </section>;
}
