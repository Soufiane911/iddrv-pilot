import { useMutation } from '@tanstack/react-query';
import { FormEvent, useState } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { useApi } from '../App';
import { StatePanel } from '../components/Ui';

export function LoginPage() {
  const api = useApi();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [signedIn, setSignedIn] = useState(() => Boolean(sessionStorage.getItem('iddrv_access_token')));
  const mutation = useMutation({ mutationFn: () => api.login(email, password), onSuccess: (response) => { if (response.accessToken) sessionStorage.setItem('iddrv_access_token', response.accessToken); setSignedIn(true); navigate('/sites'); } });
  function submit(event: FormEvent) { event.preventDefault(); if (email.trim() && password) mutation.mutate(); }
  if (signedIn) return <Navigate to="/sites" replace />;
  return <main className="login-shell"><section className="login-card"><div className="brand login-brand"><span className="brand-mark" aria-hidden="true">I</span><span><strong>IDDRV</strong><small>Industrial data vault</small></span></div><p className="eyebrow">ACCÈS PILOTE</p><h1>Reprendre la supervision</h1><p className="muted">Connectez-vous pour accéder aux sites, aux incidents et aux preuves.</p><form className="login-form" onSubmit={submit}><label htmlFor="login-email">Adresse e-mail</label><input id="login-email" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required /><label htmlFor="login-password">Mot de passe</label><input id="login-password" type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required />{mutation.isError && <StatePanel tone="error" title="Connexion refusée" text={mutation.error instanceof Error ? mutation.error.message : 'Vérifiez vos identifiants.'} />}{mutation.isSuccess && <StatePanel tone="success" title="Connexion établie" text="Ouverture de votre périmètre…" />}<button className="button-primary login-submit" type="submit" disabled={mutation.isPending}>{mutation.isPending ? 'Connexion…' : 'Ouvrir la supervision'}</button></form><p className="login-note">Le pilote local ne lit aucune donnée métier avant authentification.</p></section></main>;
}
