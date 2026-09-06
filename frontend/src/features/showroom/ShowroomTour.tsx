import { getNextTourStepIndex, getPreviousTourStepIndex, guidedTourSteps, SHOWROOM_SIMULATED_AS_OF } from './showroomModel';

const timeLabel = (value: string) => new Intl.DateTimeFormat('fr-FR', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Europe/Paris' }).format(new Date(value));

export function ShowroomTour({ active, paused, stepIndex, onActiveChange, onPausedChange, onStepChange, scenarioMachineLabel }: {
  active: boolean;
  paused: boolean;
  stepIndex: number;
  onActiveChange: (active: boolean) => void;
  onPausedChange: (paused: boolean) => void;
  onStepChange: (step: number) => void;
  scenarioMachineLabel?: string;
}) {
  if (!active) return <div className="showroom-tour-start"><div><span className="tour-start-kicker">Visite guidée</span><strong>7 étapes · scénario S001</strong><small>Parcours manuel, sans auto-avancement</small></div><button type="button" className="showroom-primary" onClick={() => { onStepChange(0); onPausedChange(false); onActiveChange(true); }}>Démarrer la visite</button></div>;
  const step = guidedTourSteps[stepIndex];
  const isLast = stepIndex >= guidedTourSteps.length - 1;
  return <section className="showroom-tour" aria-label="Visite guidée">
    <div className="tour-progress" aria-label={`Étape ${stepIndex + 1} sur ${guidedTourSteps.length}`}><span>Étape {stepIndex + 1} sur {guidedTourSteps.length}</span><div>{guidedTourSteps.map((item, index) => <i key={item.id} className={index < stepIndex ? 'done' : index === stepIndex ? 'current' : ''} aria-hidden="true" />)}</div><small>{paused ? 'Visite en pause' : 'Avancement manuel'}</small></div>
    <div className="showroom-tour-copy" aria-live="polite" aria-atomic="true"><p>Horodatage simulé · {timeLabel(SHOWROOM_SIMULATED_AS_OF[stepIndex])}</p><h2>{step.title}</h2><span>{step.description}{scenarioMachineLabel && 'targetsScenarioMachine' in step && step.targetsScenarioMachine ? ` · ${scenarioMachineLabel}` : ''}</span><button type="button" className="showroom-tour-primary" onClick={() => isLast ? onActiveChange(false) : onStepChange(getNextTourStepIndex(stepIndex))}>{step.primaryActionLabel}</button></div>
    <div className="showroom-tour-controls"><button type="button" aria-label="Étape précédente" disabled={stepIndex === 0} onClick={() => onStepChange(getPreviousTourStepIndex(stepIndex))}>Précédent</button><button type="button" aria-label={paused ? 'Reprendre la visite' : 'Mettre en pause'} onClick={() => onPausedChange(!paused)}>{paused ? 'Reprendre' : 'Pause'}</button><button type="button" aria-label="Étape suivante" disabled={isLast} onClick={() => onStepChange(getNextTourStepIndex(stepIndex))}>Suivant</button><button type="button" className="showroom-exit" aria-label="Quitter la visite" onClick={() => onActiveChange(false)}>Quitter</button></div>
  </section>;
}
