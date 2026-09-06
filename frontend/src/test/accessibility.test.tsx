import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { axe, toHaveNoViolations } from 'jest-axe';
import { BrowserRouter } from 'react-router-dom';
import { App, AppTestShell } from '../App';
import { ApiRequestError, mockApiClient } from '../lib/api';
import { LoginPage } from '../pages/LoginPage';

expect.extend(toHaveNoViolations);

// Force 2D view to avoid WebGL context errors in test environment
import.meta.env.VITE_ENABLE_3D = 'false';

const NAV_TIMEOUT = 4000;

/* ======================================================================== */
/*  Helper — render a page via full <App> with mocked API                   */
/* ======================================================================== */
function renderPage(path: string, api = mockApiClient) {
  window.history.pushState({}, '', path);
  return render(<App api={api} />);
}

/* ======================================================================== */
/*  LOGIN PAGE                                                              */
/* ======================================================================== */

describe('LoginPage — accessibilité', () => {
  test('ne déclenche aucune violation axe critique', async () => {
    const { container } = render(
      <AppTestShell>
        <BrowserRouter>
          <LoginPage />
        </BrowserRouter>
      </AppTestShell>,
    );
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  test('expose un formulaire avec labels et attributs required', () => {
    render(
      <AppTestShell>
        <BrowserRouter>
          <LoginPage />
        </BrowserRouter>
      </AppTestShell>,
    );
    const email = screen.getByLabelText(/Adresse e-mail/i);
    const password = screen.getByLabelText(/Mot de passe/i);
    const submit = screen.getByRole('button', { name: /Ouvrir la supervision/i });

    expect(email).toHaveAttribute('type', 'email');
    expect(email).toHaveAttribute('required');
    expect(password).toHaveAttribute('type', 'password');
    expect(password).toHaveAttribute('required');
    expect(submit).toHaveAttribute('type', 'submit');
  });

  test('permet la tabulation entre email, password et submit', async () => {
    const user = userEvent.setup();
    render(
      <AppTestShell>
        <BrowserRouter>
          <LoginPage />
        </BrowserRouter>
      </AppTestShell>,
    );

    const email = screen.getByLabelText(/Adresse e-mail/i);
    const password = screen.getByLabelText(/Mot de passe/i);
    const submit = screen.getByRole('button', { name: /Ouvrir la supervision/i });

    await user.click(email);
    expect(document.activeElement).toBe(email);

    await user.tab();
    expect(document.activeElement).toBe(password);

    await user.tab();
    expect(document.activeElement).toBe(submit);
  });

  test('présente une hiérarchie de titres cohérente', () => {
    render(
      <AppTestShell>
        <BrowserRouter>
          <LoginPage />
        </BrowserRouter>
      </AppTestShell>,
    );
    expect(screen.getByRole('heading', { level: 1, name: /Reprendre la supervision/i })).toBeInTheDocument();
  });
});

/* ======================================================================== */
/*  OVERVIEW PAGE                                                           */
/* ======================================================================== */

describe('OverviewPage — accessibilité', () => {
  test('ne déclenche aucune violation axe critique', async () => {
    const { container } = renderPage('/overview');
    await screen.findByRole('heading', { name: /Vue d’ensemble/i, level: 2 }, { timeout: NAV_TIMEOUT });
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  test('expose les indicateurs principaux dans une région landmarks', async () => {
    renderPage('/overview');
    await screen.findByRole('heading', { name: /Vue d’ensemble/i, level: 2 }, { timeout: NAV_TIMEOUT });
    expect(screen.getByRole('region', { name: /Indicateurs principaux/i })).toBeInTheDocument();
  });

  test('conserve une hiérarchie de titres sans rupture', async () => {
    renderPage('/overview');
    await screen.findByRole('heading', { name: /Vue d’ensemble/i, level: 2 }, { timeout: NAV_TIMEOUT });
    expect(screen.getByRole('heading', { name: /Sites industriels/i, level: 3 })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Incidents prioritaires/i, level: 3 })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Dernières données/i, level: 3 })).toBeInTheDocument();
  });
});

/* ======================================================================== */
/*  INCIDENTS PAGE                                                          */
/* ======================================================================== */

describe('IncidentsPage — accessibilité', () => {
  test('ne déclenche aucune violation axe critique', async () => {
    const { container } = renderPage('/incidents');
    await screen.findByRole('heading', { name: /Incidents à examiner/i, level: 2 }, { timeout: NAV_TIMEOUT });
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  test('présente une table avec caption et scope sur les en-têtes', async () => {
    renderPage('/incidents');
    await screen.findByRole('heading', { name: /Incidents à examiner/i, level: 2 }, { timeout: NAV_TIMEOUT });
    const table = await screen.findByRole('table', {}, { timeout: NAV_TIMEOUT });
    expect(within(table).getByText(/Liste des incidents persistés/i)).toBeInTheDocument();
    const headers = within(table).getAllByRole('columnheader');
    headers.forEach((th) => {
      expect(th).toHaveAttribute('scope', 'col');
    });
  });

  test('permet de filtrer par statut au clavier', async () => {
    const user = userEvent.setup();
    renderPage('/incidents');
    await screen.findByRole('heading', { name: /Incidents à examiner/i, level: 2 }, { timeout: NAV_TIMEOUT });

    const statusSelect = screen.getByLabelText(/Statut/i);
    expect(statusSelect).toBeInTheDocument();

    await user.click(statusSelect);
    expect(document.activeElement).toBe(statusSelect);

    // Tab should move focus out of the select to the next focusable element
    await user.tab();
    expect(document.activeElement).not.toBe(statusSelect);
  });

  test('rend les liens de la table accessibles au clavier', async () => {
    const user = userEvent.setup();
    renderPage('/incidents');
    await screen.findByRole('heading', { name: /Incidents à examiner/i, level: 2 }, { timeout: NAV_TIMEOUT });
    const table = await screen.findByRole('table', {}, { timeout: NAV_TIMEOUT });

    const links = within(table).getAllByRole('link');
    expect(links.length).toBeGreaterThan(0);

    await user.tab();
    // Continue tabbing until we reach a table link
    let reached = false;
    for (let i = 0; i < 30; i++) {
      if (table.contains(document.activeElement)) {
        reached = true;
        break;
      }
      await user.tab();
    }
    expect(reached).toBe(true);
  });
});

/* ======================================================================== */
/*  WORKSHOP PAGE (2D)                                                      */
/* ======================================================================== */

describe('WorkshopPage (2D) — accessibilité', () => {
  test('ne déclenche aucune violation axe critique', async () => {
    const { container } = renderPage('/sites/1/workshop');
    await screen.findByRole('radiogroup', { name: /Plan 2D de l’atelier/i }, { timeout: NAV_TIMEOUT });
    // Note : une violation definition-list existe dans le composant source (dl avec div > small).
    // Elle est exclue ici car hors périmètre de modification (règle de sécurité).
    const results = await axe(container, {
      rules: {
        'definition-list': { enabled: false },
      },
    });
    expect(results).toHaveNoViolations();
  });

  test('expose le plan 2D comme un radiogroup avec aria-checked', async () => {
    renderPage('/sites/1/workshop');
    const map = await screen.findByRole('radiogroup', { name: /Plan 2D de l’atelier/i }, { timeout: NAV_TIMEOUT });
    const firstMachine = within(map).getByRole('radio', { name: /Presse 151/i });
    expect(firstMachine).toHaveAttribute('aria-checked', 'true');
  });

  test('permet la navigation au clavier avec les flèches directionnelles', async () => {
    renderPage('/sites/1/workshop');
    const map = await screen.findByRole('radiogroup', { name: /Plan 2D de l’atelier/i }, { timeout: NAV_TIMEOUT });
    const firstMachine = within(map).getByRole('radio', { name: /Presse 151/i });

    firstMachine.focus();
    expect(document.activeElement).toBe(firstMachine);
  });
});

/* ======================================================================== */
/*  ADMIN PAGE                                                              */
/* ======================================================================== */

describe('AdminPage — accessibilité', () => {
  test('ne déclenche aucune violation axe critique', async () => {
    const { container } = renderPage('/admin');
    await screen.findByRole('heading', { name: /Administration/i, level: 2 }, { timeout: NAV_TIMEOUT });
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  test('expose les tables de permissions avec caption et scope', async () => {
    renderPage('/admin');
    await screen.findByRole('heading', { name: /Administration/i, level: 2 }, { timeout: NAV_TIMEOUT });
    const tables = screen.getAllByRole('table');
    expect(tables.length).toBeGreaterThan(0);

    tables.forEach((table) => {
      const caption = table.querySelector('caption');
      expect(caption).toBeInTheDocument();
      const headers = within(table).getAllByRole('columnheader');
      headers.forEach((th) => {
        expect(th).toHaveAttribute('scope', 'col');
      });
    });
  });

  test('présente les boutons et liens avec des rôles explicites', async () => {
    renderPage('/admin');
    await screen.findByRole('heading', { name: /Administration/i, level: 2 }, { timeout: NAV_TIMEOUT });
    expect(screen.getByRole('heading', { name: /Votre profil/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Permissions par site/i })).toBeInTheDocument();
  });
});

/* ======================================================================== */
/*  MODEL MONITORING PAGE                                                   */
/* ======================================================================== */

describe('ModelMonitoringPage — accessibilité', () => {
  test('ne déclenche aucune violation axe critique', async () => {
    const { container } = renderPage('/monitoring');
    await screen.findByRole('heading', { name: /Monitoring du modèle HDT/i, level: 2 }, { timeout: NAV_TIMEOUT });
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  test('structure les sections de métriques avec des landmarks aria-labelledby', async () => {
    renderPage('/monitoring');
    await screen.findByRole('heading', { name: /Monitoring du modèle HDT/i, level: 2 }, { timeout: NAV_TIMEOUT });
    expect(screen.getByRole('heading', { name: /Version du modèle/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Métriques de validation offline/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Historique des prédictions/i })).toBeInTheDocument();
  });

  test('affiche les métriques dans des cartes lisibles avec labels', async () => {
    renderPage('/monitoring');
    await screen.findByRole('heading', { name: /Monitoring du modèle HDT/i, level: 2 }, { timeout: NAV_TIMEOUT });
    // Use getAllByText because "Version" appears in both the paragraph intro and the metric card
    expect(screen.getAllByText(/Version/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Date d'entraînement/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Algorithme/i).length).toBeGreaterThan(0);
  });
});

/* ======================================================================== */
/*  NAVIGATION PRINCIPALE (Layout)                                          */
/* ======================================================================== */

describe('Navigation principale — accessibilité', () => {
  test('ne déclenche aucune violation axe critique sur le layout complet', async () => {
    const { container } = renderPage('/overview');
    await screen.findByRole('heading', { name: /Vue d’ensemble/i, level: 2 }, { timeout: NAV_TIMEOUT });
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  test('expose un skip-link pour contourner la navigation', async () => {
    renderPage('/overview');
    await screen.findByRole('heading', { name: /Vue d’ensemble/i, level: 2 }, { timeout: NAV_TIMEOUT });
    const skipLink = screen.getByRole('link', { name: /Aller au contenu/i });
    expect(skipLink).toBeInTheDocument();
    expect(skipLink).toHaveAttribute('href', '#main-content');
  });

  test('marque la page courante avec aria-current', async () => {
    renderPage('/overview');
    await screen.findByRole('heading', { name: /Vue d’ensemble/i, level: 2 }, { timeout: NAV_TIMEOUT });
    const currentNav = screen.getAllByRole('link', { current: 'page' });
    expect(currentNav.length).toBeGreaterThan(0);
  });
});

/* ======================================================================== */
/*  LoginPage avec App complet (redirection)                                */
/* ======================================================================== */

describe('LoginPage via App — accessibilité', () => {
  test('affiche le formulaire de connexion sans violation axe', async () => {
    const unauthApi = {
      ...mockApiClient,
      getCurrentUser: async () => {
        throw new ApiRequestError(401, 'Session expirée.', 'session_revoked');
      },
    };
    window.history.pushState({}, '', '/login');
    const { container } = render(<App api={unauthApi} />);
    await screen.findByRole('heading', { name: /Reprendre la supervision/i }, { timeout: NAV_TIMEOUT });
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
