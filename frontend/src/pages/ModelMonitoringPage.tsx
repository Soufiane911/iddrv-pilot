import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useApi } from '../App';
import { formatDate, formatNumber, MetricCard, SectionTitle, StatePanel } from '../components/Ui';
import { HdtScoreHistory } from '../components/monitoring/HdtScoreHistory';
import { HdtSimulator } from '../components/monitoring/HdtSimulator';
import { ModelMetricsCard } from '../components/monitoring/ModelMetricsCard';
import type { Incident } from '../lib/api';

interface IncidentWithFeedback extends Incident {
  feedback_verdict?: 'confirmed' | 'rejected' | 'uncertain' | string;
}

interface HdtHistoryEntry {
  id: string;
  timestamp: string;
  anomalyScore: number;
  threshold: number;
  alert: boolean;
  machineErpRef: string;
}

const MODEL_VERSION = 'hdt-process-drift-iforest-v1';
const TRAINING_DATE = '2025-02-01';
const STORAGE_KEY = 'iddrv:hdt-history';

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

export function ModelMonitoringPage() {
  const api = useApi();
  const [historyKey, setHistoryKey] = useState(0);

  const sitesQuery = useQuery({ queryKey: ['monitoring-sites'], queryFn: api.getSites });
  const incidentsQuery = useQuery({ queryKey: ['monitoring-incidents'], queryFn: () => api.getIncidents({}) });

  const siteId = sitesQuery.data?.[0]?.id ?? 1;

  const history = useMemo(() => loadHistory(), [historyKey]); // eslint-disable-line react-hooks/exhaustive-deps

  const incidentsWithFeedback = useMemo(() => {
    const incidents = (incidentsQuery.data ?? []) as IncidentWithFeedback[];
    return incidents.filter((i) => !!i.feedback_verdict);
  }, [incidentsQuery.data]);

  const confirmedCount = incidentsWithFeedback.filter((i) => i.feedback_verdict === 'confirmed').length;
  const rejectedCount = incidentsWithFeedback.filter((i) => i.feedback_verdict === 'rejected').length;
  const uncertainCount = incidentsWithFeedback.filter((i) => i.feedback_verdict === 'uncertain').length;

  const handleSimulatorResult = () => {
    setHistoryKey((k) => k + 1);
  };

  const isLoading = sitesQuery.isPending || incidentsQuery.isPending;
  const hasError = sitesQuery.isError || incidentsQuery.isError;

  return (
    <section className="page page-wide">
      <div className="page-intro">
        <div>
          <p className="eyebrow">INTELLIGENCE ARTIFICIELLE</p>
          <h2>Monitoring du modèle HDT</h2>
          <p className="muted">
            Supervision du modèle de détection de dérive process (HDT) : version, métriques offline, simulateur interactif et retours terrain.
          </p>
        </div>
      </div>

      {/* Version card */}
      <section className="surface-card" style={{ padding: '24px', marginBottom: '24px' }} aria-labelledby="version-heading">
        <SectionTitle eyebrow="IDENTITÉ DU MODÈLE" title="Version du modèle" />
        <div className="metric-grid metric-grid-three" style={{ marginTop: '16px', marginBottom: '0', borderBlock: 'none', background: 'transparent' }}>
          <MetricCard label="Version" value={MODEL_VERSION} detail="Modèle actif" tone="neutral" />
          <MetricCard label="Date d'entraînement" value={new Date(TRAINING_DATE).toLocaleDateString('fr-FR')} detail="Référence temporelle" tone="neutral" />
          <MetricCard label="Algorithme" value="Isolation Forest" detail="200 arbres, seuil 98e percentile" tone="neutral" />
          <MetricCard label="Horizon" value="20 cycles" detail="Projection de dérive" tone="neutral" />
          <MetricCard label="Fenêtre de volatilité" value="20 cycles" detail="Calcul des signaux" tone="neutral" />
          <MetricCard label="Site de référence" value={siteId.toString()} detail="Identifiant pilote" tone="neutral" />
        </div>
      </section>

      {/* Offline metrics */}
      <section className="surface-card" style={{ padding: '24px', marginBottom: '24px' }} aria-labelledby="metrics-heading">
        <SectionTitle eyebrow="VALIDATION OFFLINE" title="Métriques de validation offline" />
        <div style={{ marginTop: '16px' }}>
          <ModelMetricsCard />
        </div>
        <p style={{ marginTop: '16px', padding: '10px 12px', borderLeft: '3px solid var(--color-accent)', background: 'var(--color-muted)', color: 'var(--color-secondary)', fontSize: '12px', lineHeight: '1.45' }}>
          <strong>Disclaimer :</strong> Ces métriques sont issues d'une validation offline sur données synthétiques. La validation terrain reste à faire.
        </p>
      </section>

      {/* Simulator */}
      <section style={{ marginBottom: '24px' }}>
        <HdtSimulator api={api} siteId={siteId} onResult={handleSimulatorResult} />
      </section>

      {/* History */}
      <section className="surface-card" style={{ padding: '24px', marginBottom: '24px' }} aria-labelledby="history-heading">
        <SectionTitle eyebrow="HISTORIQUE" title="Historique des prédictions" />

        {history.length === 0 ? (
          <div style={{ marginTop: '16px' }}>
            <StatePanel tone="empty" title="Historique vide" text="Aucune prédiction n'a encore été stockée. Utilisez le simulateur pour générer des scores." />
          </div>
        ) : (
          <>
            <div style={{ marginTop: '16px', overflowX: 'auto' }}>
              <table className="incident-table" style={{ minWidth: '640px' }}>
                <caption className="visually-hidden">Historique des prédictions HDT</caption>
                <thead>
                  <tr>
                    <th scope="col">Horodatage</th>
                    <th scope="col">Presse</th>
                    <th scope="col">Score</th>
                    <th scope="col">Seuil</th>
                    <th scope="col">Alerte</th>
                  </tr>
                </thead>
                <tbody>
                  {history.slice(0, 20).map((entry) => (
                    <tr key={entry.id}>
                      <td data-label="Horodatage">
                        <time dateTime={entry.timestamp}>{formatDate(entry.timestamp)}</time>
                      </td>
                      <td data-label="Presse">{entry.machineErpRef}</td>
                      <td data-label="Score">{formatNumber(entry.anomalyScore, 3)}</td>
                      <td data-label="Seuil">{formatNumber(entry.threshold, 3)}</td>
                      <td data-label="Alerte">
                        <span
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px',
                            padding: '3px 6px',
                            border: '1px solid var(--color-border)',
                            fontSize: '11px',
                            fontWeight: 700,
                            color: entry.alert ? 'var(--color-destructive)' : 'var(--color-accent)',
                          }}
                        >
                          <span
                            style={{
                              width: '6px',
                              height: '6px',
                              borderRadius: '50%',
                              background: entry.alert ? 'var(--color-destructive)' : 'var(--color-accent)',
                            }}
                            aria-hidden="true"
                          />
                          {entry.alert ? 'Oui' : 'Non'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div style={{ marginTop: '24px' }}>
              <HdtScoreHistory refreshKey={historyKey} />
            </div>
          </>
        )}
      </section>

      {/* Human feedbacks */}
      <section className="surface-card" style={{ padding: '24px', marginBottom: '24px' }} aria-labelledby="feedback-heading">
        <SectionTitle eyebrow="VALIDATION TERRAIN" title="Feedbacks humains" />

        {isLoading && (
          <div style={{ marginTop: '16px' }}>
            <StatePanel tone="loading" title="Chargement des incidents" text="Récupération des signaux et feedbacks persistés." />
          </div>
        )}

        {hasError && (
          <div style={{ marginTop: '16px' }}>
            <StatePanel tone="error" title="Incidents indisponibles" text="Impossible de récupérer les données de feedback." action="Réessayer" onAction={() => { sitesQuery.refetch(); incidentsQuery.refetch(); }} />
          </div>
        )}

        {!isLoading && !hasError && (
          <div className="metric-grid metric-grid-three" style={{ marginTop: '16px', marginBottom: '0', borderBlock: 'none', background: 'transparent' }}>
            <MetricCard label="Confirmés" value={confirmedCount.toString()} detail="Feedbacks positifs" tone="good" />
            <MetricCard label="Rejetés" value={rejectedCount.toString()} detail="Feedbacks négatifs" tone="danger" />
            <MetricCard label="Incertains" value={uncertainCount.toString()} detail="À réexaminer" tone="warning" />
          </div>
        )}

        {!isLoading && !hasError && incidentsWithFeedback.length === 0 && (
          <p style={{ marginTop: '16px', color: 'var(--color-muted-foreground)', fontSize: '14px' }}>
            Aucun feedback humain n'a encore été associé aux incidents. Les compteurs se mettront à jour lorsque des retours seront soumis via la fiche incident.
          </p>
        )}
      </section>

      {/* Global disclaimer */}
      <div
        style={{
          padding: '12px 14px',
          border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius)',
          background: 'var(--color-card)',
          color: 'var(--color-secondary)',
          fontSize: '13px',
          lineHeight: '1.5',
        }}
        role="note"
        aria-label="Avertissement méthodologique"
      >
        <strong>Attention :</strong> Ces métriques sont issues d'une validation offline sur données synthétiques.
        La validation terrain reste à faire. Le modèle HDT est un prototype (v1) ; les scores indiquent une
        priorité d'inspection, pas une décision automatique.
      </div>
    </section>
  );
}
