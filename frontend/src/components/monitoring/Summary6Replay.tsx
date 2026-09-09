import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ApiRequestError, type ApiClient, type Summary6Current, type Summary6Response } from '../../lib/api';

export function replayError(error: unknown): string {
  if (error instanceof ApiRequestError) {
    const messages: Record<number, string> = { 401: 'Authentification requise.', 403: 'Accès refusé pour ce site.', 409: 'Le paquet a changé. Actualisez le runtime avant de recalculer.', 503: 'Scoring indisponible : runtime non prêt.', 429: 'Trop de requêtes.' };
    return `${messages[error.status] ?? error.message}${error.status === 429 && error.details.retryAfter ? ` Réessayer après ${error.details.retryAfter} (Retry-After).` : ''}`;
  }
  return error instanceof Error ? error.message : 'Replay indisponible';
}

export function Summary6Replay({ api, current, siteId }: { api: ApiClient; current: Summary6Current; siteId?: number }) {
  const sites = useQuery({ queryKey: ['summary6', 'authorized-sites'], queryFn: api.getSites });
  const [selectedSite, setSite] = useState<number>();
  const site = siteId ?? selectedSite;
  const authorized = sites.isSuccess && !sites.isFetching && sites.data.some(s => s.id === site);
  const ready = current.replay_enabled && current.readiness === 'ready' && Boolean(current.loaded_package_id);
  return <section className="page"><h2>Summary6 — SYNTHÉTIQUE REPLAY PAS LIVE</h2>
    <p>Live non raccordé. Aucun mapping vers les presses industrielles. Confirmation scientifique échouée ; aucune prédiction de qualité.</p>
    <p>Mode : {current.active_mode} · État : {current.readiness}</p>
    <p>Sélectionné : {current.selected_package_id}<br />Chargé : {current.loaded_package_id ?? 'aucun'}</p>
    {!ready && <p role="alert">Replay indisponible : {current.reasons.join(', ')}</p>}
    {sites.isError && <p role="alert">{replayError(sites.error)}</p>}
    {siteId !== undefined ? <p>Site de l’atelier : {sites.data?.find(s => s.id === siteId)?.name ?? siteId}. {sites.isSuccess && !authorized ? 'Site non autorisé : replay bloqué.' : ''}</p> : <label>Site autorisé (monitoring multi-sites) <select disabled={sites.isPending || sites.isError} value={site ?? ''} onChange={e => setSite(e.target.value ? Number(e.target.value) : undefined)}>
      <option value="">Choisir un site</option>{sites.data?.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
    </select></label>}
    {site !== undefined && authorized && ready && <ReplayForm key={`${site}:${current.loaded_package_id}`} api={api} site={site} packageId={current.loaded_package_id!} />}
    <p>Les archives historiques conservent leur identité et ne sont pas des résultats summary6. Aucun historique navigateur utilisé.</p>
  </section>;
}

function ReplayForm({ api, site, packageId }: { api: ApiClient; site: number; packageId: string }) {
  const data = useQuery({ queryKey: ['summary6', site, packageId, 'datasets'], queryFn: () => api.getSummary6Datasets(site) });
  const [lot, setLot] = useState('');
  const [cutoff, setCutoff] = useState(84);
  const [result, setResult] = useState<Summary6Response>();
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  // Contract: at most 400 observations, counters are zero-based (0…399).
  const maxCutoff = Math.min(400, data.data?.lots.find(l => l.lot_id === lot)?.count ?? 400) - 1;
  async function calculate() {
    setLoading(true); setResult(undefined); setError('');
    try {
      const response = await api.replaySummary6({ site_id: site, expected_package_id: packageId,
        source: { kind: 'demo_dataset', dataset_id: data.data!.dataset_id, lot_id: lot, through_cycle: cutoff } });
      if (response.package_id !== packageId || response.site_id !== site || response.through_cycle !== cutoff) throw new Error('Identité de réponse incohérente. Rechargez la page.');
      setResult(response);
    } catch (e) { setError(replayError(e)); }
    finally { setLoading(false); }
  }
  return <div className="surface-card">
    {data.isPending && <p role="status">Chargement des lots…</p>}
    {data.isError && <p role="alert">{replayError(data.error)}</p>}
    <label>Lot synthétique <select disabled={loading || !data.isSuccess || data.isFetching} value={lot} onChange={e => { setLot(e.target.value); setResult(undefined); setError(''); }}>
      <option value="">Choisir un lot</option>{data.data?.lots.map(l => <option key={l.lot_id}>{l.lot_id}</option>)}
    </select></label>
    <label>Dernier compteur inclus (0–{maxCutoff}, au plus 400 observations) <input type="number" min={0} max={maxCutoff} disabled={loading || !data.isSuccess || data.isFetching} value={cutoff} onChange={e => { setCutoff(Number(e.target.value)); setResult(undefined); setError(''); }} /></label>
    <button disabled={loading || !lot || !data.isSuccess || data.isFetching || !data.data.lots.some(l => l.lot_id === lot) || !Number.isInteger(cutoff) || cutoff < 0 || cutoff > maxCutoff} onClick={calculate}>Calculer le replay</button>
    {loading && <p role="status">Calcul summary6…</p>}{error && <p role="alert">{error}</p>}
    {result && <div aria-live="polite"><p>{result.input_count} observations · cutoff {result.through_cycle} · {result.evaluated_through}</p>
      <p>Paquet réellement calculé : {result.package_id}</p>
      <p>Pin manifeste : {result.manifest_sha256}</p>
      {result.latest.status === 'abstained' ? <p>Abstention : {result.latest.reason}. Aucune décision normale ou alerte.</p> : <p>{result.latest.alert === true ? 'Alerte process synthétique' : result.latest.alert === false ? 'Pas d’alerte process sur ce replay' : 'Aucune décision'}</p>}
      <p>Score brut : {result.latest.instant_score ?? 'indisponible'} · min3 : {result.latest.decision_score ?? 'indisponible'} · seuil : {result.latest.threshold ?? 'indisponible'}</p>
    </div>}
  </div>;
}
