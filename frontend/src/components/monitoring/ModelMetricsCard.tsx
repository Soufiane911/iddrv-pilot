import { MetricCard } from '../Ui';

export function ModelMetricsCard() {
  return (
    <div className="metric-grid metric-grid-three" role="region" aria-label="Métriques de validation offline">
      <MetricCard label="Average Precision" value="10,98 %" detail="Sur données holdout" tone="neutral" />
      <MetricCard label="ROC-AUC" value="0,868" detail="Capacité de classement" tone="neutral" />
      <MetricCard label="Prévalence" value="1,22 %" detail="Base de référence" tone="neutral" />
      <MetricCard label="Lift" value="8,97×" detail="Vs prévalence" tone="good" />
      <MetricCard label="Precision" value="9,65 %" detail="Au seuil machine" tone="neutral" />
      <MetricCard label="Recall" value="16,03 %" detail="Au seuil machine" tone="neutral" />
      <MetricCard label="Taux d'alerte" value="2,03 %" detail="259 / 12 753 cycles" tone="warning" />
    </div>
  );
}
