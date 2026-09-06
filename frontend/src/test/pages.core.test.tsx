import { describe, it, expect, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { App } from '../App';
import { mockApiClient, ApiRequestError } from '../lib/api';

/* ------------------------------------------------------------------ */
/*  Helper : monte l’application complète sur une route donnée          */
/* ------------------------------------------------------------------ */

function renderApp(api = mockApiClient, route = '/') {
  window.history.pushState({}, '', route);
  return render(<App api={api} />);
}

const mockSite = {
  id: 1,
  name: 'Usine Principale',
  timezone: 'Europe/Paris',
  status: 'online' as const,
  machineCount: 5,
  openIncidentCount: 1,
  lastImportAt: '2025-02-12T10:00:00Z',
};

const mockIncident = {
  id: 'inc-1',
  site_id: 1,
  machine_id: 2,
  status: 'open' as const,
  severity: 'high' as const,
  symptom: 'short_shot_increase',
  started_at: '2025-02-12T08:00:00Z',
  created_at: '2025-02-12T08:00:00Z',
  data_cutoff: '2025-02-12T09:00:00Z',
  machine_erp_ref: '152',
};

const mockImport = {
  id: 'imp-1',
  fileName: 'cycles.csv',
  parserType: 'csv',
  status: 'completed' as const,
  importedAt: '2025-02-12T10:00:00Z',
  rowCountTotal: 1000,
  rowCountAccepted: 980,
  rowCountRejected: 20,
};

/* ------------------------------------------------------------------ */
/*  LoginPage                                                          */
/* ------------------------------------------------------------------ */

describe('LoginPage', () => {
  it('affiche le formulaire de connexion avec les champs requis', async () => {
    renderApp({ ...mockApiClient, getCurrentUser: async () => { throw new ApiRequestError(401, 'Session expirée.', 'session_revoked'); } }, '/login');
    expect(await screen.findByRole('heading', { name: /Reprendre la supervision/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/Adresse e-mail/i)).toBeRequired();
    expect(screen.getByLabelText(/Mot de passe/i)).toBeRequired();
    expect(screen.getByRole('button', { name: /Ouvrir la supervision/i })).toBeInTheDocument();
  });

  it('soumet les identifiants et appelle la mutation de connexion', async () => {
    const login = vi.fn().mockResolvedValue({
      user: { id: 'u1', email: 'test@test.local', role: 'analyst' as const, siteIds: [1], siteRoles: { 1: 'analyst' as const } },
      expiresAt: '2025-02-12T12:00:00Z',
    });

    renderApp({ ...mockApiClient, getCurrentUser: async () => { throw new ApiRequestError(401, 'Session expirée.', 'session_revoked'); }, login }, '/login');

    fireEvent.change(screen.getByLabelText(/Adresse e-mail/i), { target: { value: 'test@test.local' } });
    fireEvent.change(screen.getByLabelText(/Mot de passe/i), { target: { value: 'secret123' } });
    fireEvent.click(screen.getByRole('button', { name: /Ouvrir la supervision/i }));

    await waitFor(() => expect(login).toHaveBeenCalledWith('test@test.local', 'secret123'));
  });

  it('redirige vers la page cible après une connexion réussie', async () => {
    const login = vi.fn().mockResolvedValue({
      user: { id: 'u1', email: 'a@b.local', role: 'analyst' as const, siteIds: [1], siteRoles: { 1: 'analyst' as const } },
      expiresAt: '2025-02-12T12:00:00Z',
    });

    renderApp({ ...mockApiClient, getCurrentUser: async () => { throw new ApiRequestError(401, 'Session expirée.', 'session_revoked'); }, login }, '/login');

    fireEvent.change(screen.getByLabelText(/Adresse e-mail/i), { target: { value: 'a@b.local' } });
    fireEvent.change(screen.getByLabelText(/Mot de passe/i), { target: { value: 'pass' } });
    fireEvent.click(screen.getByRole('button', { name: /Ouvrir la supervision/i }));

    await waitFor(() => expect(screen.getByRole('heading', { name: /Vue d’ensemble/i, level: 2 })).toBeInTheDocument());
  });

  it('affiche un message d’erreur lorsque la connexion échoue', async () => {
    const login = vi.fn().mockRejectedValue(new ApiRequestError(401, 'Identifiants invalides.', 'auth_failed'));

    renderApp({ ...mockApiClient, getCurrentUser: async () => { throw new ApiRequestError(401, 'Session expirée.', 'session_revoked'); }, login }, '/login');

    fireEvent.change(screen.getByLabelText(/Adresse e-mail/i), { target: { value: 'bad@user.local' } });
    fireEvent.change(screen.getByLabelText(/Mot de passe/i), { target: { value: 'wrong' } });
    fireEvent.click(screen.getByRole('button', { name: /Ouvrir la supervision/i }));

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent(/Connexion refusée/i);
    expect(alert).toHaveTextContent(/Identifiants invalides/i);
  });

  it('désactive le bouton de soumission pendant la connexion', async () => {
    const login = vi.fn().mockImplementation(() => new Promise((resolve) => setTimeout(resolve, 500)));

    renderApp({ ...mockApiClient, getCurrentUser: async () => { throw new ApiRequestError(401, 'Session expirée.', 'session_revoked'); }, login }, '/login');

    fireEvent.change(screen.getByLabelText(/Adresse e-mail/i), { target: { value: 'x@y.local' } });
    fireEvent.change(screen.getByLabelText(/Mot de passe/i), { target: { value: 'wait' } });
    fireEvent.click(screen.getByRole('button', { name: /Ouvrir la supervision/i }));

    await waitFor(() => expect(screen.getByRole('button', { name: /Connexion…/i })).toBeDisabled());
  });
});

/* ------------------------------------------------------------------ */
/*  OverviewPage                                                       */
/* ------------------------------------------------------------------ */

describe('OverviewPage', () => {
  it('affiche l’état de chargement initial', async () => {
    const getSites = vi.fn().mockImplementation(() => new Promise(() => {}));
    const getIncidents = vi.fn().mockImplementation(() => new Promise(() => {}));

    renderApp({ ...mockApiClient, getSites, getIncidents }, '/overview');
    expect(await screen.findByText(/Préparation de la vue d’ensemble/i)).toBeInTheDocument();
  });

  it('affiche les indicateurs, sites, incidents et imports après chargement', async () => {
    renderApp({
      ...mockApiClient,
      getSites: async () => [mockSite],
      getIncidents: async () => [mockIncident],
      getImports: async () => [mockImport],
    }, '/overview');

    expect(await screen.findByRole('heading', { name: /Vue d’ensemble/i, level: 2 })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Sites industriels/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Incidents prioritaires/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Dernières données/i })).toBeInTheDocument();
    expect(screen.getByText('Usine Principale')).toBeInTheDocument();
    expect(screen.getByText(/Hausse des pièces incomplètes/i)).toBeInTheDocument();
  });

  it('affiche une erreur quand le périmètre sites est indisponible', async () => {
    renderApp({
      ...mockApiClient,
      getSites: async () => { throw new ApiRequestError(500, 'Service indisponible', 'server_error'); },
      getIncidents: async () => [mockIncident],
      getImports: async () => [mockImport],
    }, '/overview');

    const alert = await screen.findByRole('alert', {}, { timeout: 3000 });
    expect(alert).toHaveTextContent(/Sites indisponibles/i);
    expect(screen.getByText(/Impossible de charger le périmètre/i)).toBeInTheDocument();
  });

  it('calcule et affiche les métriques consolidées', async () => {
    renderApp({
      ...mockApiClient,
      getSites: async () => [mockSite],
      getIncidents: async () => [mockIncident],
      getImports: async () => [mockImport],
    }, '/overview');

    await screen.findByRole('heading', { name: /Vue d’ensemble/i, level: 2 });
    const ledger = screen.getByLabelText(/Indicateurs principaux/i);
    expect(within(ledger).getByText('01')).toBeInTheDocument();
    expect(within(ledger).getByText('5')).toBeInTheDocument();
    expect(within(ledger).getAllByText('1').length).toBeGreaterThanOrEqual(2);
  });

  it('propose des liens de navigation vers les sections détaillées', async () => {
    renderApp({
      ...mockApiClient,
      getSites: async () => [mockSite],
      getIncidents: async () => [mockIncident],
      getImports: async () => [mockImport],
    }, '/overview');

    await screen.findByRole('heading', { name: /Vue d’ensemble/i, level: 2 });
    expect(screen.getByRole('link', { name: /Voir tous les sites/i })).toHaveAttribute('href', '/sites');
    expect(screen.getByRole('link', { name: /Ouvrir la file/i })).toHaveAttribute('href', '/incidents');
    expect(screen.getByRole('link', { name: /Journal complet/i })).toHaveAttribute('href', '/imports');
  });
});

/* ------------------------------------------------------------------ */
/*  SitesPage                                                          */
/* ------------------------------------------------------------------ */

describe('SitesPage', () => {
  it('affiche l’état de chargement des sites', async () => {
    const getSites = vi.fn().mockImplementation(() => new Promise(() => {}));
    renderApp({ ...mockApiClient, getSites }, '/sites');
    expect(await screen.findByText(/Chargement des sites/i)).toBeInTheDocument();
  });

  it('affiche les cartes de site avec statistiques et statut', async () => {
    renderApp({ ...mockApiClient, getSites: async () => [mockSite] }, '/sites');

    expect(await screen.findByRole('heading', { name: /Vos ateliers/i })).toBeInTheDocument();
    expect(await screen.findByText('Usine Principale')).toBeInTheDocument();
    expect(screen.getAllByText('5').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('presses')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Ouvrir l’atelier/i })).toBeInTheDocument();
  });

  it('affiche une erreur quand le catalogue est indisponible', async () => {
    renderApp({
      ...mockApiClient,
      getSites: async () => { throw new ApiRequestError(503, 'Catalogue indisponible', 'unavailable'); },
    }, '/sites');

    const alert = await screen.findByRole('alert', {}, { timeout: 3000 });
    expect(alert).toHaveTextContent(/Catalogue indisponible/i);
    expect(screen.getByRole('button', { name: /Réessayer/i })).toBeInTheDocument();
  });

  it('affiche un panel vide quand aucun site n’est configuré', async () => {
    renderApp({ ...mockApiClient, getSites: async () => [] }, '/sites');

    expect(await screen.findByText(/Aucun site configuré/i)).toBeInTheDocument();
    expect(screen.getByText(/Ajoutez un site côté API pour commencer/i)).toBeInTheDocument();
  });

  it('permet de naviguer vers l’atelier depuis une carte de site', async () => {
    renderApp({ ...mockApiClient, getSites: async () => [mockSite] }, '/sites');

    await screen.findByRole('heading', { name: /Vos ateliers/i });
    const button = await screen.findByRole('button', { name: /Ouvrir l’atelier/i });
    fireEvent.click(button);
    await waitFor(() => expect(screen.getByRole('heading', { name: /État des presses/i })).toBeInTheDocument());
  });
});

/* ------------------------------------------------------------------ */
/*  ImportsPage                                                        */
/* ------------------------------------------------------------------ */

describe('ImportsPage', () => {
  it('affiche l’état de chargement du journal', async () => {
    const getImports = vi.fn().mockImplementation(() => new Promise(() => {}));
    renderApp({ ...mockApiClient, getImports }, '/imports');
    expect(await screen.findByText(/Chargement du journal/i)).toBeInTheDocument();
  });

  it('affiche le tableau des traitements d’import', async () => {
    renderApp({ ...mockApiClient, getImports: async () => [mockImport] }, '/imports');

    expect(await screen.findByRole('heading', { name: /Historique des imports/i })).toBeInTheDocument();
    expect(await screen.findByText('cycles.csv')).toBeInTheDocument();
    expect(screen.getByText('Terminé')).toBeInTheDocument();
    expect(screen.getByRole('table')).toBeInTheDocument();
  });

  it('affiche une erreur quand le journal est indisponible', async () => {
    renderApp({
      ...mockApiClient,
      getImports: async () => { throw new ApiRequestError(500, 'Journal inaccessible', 'db_error'); },
    }, '/imports');

    const alert = await screen.findByRole('alert', {}, { timeout: 3000 });
    expect(alert).toHaveTextContent(/Journal indisponible/i);
    expect(screen.getByRole('button', { name: /Réessayer/i })).toBeInTheDocument();
  });

  it('affiche un panel vide quand il n’y a aucun import', async () => {
    renderApp({ ...mockApiClient, getImports: async () => [] }, '/imports');

    expect(await screen.findByText(/Aucun bilan téléversé pour ce site/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Téléverser et prévisualiser' })).toBeInTheDocument();
  });

  it('permet de rafraîchir la liste des imports', async () => {
    const getImports = vi.fn().mockResolvedValue([mockImport]);
    renderApp({ ...mockApiClient, getImports }, '/imports');

    await screen.findByRole('heading', { name: /Historique des imports/i });
    expect(getImports).toHaveBeenCalledTimes(1);
    const refreshButton = await screen.findByRole('button', { name: /Actualiser/i });
    fireEvent.click(refreshButton);
    await waitFor(() => expect(getImports).toHaveBeenCalledTimes(2));
  });
});
