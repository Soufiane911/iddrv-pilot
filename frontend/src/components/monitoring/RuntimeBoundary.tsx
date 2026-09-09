import type { ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useApi } from '../../App';
import { Summary6Replay } from './Summary6Replay';

/** Do not mount legacy hooks, caches or POST callers until mode is known. */
export function RuntimeBoundary({ children }: { children: ReactNode }) {
  const api = useApi();
  const current = useQuery({ queryKey: ['summary6', 'current'], queryFn: api.getSummary6Current, staleTime: 0, retry: false });
  if (current.isPending) return <p role="status">Vérification du runtime…</p>;
  if (current.isError) return <div role="alert">Runtime indisponible. Aucun fallback historique.<button onClick={() => current.refetch()}>Réessayer</button></div>;
  if (current.data.active_mode === 'summary6_replay') return <Summary6Replay api={api} current={current.data} />;
  if (current.data.active_mode !== 'historical') return <p role="alert">Profil runtime inconnu — calcul bloqué.</p>;
  return <>{children}</>;
}
