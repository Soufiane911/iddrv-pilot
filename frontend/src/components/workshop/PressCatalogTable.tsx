import './workshopSetup.css';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useApi } from '../../App';
import { ApiRequestError, type Machine } from '../../lib/api';
import { formatDate, StatusBadge } from '../Ui';

interface PressCatalogTableProps {
  machines: Machine[];
  canConfigure: boolean;
  onAddPress: () => void;
  onEditPress: (machine: Machine) => void;
}

export function PressCatalogTable({ machines, canConfigure, onAddPress, onEditPress }: PressCatalogTableProps) {
  const api = useApi();
  const cache = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const archive = useMutation({ mutationFn: (machineId: number) => api.archiveMachine(machineId), onSuccess: () => { setError(null); void cache.invalidateQueries({ queryKey: ['machines'] }); }, onError: (value) => setError(value instanceof ApiRequestError ? value.message : value instanceof Error ? value.message : 'Impossible d’archiver la presse.') });
  function archivePress(machine: Machine) { if (window.confirm(`Archiver ${machine.name} ? Son historique sera conservé.`)) { setError(null); archive.mutate(machine.id); } }
  return <section className="workshop-catalog-card" aria-labelledby="press-catalog-title">
    <header>
      <div><p className="eyebrow">PARC MACHINE</p><h2 id="press-catalog-title">Catalogue des presses</h2><p>{machines.length === 0 ? 'Aucune presse n’est encore déclarée pour ce site.' : `${machines.length} presse${machines.length > 1 ? 's' : ''} déclarée${machines.length > 1 ? 's' : ''}.`}</p></div>
      <button className="button-secondary" type="button" onClick={onAddPress} disabled={!canConfigure}>Ajouter une presse</button>
    </header>
    {error && <p className="helper-error" role="alert">{error}</p>}
    {machines.length === 0 ? <p className="workshop-catalog-empty">Le code atelier est obligatoire. La référence ERP, la marque et le modèle restent facultatifs.</p> : <div className="incident-table-wrap"><table className="workshop-catalog-table"><caption className="visually-hidden">Presses du site</caption><thead><tr><th>Presse</th><th>Code atelier</th><th>ERP</th><th>État</th><th>Cycle récent</th><th>Action</th></tr></thead><tbody>{machines.map((machine) => { const archived = machine.lifecycleStatus === 'archived'; return <tr key={machine.id}><td><strong>{machine.name}</strong>{machine.brand || machine.model ? <small>{[machine.brand, machine.model].filter(Boolean).join(' · ')}</small> : null}</td><td>{machine.workshopCode ?? 'N/D'}</td><td>{machine.erpRef ?? 'N/D'}</td><td><StatusBadge value={archived ? 'archived' : machine.status} /></td><td>{formatDate(machine.lastCycleAt)}</td><td>{archived ? <span className="muted">Archivée · historique conservé</span> : canConfigure ? <div className="workshop-catalog-actions"><button className="button-ghost" type="button" onClick={() => onEditPress(machine)}>Modifier</button><button className="button-ghost" type="button" onClick={() => archivePress(machine)} disabled={archive.isPending}>Archiver</button></div> : 'Lecture seule'}</td></tr>; })}</tbody></table></div>}
  </section>;
}
