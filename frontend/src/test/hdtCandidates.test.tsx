/// <reference types="node" />
import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { HdtCandidates } from '../components/monitoring/HdtCandidates';
import { createApiClient, type HdtCatalog } from '../lib/api';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

// Read the versioned source of truth only at test runtime. The production
// Docker build contains frontend/ alone and must not resolve models/ via tsc.
const catalog: HdtCatalog = JSON.parse(
  readFileSync(resolve(dirname(fileURLToPath(import.meta.url)), '../../../models/hdt/catalog.json'), 'utf8'),
);

function mount(getHdtCandidates: () => Promise<HdtCatalog>) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(<QueryClientProvider client={client}><HdtCandidates api={{ getHdtCandidates }} /></QueryClientProvider>);
}
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it('affiche les populations et blocages sans sélection ni gagnant', async () => {
  mount(vi.fn().mockResolvedValue(catalog));
  expect(await screen.findByText('Summary6 — recherche', { selector: 'h4' })).toBeVisible();
  expect(screen.getByText(/confirmation02 ABSENTE/)).toBeVisible();
  expect(screen.getByText(/plafond7\/50 conservé/)).toBeVisible();
  expect(screen.getAllByText(/Développement adaptatif — non confirmatoire/)).toHaveLength(2);
  expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
  expect(screen.queryByRole('button')).not.toBeInTheDocument();
  const summary = screen.getByText('Identité, contrat et preuves — Summary6 — recherche');
  await userEvent.tab(); // native summary is keyboard reachable
  await userEvent.tab();
  expect(summary).toHaveFocus();
  // jsdom does not implement Enter's native summary activation.
  await userEvent.click(summary);
  expect(summary.closest('details')).toHaveAttribute('open');
  expect(screen.getByText('hdt-summary6-d61007-s42-f70c137b944a')).toBeVisible();
});
it('chargement borné sans polling', () => {
  const request = vi.fn(() => new Promise<HdtCatalog>(() => {}));
  mount(request);
  expect(screen.getByRole('status')).toHaveTextContent('Chargement du catalogue');
  expect(request).toHaveBeenCalledTimes(1);
});
it('erreur explicite et nouvelle tentative', async () => {
  const request = vi.fn().mockRejectedValueOnce(new Error('denied')).mockResolvedValueOnce({ schema_version: 1, notice: 'Test', candidates: [] });
  mount(request);
  expect(await screen.findByRole('alert')).toHaveTextContent('Catalogue indisponible');
  await userEvent.click(screen.getByRole('button', { name: 'Réessayer' }));
  expect(await screen.findByText('Catalogue vide')).toBeVisible();
  expect(request).toHaveBeenCalledTimes(2);
});
it('contrat GET authentifié inchangé sans corps ni sélection', async () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue({ ok: true, status: 200, text: async () => JSON.stringify(catalog) } as Response);
  expect(await createApiClient('http://test/api/v1').getHdtCandidates()).toEqual(catalog);
  expect(fetchMock).toHaveBeenCalledTimes(1);
  const [url, options] = fetchMock.mock.calls[0];
  expect(url).toBe('http://test/api/v1/process-drift/candidates');
  expect(options?.credentials).toBe('include');
  expect(options?.body).toBeUndefined();
});
