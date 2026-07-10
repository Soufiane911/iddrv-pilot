import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { createContext, useContext, type ReactNode } from 'react';
import { Layout } from './components/Layout';
import { HealthPage } from './pages/HealthPage';
import { SitesPage } from './pages/SitesPage';
import { WorkshopPage } from './pages/WorkshopPage';
import { IncidentsPage } from './pages/IncidentsPage';
import { IncidentDetailPage } from './pages/IncidentDetailPage';
import { ImportsPage } from './pages/ImportsPage';
import { LoginPage } from './pages/LoginPage';
import type { ApiClient } from './lib/api';
import { apiClient } from './lib/api';
import './styles.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 30_000, refetchOnWindowFocus: false },
  },
});

const ApiContext = createContext<ApiClient>(apiClient);

export function useApi(): ApiClient {
  return useContext(ApiContext);
}

export function App({ api = apiClient }: { api?: ApiClient }) {
  return (
    <QueryClientProvider client={queryClient}>
      <ApiContext.Provider value={api}>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route element={<Layout />}>
              <Route index element={<Navigate to="/sites" replace />} />
              <Route path="sites" element={<SitesPage />} />
              <Route path="sites/:siteId/workshop" element={<WorkshopPage />} />
              <Route path="incidents" element={<IncidentsPage />} />
              <Route path="incidents/:incidentId" element={<IncidentDetailPage />} />
              <Route path="imports" element={<ImportsPage />} />
              <Route path="health" element={<HealthPage />} />
              <Route path="*" element={<Navigate to="/sites" replace />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </ApiContext.Provider>
    </QueryClientProvider>
  );
}

export function AppTestShell({ children, api = apiClient }: { children: ReactNode; api?: ApiClient }) {
  return (
    <QueryClientProvider client={queryClient}>
      <ApiContext.Provider value={api}>{children}</ApiContext.Provider>
    </QueryClientProvider>
  );
}
