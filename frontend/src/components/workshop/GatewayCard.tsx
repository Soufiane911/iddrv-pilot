import './workshopSetup.css';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import { useApi } from '../../App';
import { ApiRequestError, type Machine } from '../../lib/api';
import { EmptyPanel, formatDate, StatePanel } from '../Ui';
import { DetectedPressMappingTable } from './DetectedPressMappingTable';
import { UnmatchedEventQueue } from './UnmatchedEventQueue';

function gatewayError(error: unknown): string {
  if (error instanceof ApiRequestError) {
    const labels: Record<string, string> = {
      site_not_found: 'Ce site n’existe plus.', source_name_required: 'Le nom de la passerelle est requis.',
      source_not_found: 'Cette passerelle n’existe plus.', machine_not_in_source_site: 'Cette presse n’appartient pas à ce site.',
      source_mapping_conflict: 'Cet identifiant est déjà associé sur cette période.',
    };
    return labels[error.code] ?? error.message;
  }
  return error instanceof Error ? error.message : 'La passerelle n’a pas pu être configurée.';
}

interface GatewayCardProps {
  siteId: number;
  machines: Machine[];
  canConfigure: boolean;
}

export function GatewayCard({ siteId, machines, canConfigure }: GatewayCardProps) {
  const api = useApi();
  const cache = useQueryClient();
  const [issuedSecrets, setIssuedSecrets] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [mappingMachine, setMappingMachine] = useState<Record<string, string>>({});
  const sources = useQuery({ queryKey: ['sources', siteId], queryFn: () => api.getSources(siteId), retry: false });
  const source = useMemo(() => {
    const existing = (sources.data ?? [])[0];
    return existing ? { ...existing, secret: issuedSecrets[existing.id] } : null;
  }, [issuedSecrets, sources.data]);
  const create = useMutation({
    mutationFn: () => api.createSource(siteId),
    onSuccess: async (value) => {
      if (!value.id || !value.secret) { setError('La passerelle a été créée mais le secret unique n’a pas été retourné. Aucun faux succès n’est affiché.'); return; }
      setIssuedSecrets(current => ({ ...current, [value.id]: value.secret! }));
      setError(null);
      await cache.invalidateQueries({ queryKey: ['sources', siteId] });
      await sources.refetch();
    },
    onError: (value) => setError(gatewayError(value)),
  });
  const rotate = useMutation({
    mutationFn: () => api.createSourceCredential(source!.id),
    onSuccess: (credential) => { setIssuedSecrets(current => ({ ...current, [credential.sourceId]: credential.secret })); setError(null); },
    onError: (value) => setError(gatewayError(value)),
  });
  const detected = useQuery({
    queryKey: ['detected-machines', source?.id],
    queryFn: () => api.getDetectedMachines(source!.id),
    enabled: Boolean(source?.id && source.status === 'active'),
    refetchInterval: source ? 5000 : false,
    retry: false,
  });
  const map = useMutation({
    mutationFn: ({ externalMachineId, machineId }: { externalMachineId: string; machineId: number }) => api.createSourceMachineMapping(source!.id, { external_machine_id: externalMachineId, machine_id: machineId }),
    onSuccess: (_value, variables) => { setMappingMachine(current => ({ ...current, [variables.externalMachineId]: '' })); void detected.refetch(); void cache.invalidateQueries({ queryKey: ['machines', siteId] }); },
    onError: (value) => setError(gatewayError(value)),
  });
  const receiveUrl = `${window.location.origin}/api/v1/ingestion/cycle-events`;

  return <section className="workshop-gateway-card" aria-labelledby="gateway-card-title">
    <p className="eyebrow">SOURCE DU SITE</p>
    <h2 id="gateway-card-title">Passerelle locale</h2>
    <p>Une source authentifiée agrège les boîtiers de presses et conserve les événements avant leur rapprochement.</p>
    {sources.isPending && <StatePanel tone="loading" title="Lecture de la passerelle" text="Recherche des sources déjà configurées pour ce site." />}
    {sources.isError && <StatePanel tone="error" title="Sources indisponibles" text={gatewayError(sources.error)} action="Réessayer" onAction={() => sources.refetch()} />}
    {!sources.isPending && !sources.isError && !source ? <div className="gateway-create-actions"><button className="button-secondary" type="button" onClick={() => create.mutate()} disabled={!canConfigure || create.isPending}>{create.isPending ? 'Création…' : 'Créer la passerelle'}</button>{!canConfigure && <p className="helper-text" role="note">Configuration réservée aux superviseurs et administrateurs du site.</p>}{error && <p className="helper-error" role="alert">{error}</p>}</div> : !sources.isPending && !sources.isError && source ? <>
      <dl className="gateway-details"><div><dt>État</dt><dd>{source.status === 'active' ? 'Active' : source.status}</dd></div><div><dt>Dernière communication</dt><dd>{formatDate(source.lastSeenAt)}</dd></div><div><dt>Identifiant source</dt><dd><code>{source.id}</code></dd></div></dl>
      {source.secret ? <div className="gateway-secret" role="alert"><strong>Secret affiché une seule fois</strong><code>{source.secret}</code><p>Copiez-le dans la configuration de la passerelle. Il ne sera plus relu par IDDRV.</p><button className="button-ghost" type="button" onClick={() => rotate.mutate()} disabled={rotate.isPending}>{rotate.isPending ? 'Rotation…' : 'Générer un nouveau secret'}</button></div> : <p className="helper-text">Le secret n’est pas relu après sa création. Une rotation génère une nouvelle valeur affichée une seule fois.</p>}
      <div className="gateway-config-example"><strong>URL de réception</strong><code>{receiveUrl}</code><strong>Exemple de configuration</strong><pre>{JSON.stringify({ source_id: source.id, secret: '<copier le secret affiché ci-dessus>', endpoint: receiveUrl }, null, 2)}</pre></div>
      {detected.isPending && <StatePanel tone="loading" title="Recherche des identifiants" text="Lecture des identités émises par la passerelle." />}
      {detected.isError && <StatePanel tone="error" title="Détection indisponible" text={gatewayError(detected.error)} action="Réessayer" onAction={() => detected.refetch()} />}
      {!detected.isPending && !detected.isError && detected.data?.length === 0 && <EmptyPanel title="Aucun identifiant détecté" text="Les presses apparaîtront ici dès réception d’un événement. Aucun mapping n’est inventé." />}
      {!detected.isPending && !detected.isError && (detected.data?.length ?? 0) > 0 && <DetectedPressMappingTable items={detected.data!} machines={machines} values={mappingMachine} pending={map.isPending} onChange={(externalId, machineId) => setMappingMachine(current => ({ ...current, [externalId]: machineId }))} onMap={(externalId, machineId) => map.mutate({ externalMachineId: externalId, machineId })} />}
      {!detected.isPending && !detected.isError && (detected.data?.length ?? 0) > 0 && <UnmatchedEventQueue pendingCount={(detected.data ?? []).reduce((total, item) => total + item.pendingEvents, 0)} />}
      {error && !create.isError && <p className="helper-error" role="alert">{error}</p>}
    </> : null}
  </section>;
}
