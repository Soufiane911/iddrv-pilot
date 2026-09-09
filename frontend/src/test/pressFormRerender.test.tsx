import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, vi } from 'vitest';
import { PressFormDrawer } from '../components/workshop/PressFormDrawer';
import { mockApiClient, type ApiClient, type Machine } from '../lib/api';

function setupDrawer() {
  const machine: Machine = { id: 8, siteId: 2, name: 'Presse sans ERP', workshopCode: 'P-608', erpRef: null, brand: 'Marque', model: 'Modèle', status: 'offline' };
  const updateMachine = vi.fn<ApiClient['updateMachine']>().mockResolvedValue(machine);
  const createMachine = vi.fn<ApiClient['createMachine']>();
  const api: ApiClient = { ...mockApiClient, updateMachine, createMachine };
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false, gcTime: 0 } } });
  const onSaved = vi.fn();
  const originalClose = vi.fn();
  const currentClose = vi.fn();
  // All props and the provider remain identical except the onClose function.
  const drawer = (onClose: () => void) => <QueryClientProvider client={client}><PressFormDrawer api={api} siteId={2} open machine={machine} onClose={onClose} onSaved={onSaved} /></QueryClientProvider>;
  const view = render(drawer(originalClose));
  return { updateMachine, createMachine, onSaved, originalClose, currentClose, replaceClose: () => view.rerender(drawer(currentClose)) };
}

test.each([false, true])('conserve les valeurs, le focus et le payload après changement de onClose (saisie poursuivie : %s)', async (continueTyping) => {
  const user = userEvent.setup();
  const { replaceClose, updateMachine, createMachine, onSaved } = setupDrawer();
  const name = screen.getByLabelText('Nom de la presse');
  const erp = screen.getByLabelText('Référence ERP (facultative)');
  expect(name).toHaveFocus();
  await user.type(erp, continueTyping ? 'ERP' : 'ERP-608');
  expect(erp).toHaveFocus();
  expect(erp).toHaveValue(continueTyping ? 'ERP' : 'ERP-608');

  replaceClose();

  // Soft assertions retain all diagnostics on the old implementation, including
  // its actual save payload; none of these expectations is optional.
  expect.soft(erp).toHaveFocus();
  expect.soft(erp).toHaveValue(continueTyping ? 'ERP' : 'ERP-608');
  expect.soft(name).toHaveValue('Presse sans ERP');
  expect.soft(screen.getByLabelText('Code atelier')).toHaveValue('P-608');
  expect.soft(screen.getByLabelText('Marque (facultative)')).toHaveValue('Marque');
  expect.soft(screen.getByLabelText('Modèle (facultatif)')).toHaveValue('Modèle');
  // keyboard deliberately does not click/refocus ERP, unlike user.type.
  if (continueTyping) await user.keyboard('-608');
  expect.soft(erp).toHaveValue('ERP-608');
  expect.soft(name).toHaveValue('Presse sans ERP');
  await user.click(screen.getByRole('button', { name: 'Enregistrer les modifications' }));
  await waitFor(() => expect(updateMachine).toHaveBeenCalledTimes(1));
  expect.soft(updateMachine).toHaveBeenCalledWith(8, { name: 'Presse sans ERP', workshop_code: 'P-608', erp_ref: 'ERP-608', brand: 'Marque', model: 'Modèle' });
  expect(createMachine).not.toHaveBeenCalled();
  await waitFor(() => expect(onSaved).toHaveBeenCalledTimes(1));
});

test('Échap utilise le callback onClose courant après le rerender', async () => {
  const user = userEvent.setup();
  const { replaceClose, originalClose, currentClose, updateMachine } = setupDrawer();
  await user.click(screen.getByLabelText('Référence ERP (facultative)'));
  replaceClose();
  await user.keyboard('{Escape}');
  expect(currentClose).toHaveBeenCalledTimes(1);
  expect(originalClose).not.toHaveBeenCalled();
  expect(updateMachine).not.toHaveBeenCalled();
});
