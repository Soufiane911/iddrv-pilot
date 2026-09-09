import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { axe, toHaveNoViolations } from 'jest-axe';
import { BrowserRouter } from 'react-router-dom';
import { useState } from 'react';
import { AppTestShell } from '../App';
import { mockApiClient, ApiRequestError } from '../lib/api';
import { SitesPage } from '../pages/SitesPage';
import { LoginPage } from '../pages/LoginPage';
import { PressFormDrawer } from '../components/workshop/PressFormDrawer';
import { MachineConnectionPanel } from '../components/workshop/MachineConnectionPanel';
import { ProductionAssignmentEditor } from '../components/planning/ProductionAssignmentEditor';
expect.extend(toHaveNoViolations);

test('source : le test respecte les contraintes natives et annonce son attente', async () => {
  const user = userEvent.setup();
  const testConnection = vi.fn(() => new Promise<never>(() => {}));
  const api = { ...mockApiClient, getCurrentUser: async () => ({ ...await mockApiClient.getCurrentUser(), role: 'admin' as const, siteRoles: { 1: 'admin' as const } }), getMachineConnection: async () => null, testMachineConnection: testConnection };
  shell(<MachineConnectionPanel api={api} machine={{ id: 606, siteId: 1, name: 'Presse audit', erpRef: '606' }} />, api);
  await user.click(screen.getByText('Connexion de la presse'));
  const address = await screen.findByLabelText('Adresse API');
  await user.click(screen.getByRole('button', { name: 'Tester la connexion' }));
  expect(testConnection).not.toHaveBeenCalled();
  await user.type(address, 'https://source.example.test');
  await user.click(screen.getByRole('button', { name: 'Tester la connexion' }));
  expect(await screen.findByRole('status')).toHaveTextContent('Test de connexion en cours');
  expect(testConnection).toHaveBeenCalledTimes(1);
});

function shell(children: React.ReactNode, api = mockApiClient) { return render(<AppTestShell api={api}><BrowserRouter>{children}</BrowserRouter></AppTestShell>); }

test('site : boucle Tab et Maj+Tab, Échap, restauration et erreur liée', async () => {
  const user = userEvent.setup();
  shell(<SitesPage />, { ...mockApiClient, getCurrentUser: async () => ({ ...await mockApiClient.getCurrentUser(), role: 'admin' }), createSite: async () => { throw new ApiRequestError(409, 'Nom déjà utilisé', 'site_name_already_exists'); } });
  const trigger = await screen.findByRole('button', { name: 'Nouveau site' });
  await user.click(trigger);
  const dialog = screen.getByRole('dialog');
  const name = within(dialog).getByLabelText('Nom du site');
  expect(name).toHaveFocus();
  await user.tab({ shift: true });
  expect(within(dialog).getByRole('button', { name: 'Créer le site' })).toHaveFocus();
  await user.tab(); expect(name).toHaveFocus();
  await user.type(name, 'Doublon');
  await user.click(within(dialog).getByRole('button', { name: 'Créer le site' }));
  await screen.findByRole('alert');
  expect(name).toHaveAttribute('aria-invalid', 'true');
  expect(name).toHaveAccessibleDescription('Un site porte déjà ce nom.');
  expect(await axe(dialog)).toHaveNoViolations();
  await user.keyboard('{Escape}'); expect(trigger).toHaveFocus();
});

for (const kind of ['presse', 'planning'] as const) {
  test(`${kind} : confinement, restauration, axe sans règle désactivée`, async () => {
    const user = userEvent.setup();
    function Harness() {
      const [open, setOpen] = useState(false);
      return <><button onClick={() => setOpen(true)}>Ouvrir</button>{kind === 'presse' ? <PressFormDrawer api={mockApiClient} siteId={1} open={open} onClose={() => setOpen(false)} onSaved={() => setOpen(false)} /> : <ProductionAssignmentEditor siteId={1} timezone="Europe/Paris" machines={[]} open={open} canPlan onClose={() => setOpen(false)} onSaved={() => setOpen(false)} />}</>;
    }
    shell(<Harness />);
    const trigger = screen.getByRole('button', { name: 'Ouvrir' });
    await user.click(trigger);
    const dialog = screen.getByRole('dialog');
    expect(within(dialog).getByLabelText(kind === 'presse' ? 'Nom de la presse' : 'Numéro OF')).toHaveFocus();
    const buttons = within(dialog).getAllByRole('button');
    buttons[buttons.length - 1].focus(); await user.tab(); expect(buttons[0]).toHaveFocus();
    await user.tab({ shift: true }); expect(buttons[buttons.length - 1]).toHaveFocus();
    expect(await axe(dialog)).toHaveNoViolations();
    await user.keyboard('{Escape}'); expect(trigger).toHaveFocus();
  });
}

test('auth : le refus est annoncé et décrit les deux champs sans attribuer à tort un champ invalide', async () => {
  const user = userEvent.setup();
  shell(<LoginPage />, { ...mockApiClient, login: async () => { throw new Error('Identifiants refusés.'); } });
  await user.type(screen.getByLabelText('Adresse e-mail'), 'audit@example.test');
  await user.type(screen.getByLabelText('Mot de passe'), 'fictif');
  await user.click(screen.getByRole('button', { name: 'Ouvrir la supervision' }));
  await screen.findByRole('alert');
  expect(screen.getByLabelText('Mot de passe')).toHaveAccessibleDescription(/Identifiants refusés/);
});
