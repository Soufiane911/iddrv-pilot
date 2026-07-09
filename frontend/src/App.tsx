import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Layout } from './components/Layout';
import { HealthPage } from './pages/HealthPage';
import { PlaceholderPage } from './pages/PlaceholderPage';
import { mockApiClient } from './lib/api';
import './styles.css';
const queryClient = new QueryClient({ defaultOptions: { queries: { retry: 1, staleTime: 30_000 } } });
export function App() { return <QueryClientProvider client={queryClient}><BrowserRouter><Routes><Route element={<Layout />}><Route path="/" element={<PlaceholderPage title="Vue atelier" description="Le plan de l’atelier et l’état des presses seront visibles ici."/>}/><Route path="/health" element={<HealthPage api={mockApiClient}/>}/><Route path="/incidents" element={<PlaceholderPage title="Incidents" description="Le replay d’incident et les preuves seront disponibles après le diagnostic vertical."/>}/></Route></Routes></BrowserRouter></QueryClientProvider> }
