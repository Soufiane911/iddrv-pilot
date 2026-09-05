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
      <div><p className="eyebrow">CATALOGUE DES SOURCES</p><h2>Référencer les exports du périmètre</h2><p className="muted">Cette page conserve les métadonnées des fichiers et l’état de leur session côté serveur. Elle ne téléverse pas les binaires et ne lance pas encore l’ingestion.</p></div>
      <div className="workspace-status"><span className="status-pulse" /> Runtime local · données maîtrisées</div>
    </div>

    {!sessionId && <section className="surface-card workspace-start">
      <div><p className="eyebrow">NOUVEAU PROJET · SESSION CATALOGUE</p><h3>Commencer par un périmètre usine</h3><p className="muted">Une session garde les métadonnées enregistrées côté serveur. Son identifiant reste dans l’URL pour reprendre ce même périmètre après actualisation.</p></div>
      <div className="workspace-start-form">
        <label>Nom du projet<input value={projectName} onChange={(event) => setProjectName(event.target.value)} /></label>
        <label>Site<select value={siteId ?? ''} onChange={(event) => setSiteId(Number(event.target.value))} disabled={sites.isPending || sites.isError}>{sites.isPending && <option value="">Chargement…</option>}{(sites.data ?? []).map((site) => <option key={site.id} value={site.id}>{site.name}</option>)}</select></label>
        <button className="button-primary" type="button" onClick={() => create.mutate()} disabled={!canManageWorkspace || create.isPending || siteId === undefined || !projectName.trim()}>{create.isPending ? 'Création…' : <>Ouvrir le workspace <ArrowRightIcon size={17} aria-hidden="true" /></>}</button>
      </div>
    </section>}
    {authUser && (!sessionId || current) && !canManageWorkspace && <StatePanel tone="warning" title="Workspace en lecture seule" text="Votre rôle sur ce site autorise la consultation, mais pas la création de session, l’ajout de fichier ou la validation." />}
    {sites.isError && <StatePanel tone="error" title="Sites indisponibles" text="Aucun périmètre ne peut être sélectionné." action="Réessayer" onAction={() => sites.refetch()} />}
    {!sites.isPending && !sites.isError && (sites.data ?? []).length === 0 && <EmptyPanel title="Aucun site accessible" text="Un administrateur doit vous attribuer un périmètre avant de créer une session catalogue." />}
    {create.isError && <StatePanel tone="error" title="Impossible d’ouvrir le projet" text={create.error instanceof Error ? create.error.message : 'L’API est indisponible.'} action="Réessayer" onAction={() => create.mutate()} />}

    {sessionId && <>
      <div className="workspace-stepper" role="list" aria-label="Progression de la session catalogue"><span role="listitem" aria-current={current?.status === 'validated' ? undefined : 'step'} className={current?.status === 'validated' ? 'done' : 'active'}>01 Référencer</span><i aria-hidden="true" /><span role="listitem" aria-current={current?.status === 'validated' ? 'step' : undefined} className={current?.status === 'validated' ? 'done' : ''}>02 Valider les métadonnées</span><i aria-hidden="true" /><span role="listitem">03 Ingestion ultérieure</span></div>
      {session.isError && <StatePanel tone="error" title="Session indisponible" text={session.error instanceof Error ? session.error.message : 'Impossible de relire le projet.'} action="Réessayer" onAction={() => session.refetch()} />}
      {!session.isPending && !session.isError && current && <div className="workspace-session-link"><span>Session reprise par l’URL · catalogue · <Link to="/workspace">ouvrir un nouveau périmètre</Link></span><button type="button" className="button-secondary" onClick={() => session.refetch()} disabled={session.isFetching}>Actualiser la session</button></div>}
      {session.isPending && <StatePanel tone="loading" title="Chargement de la session" text="Lecture des métadonnées persistées côté serveur." />}
      {!session.isPending && !session.isError && current && <div className="workspace-grid">
        <section className="surface-card dropzone-card">
          <SectionTitle eyebrow="RÉFÉRENCEMENT" title="Référencer les exports" />
          <p className="muted">Sélectionnez un fichier local pour transmettre uniquement son nom, son type et sa taille. Le binaire n’est pas téléversé et le worker ne le rattache pas encore automatiquement à cette session.</p>
          <div className="dropzone"><span className="dropzone-icon"><UploadSimpleIcon size={32} aria-hidden="true" /></span><strong>Ajouter des métadonnées de fichier</strong><small>Aucun contenu n’est envoyé par cet écran · le catalogue est conservé par l’API</small><input aria-label="Fichiers industriels — métadonnées uniquement" type="file" multiple disabled={!sessionId || !canManageWorkspace} onChange={(event) => { Array.from(event.target.files ?? []).forEach((file) => register.mutate(file)); event.currentTarget.value = ''; }} /></div>
          <label className="source-select">Rôle des prochains fichiers<select value={sourceKind} disabled={!canManageWorkspace} onChange={(event) => setSourceKind(event.target.value as ImportSourceKind)}><option value="unknown">Détection automatique</option>{sourceOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
          {register.isPending && <p className="helper-status">Enregistrement des métadonnées…</p>}
          {register.isError && <p className="helper-error">Métadonnées non enregistrées. Réessayez avec le même fichier.</p>}
        </section>

        <aside className="surface-card understanding-card">
          <SectionTitle eyebrow="CATALOGUE SERVEUR" title="Métadonnées connues" />
          {!current || current.files.length === 0 ? <EmptyPanel title="En attente de métadonnées" text="Référencez un fichier pour documenter le périmètre. Le hash et le profil worker ne sont pas encore reliés automatiquement à cet écran." /> : <>
            <div className="understanding-score"><strong>{Math.round((current.summary.confidence ?? 0) * 100)}%</strong><span>confiance globale</span></div>
            <div className="understanding-list">{current.files.map((file) => <div className="understanding-file" key={file.id}><div><strong>{file.file_name}</strong><small>{sourceLabel(file.source_kind)} · {file.profile.recognized.length} champs reconnus · {file.profile.unknown.length} à vérifier</small></div><span className={`status-label status-label-${file.status === 'failed' ? 'failed' : file.status === 'validated' ? 'completed' : 'pending'}`}>{fileStatusLabel(file.status)}</span></div>)}</div>
            <div className="workspace-callout"><strong>{canValidate ? `${current.summary.unknownColumns ?? 0} ambiguïté(s) détectée(s)` : 'Profilage worker non raccordé'}</strong><p>{canValidate ? 'Validez l’état des métadonnées pour clôturer le catalogue. Cette action ne déclenche pas l’ingestion.' : 'Le hash et le profil doivent être fournis par une intégration worker ultérieure. Aucun résultat n’est simulé dans cet écran.'}</p></div>
            <button className="button-primary workspace-validate" type="button" aria-label={current.status === 'validated' ? 'Catalogue validé' : 'Valider la compréhension — métadonnées'} onClick={() => validate.mutate()} disabled={!canManageWorkspace || !canValidate || validate.isPending || current.status === 'validated'}>{current.status === 'validated' ? 'Catalogue validé' : validate.isPending ? 'Validation…' : canValidate ? <>Valider les métadonnées <ArrowRightIcon size={17} aria-hidden="true" /></> : 'Validation indisponible'}</button>
            {validate.isError && <p className="helper-error">Validation refusée : le profilage ou le hash du fichier est incomplet.</p>}
          </>}
        </aside>
      </div>}

      {current?.status === 'validated' && <section className="workspace-next surface-card"><div><p className="eyebrow">CATALOGUE VALIDÉ</p><h3>Les métadonnées de la session sont validées.</h3><p className="muted">Cette validation ne lance pas l’ingestion et ne génère pas encore d’atelier. Le raccordement du worker au pipeline reste une étape ultérieure du pilote.</p></div></section>}
    </>}
  </section>;
}
