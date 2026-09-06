import { useEffect } from 'react';

export type WorkshopTimeMode = 'direct' | 'replay';

interface Props {
  mode: WorkshopTimeMode;
  selectedAt: string;
  onModeChange: (mode: WorkshopTimeMode) => void;
  onSelectedAtChange: (value: string) => void;
  onRefresh?: () => void;
  disabled?: boolean;
}

/** Time boundary shared by the workshop reads. Direct polls persisted data; replay never advances itself. */
export function WorkshopTimeControls({ mode, selectedAt, onModeChange, onSelectedAtChange, onRefresh, disabled = false }: Props) {
  useEffect(() => {
    if (mode !== 'direct' || !onRefresh) return undefined;
    const timer = window.setInterval(() => {
      if (document.visibilityState !== 'hidden') onRefresh();
    }, 2000);
    return () => window.clearInterval(timer);
  }, [mode, onRefresh]);

  return <section className="workshop-time-controls" aria-label="Borne temporelle des données">
    <div className="workshop-time-modes" role="group" aria-label="Mode temporel">
      <button type="button" className={mode === 'direct' ? 'active' : ''} aria-pressed={mode === 'direct'} onClick={() => onModeChange('direct')} disabled={disabled}>Direct</button>
      <button type="button" className={mode === 'replay' ? 'active' : ''} aria-pressed={mode === 'replay'} onClick={() => onModeChange('replay')} disabled={disabled}>Rejeu</button>
    </div>
    <label>Contexte connu à
      <input type="datetime-local" value={selectedAt.slice(0, 16)} onChange={(event) => onSelectedAtChange(new Date(event.target.value).toISOString())} disabled={disabled} />
    </label>
    <small>{mode === 'direct' ? 'Lectures persistées · actualisation toutes les 2 s lorsque la page est visible.' : 'Lecture bornée à la date choisie · aucune progression automatique.'}</small>
  </section>;
}
