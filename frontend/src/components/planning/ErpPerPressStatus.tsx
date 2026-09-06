import type { PlanningSlot } from '../../lib/api';
import { formatDate, formatNumber } from '../Ui';

const labels: Record<string, string> = { pending: 'En attente ERP', matched: 'Rapproché', incomplete: 'Incomplet', conflict: 'Conflit' };
export function ErpPerPressStatus({ slot }: { slot: PlanningSlot }) {
  const known = slot.erpStatus !== 'pending';
  return <div className={`erp-press-status erp-${slot.erpStatus}`}><strong>{labels[slot.erpStatus] ?? slot.erpStatus}</strong>{known ? <><small>{slot.erpImportedAt ? `Import ${formatDate(slot.erpImportedAt)}` : 'Version : N/D'}</small><small>Produit : {slot.producedPartsErp == null ? 'N/D' : formatNumber(slot.producedPartsErp, 0)} · bonnes : {slot.goodPartsErp == null ? 'N/D' : formatNumber(slot.goodPartsErp, 0)}</small><small>Rebuts : {slot.scrapPartsErp == null ? 'N/D' : formatNumber(slot.scrapPartsErp, 0)} · cycles : {slot.cyclesErp == null ? 'N/D' : formatNumber(slot.cyclesErp, 0)}</small>{slot.cyclesErp != null && slot.cyclesReceived != null && <small>Écart cycles : {formatNumber(slot.cyclesReceived - slot.cyclesErp, 0)}</small>}</> : <small>Les quantités viennent exclusivement de l’ERP.</small>}</div>;
}
