import { MetricCard } from '../Ui';

export function ModelMetricsCard() {
  return (
    <div className="metric-grid metric-grid-three" role="region" aria-label="Métriques de validation offline">
      <MetricCard label="Average Precision" value="14,07 %" detail="Sur données holdout" tone="neutral" />
      <MetricCard label="ROC-AUC" value="0,878" detail="Capacité de classement" tone="neutral" />
      <MetricCard label="Prévalence" value="1,23 %" detail="Base de référence" tone="neutral" />
      <MetricCard label="Lift" value="11,48×" detail="Vs prévalence" tone="good" />
      <MetricCard label="Precision" value="12,29 %" detail="Au seuil machine" tone="neutral" />
      <MetricCard label="Recall" value="23,72 %" detail="Au seuil machine" tone="neutral" />
      <MetricCard label="Taux d'alerte" value="2,36 %" detail="301 / 12 732 cycles" tone="warning" />
    </div>
  );
}
