import { useEffect, useRef, useState, type ReactNode } from 'react';
import type { Incident, Machine } from '../../lib/api';
import {
  S001_ACTION_PROPOSAL,
  S001_EVIDENCE,
  S001_TRACE_POINTS,
  SHOWROOM_COST_ASSUMPTIONS,
  calculateImpactEstimate,
  type CostAssumptions,
} from './showroomModel';

const statusLabels = { running: 'En production', warning: 'À surveiller', stopped: 'Arrêtée', offline: 'Hors ligne', unknown: 'Statut inconnu' } as const;
const euros = new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' });
const formatAsOf = (value: string) => new Intl.DateTimeFormat('fr-FR', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Europe/Paris' }).format(new Date(value));
const fields: readonly { key: keyof CostAssumptions; label: string; step: string }[] = [
  { key: 'materialCostPerPart', label: 'Coût matière (€ / kg)', step: '0.1' },
  { key: 'avoidableScrapParts', label: 'Rebuts évitables (kg)', step: '1' },
  { key: 'machineHourlyCost', label: 'Coût machine (€ / heure)', step: '1' },
  { key: 'recoverableMachineHours', label: 'Heures récupérables', step: '0.1' },
];
const initialAssumptions = () => Object.fromEntries(Object.entries(SHOWROOM_COST_ASSUMPTIONS).map(([key, value]) => [key, String(value)])) as Record<keyof CostAssumptions, string>;
type InspectorSection = 'evidence' | 'hypotheses' | 'signals' | 'action' | 'impact' | 'history';
type TimestampOrigin = 'historical' | 'source' | 'simulated';

function focusSection(focus: string): InspectorSection {
  if (focus === 'impact') return 'evidence';
  if (focus === 'investigation') return 'hypotheses';
  if (focus === 'action') return 'action';
  if (focus === 'estimate') return 'impact';
  return 'history';
}

function TraceChart() {
  const x = (index: number) => 42 + index * 94;
  const line = (values: number[], min: number, max: number) => values.map((value, index) => `${x(index)},${122 - ((value - min) / (max - min)) * 82}`).join(' ');
  const temperature = S001_TRACE_POINTS.map((point) => point.temperature);
  const scrap = S001_TRACE_POINTS.map((point) => point.scrapRate);
  const cycle = S001_TRACE_POINTS.map((point) => point.cycleTime);
  return <div className="showroom-trace-visual" aria-label="Traces de démonstration fictives">
    <svg viewBox="0 0 470 160" role="img" aria-labelledby="trace-title trace-desc">
      <title id="trace-title">Traces de démonstration S001</title>
      <desc id="trace-desc">Trois séries fictives convergent vers un marqueur incident à 01:52.</desc>
      <path d="M28 122H448M28 40H448M28 122V24" stroke="#E6E8EA" strokeWidth="1" />
      <polyline points={line(temperature, 190, 212)} fill="none" stroke="#059669" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
      <polyline points={line(scrap, 0, 40)} fill="none" stroke="#DC2626" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
      <polyline points={line(cycle, 29, 34)} fill="none" stroke="#475569" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
      {S001_TRACE_POINTS.map((point, index) => <text key={point.timestamp} x={x(index)} y="146" textAnchor="middle" fontSize="12" fill="#64748B">{point.timestamp}</text>)}
      <line x1="418" x2="418" y1="20" y2="128" stroke="#DC2626" strokeWidth="2" strokeDasharray="5 5" /><circle cx="418" cy="20" r="9" fill="#DC2626" /><text x="418" y="23.5" textAnchor="middle" fontSize="12" fontWeight="700" fill="#FFFFFF">!</text><text x="426" y="36" fontSize="12" fontWeight="700" fill="#DC2626">Incident</text>
    </svg>
    <div className="trace-legend"><span><i className="trace-temp" />Température °C</span><span><i className="trace-scrap" />Rebut %</span><span><i className="trace-cycle" />Cycle s</span><strong>Points fictifs · lecture illustrative</strong></div>
  </div>;
}

function Disclosure({ section, anchorId, label, meta, open, onToggle, reference, children }: { section: InspectorSection; anchorId?: string; label: string; meta: string; open: boolean; onToggle: (open: boolean) => void; reference: (element: HTMLElement | null) => void; children: ReactNode }) {
  return <details id={anchorId} data-section={section} ref={reference} open={open} onToggle={(event) => onToggle(event.currentTarget.open)}><summary><span>{label}</span><span className="disclosure-meta">{meta}</span></summary>{children}</details>;
}

export function ShowroomInspector({ machine, incidents, scenarioMachineId, evidenceAvailable, focus, tourActive, focusRequest, mobile, open, onClose, restoreFocusTo, timestampOrigin, statusUnavailable, statusLoading, historicalRequested, incidentsUnavailable }: {
  machine?: Machine;
  incidents: Incident[];
  scenarioMachineId?: number;
  evidenceAvailable: boolean;
  focus: string;
  tourActive: boolean;
  focusRequest: number;
  mobile: boolean;
  open: boolean;
  onClose: () => void;
  restoreFocusTo: HTMLElement | null;
  timestampOrigin: TimestampOrigin;
  statusUnavailable: boolean;
  statusLoading: boolean;
  historicalRequested: boolean;
  incidentsUnavailable: boolean;
}) {
  const [values, setValues] = useState(initialAssumptions);
  const [openSections, setOpenSections] = useState<Record<InspectorSection, boolean>>({ evidence: false, hypotheses: false, signals: false, action: false, impact: false, history: false });
  const sectionRefs = useRef<Record<InspectorSection, HTMLElement | null>>({ evidence: null, hypotheses: null, signals: null, action: null, impact: null, history: null });
  const sheetRef = useRef<HTMLElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const restoreRef = useRef<HTMLElement | null>(null);
  const onCloseRef = useRef(onClose);
  useEffect(() => { onCloseRef.current = onClose; }, [onClose]);

  useEffect(() => {
    if (!tourActive) return;
    const section = focusSection(focus);
    setOpenSections((current) => ({ ...current, [section]: true }));
    const target = sectionRefs.current[section];
    const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;
    target?.scrollIntoView?.({ behavior: reducedMotion ? 'auto' : 'smooth', block: 'nearest' });
    if (target) target.dataset.focused = 'true';
  }, [focus, tourActive]);
  useEffect(() => { if (focusRequest > 0 && !mobile) headingRef.current?.focus(); }, [focusRequest, mobile]);
  useEffect(() => {
    if (!mobile || !open) return;
    restoreRef.current = restoreFocusTo ?? (document.activeElement instanceof HTMLElement ? document.activeElement : null);
    closeRef.current?.focus();
    const handleKeydown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); onCloseRef.current(); return; }
      if (event.key !== 'Tab') return;
      const focusables = Array.from(sheetRef.current?.querySelectorAll<HTMLElement>('button:not([disabled]), input:not([disabled]), summary, [href], [tabindex]:not([tabindex="-1"])') ?? []);
      if (!focusables.length) return;
      const first = focusables[0]; const last = focusables[focusables.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener('keydown', handleKeydown);
    return () => { document.removeEventListener('keydown', handleKeydown); if (restoreRef.current && document.contains(restoreRef.current)) restoreRef.current.focus(); };
  }, [mobile, open, restoreFocusTo]);

  if (!machine) return <aside className="showroom-inspector showroom-empty"><h2>Aucune machine sélectionnée</h2><p>Sélectionnez une machine dans l’atelier.</p></aside>;
  if (mobile && !open) return null;
  const isScenarioMachine = scenarioMachineId !== undefined && machine.id === scenarioMachineId;
  const status = machine.status ?? 'unknown';
  const metric = machine.metrics ?? {};
  const timestampLabel = timestampOrigin === 'historical' ? 'Horodatage historique sélectionné' : timestampOrigin === 'source' ? 'Horodatage source' : 'Horodatage simulé';
  const statusLabel = timestampOrigin === 'historical' ? 'État historique API au timestamp' : statusUnavailable && historicalRequested ? 'État du dernier catalogue connu' : 'Statut actuel';
  const metricSource = timestampOrigin === 'historical' ? 'Source : réponse statut API historique' : timestampOrigin === 'simulated' ? 'Source : état scénarisé fictif' : 'Source : catalogue machine API';
  let estimate; let estimateError = '';
  try { estimate = calculateImpactEstimate(Object.fromEntries(fields.map(({ key }) => [key, values[key] === '' ? Number.NaN : Number(values[key])])) as unknown as CostAssumptions); } catch (error) { estimateError = error instanceof Error ? error.message : 'Les hypothèses doivent être des nombres valides.'; }
  const register = (section: InspectorSection) => (element: HTMLElement | null) => { sectionRefs.current[section] = element; };
  const openSection = (section: InspectorSection) => { setOpenSections((current) => ({ ...current, [section]: true })); window.setTimeout(() => sectionRefs.current[section]?.scrollIntoView?.({ behavior: 'smooth', block: 'nearest' }), 0); };
  const updateSection = (section: InspectorSection, value: boolean) => setOpenSections((current) => ({ ...current, [section]: value }));
  const evidenceSource = (item: typeof S001_EVIDENCE[number]) => item.sourceReference.replace('machine liée à l’incident API', machine.erpRef ? `presse ${machine.erpRef}` : 'machine liée à l’incident API');

  return <aside ref={sheetRef} className={`showroom-inspector${mobile ? ' showroom-bottom-sheet' : ''}`} role={mobile ? 'dialog' : undefined} aria-modal={mobile ? true : undefined} aria-label={mobile ? `Détails de ${machine.name}` : undefined}>
    {mobile && <><div className="sheet-handle" aria-hidden="true" /><button ref={closeRef} type="button" className="showroom-sheet-close" aria-label="Fermer les détails" onClick={onClose}>Fermer</button></>}
    <section className="showroom-machine-summary" aria-labelledby="showroom-machine-title"><p className="showroom-kicker">Machine sélectionnée</p><h2 ref={headingRef} id="showroom-machine-title" tabIndex={-1}>{machine.name}</h2><p className="showroom-subtitle">ERP {machine.erpRef ?? 'non renseigné'} · {incidentsUnavailable ? 'incidents historiques indisponibles' : `${incidents.length} incident${incidents.length > 1 ? 's' : ''} associé${incidents.length > 1 ? 's' : ''}`}</p>
      {statusLoading ? <div className="showroom-status-loading" role="status" aria-label="Chargement du statut"><strong>Chargement du statut à l’horodatage…</strong><span aria-hidden="true" /></div> : <div className="showroom-machine-metrics">
        <div className={`metric-status status-${status}`}><span>{statusLabel}</span><strong>{statusLabels[status]}</strong><small>{metricSource}</small></div><div><span>OF courant</span><strong>{metric.currentOrderId ?? 'Indisponible'}</strong><small>{metricSource}</small></div><div><span>TRS</span><strong>{metric.trs == null ? 'Indisponible' : `${Math.round(metric.trs * 100)} %`}</strong><small>{metric.trs == null ? 'Non fourni par le statut API' : metricSource}</small></div><div><span>Rebuts</span><strong>{metric.scrapRate == null ? 'Indisponible' : `${(metric.scrapRate * 100).toFixed(1)} %`}</strong><small>{metric.scrapRate == null ? 'Non fourni par le statut API' : metricSource}</small></div><div><span>Variance cycle</span><strong>{metric.cycleTimeS == null ? 'Indisponible' : `${(metric.cycleTimeS - 30).toFixed(1)} s`}</strong><small>{metric.cycleTimeS == null ? 'Cycle absent de la réponse statut' : 'Formule : cycle observé − baseline fictive 30,0 s'}</small></div><div><span>{timestampLabel}</span><strong>{machine.asOf ? formatAsOf(machine.asOf) : 'Non renseigné'}</strong><small>{timestampOrigin === 'historical' ? 'Replay partagé avec incidents et preuves' : timestampOrigin === 'simulated' ? 'Démonstration sans écriture' : 'Provenance catalogue'}</small></div><div><span>Fraîcheur</span><strong>{machine.freshnessS == null ? 'Non renseignée' : machine.freshnessS > 300 ? `Données anciennes · ${machine.freshnessS} s` : `À jour · ${machine.freshnessS} s`}</strong><small>Source : API statut</small></div>
      </div>}
      <div className="showroom-machine-actions"><button type="button" className="button-primary" onClick={() => openSection('hypotheses')}>Comprendre l’incident</button><button type="button" onClick={() => openSection('signals')}>Voir les signaux</button><button type="button" onClick={() => openSection('history')}>Historique</button></div>
    </section>
    {statusUnavailable && <p className="showroom-degraded" role="status"><span className="status-shape" aria-hidden="true" />Statut détaillé indisponible · dernier catalogue connu affiché, pas l’horodatage sélectionné.</p>}
    {(metric.trs == null || metric.scrapRate == null || metric.cycleTimeS == null) && <p className="showroom-degraded"><span className="status-shape" aria-hidden="true" />Couverture partielle : le contrat statut ne fournit pas toutes les métriques.</p>}
    {(machine.freshnessS ?? 0) > 300 && <p className="showroom-degraded"><span className="status-shape" aria-hidden="true" />Données anciennes, à interpréter avec prudence.</p>}
    {!machine.asOf && <p className="showroom-degraded"><span className="status-shape" aria-hidden="true" />Replay indisponible pour cette sélection.</p>}
    {incidentsUnavailable ? <p className="showroom-degraded" role="alert"><span className="status-shape" aria-hidden="true" />Incidents historiques indisponibles · aucune absence de preuve n’est déduite.</p> : incidents.length === 0 && <p className="showroom-degraded"><span className="status-shape" aria-hidden="true" />Investigation non exécutée · aucune preuve liée à cet instant.</p>}
    {isScenarioMachine && incidentsUnavailable ? <><section id="actions" className="showroom-no-evidence" role="alert"><h3>Preuves historiques indisponibles</h3><p>La requête d’incidents au temps sélectionné a échoué. Les preuves fictives restent masquées et l’interface ne conclut pas à leur absence.</p></section><section id="gains" className="showroom-no-evidence"><h3>Impact non disponible</h3><p>Aucune estimation n’est affichée sans fenêtre historique vérifiée.</p></section></> : isScenarioMachine && !evidenceAvailable ? <><section id="actions" className="showroom-no-evidence" role="status"><h3>Aucune preuve liée à cet instant</h3><p>Le replay est antérieur à l’incident S001. Les preuves fictives restent masquées jusqu’à leur fenêtre de démonstration.</p></section><section id="gains" className="showroom-no-evidence"><h3>Impact non disponible</h3><p>Aucune estimation n’est affichée avant la fenêtre de l’incident.</p></section></> : !isScenarioMachine ? <><section id="actions" className="showroom-no-evidence" role="status"><h3>Aucune preuve S001 liée à cette machine</h3><p>Le scénario fictif est rattaché à la machine et à l’OF présents dans l’incident API. Cette sélection reste disponible pour explorer le catalogue.</p></section><section id="gains" className="showroom-no-evidence"><h3>Impact non disponible</h3><p>Aucune estimation n’est affichée sans correspondance machine et incident.</p></section></> : <>
      <Disclosure section="hypotheses" label="Hypothèses classées" meta="Contexte de démonstration" open={openSections.hypotheses} onToggle={(value) => updateSection('hypotheses', value)} reference={register('hypotheses')}><div className="showroom-hypotheses" data-focused={tourActive && focus === 'investigation'}><ol aria-label="Hypothèses classées de démonstration"><li><strong>Température zone 2 trop basse</strong><span>Hypothèse principale de démonstration</span><p>Confiance de démonstration élevée selon les règles fictives S001 ; ce n’est ni une probabilité ni une preuve.</p><dl><div><dt>Éléments favorables</dt><dd>Température et rebut évoluent sur la même fenêtre fictive.</dd></div><div><dt>Éléments contradictoires</dt><dd>La concomitance ne démontre pas la causalité.</dd></div><div><dt>Données manquantes</dt><dd>Mesure électrique indépendante de la zone 2.</dd></div><div><dt>Prochain contrôle recommandé</dt><dd>Vérifier physiquement la régulation avant conclusion.</dd></div></dl></li><li><strong>Écart de matière ou de lot</strong><span>Hypothèse alternative</span><p>Contexte fictif, aucune probabilité produite.</p></li><li><strong>Dérive de cadence</strong><span>Hypothèse alternative</span><p>Amplitude simulée insuffisante pour conclure.</p></li></ol></div></Disclosure>
      <Disclosure section="evidence" label="Preuves observées" meta={`${S001_EVIDENCE.length} sources · simulées`} open={openSections.evidence} onToggle={(value) => updateSection('evidence', value)} reference={register('evidence')}><div className="showroom-evidence" data-focused={tourActive && focus === 'impact'}>{S001_EVIDENCE.map((item) => <article key={item.label}><strong>{item.label}</strong><small>Source : {item.source} · points explicitement fictifs</small><dl><div><dt>Observé</dt><dd>{item.observedValue} {item.unit}</dd></div><div><dt>Référence</dt><dd>{item.baselineValue} {item.unit}</dd></div><div><dt>Écart</dt><dd>{item.observedValue - item.baselineValue > 0 ? '+' : ''}{(item.observedValue - item.baselineValue).toFixed(1)} {item.unit}</dd></div></dl><p>{item.periodLabel}</p><ul className="showroom-provenance"><li><strong>Référence source :</strong> {evidenceSource(item)}</li><li><strong>Fenêtre :</strong> {item.simulatedWindow}</li><li><strong>Échantillon :</strong> {item.sampleContext}</li></ul></article>)}</div></Disclosure>
      <Disclosure section="signals" label="Signaux synchronisés" meta="Traces de démonstration" open={openSections.signals} onToggle={(value) => updateSection('signals', value)} reference={register('signals')}><div><TraceChart /><table className="showroom-trace-table"><caption>Table alternative des traces fictives S001</caption><thead><tr><th>Temps</th><th>Température °C</th><th>Rebut %</th><th>Cycle s</th></tr></thead><tbody>{S001_TRACE_POINTS.map((point) => <tr key={point.timestamp}><th scope="row">{point.timestamp}</th><td>{point.temperature}</td><td>{point.scrapRate}</td><td>{point.cycleTime}</td></tr>)}</tbody></table></div></Disclosure>
      <Disclosure section="action" label="Action proposée" meta="Aperçu · non persistée" open={openSections.action} onToggle={(value) => updateSection('action', value)} reference={register('action')}><div id="actions" className="showroom-action" data-focused={tourActive && focus === 'action'}><h3>{S001_ACTION_PROPOSAL.recommendation}</h3><p>{S001_ACTION_PROPOSAL.justification}</p><dl><div><dt>Rôle</dt><dd>{S001_ACTION_PROPOSAL.responsibleRole}</dd></div><div><dt>Durée estimée</dt><dd>{S001_ACTION_PROPOSAL.estimatedDuration}</dd></div><div><dt>Critère de succès</dt><dd>{S001_ACTION_PROPOSAL.successMetric}</dd></div><div><dt>Risque opérationnel</dt><dd>{S001_ACTION_PROPOSAL.operationalRisk}</dd></div></dl><p className="showroom-honesty">{S001_ACTION_PROPOSAL.statusLabel}. Aucune commande machine automatique.</p></div></Disclosure>
      <Disclosure section="impact" label="Impact potentiel" meta="Coûts fictifs · ±20 %" open={openSections.impact} onToggle={(value) => updateSection('impact', value)} reference={register('impact')}><div id="gains" className="showroom-impact" data-focused={tourActive && focus === 'estimate'}><p className="showroom-honesty">Aperçu économique de démonstration · aucune économie validée, aucun gain enregistré.</p><div className="showroom-impact-editor">{fields.map(({ key, label, step }) => <label key={key}>{label}<input type="number" min="0" step={step} value={values[key]} aria-label={label} aria-invalid={Boolean(estimateError)} onChange={(event) => setValues((current) => ({ ...current, [key]: event.target.value }))} /></label>)}</div>{estimateError && <p className="showroom-input-error" role="alert">{estimateError}</p>}<button type="button" className="showroom-reset-assumptions" onClick={() => setValues(initialAssumptions())}>Réinitialiser les hypothèses</button>{estimate && <><p className="showroom-formula">{estimate.formulaLabel}</p><dl className="showroom-subtotals"><div><dt>Sous-total matière</dt><dd>{euros.format(estimate.materialImpact)}</dd></div><div><dt>Sous-total temps machine</dt><dd>{euros.format(estimate.machineTimeImpact)}</dd></div></dl><div className="showroom-total"><span>Estimation centrale de démonstration</span><strong>{euros.format(estimate.total)}</strong></div><div className="showroom-impact-range"><p>Plage illustrative explicitement fixée à ± 20 % autour de l’estimation centrale.</p><dl><div><dt>Basse</dt><dd>{euros.format(estimate.total * .8)}</dd></div><div><dt>Centrale</dt><dd>{euros.format(estimate.total)}</dd></div><div><dt>Haute</dt><dd>{euros.format(estimate.total * 1.2)}</dd></div></dl></div></>}</div></Disclosure>
      <Disclosure section="history" label="Historique de la sélection" meta="Horodatage et provenance" open={openSections.history} onToggle={(value) => updateSection('history', value)} reference={register('history')}><div className="showroom-history"><p><strong>Fenêtre S001</strong> · 12 février 2025, 00:21 à 01:52 (fenêtre simulée).</p><p>Incident API associé : {incidents[0]?.id ?? 'aucun incident résolu'} · OF {incidents[0]?.production_order_id ?? metric.currentOrderId ?? 'non renseigné'}.</p><p>Les données affichées distinguent l’historique API, le catalogue source et les points fictifs de présentation.</p></div></Disclosure>
    </>}
  </aside>;
}
