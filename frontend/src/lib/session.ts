export const SESSION_STATE_KEY = 'iddrv:session-state';

type SessionState = {
  type: 'login' | 'logout';
  at: number;
  expiresAt?: string;
};

export function broadcastSessionState(type: SessionState['type'], expiresAt?: string): void {
  if (typeof window === 'undefined') return;
  const state: SessionState = { type, at: Date.now(), ...(expiresAt ? { expiresAt } : {}) };
  try { window.localStorage.setItem(SESSION_STATE_KEY, JSON.stringify(state)); } catch { /* Session sync is best-effort when storage is disabled. */ }
}

export function readSessionExpiry(): string | undefined {
  if (typeof window === 'undefined') return undefined;
  try {
    const raw = window.localStorage.getItem(SESSION_STATE_KEY);
    if (!raw) return undefined;
    const value = JSON.parse(raw) as Partial<SessionState>;
    return value.type === 'login' && typeof value.expiresAt === 'string' ? value.expiresAt : undefined;
  } catch {
    return undefined;
  }
}
