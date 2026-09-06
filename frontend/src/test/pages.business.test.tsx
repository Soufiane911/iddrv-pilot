import { configure, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import { App } from '../App';
import { mockApiClient, ApiRequestError } from '../lib/api';
import type { ApiClient, Incident, Site } from '../lib/api';

interface IncidentWithFeedback extends Incident {
  feedback_verdict?: 'confirmed' | 'rejected' | 'uncertain' | string;
}

configure({ asyncUtilTimeout: 8000 });

const DEMO_INCIDENT: Incident = {
  id: 's001-demo',
  site_id: 1,
  machine_id: 2,
  machine_erp_ref: '152',
  production_order_id: 'OF-2025-0012',
  status: 'open',
  severity: 'high',
  symptom: 'short_shot_increase',
  defect_type: 'short_shot',
  started_at: '2025-02-12T00:21:43Z',
  ended_at: '2025-02-12T01:52:40Z',
  created_at: '2025-02-12T02:00:00Z',
  data_cutoff: '2025-02-12T02:00:00Z',
  confidence: 'high',
};

function renderApp(path: string, api: ApiClient = mockApiClient) {
  window.history.pushState({}, '', path);
  return render(<App api={api} />);
}

describe('IncidentsPage', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it('affiche l’état de chargement initial', async () => {
    const api: ApiClient = { ...mockApiClient, getIncidents: vi.fn(() => new Promise<Incident[]>(() => {})) };
    renderApp('/incidents', api);
    expect(await screen.findByText(/Chargement des incidents/i)).toBeInTheDocument();
  });

  it('affiche la liste des incidents après chargement', async () => {
    renderApp('/incidents');
    expect(await screen.findByRole('heading', { name: /Incidents à examiner/i })).toBeInTheDocument();
    const matches = await screen.findAllByText(/Hausse des pièces incomplètes/i);
    expect(matches.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/Presse 152/i)).toBeInTheDocument();
    expect(screen.getByRole('table', { name: /Liste des incidents persistés/i })).toBeInTheDocument();
  });

  it('affiche une erreur lorsque l’API incidents échoue', async () => {
    const api: ApiClient = { ...mockApiClient, getIncidents: async () => { throw new ApiRequestError(500, 'Service indisponible'); } };
    renderApp('/incidents', api);
    await waitFor(() => expect(screen.getByText(/Incidents indisponibles/i)).toBeInTheDocument(), { timeout: 8000 });
    expect(screen.getByText(/Service indisponible/i)).toBeInTheDocument();
  });

  it('filtre les incidents par statut', async () => {
    const getIncidents = vi.fn(mockApiClient.getIncidents);
    const api: ApiClient = { ...mockApiClient, getIncidents };
    renderApp('/incidents', api);
    await screen.findByRole('heading', { name: /Incidents à examiner/i });
    const select = screen.getByLabelText(/Statut/i);
    fireEvent.change(select, { target: { value: 'open' } });
    await waitFor(() => expect(getIncidents).toHaveBeenCalledWith({ status: 'open' }));
  });

  // TODO: implémenter les filtres par date (Du/Au) dans IncidentsPage, puis réactiver ce test.
  it.skip('filtre les incidents par date puis réinitialise les filtres', async () => {
    renderApp('/incidents');
    await screen.findByRole('heading', { name: /Incidents à examiner/i });
    const fromInput = screen.getByLabelText(/Du/i);
    fireEvent.change(fromInput, { target: { value: '2025-02-13' } });
    expect(await screen.findByText(/Aucun incident dans ce filtre/i)).toBeInTheDocument();
    const resetBtns = screen.getAllByRole('button', { name: /Réinitialiser les filtres/i });
    fireEvent.click(resetBtns[0]);
    await waitFor(() => expect(screen.getAllByText(/Hausse des pièces incomplètes/i).length).toBeGreaterThanOrEqual(1));
  });

  // TODO: brancher le composant Pagination (sélecteur « Résultats par page ») dans IncidentsPage, puis réactiver ce test.
  it.skip('change la taille de page', async () => {
    renderApp('/incidents');
    await screen.findByRole('heading', { name: /Incidents à examiner/i });
    const pageSize = await screen.findByLabelText(/Résultats par page/i);
    expect(pageSize).toBeTruthy();
    fireEvent.change(pageSize, { target: { value: '25' } });
    expect(pageSize).toHaveValue('25');
  });
});

describe('IncidentDetailPage', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it('affiche l’état de chargement initial', async () => {
    const api: ApiClient = { ...mockApiClient, getIncident: vi.fn(() => new Promise<Incident>(() => {})) };
    renderApp('/incidents/s001-demo', api);
    expect(await screen.findByText(/Chargement de l’incident/i)).toBeInTheDocument();
  });

  it('affiche les détails de l’incident après chargement', async () => {
    renderApp('/incidents/s001-demo');
    expect(await screen.findByRole('heading', { name: /Hausse des pièces incomplètes/i })).toBeInTheDocument();
    expect(screen.getByText(/Presse 152/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Lancer l’investigation/i })).toBeInTheDocument();
  });

  it('affiche une erreur si l’incident est introuvable', async () => {
    const api: ApiClient = { ...mockApiClient, getIncident: async () => { throw new ApiRequestError(500, 'Introuvable'); } };
    renderApp('/incidents/s001-demo', api);
    await waitFor(() => expect(screen.getByText(/Incident introuvable/i)).toBeInTheDocument(), { timeout: 8000 });
    expect(screen.getAllByText(/Introuvable/i).length).toBeGreaterThanOrEqual(1);
  });

  it('lance une investigation et affiche le succès', async () => {
    const runInvestigation = vi.fn(mockApiClient.runInvestigation);
    const api: ApiClient = { ...mockApiClient, runInvestigation };
    renderApp('/incidents/s001-demo', api);
    await screen.findByRole('heading', { name: /Hausse des pièces incomplètes/i });
    fireEvent.click(screen.getByRole('button', { name: /Lancer l’investigation/i }));
    await waitFor(() => expect(runInvestigation).toHaveBeenCalled());
    expect(await screen.findByText(/Investigation terminée/i)).toBeInTheDocument();
  });

  it('affiche un run incompatible', async () => {
    const api: ApiClient = {
      ...mockApiClient,
      getInvestigation: async () => ({
        run_id: 'run-other',
        incident_id: 'another-incident',
        status: 'completed',
        dataCutoff: DEMO_INCIDENT.data_cutoff,
        hypotheses: [],
        evidence: [],
      }),
    };
    renderApp('/incidents/s001-demo?run=run-other', api);
    expect(await screen.findByText(/Run incompatible/i)).toBeInTheDocument();
  });

  it('soumet un feedback terrain', async () => {
    const submitFeedback = vi.fn(mockApiClient.submitFeedback);
    const api: ApiClient = { ...mockApiClient, submitFeedback };
    renderApp('/incidents/s001-demo', api);
    await screen.findByRole('heading', { name: /Hausse des pièces incomplètes/i });
    const verdict = screen.getByLabelText(/Verdict/i);
    fireEvent.change(verdict, { target: { value: 'rejected' } });
    const comment = screen.getByLabelText(/Commentaire/i);
    fireEvent.change(comment, { target: { value: 'Constat rejeté' } });
    fireEvent.click(screen.getByRole('button', { name: /Enregistrer le retour/i }));
    await waitFor(() => expect(submitFeedback).toHaveBeenCalledWith('s001-demo', 'rejected', 'Constat rejeté'));
    expect(await screen.findByText(/Retour enregistré/i)).toBeInTheDocument();
  });
});

describe('AdminPage', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it('affiche le profil utilisateur et les permissions', async () => {
    renderApp('/admin');
    await waitFor(() => {
      expect(screen.getAllByText(/demo@iddrv.local/i).length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText(/Analyste/i).length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText(/Permissions par site/i).length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText(/Usine Principale/i).length).toBeGreaterThanOrEqual(1);
    }, { timeout: 8000 });
  }, 10000);

  it('affiche une erreur si le profil est indisponible', async () => {
    const api: ApiClient = { ...mockApiClient, getCurrentUser: async () => { throw new ApiRequestError(500, 'Auth indisponible'); } };
    renderApp('/admin', api);
    await waitFor(() => expect(screen.getByText(/Session indisponible/i)).toBeInTheDocument(), { timeout: 8000 });
    expect(screen.getByText(/Auth indisponible/i)).toBeInTheDocument();
  }, 10000);

  it('affiche la matrice des rôles pour un administrateur', async () => {
    const api: ApiClient = {
      ...mockApiClient,
      getCurrentUser: async () => ({
        id: 'admin-user',
        email: 'admin@iddrv.local',
        role: 'admin',
        siteIds: [1],
        siteRoles: { 1: 'admin' },
      }),
    };
    renderApp('/admin', api);
    await waitFor(() => {
      expect(screen.getAllByText(/admin@iddrv.local/i).length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText(/Matrice des rôles/i).length).toBeGreaterThanOrEqual(1);
    }, { timeout: 8000 });
    expect(screen.getByText(/Gestion des comptes utilisateurs disponible côté API uniquement/i)).toBeInTheDocument();
  }, 10000);

  it('affiche le chargement des sites', async () => {
    const api: ApiClient = { ...mockApiClient, getSites: vi.fn(() => new Promise<Site[]>(() => {})) };
    renderApp('/admin', api);
    await waitFor(() => expect(screen.getByText(/Permissions par site/i)).toBeInTheDocument(), { timeout: 8000 });
    expect(screen.getByText(/Chargement des sites…/i)).toBeInTheDocument();
  }, 10000);
});

describe('ModelMonitoringPage', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it('affiche l’état de chargement initial', async () => {
    const api: ApiClient = { ...mockApiClient, getIncidents: vi.fn(() => new Promise<Incident[]>(() => {})) };
    renderApp('/monitoring', api);
    expect(await screen.findByText(/Chargement des incidents/i)).toBeInTheDocument();
  });

  it('affiche les informations du modèle après chargement', async () => {
    renderApp('/monitoring');
    expect(await screen.findByRole('heading', { name: /Monitoring du modèle HDT/i })).toBeInTheDocument();
    expect(await screen.findByText(/hdt-process-drift-iforest-v1/i)).toBeInTheDocument();
    expect(screen.getByText(/Isolation Forest/i)).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Simulateur interactif HDT/i })).toBeInTheDocument();
  });

  it('affiche une erreur lorsque les données monitoring échouent', async () => {
    const api: ApiClient = { ...mockApiClient, getIncidents: async () => { throw new ApiRequestError(500, 'Monitoring down'); } };
    renderApp('/monitoring', api);
    await waitFor(() => expect(screen.getByText(/Incidents indisponibles/i)).toBeInTheDocument(), { timeout: 8000 });
    expect(screen.getByText(/Impossible de récupérer les données de feedback/i)).toBeInTheDocument();
  });

  it('affiche les compteurs de feedbacks humains', async () => {
    const incidents: IncidentWithFeedback[] = [
      { ...DEMO_INCIDENT, id: 'inc-1', feedback_verdict: 'confirmed' },
      { ...DEMO_INCIDENT, id: 'inc-2', feedback_verdict: 'rejected' },
      { ...DEMO_INCIDENT, id: 'inc-3', feedback_verdict: 'uncertain' },
    ];
    const api: ApiClient = { ...mockApiClient, getIncidents: async () => incidents };
    renderApp('/monitoring', api);
    await screen.findByRole('heading', { name: /Monitoring du modèle HDT/i });
    expect(await screen.findByText(/Confirmés/i)).toBeInTheDocument();
    expect(await screen.findByText(/Rejetés/i)).toBeInTheDocument();
    expect(await screen.findByText(/Incertains/i)).toBeInTheDocument();
    const ones = screen.getAllByText('1');
    expect(ones.length).toBeGreaterThanOrEqual(3);
  });

  it('affiche l’historique des prédictions stocké dans le localStorage', async () => {
    const history = [
      {
        id: 'h1',
        timestamp: '2025-02-12T01:00:00Z',
        anomalyScore: 0.73,
        threshold: 0.41,
        alert: true,
        machineErpRef: '152',
        signals: [],
      },
    ];
    window.localStorage.setItem('iddrv:hdt-history', JSON.stringify(history));
    renderApp('/monitoring');
    await screen.findByRole('heading', { name: /Monitoring du modèle HDT/i });
    expect(screen.getByText('0,730')).toBeInTheDocument();
    expect(screen.getByText(/152/)).toBeInTheDocument();
  });

  it('affiche le simulateur HDT avec le bouton désactivé tant que les cycles sont vides', async () => {
    renderApp('/monitoring');
    await screen.findByRole('heading', { name: /Monitoring du modèle HDT/i });
    expect(screen.getByRole('heading', { name: /Simulateur interactif HDT/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Calculer le score HDT/i })).toBeDisabled();
  });
});
