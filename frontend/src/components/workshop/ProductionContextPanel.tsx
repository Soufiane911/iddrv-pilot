export interface ProductionContextDeclaration {
  id: string; orderRef: string; team?: string | null; producedParts?: number | null; goodParts?: number | null; scrapParts?: number | null;
  status?: string | null; reopenReason?: string | null; history?: Array<{ status?: string | null; recordedAt?: string | null }>; warnings?: string[];
}
export interface ProductionOrderSummary { orderRef: string; target?: number | null; status?: string | null; goodPartsNet?: number | null; remainingQuantity?: number | null; warnings: number; statusHistory: Array<{ status?: string | null; recordedAt?: string | null; reason?: string | null }> }
export interface ProductionContext {
  knownAt: string; importedAt?: string | null; declarations: ProductionContextDeclaration[]; orders?: ProductionOrderSummary[]; certified?: boolean;
  target?: number | null; erpStatus?: string | null; qualityStatus?: 'known' | 'unknown' | string; coverageStatus?: 'complete' | 'incomplete' | string;
}
const statusLabel = (status?: string | null) => status === 'reopened' ? 'Rouverte' : status === 'closed' ? 'Clôturée' : status || 'Statut ERP non fourni';

export function ProductionContextPanel({ context }: { context?: ProductionContext | null }) {
  if (!context) return <section className="production-context-panel" aria-label="Contexte de production"><h3>Contexte de production</h3><p>Bilan ERP en attente.</p></section>;
  const grouped = context.declarations.reduce<Map<string, ProductionContextDeclaration[]>>((map, declaration) => { const list = map.get(declaration.orderRef) ?? []; list.push(declaration); map.set(declaration.orderRef, list); return map; }, new Map());
  const summaryByOrder = new Map((context.orders ?? []).map((order) => [order.orderRef, order]));
  const firstSummary = Array.from(summaryByOrder.values())[0];
  const target = context.target ?? firstSummary?.target;
  const erpStatus = context.erpStatus ?? firstSummary?.status;
  return <section className="production-context-panel" aria-label="Contexte de production">
    <header><div><span className="eyebrow">RAPPROCHEMENT DE PRODUCTION</span><h3>Contexte ERP</h3></div><label className="production-context-known-at">Contexte connu à <time dateTime={context.knownAt}>{new Date(context.knownAt).toLocaleString('fr-FR')}</time></label></header>
    {context.importedAt && new Date(context.importedAt) > new Date(context.knownAt) ? <p className="helper-status">Contexte enrichi depuis {new Date(context.importedAt).toLocaleString('fr-FR')}.</p> : null}
    <div className="production-context-badges"><span>{target == null ? 'Cible inconnue' : `Cible ${target}`}</span><span>{erpStatus ? `Statut ERP : ${erpStatus === 'reopened' ? 'Rouverte' : erpStatus}` : 'Statut ERP non fourni'}</span><span>{context.coverageStatus === 'incomplete' || Array.from(summaryByOrder.values()).some((order) => order.warnings > 0) ? 'Historique incomplet' : 'Couverture source vérifiée'}</span></div>
    {Array.from(summaryByOrder.values()).some((order) => order.warnings > 0) ? <p className="helper-error">Progression non certifiée tant que les avertissements ERP restent à vérifier.</p> : null}
    {Array.from(summaryByOrder.values()).map((summary) => <p key={`${summary.orderRef}-history`} className="muted">{summary.statusHistory.length > 0 ? `Historique ${summary.orderRef} : ${summary.statusHistory.map((item) => item.status).filter(Boolean).join(' → ')}` : ''}</p>)}
    {grouped.size === 0 ? <p>Bilan ERP en attente.</p> : Array.from(grouped.entries()).map(([orderRef, declarations]) => { const summary = summaryByOrder.get(orderRef); return <article key={orderRef} className="production-order-context"><h4>{orderRef}</h4><p className="muted">Identité OF unique · progression globale {summary?.goodPartsNet ?? declarations.reduce((sum, item) => sum + (item.producedParts ?? 0), 0)} pièces bonnes · restant {summary?.remainingQuantity ?? 'N/D'}</p><div className="production-team-list">{declarations.map((declaration) => <details key={declaration.id} open={false}><summary>{`Équipe ${declaration.team || 'non renseignée'} · ${statusLabel(declaration.status || summary?.status)}`}</summary><dl><div><dt>Produit</dt><dd>{declaration.producedParts ?? 'N/D'}</dd></div><div><dt>Bonnes pièces ERP</dt><dd>{declaration.goodParts ?? 'N/D'}</dd></div><div><dt>Rebuts ERP</dt><dd>{declaration.scrapParts ?? 'N/D'}</dd></div></dl>{declaration.reopenReason ? <p>Réouverture : {declaration.reopenReason}</p> : null}</details>)}</div></article>; })}
    {context.qualityStatus === 'unknown' ? <p className="muted">Qualité non renseignée</p> : null}
  </section>;
}
