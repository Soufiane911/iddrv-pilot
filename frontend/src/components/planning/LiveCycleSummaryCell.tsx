import { formatDate, formatNumber } from '../Ui';
import type { PlanningSlot } from '../../lib/api';

export function LiveCycleSummaryCell({ slot }: { slot: PlanningSlot }) {
  return <div className="live-cycle-cell"><strong>{typeof slot.cyclesReceived === 'number' ? formatNumber(slot.cyclesReceived, 0) : 'N/D'}</strong><small>{slot.firstCycleAt ? `1er ${formatDate(slot.firstCycleAt)}` : 'Premier cycle : N/D'}</small><small>{slot.lastCycleAt ? `Dernier ${formatDate(slot.lastCycleAt)}` : 'Dernier cycle : N/D'}</small><small>Compteur : {slot.lastCycleCounter ?? 'N/D'}</small><small>Fraîcheur : {slot.sourceLastSuccessAt ? formatDate(slot.sourceLastSuccessAt) : 'N/D'}</small><small>Cycle : {slot.lastCycleTimeS != null ? `${formatNumber(slot.lastCycleTimeS, 2)} s` : 'N/D'} · moy. {slot.averageCycleTimeS != null ? `${formatNumber(slot.averageCycleTimeS, 2)} s` : 'N/D'}</small></div>;
}
