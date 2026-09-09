import './workshopSetup.css';
import { AccessibleDialog } from '../AccessibleDialog';
import { useEffect, useRef, useState, type FormEvent } from 'react';
import { useMutation } from '@tanstack/react-query';
import type { ApiClient, Machine } from '../../lib/api';
import { ApiRequestError } from '../../lib/api';

interface PressFormDrawerProps {
  api: ApiClient;
  siteId: number;
  open: boolean;
  machine?: Machine | null;
  onClose: () => void;
  onSaved: () => void;
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiRequestError) {
    if (error.code === 'workshop_code_already_exists') return 'Ce code atelier existe déjà sur ce site.';
    if (error.code === 'machine_erp_ref_already_exists') return 'Cette référence ERP est déjà utilisée par une autre presse de ce site.';
    if (error.code === 'machine_identity_already_exists' || error.code === 'machine_ref_already_exists') return 'Cette identité presse existe déjà sur ce site.';
    return error.message;
  }
  return error instanceof Error ? error.message : 'Impossible d’enregistrer la presse.';
}

export function PressFormDrawer({ api, siteId, open, machine = null, onClose, onSaved }: PressFormDrawerProps) {
  const [name, setName] = useState('');
  const [workshopCode, setWorkshopCode] = useState('');
  const [erpRef, setErpRef] = useState('');
  const [brand, setBrand] = useState('');
  const [model, setModel] = useState('');
  const [validationError, setValidationError] = useState<string | null>(null);
  const nameRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (!open) return;
    setName(machine?.name ?? '');
    setWorkshopCode(machine?.workshopCode ?? '');
    setErpRef(machine?.erpRef ?? '');
    setBrand(machine?.brand ?? '');
    setModel(machine?.model ?? '');
    setValidationError(null);
  }, [machine, open]);
  const create = useMutation({
    mutationFn: () => {
      const input = { name: name.trim(), workshop_code: workshopCode.trim(), erp_ref: erpRef.trim() || null, brand: brand.trim() || null, model: model.trim() || null };
      return machine ? api.updateMachine(machine.id, input) : api.createMachine(siteId, input);
    },
    onSuccess: () => {
      setName(''); setWorkshopCode(''); setErpRef(''); setBrand(''); setModel(''); setValidationError(null);
      onSaved();
    },
    onError: (error) => setValidationError(errorMessage(error)),
  });

  if (!open) return null;
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setValidationError(null);
    if (!name.trim()) { setValidationError('Le nom de la presse est requis.'); return; }
    if (!workshopCode.trim()) { setValidationError('Le code atelier est requis.'); return; }
    create.mutate();
  }
  function close() {
    if (create.isPending) return;
    setValidationError(null);
    onClose();
  }
  const editing = Boolean(machine);
  return <AccessibleDialog className="workshop-form-drawer" labelledBy="press-form-title" describedBy="press-form-description" onClose={close} busy={create.isPending}>
      <header><div><p className="eyebrow">PARC MACHINE</p><h2 id="press-form-title">{editing ? 'Modifier la presse' : 'Ajouter une presse'}</h2></div><button className="button-secondary" type="button" onClick={close} disabled={create.isPending}>Fermer</button></header>
      <p className="muted" id="press-form-description">{editing ? 'Modifiez l’identité atelier ou associez la référence ERP à cette presse. La référence ERP est unique dans le site.' : 'La presse est créée immédiatement dans le catalogue. Son mapping source pourra être fait plus tard.'} Appuyez sur Échap pour fermer.</p>
      <form onSubmit={submit}>
        <label htmlFor="press-name">Nom de la presse</label><input ref={nameRef} id="press-name" aria-invalid={validationError && !name.trim() ? true : undefined} aria-describedby={validationError ? 'press-form-error' : undefined} value={name} onChange={(event) => setName(event.target.value)} required maxLength={100} placeholder="Ex. Presse 606" />
        <label htmlFor="press-workshop-code">Code atelier</label><input id="press-workshop-code" aria-invalid={validationError && (!workshopCode.trim() || create.error instanceof ApiRequestError && create.error.code === 'workshop_code_already_exists') ? true : undefined} aria-describedby={validationError ? 'press-code-hint press-form-error' : 'press-code-hint'} value={workshopCode} onChange={(event) => setWorkshopCode(event.target.value)} required maxLength={50} placeholder="Ex. P-606" />
        <p id="press-code-hint" className="helper-text">Ce code est unique dans le site et ne remplace pas la référence ERP.</p>
        <label htmlFor="press-erp-ref">Référence ERP (facultative)</label><input id="press-erp-ref" aria-invalid={create.error instanceof ApiRequestError && create.error.code === 'machine_erp_ref_already_exists' ? true : undefined} aria-describedby={validationError ? 'press-form-error' : undefined} value={erpRef} onChange={(event) => setErpRef(event.target.value)} maxLength={50} />
        <label htmlFor="press-brand">Marque (facultative)</label><input id="press-brand" value={brand} onChange={(event) => setBrand(event.target.value)} maxLength={50} />
        <label htmlFor="press-model">Modèle (facultatif)</label><input id="press-model" value={model} onChange={(event) => setModel(event.target.value)} maxLength={100} />
        {create.isPending && <p role="status">Enregistrement de la presse…</p>}
        {validationError && <p id="press-form-error" className="helper-error" role="alert">{validationError}</p>}
        <div className="workshop-form-actions"><button className="button-secondary" type="button" onClick={close} disabled={create.isPending}>Annuler</button><button className="button-primary" type="submit" disabled={create.isPending}>{create.isPending ? 'Enregistrement…' : editing ? 'Enregistrer les modifications' : 'Ajouter la presse'}</button></div>
      </form>
    </AccessibleDialog>;
}
