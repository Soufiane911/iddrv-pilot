import { QueryClient, QueryClientProvider, useQuery, useQueryClient } from '@tanstack/react-query';
import { createContext, lazy, Suspense, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { Layout } from './components/Layout';
import { StatePanel } from './components/Ui';
import { ApiRequestError, apiClient, type ApiClient } from './lib/api';
import { broadcastSessionState } from './lib/session';
import { HealthPage } from './pages/HealthPage';
import { AdminPage } from './pages/AdminPage';
import { ImportsPage } from './pages/ImportsPage';
import { IncidentDetailPage } from './pages/IncidentDetailPage';
import { IncidentsPage } from './pages/IncidentsPage';
import { LoginPage } from './pages/LoginPage';
import { ModelMonitoringPage } from './pages/ModelMonitoringPage';
import { OpportunitiesPage } from './pages/OpportunitiesPage';
import { OverviewPage } from './pages/OverviewPage';
import { ShowroomPage } from './pages/ShowroomPage';
import { SitesPage } from './pages/SitesPage';
import { WorkspacePage } from './pages/WorkspacePage';
import './styles.css';

const WorkshopPage = lazy(() => import('./pages/WorkshopPage').then((module) => ({ default: module.WorkshopPage })));
const DIRECT_LOCAL_ACCESS = import.meta.env.VITE_SKIP_AUTH === 'true';

function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: (failureCount, error) => !(error instanceof ApiRequestError && error.status === 401) && failureCount < 1,
        staleTime: 30_000,
        refetchOnWindowFocus: false,
      },
    },
  });
}

const testQueryClient = createQueryClient();
const ApiContext = createContext<ApiClient>(apiClient);

export function useApi(): ApiClient {
  return useContext(ApiContext);
}

function ProtectedLayout() {
  const api = useApi();
  const location = useLocation();
  const queryClient = useQueryClient();
  const unauthorizedHandled = useRef(false);
  const [sessionInvalid, setSessionInvalid] = useState(false);
  const authQuery = useQuery({
    queryKey: ['auth-me'],
    queryFn: () => api.getCurrentUser(),
    retry: false,
    enabled: !DIRECT_LOCAL_ACCESS,
  });
  const requestedPath = `${location.pathname}${location.search}${location.hash}`;

  useEffect(() => {
    if (DIRECT_LOCAL_ACCESS) return;
    const handleUnauthorized = () => {
      if (unauthorizedHandled.current) return;
      unauthorizedHandled.current = true;
      broadcastSessionState('logout');
      queryClient.clear();
      setSessionInvalid(true);
    };
    window.addEventListener('iddrv:unauthorized', handleUnauthorized);
    return () => window.removeEventListener('iddrv:unauthorized', handleUnauthorized);
  }, [queryClient]);

  if (DIRECT_LOCAL_ACCESS) return <Layout />;
  if (sessionInvalid || (authQuery.error instanceof ApiRequestError && authQuery.error.status === 401)) {
    return <Navigate to="/login" replace state={{ from: requestedPath }} />;
  }
  if (authQuery.isPending) {
    return <main className="auth-gate"><StatePanel tone="loading" title="Vérification de la session" text="Connexion au périmètre industriel." /></main>;
  }
  if (authQuery.isError) {
    return <main className="auth-gate"><StatePanel tone="error" title="Session indisponible" text={authQuery.error instanceof Error ? authQuery.error.message : 'Impossible de vérifier votre session.'} action="Réessayer" onAction={() => authQuery.refetch()} /></main>;
  }
  return <Layout />;
}

export function App({ api = apiClient }: { api?: ApiClient }) {
  const [queryClient] = useState(createQueryClient);
  return <QueryClientProvider client={queryClient}>
    <ApiContext.Provider value={api}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={DIRECT_LOCAL_ACCESS ? <Navigate to="/overview" replace /> : <LoginPage />} />
          <Route element={<ProtectedLayout />}>
            <Route index element={<Navigate to="/overview" replace />} />
            <Route path="overview" element={<OverviewPage />} />
            <Route path="showroom" element={<ShowroomPage />} />
            <Route path="workspace" element={<WorkspacePage />} />
            <Route path="sites" element={<SitesPage />} />
            <Route path="sites/:siteId/workshop" element={<Suspense fallback={<section className="page"><StatePanel tone="loading" title="Chargement de l’atelier" text="Préparation du plan 2D." /></section>}><WorkshopPage /></Suspense>} />
            <Route path="sites/:siteId/opportunities" element={<OpportunitiesPage />} />
            <Route path="incidents" element={<IncidentsPage />} />
            <Route path="incidents/:incidentId" element={<IncidentDetailPage />} />
            <Route path="imports" element={<ImportsPage />} />
            <Route path="admin" element={<AdminPage />} />
            <Route path="monitoring" element={<ModelMonitoringPage />} />
            <Route path="health" element={<HealthPage />} />
            <Route path="*" element={<Navigate to="/overview" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ApiContext.Provider>
  </QueryClientProvider>;
}

export function AppTestShell({ children, api = apiClient }: { children: ReactNode; api?: ApiClient }) {
  return <QueryClientProvider client={testQueryClient}>
    <ApiContext.Provider value={api}>{children}</ApiContext.Provider>
  </QueryClientProvider>;
}
