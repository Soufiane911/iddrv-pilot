import type { ReactNode } from 'react';

export type SourceState = 'disconnected' | 'reachable' | 'interrupted';
export type CycleState = 'waiting' | 'received' | 'unknown';
export type ErpState = 'pending' | 'available' | 'unknown';
export type HdtState = 'building' | 'scored' | 'unknown';

const labels = {
  disconnected: 'Non connectée', reachable: 'Source joignable', interrupted: 'Collecte interrompue',
  waiting: 'En attente de cycles', received: 'Mesures visibles', unknown: 'Cycles inconnus',
  pending: 'Bilan ERP en attente', available: 'Bilan ERP disponible',
  building: 'Historique HDT en constitution', scored: 'Score HDT disponible',
};

export function MachineSourceStatus({ sourceState, cycleState, erpState, hdtState, children }: { sourceState: SourceState; cycleState: CycleState; erpState: ErpState; hdtState: HdtState; children?: ReactNode }) {
  const cells = [
    ['Source', labels[sourceState]], ['Cycles', labels[cycleState]], ['ERP', labels[erpState]], ['HDT', labels[hdtState]],
  ] as const;
  return <section className="machine-source-status" aria-label="États indépendants de la presse">
    {cells.map(([name, value]) => <div key={name} className={`machine-source-status-item state-${value === 'Collecte interrompue' ? 'danger' : 'neutral'}`}><span>{name}</span><strong>{value}</strong></div>)}
    {sourceState === 'interrupted' ? <p className="helper-error">Interruption observée. L’absence de réponse ne confirme pas un arrêt machine.</p> : null}
    {children}
  </section>;
}
