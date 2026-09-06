import type { PlanningSlot } from '../../lib/api';
import { formatNumber } from '../Ui';

export function ProcessParametersPanel({ slot }: { slot: PlanningSlot }) {
  const parameters = slot.processParameters ? Object.entries(slot.processParameters) : [];
  return <details className="planning-parameters"><summary>Paramètres {slot.parameterCoverage == null ? '· N/D' : `· ${Math.round(slot.parameterCoverage * 100)} % couverts`}</summary>{parameters.length ? <dl>{parameters.map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{typeof value === 'number' ? formatNumber(value, 2) : value ?? 'N/D'}</dd></div>)}</dl> : <p className="muted">Aucun paramètre process n’est disponible pour ce créneau.</p>}</details>;
}
