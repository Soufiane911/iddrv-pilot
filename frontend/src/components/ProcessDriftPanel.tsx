import { CheckIcon } from '@phosphor-icons/react/Check';
import { WarningIcon } from '@phosphor-icons/react/Warning';
import { useQuery } from '@tanstack/react-query';
import { useId } from 'react';
import type { ApiClient, HdtPrediction, ProcessDriftCycle, ProcessDriftInput, ProcessDriftPrediction } from '../lib/api';
import { EmptyPanel, StatePanel, formatNumber } from './Ui';
import { metricLabel } from '../lib/metricLabels';

interface Props {
  api: Pick<ApiClient, 'predictProcessDrift'>;
  siteId: number;
  cycles?: ProcessDriftCycle[];
  cyclesLoading?: boolean;
  cyclesError?: Error | null;
  onRetryCycles?: () => void;
  machineName?: string;
  persistedPrediction?: HdtPrediction | null;
  readOnly?: boolean;
}

function signalLabel(value: string): string {
  const metric = value.replace(/_volatility_20$/, '');
  return `${metricLabel(metric)}${metric !== value ? ' · variabilité sur 20 cycles' : ''}`;
}

function predictionText(prediction: ProcessDriftPrediction): string {
  return prediction.predicted_instability_next_20_cycles
    ? `Trajectoire à inspecter avant les ${prediction.horizon_cycles} prochains cycles.`
    : `Aucune dérive détectée sur les ${prediction.horizon_cycles} prochains cycles.`;
}

export function ProcessDriftPanel({ api, siteId, cycles = [], cyclesLoading = false, cyclesError = null, onRetryCycles, machineName, persistedPrediction, readOnly = false }: Props) {
  const titleId = useId();
  const input: ProcessDriftInput = { site_id: siteId, cycles };
  const query = useQuery({
    queryKey: ['process-drift', siteId, cycles],
    queryFn: () => api.predictProcessDrift(input),
    enabled: cycles.length >= 3 && !readOnly && !persistedPrediction,
    retry: false,
  });

  if (cyclesLoading) {
    return <section className="process-drift-panel" aria-labelledby={titleId}>
      <header className="process-drift-heading"><div><span>HDT · HORIZON DE DÉRIVE</span><h3 id={titleId}>Priorité d’inspection</h3></div></header>
      <StatePanel tone="loading" title="Chargement des cycles bruts" text={`Lecture de l’historique process${machineName ? ` pour ${machineName}` : ''}.`} />
    </section>;
  }

  if (cyclesError) {
    return <section className="process-drift-panel" aria-labelledby={titleId}>
      <header className="process-drift-heading"><div><span>HDT · HORIZON DE DÉRIVE</span><h3 id={titleId}>Priorité d’inspection</h3></div></header>
      <StatePanel tone="error" title="Cycles bruts indisponibles" text={cyclesError.message || 'Impossible de récupérer les cycles bruts.'} action="Réessayer" onAction={onRetryCycles} />
    </section>;
  }

  if (cycles.length < 3) {
    return <section className="process-drift-panel" aria-labelledby={titleId}>
      <header className="process-drift-heading"><div><span>HDT · HORIZON DE DÉRIVE</span><h3 id={titleId}>Priorité d’inspection</h3></div></header>
      <EmptyPanel title="Historique process insuffisant" text="Le score HDT attend au moins 3 cycles bruts pour cette presse." />
    </section>;
  }

  if (persistedPrediction) {
    if (persistedPrediction.status !== 'scored' || persistedPrediction.score == null || persistedPrediction.threshold == null) {
      return <section className="process-drift-panel" aria-labelledby={titleId}><header className="process-drift-heading"><div><span>HDT · HORIZON DE DÉRIVE</span><h3 id={titleId}>Priorité d’inspection</h3></div></header><EmptyPanel title="Historique process insuffisant" text={persistedPrediction.reason ?? 'Le score HDT persistant ne permet pas encore une alerte.'} /></section>;
    }
    const persisted: ProcessDriftPrediction = { model_version: persistedPrediction.modelVersion ?? 'modèle non communiqué', machine_erp_ref: machineName ?? 'presse sélectionnée', anomaly_score: persistedPrediction.score, threshold: persistedPrediction.threshold, horizon_cycles: 20, predicted_instability_next_20_cycles: persistedPrediction.score >= persistedPrediction.threshold, signals: [] };
    return <PersistedPredictionView prediction={persisted} evaluatedThrough={persistedPrediction.evaluatedThrough} titleId={titleId} />;
  }

  if (readOnly) {
    return <section className="process-drift-panel" aria-labelledby={titleId}><header className="process-drift-heading"><div><span>HDT · HORIZON DE DÉRIVE</span><h3 id={titleId}>Priorité d’inspection</h3></div></header><EmptyPanel title="Score HDT en attente" text="Le Direct affiche uniquement les scores persistés disponibles." /></section>;
  }

  if (query.isPending) {
    return <section className="process-drift-panel" aria-labelledby={titleId}>
      <header className="process-drift-heading"><div><span>HDT · HORIZON DE DÉRIVE</span><h3 id={titleId}>Priorité d’inspection</h3></div></header>
      <StatePanel tone="loading" title="Calcul HDT en cours" text={`Analyse de ${cycles.length} cycle(s)${machineName ? ` pour ${machineName}` : ''}.`} />
    </section>;
  }

  if (query.isError || !query.data) {
    return <section className="process-drift-panel" aria-labelledby={titleId}>
      <header className="process-drift-heading"><div><span>HDT · HORIZON DE DÉRIVE</span><h3 id={titleId}>Priorité d’inspection</h3></div></header>
      <StatePanel tone="error" title="Score HDT indisponible" text={query.error instanceof Error ? query.error.message : 'La prédiction de dérive n’est pas disponible.'} action="Réessayer" onAction={() => query.refetch()} />
    </section>;
  }

  const prediction = query.data;
  const driftDetected = prediction.predicted_instability_next_20_cycles;
  return <section className={`process-drift-panel ${driftDetected ? 'is-drift' : 'is-normal'}`} aria-labelledby={titleId}>
    <header className="process-drift-heading"><div><span>HDT · HORIZON DE DÉRIVE</span><h3 id={titleId}>Priorité d’inspection</h3></div><span className="process-drift-status">{driftDetected ? <><WarningIcon size={16} aria-hidden="true" />Dérive détectée</> : <><CheckIcon size={16} aria-hidden="true" />État normal</>}</span></header>
    <div className="process-drift-summary">
      <div><span>SCORE D’ANOMALIE</span><strong>{formatNumber(prediction.anomaly_score, 2)}</strong><small>seuil {formatNumber(prediction.threshold, 2)}</small></div>
      <div><span>PROJECTION</span><strong>{driftDetected ? 'À inspecter' : 'Pas d’alerte'}</strong><small>{predictionText(prediction)}</small></div>
    </div>
    <details className="technical-details process-drift-details"><summary>Signaux contributifs et modèle</summary><div className="process-drift-signals">{prediction.signals.length === 0 ? <p>Aucun signal détaillé communiqué.</p> : <ul>{prediction.signals.map((signal) => <li key={signal.feature}><span title={signal.feature}>{signalLabel(signal.feature)}</span><strong>{formatNumber(signal.volatility, 2)}</strong></li>)}</ul>}</div><footer>Modèle {prediction.model_version} · presse {prediction.machine_erp_ref} · horizon {prediction.horizon_cycles} cycles</footer></details>
    <p className="process-drift-disclaimer">Ce score indique une priorité d’inspection, pas une décision automatique. Il ne commande ni arrêt ni réglage de la presse et reste à confronter à une validation terrain.</p>
  </section>;
}

function PersistedPredictionView({ prediction, evaluatedThrough, titleId }: { prediction: ProcessDriftPrediction; evaluatedThrough?: string; titleId: string }) {
  const driftDetected = prediction.predicted_instability_next_20_cycles;
  return <section className={`process-drift-panel ${driftDetected ? 'is-drift' : 'is-normal'}`} aria-labelledby={titleId}>
    <header className="process-drift-heading"><div><span>HDT · HORIZON DE DÉRIVE</span><h3 id={titleId}>Priorité d’inspection</h3></div><span className="process-drift-status">{driftDetected ? <><WarningIcon size={16} aria-hidden="true" />Dérive détectée</> : <><CheckIcon size={16} aria-hidden="true" />État normal</>}</span></header>
    <div className="process-drift-summary"><div><span>SCORE D’ANOMALIE</span><strong>{formatNumber(prediction.anomaly_score, 2)}</strong><small>seuil {formatNumber(prediction.threshold, 2)}</small></div><div><span>PROJECTION</span><strong>{driftDetected ? 'À inspecter' : 'Pas d’alerte'}</strong><small>{predictionText(prediction)}</small></div></div>
    <p className="helper-status">Score persistant · évalué jusqu’au {evaluatedThrough ? new Date(evaluatedThrough).toLocaleString('fr-FR') : 'horodatage indisponible'}.</p>
    <p className="process-drift-disclaimer">Ce score indique une priorité d’inspection, pas une décision automatique. Il ne commande ni arrêt ni réglage de la presse et reste à confronter à une validation terrain.</p>
  </section>;
}
