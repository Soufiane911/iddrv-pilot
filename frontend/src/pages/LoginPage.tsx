import { useMutation, useQueryClient } from '@tanstack/react-query';
import { FormEvent, useState } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { useApi } from '../App';
import { broadcastSessionState, readSessionExpiry } from '../lib/session';
import type { AuthUser } from '../lib/api';
import { StatePanel } from '../components/Ui';

export function LoginPage() {
  const api = useApi();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const location = useLocation();
  const target = (location.state as { from?: string } | null)?.from ?? '/overview';
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const cachedSession = queryClient.getQueryData<AuthUser>(['auth-me']);
  const storedExpiry = readSessionExpiry();
  const clientSessionExpired = Boolean(storedExpiry && Date.parse(storedExpiry) <= Date.now());
  const mutation = useMutation({
    mutationFn: () => api.login(email, password),
    onSuccess: (response) => {
      broadcastSessionState('login', response.expiresAt);
      queryClient.clear();
      queryClient.setQueryData(['auth-me'], response.user);
      navigate(target, { replace: true });
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    if (email.trim() && password) mutation.mutate();
  }

  if (cachedSession && !clientSessionExpired) return <Navigate to={target} replace />;

  return <main className="login-shell">
    <section className="login-card">
      <div className="brand login-brand"><span className="brand-mark" aria-hidden="true"><i /><i /><i /></span><span><strong>IDDRV</strong><small>Industrial evidence system</small></span></div>
      <p className="eyebrow">ACCÈS PILOTE</p>
      <h1>Reprendre la supervision</h1>
      <p className="muted">Identifiez-vous pour retrouver les sites, les incidents et leurs preuves.</p>
      <form className="login-form" onSubmit={submit}>
        <label htmlFor="login-email">Adresse e-mail</label>
        <input id="login-email" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
        <label htmlFor="login-password">Mot de passe</label>
        <input id="login-password" type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required />
        {mutation.isError && <StatePanel tone="error" title="Connexion refusée" text={mutation.error instanceof Error ? mutation.error.message : 'Vérifiez vos identifiants.'} />}
        {mutation.isSuccess && <StatePanel tone="success" title="Connexion établie" text="Ouverture de votre périmètre…" />}
        <button className="button-primary login-submit" type="submit" disabled={mutation.isPending}>{mutation.isPending ? 'Connexion…' : 'Ouvrir la supervision'}</button>
      </form>
      <p className="login-note">La session est conservée par un cookie HttpOnly. Aucun jeton n’est stocké dans le navigateur.</p>
    </section>
  </main>;
}
