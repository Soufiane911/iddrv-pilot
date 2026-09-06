import { useId, useState } from 'react';
import type { ApiClient, ProcessDriftCycle, ProcessDriftPrediction } from '../../lib/api';
import { EmptyPanel, formatNumber, StatePanel } from '../Ui';

interface Props {
  api: Pick<ApiClient, 'predictProcessDrift'>;
  siteId: number;
  onResult?: () => void;
}

interface CycleFormData {
  cycle_time_s: string;
  injection_time_s: string;
  cooling_time_s: string;
  peak_pressure_bar: string;
  barrel_temp_zone2_c: string;
  energy_kwh: string;
}

interface HdtHistoryEntry {
  id: string;
  timestamp: string;
  anomalyScore: number;
  threshold: number;
  alert: boolean;
  machineErpRef: string;
  signals: { feature: string; volatility: number }[];
}

const STORAGE_KEY = 'iddrv:hdt-history';
const DEFAULT_MACHINE_REF = '152';

const FEATURE_LABELS: Record<string, string> = {
  cycle_time_s: 'Temps de cycle (s)',
  injection_time_s: "Temps d'injection (s)",
  cooling_time_s: 'Temps de refroidissement (s)',
  peak_pressure_bar: 'Pression max (bar)',
  barrel_temp_zone2_c: 'Température zone 2 (°C)',
  energy_kwh: 'Énergie (kWh)',
};

function makeEmptyCycle(): CycleFormData {
  return {
    cycle_time_s: '',
    injection_time_s: '',
    cooling_time_s: '',
    peak_pressure_bar: '',
    barrel_temp_zone2_c: '',
    energy_kwh: '',
  };
}

function signalLabel(value: string): string {
  return value.replace(/_volatility_20$/, ' · variabilité 20 cycles').split('_').join(' ');
}

function loadHistory(): HdtHistoryEntry[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as HdtHistoryEntry[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function saveHistory(entry: HdtHistoryEntry) {
  const history = loadHistory();
  history.unshift(entry);
  if (history.length > 50) history.length = 50;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(history));
}

export function HdtSimulator({ api, siteId, onResult }: Props) {
  const titleId = useId();
  const [cycles, setCycles] = useState<CycleFormData[]>([makeEmptyCycle(), makeEmptyCycle(), makeEmptyCycle()]);
  const [prediction, setPrediction] = useState<ProcessDriftPrediction | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const updateCycle = (index: number, field: keyof CycleFormData, value: string) => {
    setCycles((prev) => {
      const next = [...prev];
      next[index] = { ...next[index], [field]: value };
      return next;
    });
  };

  const isValid = cycles.every((cycle) =>
    Object.values(cycle).every((v) => v.trim() !== '' && !Number.isNaN(Number(v)))
  );

  const handleSubmit = async () => {
    if (!isValid) return;
    setLoading(true);
    setError(null);
    setPrediction(null);
    try {
      const now = new Date();
      const payloadCycles: ProcessDriftCycle[] = cycles.map((cycle, index) => ({
        timestamp: new Date(now.getTime() - (cycles.length - 1 - index) * 60_000).toISOString(),
        machine_erp_ref: DEFAULT_MACHINE_REF,
        cycle_time_s: Number(cycle.cycle_time_s),
        injection_time_s: Number(cycle.injection_time_s),
        cooling_time_s: Number(cycle.cooling_time_s),
        peak_pressure_bar: Number(cycle.peak_pressure_bar),
        barrel_temp_zone2_c: Number(cycle.barrel_temp_zone2_c),
        energy_kwh: Number(cycle.energy_kwh),
      }));

      const result = await api.predictProcessDrift({ site_id: siteId, cycles: payloadCycles });
      setPrediction(result);

      saveHistory({
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
        timestamp: now.toISOString(),
        anomalyScore: result.anomaly_score,
        threshold: result.threshold,
        alert: result.predicted_instability_next_20_cycles,
        machineErpRef: result.machine_erp_ref,
        signals: result.signals,
      });
      onResult?.();
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Erreur lors du calcul HDT'));
    } finally {
      setLoading(false);
    }
  };

  const featureKeys = Object.keys(FEATURE_LABELS) as (keyof CycleFormData)[];

  return (
    <section className="surface-card" style={{ padding: '24px' }} aria-labelledby={titleId}>
      <div className="section-title" style={{ marginBottom: '20px' }}>
        <div>
          <p className="eyebrow">SIMULATION</p>
          <h2 id={titleId}>Simulateur interactif HDT</h2>
        </div>
      </div>

      <p style={{ marginBottom: '16px', color: 'var(--color-muted-foreground)', fontSize: '14px' }}>
        Saisissez au moins 3 cycles de données process pour calculer un score de dérive HDT en temps réel.
      </p>

      <div role="table" aria-label="Saisie des cycles process">
        <div role="rowgroup">
          <div role="row" style={{ display: 'grid', gridTemplateColumns: '100px repeat(6, 1fr)', gap: '8px', fontSize: '12px', fontWeight: 600, color: 'var(--color-muted-foreground)', marginBottom: '8px' }}>
            <div role="columnheader">Cycle</div>
            {featureKeys.map((key) => (
              <div role="columnheader" key={key}>{FEATURE_LABELS[key]}</div>
            ))}
          </div>
        </div>
        <div role="rowgroup">
          {cycles.map((cycle, index) => (
            <div role="row" key={index} style={{ display: 'grid', gridTemplateColumns: '100px repeat(6, 1fr)', gap: '8px', marginBottom: '8px' }}>
              <div role="rowheader" style={{ display: 'flex', alignItems: 'center', fontSize: '14px', fontWeight: 600 }}>
                Cycle {index + 1}
              </div>
              {featureKeys.map((key) => (
                <div role="cell" key={key}>
                  <label htmlFor={`cycle-${index}-${key}`} className="visually-hidden">
                    {FEATURE_LABELS[key]} — cycle {index + 1}
                  </label>
                  <input
                    id={`cycle-${index}-${key}`}
                    type="number"
                    step="any"
                    value={cycle[key]}
                    onChange={(e) => updateCycle(index, key, e.target.value)}
                    placeholder="—"
                    aria-label={`${FEATURE_LABELS[key]} cycle ${index + 1}`}
                    style={{ width: '100%' }}
                  />
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>

      <div style={{ marginTop: '16px', display: 'flex', gap: '12px', alignItems: 'center' }}>
        <button
          type="button"
          className="button-primary"
          onClick={handleSubmit}
          disabled={!isValid || loading}
          aria-busy={loading}
        >
          {loading ? 'Calcul en cours…' : 'Calculer le score HDT'}
        </button>
        {!isValid && (
          <span style={{ fontSize: '13px', color: 'var(--color-muted-foreground)' }}>
            Remplissez tous les champs numériques pour activer le calcul.
          </span>
        )}
      </div>

      {loading && (
        <div style={{ marginTop: '16px' }}>
          <StatePanel tone="loading" title="Calcul HDT en cours" text="Analyse des cycles process par le modèle Isolation Forest." />
        </div>
      )}

      {error && (
        <div style={{ marginTop: '16px' }}>
          <StatePanel tone="error" title="Erreur de prédiction" text={error.message} action="Réessayer" onAction={handleSubmit} />
        </div>
      )}

      {prediction && !loading && !error && (
        <div
          style={{
            marginTop: '20px',
            padding: '16px',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius)',
            background: prediction.predicted_instability_next_20_cycles ? 'color-mix(in srgb, var(--color-destructive) 6%, var(--color-card))' : 'color-mix(in srgb, var(--color-accent) 6%, var(--color-card))',
          }}
          role="region"
          aria-label="Résultat de la prédiction HDT"
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
            <strong style={{ fontSize: '16px' }}>
              {prediction.predicted_instability_next_20_cycles ? 'Dérive détectée' : 'Aucune dérive détectée'}
            </strong>
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '5px',
                padding: '5px 7px',
                border: '1px solid var(--color-border)',
                fontSize: '11px',
                fontWeight: 700,
                color: prediction.predicted_instability_next_20_cycles ? 'var(--color-destructive)' : 'var(--color-accent)',
              }}
              aria-label={prediction.predicted_instability_next_20_cycles ? 'Alerte active' : 'Pas d\'alerte'}
            >
              {prediction.predicted_instability_next_20_cycles ? '⚠ Alerte' : '✓ Normal'}
            </span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px', marginBottom: '12px' }}>
            <div>
              <span style={{ display: 'block', fontSize: '10px', fontWeight: 700, color: 'var(--color-muted-foreground)', letterSpacing: '.04em' }}>SCORE D'ANOMALIE</span>
              <strong style={{ display: 'block', marginTop: '5px', fontSize: '18px' }}>{formatNumber(prediction.anomaly_score, 2)}</strong>
              <small style={{ display: 'block', marginTop: '4px', fontSize: '11px', color: 'var(--color-muted-foreground)' }}>seuil {formatNumber(prediction.threshold, 2)}</small>
            </div>
            <div>
              <span style={{ display: 'block', fontSize: '10px', fontWeight: 700, color: 'var(--color-muted-foreground)', letterSpacing: '.04em' }}>HORIZON</span>
              <strong style={{ display: 'block', marginTop: '5px', fontSize: '18px' }}>{prediction.horizon_cycles} cycles</strong>
              <small style={{ display: 'block', marginTop: '4px', fontSize: '11px', color: 'var(--color-muted-foreground)' }}>fenêtre de projection</small>
            </div>
            <div>
              <span style={{ display: 'block', fontSize: '10px', fontWeight: 700, color: 'var(--color-muted-foreground)', letterSpacing: '.04em' }}>PRESSE</span>
              <strong style={{ display: 'block', marginTop: '5px', fontSize: '18px' }}>{prediction.machine_erp_ref}</strong>
              <small style={{ display: 'block', marginTop: '4px', fontSize: '11px', color: 'var(--color-muted-foreground)' }}>référence machine</small>
            </div>
          </div>

          {prediction.signals.length > 0 && (
            <div style={{ marginTop: '12px' }}>
              <span style={{ display: 'block', fontSize: '11px', fontWeight: 700, color: 'var(--color-muted-foreground)', letterSpacing: '.05em' }}>SIGNAUX CONTRIBUTIFS</span>
              <ul style={{ display: 'grid', gap: '6px', margin: '8px 0 0', padding: 0, listStyle: 'none' }}>
                {prediction.signals.slice(0, 4).map((signal) => (
                  <li key={signal.feature} style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: '8px', borderTop: '1px solid var(--color-border)', paddingTop: '6px', fontSize: '12px' }}>
                    <span>{signalLabel(signal.feature)}</span>
                    <strong style={{ fontVariantNumeric: 'tabular-nums' }}>{formatNumber(signal.volatility, 2)}</strong>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <p style={{ marginTop: '12px', padding: '9px 10px', borderLeft: '3px solid var(--color-secondary)', background: 'var(--color-muted)', color: 'var(--color-secondary)', fontSize: '11px', lineHeight: '1.45' }}>
            Ce score indique une priorité d'inspection, pas une décision automatique. Il ne commande ni arrêt ni réglage de la presse.
          </p>
        </div>
      )}

      {!prediction && !loading && !error && (
        <div style={{ marginTop: '16px' }}>
          <EmptyPanel title="Aucune prédiction" text="Remplissez les cycles et lancez le calcul pour voir le résultat." />
        </div>
      )}
    </section>
  );
}
