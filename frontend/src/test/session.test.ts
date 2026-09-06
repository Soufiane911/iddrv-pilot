import { afterEach, describe, expect, it } from 'vitest';
import { broadcastSessionState, readSessionExpiry, SESSION_STATE_KEY } from '../lib/session';

describe('synchronisation de session sans jeton navigateur', () => {
  afterEach(() => window.localStorage.clear());

  it('ne conserve que le type d’événement et l’expiration publique', () => {
    broadcastSessionState('login', '2026-07-14T00:00:00Z');
    expect(readSessionExpiry()).toBe('2026-07-14T00:00:00Z');
    const stored = window.localStorage.getItem(SESSION_STATE_KEY) ?? '';
    expect(stored).toContain('login');
    expect(stored).not.toContain('token');
  });

  it('retire l’expiration lors de la déconnexion', () => {
    broadcastSessionState('login', '2026-07-14T00:00:00Z');
    broadcastSessionState('logout');
    expect(readSessionExpiry()).toBeUndefined();
  });
});
