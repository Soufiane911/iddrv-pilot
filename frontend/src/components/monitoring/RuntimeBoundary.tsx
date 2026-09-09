import type { ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useApi } from '../../App';
import { Summary6Replay, replayError } from './Summary6Replay';

/** Do not mount legacy hooks, caches or POST callers until mode is known. */
export function RuntimeBoundary({ children, siteId }: { children: ReactNode; siteId?: number }) {
  const api = useApi();
  const current = useQuery({ queryKey: ['summary6', 'current'], queryFn: api.getSummary6Current, staleTime: 0, refetchOnMount: 'always', retry: false });
  if (current.isError) return <div role="alert">Scoring indisponible. {replayError(current.error)} Aucun fallback historique.<button onClick={() => current.refetch()}>Réessayer</button></div>;
  // Cached historical data never authorizes mounting a POST-capable child.
  // Keep this observer mounted while gating, including after a failed refetch.
  if (!current.isFetchedAfterMount || current.fetchStatus !== 'idle' || !current.isSuccess) return <p role="status">Vérification du runtime… Scoring indisponible.</p>;
  if (current.data.active_mode === 'summary6_replay') return <><Summary6Replay api={api} current={current.data} siteId={siteId} /><button type="button" onClick={() => current.refetch()}>Actualiser le runtime</button></>;
  if (current.data.active_mode !== 'historical') return <section><p role="alert">Scoring indisponible — mode {current.data.active_mode}. {current.data.reasons.join(', ')} Aucun calcul historique.</p><p>Paquet sélectionné : {current.data.selected_package_id || 'aucun'} · chargé : {current.data.loaded_package_id ?? 'aucun'}. Live non raccordé.</p><button type="button" onClick={() => current.refetch()}>Actualiser le runtime</button></section>;
  return <>{children}</>;
}
