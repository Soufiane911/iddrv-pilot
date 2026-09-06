import { EmptyPanel, StatePanel } from '../Ui';

/** Durable source receipts which are waiting for a mapping or an OF. */
export function UnmatchedEventQueue({ pendingCount, loading = false, error, onRetry }: { pendingCount: number; loading?: boolean; error?: string | null; onRetry?: () => void }) {
  if (loading) return <StatePanel tone="loading" title="File des événements" text="Lecture des événements à rapprocher." />;
  if (error) return <StatePanel tone="error" title="File indisponible" text={error} action={onRetry ? 'Réessayer' : undefined} onAction={onRetry} />;
  if (!pendingCount) return <EmptyPanel title="Aucun événement à rapprocher" text="Les événements reçus après mapping sont matérialisés sans perdre leur payload brut." />;
  return <div className="unmatched-event-queue" role="status"><strong>{pendingCount} événement{pendingCount > 1 ? 's' : ''} à rapprocher</strong><span>Mappez l’identifiant externe ou créez l’OF pour déclencher le replay.</span></div>;
}
