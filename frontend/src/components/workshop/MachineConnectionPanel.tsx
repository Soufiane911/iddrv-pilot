import './MachineConnectionPanel.css';
import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { ApiClient, ContinuityRecoveryInput, ContinuityReview, Machine, MachineConnection, MachineConnectionInput } from '../../lib/api';

const states: Record<string, string> = { disabled: 'Collecte désactivée', configured: 'Prête à collecter', collecting: 'Collecte en cours', retrying: 'Nouvelle tentative prévue', access_error: 'Accès source refusé', configuration_error: 'Configuration à vérifier', gap_detected: 'Lacune de collecte · reprise à vérifier', contract_error: 'Données source à vérifier' };
const errors: Record<string, string> = { continuity_review_required: 'La continuité du flux doit être vérifiée avant de reprendre.', source_identity_locked: 'Cette source possède déjà un historique. Sa référence ne peut pas être remplacée.', collection_busy: 'Une lecture est en cours. Réessayez dans un instant.', cursor_expired: 'L’historique demandé n’est plus disponible à la source.', event_content_conflict: 'La source a modifié un événement déjà reçu.', origin_not_allowed: 'Cette adresse doit être autorisée dans la configuration du serveur.' };
const date = (value?: string | null) => value ? new Date(value).toLocaleString('fr-FR') : 'Aucune réponse reçue';

function ConnectionForm({ api, machine, value, canConfigure }: { api: ApiClient; machine: Machine; value: MachineConnection | null; canConfigure: boolean }) {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<MachineConnectionInput>(() => ({ base_url: value?.base_url ?? '', external_machine_id: value?.external_machine_id ?? machine.erpRef ?? '', secret_ref: value?.secret_ref ?? null, poll_interval_s: value?.poll_interval_s ?? 1, enabled: value?.enabled ?? false, mapping_profile: 'iddrv-cycle-v1' }));
  const save = useMutation({ mutationFn: () => api.saveMachineConnection(machine.id, draft), onSuccess: data => queryClient.setQueryData(['machine-connection', machine.id], data) });
  const test = useMutation({ mutationFn: () => api.testMachineConnection(machine.id, draft) });
  const result = test.data;
  const busy = save.isPending || test.isPending;
  const message = save.error ?? test.error;
  const change = (update: Partial<MachineConnectionInput>) => { setDraft(old => ({ ...old, ...update })); test.reset(); save.reset(); };
  return <form onSubmit={event => { event.preventDefault(); save.mutate(); }} className="machine-connection-form">
    <p>{states[value?.state ?? 'disabled'] ?? 'État inconnu'}</p>
    {value?.public_error && <p role="alert" className="helper-error">{errors[value.public_error] ?? 'La source demande une vérification de sa configuration.'}</p>}
    <dl><div><dt>Dernière réponse API</dt><dd>{date(value?.last_response_at)}</dd></div><div><dt>Dernier cycle reçu</dt><dd>{value?.last_cycle_at ? date(value.last_cycle_at) : 'Aucun cycle reçu'}</dd></div></dl>
    <p className="muted">Une API joignable ne confirme pas que la presse produit. La qualité reste inconnue sans observation.</p>
    <fieldset disabled={!canConfigure || busy}>
      <label>Adresse API<input type="url" required value={draft.base_url} placeholder="http://press-simulator:8090" onChange={event => change({ base_url: event.target.value })} /></label>
      <label>Référence de presse source<input required value={draft.external_machine_id} onChange={event => change({ external_machine_id: event.target.value })} /></label>
      <label>Référence de secret (facultatif)<input value={draft.secret_ref ?? ''} placeholder="PRESS_606" onChange={event => change({ secret_ref: event.target.value || null })} /></label>
      <label>Fréquence de lecture (secondes)<input type="number" min={1} max={60} required value={draft.poll_interval_s} onChange={event => change({ poll_interval_s: Number(event.target.value) })} /></label>
      <label><input type="checkbox" checked={draft.enabled} onChange={event => change({ enabled: event.target.checked })} />Collecte active</label>
      <button className="button-secondary" type="button" onClick={event => { if (event.currentTarget.form?.reportValidity()) test.mutate(); }}>{test.isPending ? 'Test en cours…' : 'Tester la connexion'}</button>
      <button className="button-primary" type="submit">{save.isPending ? 'Enregistrement…' : 'Enregistrer la connexion'}</button>
    </fieldset>
    {busy && <p role="status">{test.isPending ? 'Test de connexion en cours…' : 'Enregistrement de la connexion…'}</p>}
    {result && <p role="status" className={result.ok ? 'helper-status' : 'helper-error'}>{result.ok ? `API joignable · production ${result.source_state === 'running' ? 'observée' : result.source_state === 'stopped' ? 'arrêtée selon la source' : 'inconnue'}. Historique disponible depuis : ${result.oldest_available_at ? date(result.oldest_available_at) : 'aucun cycle disponible'}.` : errors[result.public_error ?? ''] ?? 'Connexion impossible. Vérifiez l’adresse, la référence et les accès.'}{result.sample_valid === false ? ' Le cycle de test contient des mesures à vérifier.' : ''}</p>}
    {message && <p role="alert" className="helper-error">{errors[message.message] ?? message.message}</p>}
    {save.isSuccess && <p role="status">Configuration enregistrée.</p>}
    {!canConfigure && <p className="muted">Configuration réservée aux superviseurs et administrateurs du site.</p>}
  </form>;
}

export function MachineConnectionPanel({ api, machine }: { api: ApiClient; machine: Machine }) {
  const connection = useQuery({ queryKey: ['machine-connection', machine.id], queryFn: () => api.getMachineConnection(machine.id), refetchInterval: 5000 });
  const auth = useQuery({ queryKey: ['auth-me'], queryFn: () => api.getCurrentUser() });
  const role = (machine.siteId != null ? auth.data?.siteRoles?.[machine.siteId] : undefined) ?? auth.data?.role;
  const canConfigure = role === 'supervisor' || role === 'admin';
  return <details className="workshop-inspector-section"><summary>Connexion de la presse</summary>
    {connection.isPending ? <p role="status">Lecture de la connexion…</p> : connection.isError ? <p role="alert">Connexion indisponible. <button onClick={() => connection.refetch()}>Réessayer</button></p> : <><ConnectionForm key={machine.id} api={api} machine={machine} value={connection.data} canConfigure={canConfigure} />{connection.data?.state === 'gap_detected' ? <ContinuityRecovery api={api} machine={machine} canConfigure={canConfigure} /> : null}</>}
  </details>;
}

function ContinuityRecovery({ api, machine, canConfigure }: { api: ApiClient; machine: Machine; canConfigure: boolean }) {
  const review = useQuery({ queryKey: ['machine-continuity', machine.id], queryFn: () => api.getContinuityReview(machine.id), enabled: canConfigure });
  const [decision, setDecision] = useState<ContinuityRecoveryInput['decision']>('resume_available');
  const [newStreamId, setNewStreamId] = useState('');
  const [resumeCursor, setResumeCursor] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const recover = useMutation({ mutationFn: (value: ContinuityRecoveryInput) => api.recoverContinuity(machine.id, value), onSuccess: () => review.refetch() });
  if (!canConfigure) return <p className="muted">La reprise d’une lacune est réservée aux superviseurs et administrateurs.</p>;
  if (review.isPending) return <p role="status">Lecture de la position validée…</p>;
  if (review.isError || !review.data) return <p role="alert">Informations de continuité indisponibles.</p>;
  const value: ContinuityReview = review.data;
  const stream = newStreamId || value.lastValidated.streamId || '';
  return <section className="continuity-recovery" aria-label="Reprise après lacune"><h4>Reprise de la collecte</h4><p className="helper-error">{value.publicError ?? 'Lacune détectée'} · aucune avance automatique à latest.</p><dl><div><dt>Dernière position validée</dt><dd>{value.lastValidated.cursor ?? 'Aucune'}</dd></div><div><dt>Historique encore disponible</dt><dd>{value.availableHistory.oldestAvailableAt ?? 'Non communiqué'}</dd></div></dl>
    <label>Décision<select value={decision} onChange={(event) => setDecision(event.target.value as ContinuityRecoveryInput['decision'])}><option value="resume_available">Reprendre l’historique disponible</option><option value="initialize_new_stream">Initialiser un nouveau flux</option></select></label>
    {decision === 'resume_available' ? <label>Curseur de reprise<input value={resumeCursor} onChange={(event) => setResumeCursor(event.target.value)} placeholder="flux:position avant rétention" /></label> : <label>Identité du nouveau flux<input value={newStreamId} onChange={(event) => setNewStreamId(event.target.value)} placeholder="flux-nouveau" /></label>}
    <label className="continuity-confirm"><input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} />Je confirme conserver la lacune et l’historique disponible.</label>
    <button className="button-secondary" type="button" disabled={!confirmed || recover.isPending || !stream || (decision === 'resume_available' && !resumeCursor)} onClick={() => recover.mutate({ decision, expectedStreamId: value.lastValidated.streamId ?? '', expectedCursor: value.lastValidated.cursor, newStreamId: stream, availableFromSequence: value.availableHistory.fromSequence, resumeCursor: decision === 'resume_available' ? resumeCursor : null, confirmation: 'I understand the gap and retained history' })}>{recover.isPending ? 'Confirmation…' : 'Confirmer la reprise'}</button>
    {recover.isError ? <p role="alert">La confirmation n’a pas été acceptée. Relisez la position avant de réessayer.</p> : null}{recover.isSuccess ? <p role="status">Choix journalisé. La lacune reste conservée.</p> : null}
  </section>;
}
