export type Health = { status: 'ok' | 'degraded' | 'unknown'; checkedAt?: string; message?: string };
export interface ApiClient { getHealth(): Promise<Health>; }
export function createApiClient(baseUrl = import.meta.env.VITE_API_URL ?? '/api'): ApiClient {
  return { async getHealth() { const response = await fetch(`${baseUrl}/health`); if (!response.ok) throw new Error(`API health: ${response.status}`); return response.json() as Promise<Health>; } };
}
export const mockApiClient: ApiClient = { getHealth: async () => ({ status: 'ok', checkedAt: new Date().toISOString(), message: 'API connectée' }) };
