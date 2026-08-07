export const DEMO_LABEL = 'Démonstration sur données fictives';

export type MachineVisualState = 'stable' | 'watch' | 'incident';
export type TourFocus = 'workshop' | 'machine' | 'impact' | 'investigation' | 'action' | 'estimate';
export const SHOWROOM_REPLAY_START = '2025-02-11T21:00:00Z';
export const SHOWROOM_REPLAY_END = '2025-02-12T01:52:40Z';

export const SHOWROOM_SIMULATED_AS_OF = [
  '2025-02-11T21:00:00Z',
  '2025-02-11T23:00:00Z',
  '2025-02-11T23:21:00Z',
  '2025-02-12T00:05:00Z',
  '2025-02-12T00:52:00Z',
  '2025-02-12T01:00:00Z',
  '2025-02-12T01:10:00Z',
] as const;

export interface GuidedTourStep {
  readonly id: string;
  readonly scenarioId: 'S001';
  readonly title: string;
  readonly description: string;
  readonly primaryActionLabel: string;
  readonly focus: TourFocus;
  readonly targetsScenarioMachine?: boolean;
}

export const guidedTourSteps = [
  {
    id: 'workshop-reconstructed',
    scenarioId: 'S001',
    title: 'Atelier reconstitué',
    description: 'Les données ERP, machine, qualité, maintenance et les notes opérateur composent une vue temporelle commune.',
    primaryActionLabel: 'Découvrir la période saine',
    focus: 'workshop',
  },
  {
    id: 'stable-production',
    scenarioId: 'S001',
    title: 'Production stable',
    description: 'Une période comparable et saine sert de référence avant l’apparition de la dérive.',
    primaryActionLabel: 'Observer la dérive',
    focus: 'machine',
    targetsScenarioMachine: true,
  },
  {
    id: 'drift-detected',
    scenarioId: 'S001',
    title: 'Dérive détectée',
    description: 'La presse liée à l’incident API passe sous surveillance lorsque ses signaux s’écartent de la période de référence.',
    primaryActionLabel: 'Voir l’impact observé',
    focus: 'machine',
    targetsScenarioMachine: true,
  },
  {
    id: 'impact-observed',
    scenarioId: 'S001',
    title: 'Impact observé',
    description: 'Les indicateurs de rebut et de cycle se dégradent sur la même période simulée.',
    primaryActionLabel: 'Ouvrir l’investigation',
    focus: 'impact',
    targetsScenarioMachine: true,
  },
  {
    id: 'investigation-completed',
    scenarioId: 'S001',
    title: 'Investigation terminée',
    description: 'La dérive thermique de la zone 2 est l’hypothèse principale de démonstration à vérifier avant toute conclusion.',
    primaryActionLabel: 'Examiner l’action proposée',
    focus: 'investigation',
    targetsScenarioMachine: true,
  },
  {
    id: 'action-proposed',
    scenarioId: 'S001',
    title: 'Action proposée',
    description: 'Une vérification humaine est recommandée avant le prochain ordre de fabrication comparable.',
    primaryActionLabel: 'Estimer l’impact potentiel',
    focus: 'action',
    targetsScenarioMachine: true,
  },
  {
    id: 'impact-estimated',
    scenarioId: 'S001',
    title: 'Impact potentiel estimé',
    description: 'Le résultat simulé dépend uniquement d’hypothèses de coûts fictives, visibles et configurées pour cette démonstration.',
    primaryActionLabel: 'Explorer librement',
    focus: 'estimate',
    targetsScenarioMachine: true,
  },
] as const satisfies readonly GuidedTourStep[];

export interface ShowroomEvidence {
  readonly label: string;
  readonly source: string;
  readonly observedValue: number;
  readonly baselineValue: number;
  readonly unit: string;
  readonly periodLabel: string;
  readonly sourceReference: string;
  readonly simulatedWindow: string;
  readonly sampleContext: string;
}

export const S001_EVIDENCE: readonly ShowroomEvidence[] = [
  {
    label: 'Température zone 2',
    source: 'Mesures machine agrégées',
    observedValue: 194.9,
    baselineValue: 210.1,
    unit: '°C',
    periodLabel: 'Période simulée sélectionnée comparée à la référence saine',
    sourceReference: 'S001 / machine liée à l’incident API / cycles / barrel_temp_zone2_c',
    simulatedWindow: '12 février 2025, 00:21 à 01:52 (fenêtre simulée)',
    sampleContext: '217 cycles agrégés observés, comparés à 216 cycles de référence saine',
  },
  {
    label: 'Taux de rebut',
    source: 'Contrôles qualité agrégés',
    observedValue: 34.6,
    baselineValue: 2.8,
    unit: '%',
    periodLabel: 'Période simulée sélectionnée comparée à la référence saine',
    sourceReference: 'S001 / machine liée à l’incident API / qualité / scrap_rate',
    simulatedWindow: '12 février 2025, 00:21 à 01:52 (fenêtre simulée)',
    sampleContext: '1 200 contrôles qualité simulés, comparés à 1 180 contrôles de référence',
  },
];

export interface ShowroomTracePoint {
  readonly timestamp: string;
  readonly temperature: number;
  readonly scrapRate: number;
  readonly cycleTime: number;
}

/** Explicitly fictitious points used only to make the demonstration readable. */
export const S001_TRACE_POINTS: readonly ShowroomTracePoint[] = [
  { timestamp: '00:21', temperature: 210.1, scrapRate: 2.8, cycleTime: 30.0 },
  { timestamp: '00:42', temperature: 206.7, scrapRate: 8.4, cycleTime: 30.8 },
  { timestamp: '01:03', temperature: 201.4, scrapRate: 18.9, cycleTime: 31.7 },
  { timestamp: '01:24', temperature: 197.1, scrapRate: 27.8, cycleTime: 32.1 },
  { timestamp: '01:52', temperature: 194.9, scrapRate: 34.6, cycleTime: 31.4 },
];

export interface ActionProposal {
  readonly recommendation: string;
  readonly justification: string;
  readonly responsibleRole: string;
  readonly estimatedDuration: string;
  readonly successMetric: string;
  readonly operationalRisk: string;
  readonly statusLabel: string;
}

export const S001_ACTION_PROPOSAL: ActionProposal = {
  recommendation: 'Vérifier la régulation thermique de la zone 2 avant le prochain ordre comparable.',
  justification: 'La dérive thermique et la hausse des rebuts sont observées sur la même période.',
  responsibleRole: 'Méthodes et maintenance',
  estimatedDuration: '30 minutes',
  successMetric: 'Température revenue dans la plage saine et taux de rebut stabilisé',
  operationalRisk: 'Arrêt court à planifier ; aucune commande machine automatique',
  statusLabel: 'Aperçu de démonstration, décision non enregistrée',
};

export interface CostAssumptions {
  readonly materialCostPerPart: number;
  readonly avoidableScrapParts: number;
  readonly machineHourlyCost: number;
  readonly recoverableMachineHours: number;
}

export const SHOWROOM_COST_ASSUMPTIONS: CostAssumptions = {
  materialCostPerPart: 4.5,
  avoidableScrapParts: 50,
  machineHourlyCost: 120,
  recoverableMachineHours: 1.5,
};

export interface ImpactInput {
  readonly key: keyof CostAssumptions;
  readonly label: string;
  readonly value: number;
  readonly unit: string;
}

export interface ImpactEstimate {
  readonly inputs: readonly ImpactInput[];
  readonly materialImpact: number;
  readonly machineTimeImpact: number;
  readonly total: number;
  readonly formulaLabel: string;
  readonly disclaimer: string;
}

export function calculateImpactEstimate(assumptions: CostAssumptions): ImpactEstimate {
  const assumptionKeys: readonly (keyof CostAssumptions)[] = [
    'materialCostPerPart',
    'avoidableScrapParts',
    'machineHourlyCost',
    'recoverableMachineHours',
  ];
  for (const key of assumptionKeys) {
    if (!Number.isFinite(assumptions[key]) || assumptions[key] < 0) {
      throw new RangeError(`L’hypothèse ${key} doit être un nombre fini supérieur ou égal à zéro.`);
    }
  }

  const materialImpact = assumptions.materialCostPerPart * assumptions.avoidableScrapParts;
  const machineTimeImpact = assumptions.machineHourlyCost * assumptions.recoverableMachineHours;

  return {
    inputs: [
      { key: 'materialCostPerPart', label: 'Coût matière par kg', value: assumptions.materialCostPerPart, unit: '€ / kg' },
      { key: 'avoidableScrapParts', label: 'Quantité de rebuts évitables en kg', value: assumptions.avoidableScrapParts, unit: 'kg' },
      { key: 'machineHourlyCost', label: 'Coût horaire machine', value: assumptions.machineHourlyCost, unit: '€ / heure' },
      { key: 'recoverableMachineHours', label: 'Temps machine récupérable', value: assumptions.recoverableMachineHours, unit: 'heures' },
    ],
    materialImpact,
    machineTimeImpact,
    total: materialImpact + machineTimeImpact,
    formulaLabel: 'Impact potentiel = (coût matière × rebuts évitables) + (coût horaire machine × temps récupérable)',
    disclaimer: 'Estimation de démonstration fondée sur des coûts fictifs configurés.',
  };
}

export function getNextTourStepIndex(currentIndex: number): number {
  return Math.min(normalizeTourStepIndex(currentIndex) + 1, guidedTourSteps.length - 1);
}

export function getPreviousTourStepIndex(currentIndex: number): number {
  return Math.max(normalizeTourStepIndex(currentIndex) - 1, 0);
}

function normalizeTourStepIndex(index: number): number {
  if (!Number.isFinite(index)) return 0;
  return Math.min(Math.max(Math.trunc(index), 0), guidedTourSteps.length - 1);
}

export function getMachineVisualState(machineId: number, tourStepIndex: number, scenarioMachineId?: number): MachineVisualState {
  const normalizedTourStepIndex = normalizeTourStepIndex(tourStepIndex);
  if (scenarioMachineId === undefined || machineId !== scenarioMachineId || normalizedTourStepIndex < 2) return 'stable';
  if (normalizedTourStepIndex === 2) return 'watch';
  return 'incident';
}
