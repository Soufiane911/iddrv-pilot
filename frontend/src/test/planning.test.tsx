import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { AppTestShell } from '../App';
import { mockApiClient, type ApiClient, type PlanningSlot } from '../lib/api';
import { ProductionPlanningPage } from '../pages/ProductionPlanningPage';
import { vi } from 'vitest';

const slot: PlanningSlot = { id: 'slot-1', siteId: 2, allocationId: 'allocation-1', machineId: 10, machineName: 'Presse A', machineErpRef: '006', workOrderId: 'order-1', orderNumber: '000123', startsAt: '2026-09-07T08:00:00Z', endsAt: '2026-09-07T10:00:00Z', status: 'planned', planningStatus: 'planned', collectionStatus: 'no_cycle', erpStatus: 'pending', rowVersion: 1, cyclesReceived: 0 };

function renderPlanning(api: ApiClient) {
  return render(<AppTestShell api={api}><MemoryRouter initialEntries={['/sites/2/planning?week=2026-W37']}><Routes><Route path="/sites/:siteId/planning" element={<ProductionPlanningPage />} /></Routes></MemoryRouter></AppTestShell>);
}

test('affiche les états planning, collecte et ERP séparément sans inventer la quantité', async () => {
  const api: ApiClient = { ...mockApiClient, getCurrentUser: async () => ({ id: 'u', email: 'supervisor@test', role: 'supervisor', siteIds: [2], siteRoles: { 2: 'supervisor' } }), getSite: async () => ({ id: 2, name: 'Atelier', timezone: 'Europe/Paris' }), getMachines: async () => [], getPlanning: async () => ({ siteId: 2, timezone: 'Europe/Paris', weekStart: '2026-09-07', weekEnd: '2026-09-14', items: [slot] }) };
  renderPlanning(api);
  expect(await screen.findByText('Planifié')).toBeInTheDocument();
  expect(screen.getAllByText('Aucun cycle').length).toBeGreaterThan(1);
  expect(screen.getByText('En attente ERP')).toBeInTheDocument();
  expect(screen.queryByText(/quantité.*0/i)).not.toBeInTheDocument();
});

test('conserve les zéros initiaux et permet le même OF sur deux presses', async () => {
  const user = userEvent.setup();
  const createWorkOrder = vi.fn(async () => ({ id: 'order-2', siteId: 2, orderNumber: '000123', allocations: [] }));
  const api: ApiClient = { ...mockApiClient, getCurrentUser: async () => ({ id: 'u', email: 'supervisor@test', role: 'supervisor', siteIds: [2], siteRoles: { 2: 'supervisor' } }), getSite: async () => ({ id: 2, name: 'Atelier', timezone: 'Europe/Paris' }), getMachines: async () => [{ id: 10, siteId: 2, name: 'Presse A', workshopCode: 'A' }, { id: 11, siteId: 2, name: 'Presse B', workshopCode: 'B' }], getPlanning: async () => ({ siteId: 2, timezone: 'Europe/Paris', weekStart: '2026-09-07', weekEnd: '2026-09-14', items: [] }), createWorkOrder };
  renderPlanning(api);
  await user.click(await screen.findByRole('button', { name: 'Planifier un OF' }));
  await user.type(screen.getByLabelText('Numéro OF'), '000123');
  const starts = screen.getAllByLabelText('Début prévu');
  fireEvent.change(starts[0], { target: { value: '2026-09-07T08:00' } });
  fireEvent.change(screen.getAllByLabelText('Fin prévue')[0], { target: { value: '2026-09-07T10:00' } });
  await user.click(screen.getByRole('button', { name: 'Ajouter une presse au même OF' }));
  const pressFields = screen.getAllByLabelText('Presse').slice(-2);
  expect(pressFields).toHaveLength(2);
  await user.selectOptions(pressFields[1], '11');
  fireEvent.change(screen.getAllByLabelText('Début prévu')[1], { target: { value: '2026-09-07T08:00' } });
  fireEvent.change(screen.getAllByLabelText('Fin prévue')[1], { target: { value: '2026-09-07T10:00' } });
  await user.click(screen.getByRole('button', { name: 'Planifier l’OF' }));
  await waitFor(() => expect(createWorkOrder).toHaveBeenCalledWith(2, expect.objectContaining({ order_number: '000123', allocations: expect.arrayContaining([expect.objectContaining({ machine_id: 10 }), expect.objectContaining({ machine_id: 11 })]) })));
});
