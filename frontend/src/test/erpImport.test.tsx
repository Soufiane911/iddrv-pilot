import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { App } from '../App';
import { ApiRequestError, createApiClient, mockApiClient, type ERPImportPreview } from '../lib/api';

const preview: ERPImportPreview = {
  id: 'erp-1', site_id: 1, original_name: 'teams.xlsx', state: 'preview_ready', preview_version: 1,
  items: [{ source_row: 12, machine_ref: '606', order_ref: '000012', shift_number: 1, shift_started_at: '2026-09-05T03:00:00Z', good_parts: 760, produced_parts: 800, scrap_parts: 40, cycle_count: 100, change: 'created', bounds_origin: 'awaiting_context', identity_candidates: [] }],
  counts: { created: 1, revised: 0, unchanged: 0 }, new_machine_refs: ['606'], issues: [], sheets: ['RESULTAT_EQUIPE'], sheet_name: 'RESULTAT_EQUIPE', order_fields_available: [],
};

function setup(confirm = vi.fn().mockResolvedValue({ ...preview, state: 'queued' })) {
  const upload = vi.fn().mockResolvedValue({ ...preview, state: 'uploaded' });
  const getPreview = vi.fn().mockResolvedValue(preview);
  window.history.pushState({}, '', '/imports');
  render(<App api={{ ...mockApiClient, uploadERP: upload, getERPPreview: getPreview, confirmERP: confirm }} />);
  return { upload, getPreview, confirm };
}

async function uploadFile() {
  const input = await screen.findByLabelText('Fichier bilan TRS');
  const file = new File(['synthetic xlsx contents supplied to mocked API'], 'teams.xlsx', { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
  fireEvent.change(input, { target: { files: [file] } });
  fireEvent.click(screen.getByRole('button', { name: 'Téléverser et prévisualiser' }));
  await screen.findByText('000012');
  return file;
}

describe('Import TRS confirmé', () => {
  it('téléverse un vrai File, affiche les déclarations puis confirme le job', async () => {
    const { upload, getPreview, confirm } = setup();
    const file = await uploadFile();
    expect(upload).toHaveBeenCalledWith(1, file);
    expect(getPreview).toHaveBeenCalledWith('erp-1', true);
    fireEvent.click(screen.getByLabelText('Créer la presse 606'));
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer l’import' }));
    await waitFor(() => expect(confirm).toHaveBeenCalledWith('erp-1', { preview_version: 1, create_machine_refs: ['606'], replacements: [] }));
    expect(await screen.findByText(/Import en attente de traitement/)).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Historique des imports' })).toBeInTheDocument();
  });

  it('un conflit conserve l’aperçu et propose sa relecture sans simuler un succès', async () => {
    setup(vi.fn().mockRejectedValue(new ApiRequestError(409, 'Aperçu obsolète', 'preview_stale')));
    await uploadFile();
    fireEvent.click(screen.getByLabelText('Créer la presse 606'));
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer l’import' }));
    expect(await screen.findByRole('button', { name: 'Relire l’aperçu' })).toBeInTheDocument();
    expect(screen.getByText('000012')).toBeInTheDocument();
    expect(screen.queryByText(/Import terminé/)).not.toBeInTheDocument();
  });
});

it('affiche la limite de taille sans présenter une erreur HTML comme un succès', async () => {
  window.history.pushState({}, '', '/imports');
  render(<App api={{ ...mockApiClient, uploadERP: vi.fn().mockRejectedValue(new ApiRequestError(413, '<html>too large</html>', 'http_413')) }} />);
  const input = await screen.findByLabelText('Fichier bilan TRS');
  fireEvent.change(input, { target: { files: [new File(['x'], 'large.xlsx')] } });
  fireEvent.click(screen.getByRole('button', { name: 'Téléverser et prévisualiser' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('20 Mio compressés');
  expect(screen.queryByText(/Import terminé/)).not.toBeInTheDocument();
});


it('sépare la lecture GET du profilage POST dans le client HTTP', async () => {
  const fetch = vi.spyOn(globalThis, 'fetch').mockImplementation(async () => new Response(JSON.stringify(preview), { status: 200, headers: { 'Content-Type': 'application/json' } }));
  try {
    const api = createApiClient();
    await api.getERPPreview('erp-1');
    await api.getERPPreview('erp-1', true);
    expect(fetch.mock.calls[0][0]).toMatch(/\/erp-imports\/erp-1\/preview$/);
    expect(fetch.mock.calls[0][1]?.method).toBe('GET');
    expect(fetch.mock.calls[1][0]).toMatch(/\/erp-imports\/erp-1\/preview\/refresh$/);
    expect(fetch.mock.calls[1][1]?.method).toBe('POST');
  } finally { fetch.mockRestore(); }
});

it('un viewer consulte un fichier non profilé sans action de préparation', async () => {
  const uploaded = { ...preview, state: 'uploaded' as const, preview_version: 0, items: [], counts: { created: 0, revised: 0, unchanged: 0 } };
  const read = vi.fn().mockResolvedValue(uploaded);
  window.history.pushState({}, '', '/imports');
  render(<App api={{ ...mockApiClient,
    getCurrentUser: async () => ({ id: 'viewer', email: 'viewer@example.test', role: 'viewer', siteIds: [1], siteRoles: { 1: 'viewer' } }),
    getERPImports: async () => [uploaded], getERPPreview: read }} />);
  fireEvent.click(await screen.findByRole('button', { name: 'teams.xlsx' }));
  expect(await screen.findByText(/L’aperçu n’est pas encore préparé/)).toBeInTheDocument();
  expect(read).toHaveBeenCalledExactlyOnceWith('erp-1');
  expect(screen.queryByRole('button', { name: 'Relire l’aperçu' })).not.toBeInTheDocument();
  expect(screen.queryByLabelText('Fichier bilan TRS')).not.toBeInTheDocument();
});
