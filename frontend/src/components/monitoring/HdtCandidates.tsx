import { useQuery } from '@tanstack/react-query';
import type { ApiClient } from '../../lib/api';
import { StatePanel } from '../Ui';

const statuses = { executable: 'Exécutable historique', research_only: 'Recherche uniquement', blocked: 'Bloqué — non exécutable' };

export function HdtCandidates({ api }: { api: Pick<ApiClient, 'getHdtCandidates'> }) {
  const query = useQuery({ queryKey: ['hdt-candidates', 1], queryFn: () => api.getHdtCandidates(), retry: false });
  return <section className="surface-card" style={{ padding: 24, marginBottom: 24, overflowWrap: 'anywhere' }} aria-labelledby="hdt-candidates-heading">
    <h3 id="hdt-candidates-heading">Catalogue des candidats HDT</h3>
    <p>Consultation uniquement : aucun changement du modèle utilisé par le simulateur ou le Direct. Les métriques de recherche ne sont pas les métriques live.</p>
    {query.isPending && <StatePanel tone="loading" title="Chargement du catalogue" text="Lecture des candidats versionnés." />}
    {query.isError && <StatePanel tone="error" title="Catalogue indisponible" text="Impossible de lire le catalogue. Vérifiez votre accès." action="Réessayer" onAction={() => { void query.refetch(); }} />}
    {query.isSuccess && <>
      <p role="note">{query.data.notice}</p>
      {query.data.candidates.length === 0 && <StatePanel tone="empty" title="Catalogue vide" text="Aucun candidat disponible." />}
      {query.data.candidates.map(candidate => <article key={candidate.candidate_id} aria-labelledby={`${candidate.candidate_id}-heading`}>
        <h4 id={`${candidate.candidate_id}-heading`}>{candidate.label}</h4>
        <p><strong>{statuses[candidate.status]}</strong>{candidate.default ? ' — défaut applicatif inchangé' : ' — exécution interdite'}</p>
        <p>{candidate.scientific_status}</p>
        {candidate.blocked_reason && <p>Blocage : {candidate.blocked_reason}</p>}
        <p>Artefact : {candidate.artifact.artifact_packaged ? 'distribué (historique)' : 'source_only — non distribué'} · Jeu {candidate.artifact.dataset} · Graine {candidate.artifact.seed ?? 'non vérifiée'}</p>
        {candidate.evaluations.map((evaluation, index) => <div key={index}>
          <h5>{evaluation.phase === 'development' ? 'Développement adaptatif — non confirmatoire' : 'Évaluation de confirmation'}</h5>
          <p>{evaluation.population}</p>
          <p>Rappel utile : {evaluation.useful_recall_pct}% · FP / 1 000 cycles sains : {evaluation.fp_per_1000_healthy_cycles} · Support : {evaluation.support_pct}% · Graines : {evaluation.seeds.join(', ')}</p>
          <p>{evaluation.interpretation}</p>
        </div>)}
        <details>
          <summary>Identité, contrat et preuves — {candidate.label}</summary>
          <p>Identifiant immuable : <code>{candidate.candidate_id}</code></p>
          <p>Version source : {candidate.model_version} · Représentation : {candidate.representation}</p>
          <p>Capteurs ordonnés (unités dans les noms) : {candidate.input_contract.sensors.join(', ')}</p>
          <p>Contexte : {candidate.input_contract.context.join(', ')}</p>
          <p>{candidate.input_contract.preprocessing}</p><p>{candidate.input_contract.decision}</p>
          <p>Artefact référencé : <code>{candidate.artifact.path}</code> · SHA256 : <code>{candidate.artifact.sha256}</code></p>
          <ul>{candidate.evidence.map(proof => <li key={proof.path}><code>{proof.path}</code> · SHA256 : <code>{proof.sha256}</code></li>)}</ul>
          <p>Références documentaires relatives, sans téléchargement ni chargement des artefacts recherche.</p>
        </details>
      </article>)}
    </>}
  </section>;
}
