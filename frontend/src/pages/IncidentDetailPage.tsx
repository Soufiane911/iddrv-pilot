import { ArrowLeftIcon } from '@phosphor-icons/react/ArrowLeft';
import { CheckIcon } from '@phosphor-icons/react/Check';
import { XIcon } from '@phosphor-icons/react/X';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { FormEvent, useMemo, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { useApi } from '../App';
import { EmptyPanel, formatDate, formatNumber, formatPercent, incidentConfidenceLabel, incidentSeverityLabel, incidentSymptomLabel, MetricCard, SectionTitle, StatePanel } from '../components/Ui';
import { canWriteSite, type AuthUser, type Evidence, type Hypothesis } from '../lib/api';

function evidenceValue(evidence: Evidence, field: string): number | undefined {
  const value = evidence.observation[field];
  return typeof value === 'number' ? value : undefined;
}

function evidenceMetricLabel(value: string): string {
  return ({ scrap_rate: 'Taux de rebut', barrel_temp_zone2_c: 'Température zone 2', operator_note: 'Note opérateur' } as Record<string, string>)[value] ?? value.split('_').join(' ');
}

function evidenceSourceLabel(value: string): string {
  return ({ cycle_aggregate: 'Agrégat de cycles', operator_note: 'Note opérateur', quality_check: 'Contrôle qualité' } as Record<string, string>)[value] ?? value.split('_').join(' ');
}

function nextCheckLabel(value: string): string {
  return ({ inspect_barrel_zone_2_heating: 'Contrôler la chauffe de la zone 2' } as Record<string, string>)[value] ?? value.split('_').join(' ');
}

function observationFieldLabel(value: string): string {
  return ({ value: 'Valeur', slope_per_day: 'Pente par jour', count: 'Nombre', mean: 'Moyenne', min: 'Minimum', max: 'Maximum' } as Record<string, string>)[value] ?? value.split('_').join(' ');
}

function evidenceObservation(evidence: Evidence): string {
  const unit = typeof evidence.observation.unit === 'string' ? evidence.observation.unit : '';
  const fields = Object.entries(evidence.observation).filter(([key, value]) => key !== 'unit' && (typeof value === 'number' || typeof value === 'string' || typeof value === 'boolean'));
  if (fields.length === 0) return 'Observation structurée sans valeur scalaire.';
  return fields.map(([key, value]) => `${observationFieldLabel(key)} : ${typeof value === 'number' ? formatNumber(value, 2) : String(value)}${typeof value === 'number' && unit ? ` ${unit}` : ''}`).join(' · ');
}

function EvidenceRow({ evidence }: { evidence: Evidence }) {
  const baseline = evidence.baseline && typeof evidence.baseline.value === 'number' ? evidence.baseline.value : undefined;
  const unit = typeof evidence.observation.unit === 'string' ? evidence.observation.unit : '';
  return <article className={`evidence-row ${evidence.supports ? 'supports' : 'contradicts'}`}><div className="evidence-mark" aria-hidden="true">{evidence.supports ? <CheckIcon size={17} weight="bold" /> : <XIcon size={17} weight="bold" />}</div><div className="evidence-main"><span className="visually-hidden">{evidence.supports ? 'Élément favorable' : 'Élément contradictoire'}</span><div className="evidence-heading"><strong>{evidenceMetricLabel(evidence.metric)}</strong><span>{evidenceSourceLabel(evidence.source_kind)}</span></div><p>{evidenceObservation(evidence)}</p>{baseline !== undefined && <small>Baseline : {formatNumber(baseline, 2)} {typeof evidence.baseline?.unit === 'string' ? evidence.baseline.unit : unit} · Δ {evidence.delta !== null && evidence.delta !== undefined ? formatNumber(evidence.delta, 2) : 'N/D'}</small>}{evidence.excerpt && <small className="evidence-excerpt">“{evidence.excerpt}”</small>}</div><div className="evidence-window">{formatDate(evidence.window.start, false)}<br /><span>→ {formatDate(evidence.window.end, false)}</span></div></article>;
}

export function IncidentDetailPage() {
  const { incidentId = '' } = useParams();
  const api = useApi();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const runId = searchParams.get('run') ?? undefined;
  const authUser = queryClient.getQueryData<AuthUser>(['auth-me']);
  const [feedbackVerdict, setFeedbackVerdict] = useState('confirmed');
  const [feedbackComment, setFeedbackComment] = useState('');
  const [feedbackSent, setFeedbackSent] = useState(false);
  const incidentQuery = useQuery({ queryKey: ['incident', incidentId], queryFn: () => api.getIncident(incidentId), enabled: Boolean(incidentId) });
  const canRunInvestigation = canWriteSite(authUser, incidentQuery.data?.site_id);
  const evidenceQuery = useQuery({ queryKey: ['incident-evidence', incidentId], queryFn: () => api.getEvidence(incidentId), enabled: Boolean(incidentId) && !runId });
  const investigationQuery = useQuery({ queryKey: ['investigation-run', runId], queryFn: () => api.getInvestigation(runId as string), enabled: Boolean(runId), retry: false });
  const investigationMutation = useMutation({
    mutationFn: () => api.runInvestigation(incidentId, incidentQuery.data?.data_cutoff),
    onMutate: () => queryClient.cancelQueries({ queryKey: ['incident-evidence', incidentId] }),
    onSuccess: (result) => {
      queryClient.setQueryData(['incident-evidence', incidentId], result.evidence);
      if (result.run_id) {
        queryClient.setQueryData(['investigation-run', result.run_id], { run_id: result.run_id, incident_id: incidentId, status: 'completed', dataCutoff: result.incident.data_cutoff, hypotheses: result.hypotheses, evidence: result.evidence });
        const next = new URLSearchParams(searchParams);
        next.set('run', result.run_id);
        setSearchParams(next, { replace: true });
      }
    },
  });
  const feedbackMutation = useMutation({ mutationFn: () => api.submitFeedback(incidentId, feedbackVerdict, feedbackComment || undefined), onSuccess: () => { setFeedbackSent(true); setFeedbackComment(''); } });
  const mutationRun = investigationMutation.data && (!runId || investigationMutation.data.run_id === runId) ? investigationMutation.data : undefined;
  const runIncidentMismatch = Boolean(investigationQuery.data && investigationQuery.data.incident_id !== incidentId);
  const persistedRun = runIncidentMismatch ? undefined : investigationQuery.data;
  const evidence = persistedRun?.evidence ?? (!runId ? evidenceQuery.data : undefined) ?? mutationRun?.evidence ?? [];
  const hypotheses: Hypothesis[] = persistedRun?.hypotheses ?? mutationRun?.hypotheses ?? [];
  const evidencePending = runId ? investigationQuery.isPending : evidenceQuery.isPending;
  const evidenceUnavailable = runIncidentMismatch || (runId ? investigationQuery.isError : evidenceQuery.isError);
  const scrapEvidence = evidence.find((item) => item.metric === 'scrap_rate');
  const temperatureEvidence = evidence.find((item) => item.metric === 'barrel_temp_zone2_c');
  const timeline = useMemo(() => incidentQuery.data ? [{ label: 'Avant', date: new Date(new Date(incidentQuery.data.started_at).getTime() - 60 * 60 * 1000).toISOString(), tone: 'before' }, { label: 'Pendant', date: incidentQuery.data.started_at, tone: 'during' }, { label: 'Fin du signal', date: incidentQuery.data.ended_at ?? incidentQuery.data.data_cutoff, tone: 'during' }, { label: 'Après / cutoff', date: incidentQuery.data.data_cutoff, tone: 'after' }] : [], [incidentQuery.data]);

  function submitFeedback(event: FormEvent) { event.preventDefault(); feedbackMutation.mutate(); }
  if (incidentQuery.isPending) return <section className="page"><StatePanel tone="loading" title="Chargement de l’incident" text="Le contexte et les preuves sont en cours de récupération." /></section>;
  if (incidentQuery.isError || !incidentQuery.data) return <section className="page"><StatePanel tone="error" title="Incident introuvable" text={incidentQuery.error instanceof Error ? incidentQuery.error.message : 'Ce signal n’existe pas ou n’est plus accessible.'} action="Retour aux incidents" onAction={() => window.history.back()} /></section>;
  const incident = incidentQuery.data;
  return <section className="page page-wide incident-detail-page">
    <div className="page-intro"><div><Link className="back-link" to="/incidents"><ArrowLeftIcon size={17} aria-hidden="true" />Tous les incidents</Link><p className="eyebrow">INCIDENT · {incident.id.slice(0, 8)}{runId ? ` · RUN ${runId.slice(0, 8)}` : ''}</p><h2>{incidentSymptomLabel(incident.symptom)}</h2><p className="muted">Presse {incident.machine_erp_ref ?? incident.machine_id} · OF {incident.production_order_id ?? 'non renseigné'} · créé le {formatDate(incident.created_at)}</p></div><div className="detail-actions"><span className={`severity severity-${incident.severity}`}>{incidentSeverityLabel(incident.severity)}</span>{canRunInvestigation ? <button type="button" className="button-primary" onClick={() => investigationMutation.mutate()} disabled={investigationMutation.isPending}>{investigationMutation.isPending ? 'Investigation…' : 'Lancer l’investigation'}</button> : <span className="readonly-note">Lecture seule</span>}</div></div>
    {investigationMutation.isError && <StatePanel tone="error" title="Investigation impossible" text={investigationMutation.error instanceof Error ? investigationMutation.error.message : 'Le moteur déterministe n’a pas pu produire de résultat.'} action="Réessayer" onAction={() => investigationMutation.mutate()} />}
    {investigationMutation.isSuccess && <StatePanel tone="success" title="Investigation terminée" text="Les chiffres affichés ci-dessous proviennent du run déterministe persisté. Son identifiant est conservé dans l’URL." />}
    {(investigationQuery.isError || runIncidentMismatch) && <StatePanel tone="error" title={runIncidentMismatch ? 'Run incompatible' : 'Run indisponible'} text={runIncidentMismatch ? 'Ce run appartient à un autre incident et ne sera pas affiché ici.' : investigationQuery.error instanceof Error ? investigationQuery.error.message : 'Ce run ne peut pas être relu.'} action="Retirer le run de l’URL" onAction={() => { const next = new URLSearchParams(searchParams); next.delete('run'); setSearchParams(next, { replace: true }); }} />}
    <div className="detail-summary"><MetricCard label="Fenêtre du signal" value={formatDate(incident.started_at, false)} detail={`jusqu’au ${formatDate(incident.ended_at ?? incident.data_cutoff, false)}`} /><MetricCard label="Rebut observé" value={scrapEvidence ? formatPercent(evidenceValue(scrapEvidence, 'value')) : 'N/D'} detail={scrapEvidence?.baseline ? `baseline ${formatPercent(typeof scrapEvidence.baseline.value === 'number' ? scrapEvidence.baseline.value : undefined)}` : 'preuve à calculer'} tone={scrapEvidence?.supports ? 'danger' : 'neutral'} /><MetricCard label="Zone 2" value={temperatureEvidence ? `${formatNumber(evidenceValue(temperatureEvidence, 'value'), 1)} °C` : 'N/D'} detail={temperatureEvidence?.baseline ? `baseline ${formatNumber(typeof temperatureEvidence.baseline.value === 'number' ? temperatureEvidence.baseline.value : undefined, 1)} °C` : 'preuve à calculer'} tone={temperatureEvidence?.supports ? 'warning' : 'neutral'} /><MetricCard label="Confiance" value={incidentConfidenceLabel(incident.confidence)} detail="classification serveur" tone={incident.confidence ? (incident.confidence === 'high' ? 'good' : 'warning') : undefined} /></div>
    <section className="surface-card timeline-card"><SectionTitle eyebrow="RECONSTITUTION TEMPORELLE" title="Avant · pendant · après" /><div className="investigation-timeline">{timeline.map((item) => <div key={item.label} className={`timeline-step ${item.tone}`}><span className="timeline-dot" aria-hidden="true" /><strong>{item.label}</strong><time dateTime={item.date}>{formatDate(item.date)}</time></div>)}</div><p className="timeline-cutoff">Cutoff de données : <strong>{formatDate(incident.data_cutoff)}</strong>. L’heure courante n’est jamais utilisée pour ce replay.</p></section>
    <div className="investigation-grid"><section className="surface-card hypotheses-card"><SectionTitle eyebrow="RAISONNEMENT STRUCTURÉ" title="Hypothèses"><p className="muted small">{hypotheses.length ? `${hypotheses.length} cause${hypotheses.length > 1 ? 's' : ''} classée${hypotheses.length > 1 ? 's' : ''} par le moteur local.` : evidence.length ? 'Les preuves persistées sont lisibles. Les hypothèses nécessitent l’identifiant du run dans l’URL.' : canRunInvestigation ? 'Lancez une investigation pour produire des hypothèses et leurs liens de preuve.' : 'Aucun run lisible n’est associé à cette URL en lecture seule.'}</p></SectionTitle>{hypotheses.length ? <div className="hypothesis-list">{hypotheses.map((hypothesis, index) => <article className="hypothesis-card" key={hypothesis.cause_code}><div className="hypothesis-confidence"><strong>{Math.round(hypothesis.confidence * 100)}%</strong><span>confiance</span></div><div><p className="hypothesis-rank">Rang {index + 1}</p><h3>{hypothesis.label}</h3><p className="hypothesis-code">Code : {hypothesis.cause_code}</p><div className="hypothesis-links"><span>{hypothesis.supporting_evidence_ids.length} élément{hypothesis.supporting_evidence_ids.length > 1 ? 's' : ''} favorable{hypothesis.supporting_evidence_ids.length > 1 ? 's' : ''}</span><span>{hypothesis.contradicting_evidence_ids.length} contradictoire{hypothesis.contradicting_evidence_ids.length > 1 ? 's' : ''}</span><span>{hypothesis.missing_data.length} donnée{hypothesis.missing_data.length > 1 ? 's' : ''} manquante{hypothesis.missing_data.length > 1 ? 's' : ''}</span></div>{hypothesis.next_check && <div className="next-check"><strong>Prochaine vérification</strong><span>{nextCheckLabel(hypothesis.next_check)}</span></div>}</div></article>)}</div> : <EmptyPanel title="Aucun run disponible" text={canRunInvestigation ? 'Lancez le moteur local ou ouvrez une URL contenant un identifiant de run persisté.' : 'Demandez une URL de run persisté à un analyste.'} />}</section><section className="surface-card evidence-card"><SectionTitle eyebrow="COFFRE DE PREUVES" title="Preuves citées"><span className="evidence-count">{evidenceUnavailable ? 'N/D' : `${evidence.length} preuve${evidence.length > 1 ? 's' : ''}`}</span></SectionTitle>{evidencePending ? <StatePanel tone="loading" title="Lecture des preuves" text="Le coffre persisté est en cours de lecture." /> : evidenceUnavailable ? <StatePanel tone="error" title="Preuves indisponibles" text="Le coffre de preuves n’a pas pu être lu. Aucune absence de preuve n’est déduite." action={runIncidentMismatch ? 'Retirer le run de l’URL' : 'Réessayer'} onAction={() => { if (runIncidentMismatch) { const next = new URLSearchParams(searchParams); next.delete('run'); setSearchParams(next, { replace: true }); } else if (runId) investigationQuery.refetch(); else evidenceQuery.refetch(); }} /> : evidence.length === 0 ? <EmptyPanel title="Preuves non calculées" text="Aucune valeur n’est inventée : lancez l’investigation pour recalculer la fenêtre." /> : <div className="evidence-list">{evidence.map((item) => <EvidenceRow key={item.id} evidence={item} />)}</div>}</section></div>
    <section className="surface-card feedback-card">{!canRunInvestigation ? <StatePanel tone="warning" title="Validation en lecture seule" text="Le rôle viewer peut consulter les preuves mais ne peut pas enregistrer de verdict." /> : <><SectionTitle eyebrow="VALIDATION HUMAINE" title="Votre retour"><p className="muted small">Ce retour est enregistré avec l’incident pour améliorer la recette.</p></SectionTitle>{feedbackSent ? <StatePanel tone="success" title="Retour enregistré" text="Merci. Votre verdict est associé à cet incident." action="Modifier le retour" onAction={() => setFeedbackSent(false)} /> : <form className="feedback-form" onSubmit={submitFeedback}><label htmlFor="feedback-verdict">Verdict</label><select id="feedback-verdict" value={feedbackVerdict} onChange={(event) => setFeedbackVerdict(event.target.value)}><option value="confirmed">Cause confirmée</option><option value="rejected">Cause rejetée</option><option value="uncertain">À confirmer</option></select><label htmlFor="feedback-comment">Commentaire <span>(facultatif)</span></label><textarea id="feedback-comment" value={feedbackComment} onChange={(event) => setFeedbackComment(event.target.value)} maxLength={4000} rows={3} placeholder="Ajoutez un constat terrain…" /><div className="feedback-submit"><span className="muted">Le commentaire reste rattaché à l’incident.</span><button className="button-primary" type="submit" disabled={feedbackMutation.isPending}>{feedbackMutation.isPending ? 'Enregistrement…' : 'Enregistrer le retour'}</button></div>{feedbackMutation.isError && <p className="helper-error">Impossible d’enregistrer le retour. Réessayez.</p>}</form>}</>}</section>
  </section>;
}
