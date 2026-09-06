import { useEffect, useState, type FormEvent } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useApi } from '../../App';
import { ApiRequestError, type ERPImportPreview, type ERPImportRequest, type ERPPreviewChoices, type ERPReplacement, type ShiftCalendar } from '../../lib/api';
import { formatDate, SectionTitle } from '../Ui';
import './ErpImportWizard.css';

const FIELD_LABELS: Record<string, string> = {
  order_target_quantity: 'Quantité cible OF', order_status: 'Statut OF', order_status_effective_at: 'Date du statut',
  order_status_reason: 'Motif du statut', quality_lot_ref: 'Lot qualité', coverage_complete: 'Historique OF complet',
};
const STATE_LABELS: Record<string, string> = { uploaded: 'Fichier reçu', profiling: 'Analyse', preview_ready: 'À confirmer', queued: 'En attente de traitement', processing: 'En cours', completed: 'Terminé', failed: 'Échec' };
function message(error: unknown) {
  if (error instanceof ApiRequestError) {
    if (error.status === 413) return 'Le fichier dépasse la limite autorisée : 20 Mio compressés ou 100 Mio décompressés.';
    if (error.status === 415) return 'Sélectionnez un classeur XLSX valide et non chiffré.';
    if (error.status === 409) return 'Les données ou les choix ont changé. Relisez l’aperçu avant de confirmer.';
    if (error.status === 422) return 'Le fichier ou les champs saisis ne peuvent pas être lus. Vérifiez leur format.';
  }
  return error instanceof Error ? error.message : 'Le traitement a échoué.';
}

function SitePreparation({ siteId, timezone, onCalendarChanged }: { siteId: number; timezone: string; onCalendarChanged: () => void }) {
  const api = useApi();
  const cache = useQueryClient();
  const calendar = useQuery({ queryKey: ['shift-calendar', siteId], queryFn: () => api.getShiftCalendar(siteId) });
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [rows, setRows] = useState([{ number: 1, start: '', end: '' }]);
  const [zone, setZone] = useState(timezone);
  const [validFrom, setValidFrom] = useState('');
  const [validTo, setValidTo] = useState('');
  function loadCalendar(value: ShiftCalendar) {
    setRows(value.shifts); setZone(value.timezone); setValidFrom(value.valid_from); setValidTo(value.valid_to ?? '');
  }
  async function save(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(''); setNotice('');
    try {
      await api.saveShiftCalendar(siteId, { timezone: zone, valid_from: validFrom, valid_to: validTo || null, expected_version: calendar.data?.version ?? 0, shifts: rows });
      await cache.invalidateQueries({ queryKey: ['shift-calendar', siteId] });
      onCalendarChanged(); setNotice('Calendrier enregistré. Relisez l’aperçu pour actualiser les périodes.');
    } catch (error) { setError(message(error)); } finally { setBusy(false); }
  }
  async function createMachine(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = event.currentTarget; const data = new FormData(form);
    setBusy(true); setError(''); setNotice('');
    try {
      await api.createMachine(siteId, { erp_ref: String(data.get('erp_ref')), name: String(data.get('name')) });
      await cache.invalidateQueries({ queryKey: ['machines'] });
      setNotice('Presse ajoutée au catalogue de l’atelier.'); form.reset();
    } catch (error) { setError(message(error)); } finally { setBusy(false); }
  }
  return <details className="surface-card erp-site-preparation">
    <summary>Préparer le site : presse et calendrier d’équipes</summary>
    {error && <p role="alert" className="helper-error">{error}</p>}
    {notice && <p role="status">{notice}</p>}
    <form onSubmit={createMachine} className="form-grid">
      <h3>Ajouter une presse sans bilan ERP</h3>
      <label>Référence ERP<input name="erp_ref" required maxLength={50} /></label>
      <label>Nom de la presse<input name="name" required maxLength={100} /></label>
      <button type="submit" className="button-secondary" disabled={busy}>Ajouter la presse</button>
    </form>
    <form onSubmit={save} className="form-grid">
      <h3>Calendrier des relais</h3>
      <p className="muted">Renseignez les horaires réels du site. Ils donnent une période estimée aux déclarations sans heure de fin.</p>
      {calendar.isError && <p role="alert" className="helper-error">Calendrier indisponible.</p>}
      {calendar.data && <button type="button" className="button-secondary" onClick={() => loadCalendar(calendar.data!)}>Reprendre la version {calendar.data.version}</button>}
      <label>Fuseau horaire<input required value={zone} onChange={event => setZone(event.target.value)} /></label>
      <label>Valable à partir du<input type="date" required value={validFrom} onChange={event => setValidFrom(event.target.value)} /></label>
      <label>Valable jusqu’au (facultatif)<input type="date" value={validTo} onChange={event => setValidTo(event.target.value)} /></label>
      {rows.map((row, index) => <fieldset key={index}>
        <legend>Relais {index + 1}</legend>
        <label>Numéro d’équipe<input type="number" min={1} max={32767} required value={row.number} onChange={event => setRows(rows.map((item, i) => i === index ? { ...item, number: Number(event.target.value) } : item))} /></label>
        <label>Début local<input type="time" required value={row.start} onChange={event => setRows(rows.map((item, i) => i === index ? { ...item, start: event.target.value } : item))} /></label>
        <label>Fin locale<input type="time" required value={row.end} onChange={event => setRows(rows.map((item, i) => i === index ? { ...item, end: event.target.value } : item))} /></label>
        {rows.length > 1 && <button type="button" className="button-ghost" onClick={() => setRows(rows.filter((_, i) => i !== index))}>Retirer ce relais</button>}
      </fieldset>)}
      <button type="button" className="button-ghost" onClick={() => setRows([...rows, { number: Math.max(...rows.map(row => row.number)) + 1, start: '', end: '' }])}>Ajouter un relais</button>
      <button type="submit" className="button-secondary" disabled={busy || calendar.isPending || calendar.isError}>Confirmer le calendrier</button>
    </form>
  </details>;
}

export function ErpImportWizard({ siteId, timezone, canImport, canConfigure }: { siteId: number; timezone: string; canImport: boolean; canConfigure: boolean }) {
  const api = useApi();
  const cache = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ERPImportPreview | null>(null);
  const [job, setJob] = useState<ERPImportRequest | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [stale, setStale] = useState(false);
  const [machines, setMachines] = useState<string[]>([]);
  const [choices, setChoices] = useState<ERPPreviewChoices>({});
  const [replacements, setReplacements] = useState<Record<number, string>>({});
  const [previewPage, setPreviewPage] = useState(0);
  const previewPageSize = 20;
  const journal = useQuery({ queryKey: ['erp-imports', siteId], queryFn: () => api.getERPImports(siteId), refetchInterval: 5000 });
  const pending = job?.state === 'queued' || job?.state === 'processing';
  useEffect(() => {
    if (!pending || !job) return;
    let active = true;
    const timer = window.setInterval(() => {
      api.getERPPreview(job.id).then(result => {
        if (!active) return;
        setJob(result);
        if (result.state === 'completed') {
          void cache.invalidateQueries({ queryKey: ['imports'] });
          void cache.invalidateQueries({ queryKey: ['machines'] });
          void cache.invalidateQueries({ queryKey: ['erp-imports', siteId] });
        }
      }).catch(error => { if (active) setError(message(error)); });
    }, 2000);
    return () => { active = false; window.clearInterval(timer); };
  }, [api, cache, job, pending, siteId]);
  async function run(action: () => Promise<void>) {
    setBusy(true); setError('');
    try { await action(); } catch (error) {
      setError(message(error)); if (error instanceof ApiRequestError && error.status === 409) setStale(true);
    } finally { setBusy(false); }
  }
  function display(value: ERPImportPreview) {
    setPreview(value); setJob(value); setChoices(value.choices ?? {}); setMachines([]); setReplacements({}); setPreviewPage(0); setStale(false);
  }
  function upload(event: FormEvent) {
    event.preventDefault(); if (!file) return;
    void run(async () => {
      const request = await api.uploadERP(siteId, file); setJob(request);
      display(await api.getERPPreview(request.id, true));
      await cache.invalidateQueries({ queryKey: ['erp-imports', siteId] });
    });
  }
  function reload() {
    if (!job) return;
    void run(async () => display(await api.getERPPreview(job.id, true)));
  }
  function confirm() {
    if (!preview) return;
    const selected: ERPReplacement[] = Object.entries(replacements).filter(([, id]) => id && id !== 'new').map(([row, id]) => {
      const candidate = preview.items.find(item => item.source_row === Number(row))!.identity_candidates.find(item => item.declaration_id === id)!;
      return { source_row: Number(row), ...candidate };
    });
    void run(async () => {
      const newRows = Object.entries(replacements).filter(([, id]) => id === 'new').map(([row]) => Number(row));
      setJob(await api.confirmERP(preview.id, { preview_version: preview.preview_version, create_machine_refs: machines, replacements: selected, ...(newRows.length ? { new_identity_rows: newRows } : {}) }));
      await cache.invalidateQueries({ queryKey: ['erp-imports', siteId] });
    });
  }
  const locked = pending || job?.state === 'completed';
  const errors = preview?.issues.filter(issue => !issue.severity || issue.severity === 'error') ?? [];
  const warnings = preview?.issues.filter(issue => issue.severity === 'warning') ?? [];
  return <>
    {canConfigure && <SitePreparation siteId={siteId} timezone={timezone} onCalendarChanged={() => setStale(true)} />}
    <section className="surface-card import-table-card erp-import-card">
      <SectionTitle eyebrow="BILANS D’ÉQUIPE" title="Importer un bilan TRS" />
      <p className="muted">Chaque ligne conserve le résultat d’une équipe pour un OF. Les nouvelles presses et les corrections sont vérifiées avant confirmation.</p>
      {canImport ? <form onSubmit={upload} className="form-grid">
        <label>Fichier bilan TRS<input type="file" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" onChange={event => setFile(event.target.files?.[0] ?? null)} /></label>
        <small className="muted">XLSX · 20 Mio maximum · dates interprétées dans {timezone}.</small>
        <button type="submit" className="button-primary" disabled={!file || busy || pending}>{busy ? 'Traitement…' : 'Téléverser et prévisualiser'}</button>
      </form> : <p>Votre rôle permet de consulter les imports. Un analyste peut téléverser et confirmer un fichier.</p>}
      {error && <p className="helper-error" role="alert">{error}</p>}
      {stale && <p role="alert">L’aperçu doit être relu avant confirmation.</p>}
      {canImport && (stale || (job && (!preview || preview.preview_version === 0))) && <button type="button" className="button-secondary" disabled={busy} onClick={reload}>Relire l’aperçu</button>}
      {pending && <p role="status">Import en attente de traitement. Le journal reste disponible.</p>}
      {job?.state === 'failed' && <p className="helper-error" role="alert">Import échoué : {job.public_error === 'preview_stale' ? 'le contexte a changé, relisez l’aperçu.' : 'le fichier est conservé pour une nouvelle tentative.'} {canImport && <button type="button" className="button-ghost" onClick={reload}>Relire l’aperçu</button>}</p>}
      {job?.state === 'completed' && <p role="status">Import terminé : {job.result?.created ?? 0} nouvelles déclarations, {job.result?.revised ?? 0} corrections, {job.result?.unchanged ?? 0} inchangées. {job.result?.awaiting_context ?? 0} périodes à vérifier.</p>}
      {preview?.preview_version === 0 && <p>L’aperçu n’est pas encore préparé. Un analyste peut lancer sa préparation.</p>}
      {preview && preview.preview_version > 0 && <>
        <h3>Aperçu · version {preview.preview_version}</h3>
        <p>{preview.counts.created} nouvelles · {preview.counts.revised} corrigées · {preview.counts.unchanged} inchangées</p>
        {preview.sheets.length > 1 && <label>Feuille TRS<select disabled={locked} value={choices.sheet_name ?? preview.sheet_name} onChange={event => setChoices({ ...choices, sheet_name: event.target.value })}><option value="">Choisir une feuille</option>{preview.sheets.map(sheet => <option key={sheet}>{sheet}</option>)}</select></label>}
        {errors.length > 0 && <div role="alert"><strong>{errors.length} erreurs bloquantes</strong><ul>{errors.slice(0, 25).map((issue, index) => <li key={index}>Ligne {issue.source_row || 'en-tête'} : {issue.field ? `${issue.field} · ` : ''}{issue.message}</li>)}</ul></div>}
        {warnings.length > 0 && <details open><summary>{warnings.length} valeurs ERP à vérifier</summary><p className="muted">Ces chiffres sont conservés. Ils empêchent de certifier la progression de l’OF.</p><ul>{warnings.slice(0, 25).map((issue, index) => <li key={index}>Ligne {issue.source_row} · {issue.field} : {issue.message}</li>)}</ul></details>}
        <div className="incident-table-wrap import-preview-scroll"><table className="incident-table import-table"><caption className="visually-hidden">Déclarations du bilan TRS</caption><thead><tr><th>Ligne</th><th>Presse / OF</th><th>Équipe</th><th>Pièces fabriquées / bonnes / rebuts</th><th>Cycles</th><th>Période</th><th>Modification</th></tr></thead>
          <tbody>{preview.items.slice(previewPage * previewPageSize, (previewPage + 1) * previewPageSize).map(item => <tr key={item.source_row}><td>{item.source_row}</td><td><strong>{item.machine_ref}</strong><small><span>OF </span><span>{item.order_ref}</span></small></td><td><span>Équipe {item.shift_number}</span><small>{formatDate(item.shift_started_at)}</small></td><td>{item.produced_parts ?? 'N/D'} / {item.good_parts ?? 'N/D'} / {item.scrap_parts ?? 'N/D'}</td><td>{item.cycle_count ?? 'N/D'}</td><td>{item.bounds_origin === 'source' ? 'Source ERP' : item.bounds_origin === 'calendar' ? 'Calendrier estimé' : 'À vérifier'}</td><td>{item.historical_replay ? 'Ancienne version déjà vue : ignorée' : { created: 'Nouvelle', revised: 'Correction', unchanged: 'Inchangée' }[item.change]}</td></tr>)}</tbody></table></div>
        {preview.items.length > previewPageSize && <nav className="import-preview-pagination" aria-label="Pagination de l’aperçu"><button type="button" className="button-ghost" disabled={previewPage === 0} onClick={() => setPreviewPage(page => page - 1)}>Précédent</button><span>Page {previewPage + 1} sur {Math.ceil(preview.items.length / previewPageSize)} · {preview.items.length} lignes</span><button type="button" className="button-ghost" disabled={(previewPage + 1) * previewPageSize >= preview.items.length} onClick={() => setPreviewPage(page => page + 1)}>Suivant</button></nav>}
        {canImport && !locked && <>
          {preview.new_machine_refs.map(ref => <label key={ref}><input type="checkbox" checked={machines.includes(ref)} onChange={event => setMachines(event.target.checked ? [...machines, ref] : machines.filter(value => value !== ref))} />Créer la presse {ref}</label>)}
          {preview.items.filter(item => item.identity_candidates.length > 0).map(item => <label key={item.source_row}>Identité à vérifier · ligne {item.source_row}<select value={replacements[item.source_row] ?? ''} onChange={event => setReplacements({ ...replacements, [item.source_row]: event.target.value })}><option value="">Choisir le traitement de cette identité</option><option value="new">Confirmer une nouvelle déclaration distincte</option>{item.identity_candidates.map(candidate => <option key={candidate.declaration_id} value={candidate.declaration_id}>OF {item.order_ref} · équipe {item.shift_number} · {formatDate(item.shift_started_at)} · révision {candidate.expected_revision}</option>)}</select></label>)}
          {preview.order_fields_available.length > 0 && <details><summary>Confirmer les champs de contexte OF</summary><p>Utilisez ces colonnes uniquement si elles décrivent bien la cible et le statut de l’ordre entier.</p>{preview.order_fields_available.map(field => <label key={field}><input type="checkbox" checked={choices.confirmed_order_fields?.includes(field) ?? false} onChange={event => setChoices({ ...choices, confirmed_order_fields: event.target.checked ? [...(choices.confirmed_order_fields ?? []), field] : choices.confirmed_order_fields?.filter(value => value !== field) })} />{FIELD_LABELS[field] ?? field}</label>)}</details>}
          <details><summary>Couverture de l’historique OF</summary><p>Confirmez uniquement les OF dont toutes les déclarations sont présentes dans ce fichier ou déjà importées. Sans cette confirmation, le reste à produire demeure inconnu.</p>{[...new Set(preview.items.map(item => item.order_ref))].map(ref => <label key={ref}><input type="checkbox" checked={choices.complete_order_refs?.includes(ref) ?? false} onChange={event => setChoices({ ...choices, complete_order_refs: event.target.checked ? [...(choices.complete_order_refs ?? []), ref] : choices.complete_order_refs?.filter(value => value !== ref) })} />Historique complet de l’OF {ref}</label>)}</details>
          <div className="form-actions"><button type="button" className="button-secondary" disabled={busy} onClick={() => void run(async () => display(await api.configureERPPreview(preview.id, choices)))}>Actualiser les choix de l’aperçu</button><button type="button" className="button-primary" disabled={busy || stale || errors.length > 0 || !preview.items.length || machines.length !== preview.new_machine_refs.length || preview.items.some(item => item.identity_candidates.length > 0 && !replacements[item.source_row]) || JSON.stringify(choices) !== JSON.stringify(preview.choices ?? {})} onClick={confirm}>Confirmer l’import</button></div>
        </>}
      </>}
    </section>
    <section className="surface-card import-table-card erp-import-card"><SectionTitle eyebrow="TÉLÉVERSEMENTS" title="Demandes TRS" />
      {journal.isError && <p role="alert" className="helper-error">Les demandes TRS sont indisponibles.</p>}
      {!journal.isPending && !journal.isError && journal.data?.length === 0 && <p className="muted">Aucun bilan téléversé pour ce site.</p>}
      <ul>{journal.data?.map(item => <li key={item.id}><button className="button-ghost" type="button" disabled={busy || pending} onClick={() => void run(async () => display(await api.getERPPreview(item.id)))}>{item.original_name}</button> · {STATE_LABELS[item.state]} {item.public_error && <span className="helper-error">· traitement à vérifier</span>}</li>)}</ul>
    </section>
  </>;
}
