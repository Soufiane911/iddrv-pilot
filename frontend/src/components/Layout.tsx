import { CubeIcon } from '@phosphor-icons/react/Cube';
import { DatabaseIcon } from '@phosphor-icons/react/Database';
import { DotsThreeIcon } from '@phosphor-icons/react/DotsThree';
import { DownloadSimpleIcon } from '@phosphor-icons/react/DownloadSimple';
import { FactoryIcon } from '@phosphor-icons/react/Factory';
import { GearSixIcon } from '@phosphor-icons/react/GearSix';
import { SignOutIcon } from '@phosphor-icons/react/SignOut';
import { SquaresFourIcon } from '@phosphor-icons/react/SquaresFour';
import { WarningIcon } from '@phosphor-icons/react/Warning';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { useApi } from '../App';
import { broadcastSessionState } from '../lib/session';
import './layout.css';

type IconName = 'overview' | 'workshop' | 'incident' | 'data' | 'import' | 'admin' | 'demo';
type NavItem = { to: string; label: string; caption: string; icon: IconName };

const primary: NavItem[] = [
  { to: '/overview', label: 'Vue d’ensemble', caption: 'Situation', icon: 'overview' },
  { to: '/sites', label: 'Atelier', caption: 'Sites & machines', icon: 'workshop' },
  { to: '/incidents', label: 'Incidents', caption: 'Preuves', icon: 'incident' },
  { to: '/workspace', label: 'Données', caption: 'Nouvel import', icon: 'data' },
];
const secondary: NavItem[] = [
  { to: '/imports', label: 'Journal des imports', caption: 'Traçabilité', icon: 'import' },
  { to: '/health', label: 'Administration', caption: 'Santé locale', icon: 'admin' },
  { to: '/showroom', label: 'Démonstration', caption: 'Scénario fictif', icon: 'demo' },
];
const DIRECT_LOCAL_ACCESS = import.meta.env.VITE_SKIP_AUTH === 'true';

function Icon({ name }: { name: IconName }) {
  const icons = { overview: SquaresFourIcon, workshop: FactoryIcon, incident: WarningIcon, data: DatabaseIcon, import: DownloadSimpleIcon, admin: GearSixIcon, demo: CubeIcon };
  const Glyph = icons[name];
  return <Glyph className="nav-svg" size={20} weight="regular" aria-hidden="true" />;
}

function titleFor(pathname: string) {
  if (pathname.startsWith('/overview')) return ['PILOTAGE', 'Vue d’ensemble'];
  if (pathname.startsWith('/workspace')) return ['DONNÉES', 'Nouvel import'];
  if (pathname.startsWith('/incidents/')) return ['INVESTIGATION', 'Dossier incident'];
  if (pathname.startsWith('/incidents')) return ['SUPERVISION', 'File des incidents'];
  if (pathname.startsWith('/imports')) return ['DONNÉES', 'Journal des imports'];
  if (pathname.startsWith('/health')) return ['ADMINISTRATION', 'État des services'];
  if (pathname.includes('/workshop')) return ['ATELIER', 'Parc machines'];
  if (pathname.startsWith('/showroom')) return ['DÉMONSTRATION', 'Scénario industriel'];
  return ['ORGANISATION', 'Sites industriels'];
}

function active(item: NavItem, pathname: string) {
  if (item.to === '/sites') return pathname.startsWith('/sites');
  if (item.to === '/incidents') return pathname.startsWith('/incidents');
  return pathname.startsWith(item.to);
}

export function Layout() {
  const location = useLocation();
  const navigate = useNavigate();
  const api = useApi();
  const queryClient = useQueryClient();
  const logout = useMutation({ mutationFn: () => api.logout(), onSuccess: () => { broadcastSessionState('logout'); queryClient.clear(); navigate('/login', { replace: true }); } });
  const [eyebrow, title] = titleFor(location.pathname);
  const showroom = location.pathname === '/showroom';
  const [mobileMoreOpen, setMobileMoreOpen] = useState(false);
  useEffect(() => { document.title = `${title} · IDDRV`; setMobileMoreOpen(false); }, [location.pathname, title]);
  useEffect(() => {
    if (!mobileMoreOpen) return;
    const closeOnEscape = (event: KeyboardEvent) => { if (event.key === 'Escape') setMobileMoreOpen(false); };
    window.addEventListener('keydown', closeOnEscape);
    return () => window.removeEventListener('keydown', closeOnEscape);
  }, [mobileMoreOpen]);

  return <div className={`app-shell${showroom ? ' showroom-shell' : ''}`}>
    <a className="skip-link" href="#main-content">Aller au contenu</a>
    <aside className="sidebar" aria-label="Navigation principale">
      <Link className="brand" to="/overview" aria-label="IDDRV, vue d’ensemble"><span className="brand-mark" aria-hidden="true"><i /><i /><i /></span><span><strong>IDDRV</strong><small>Industrial evidence system</small></span></Link>
      <div className="sidebar-scope"><span>ENVIRONNEMENT</span><strong>Pilote local</strong><small>Données industrielles maîtrisées</small></div>
      <nav className="primary-nav" aria-label="Navigation métier">{primary.map((item) => <Link key={item.to} to={item.to} aria-label={`${item.label}, ${item.caption}`} className={`nav-link${active(item, location.pathname) ? ' active' : ''}`} aria-current={active(item, location.pathname) ? 'page' : undefined}><Icon name={item.icon} /><span><strong>{item.label}</strong><small>{item.caption}</small></span></Link>)}</nav>
      <div className="sidebar-divider"><span>OUTILS</span></div>
      <nav className="secondary-nav" aria-label="Outils et administration">{secondary.map((item) => <Link key={item.to} to={item.to} aria-label={`${item.label}, ${item.caption}`} className={`nav-link${active(item, location.pathname) ? ' active' : ''}`} aria-current={active(item, location.pathname) ? 'page' : undefined}><Icon name={item.icon} /><span><strong>{item.label}</strong><small>{item.caption}</small></span></Link>)}</nav>
      <button className="mobile-more-trigger" type="button" aria-expanded={mobileMoreOpen} aria-controls="mobile-more-menu" onClick={() => setMobileMoreOpen((open) => !open)}><DotsThreeIcon size={20} aria-hidden="true" /><small>Plus</small></button>
      {mobileMoreOpen ? <nav id="mobile-more-menu" className="mobile-more-menu" aria-label="Navigation complémentaire">{secondary.map((item) => <Link key={item.to} to={item.to} aria-current={active(item, location.pathname) ? 'page' : undefined}><Icon name={item.icon} /><span>{item.label}<small>{item.caption}</small></span></Link>)}{!DIRECT_LOCAL_ACCESS ? <button type="button" onClick={() => logout.mutate()} disabled={logout.isPending}>Se déconnecter</button> : null}</nav> : null}
      <div className="sidebar-foot"><span className="status-pulse" aria-hidden="true" /><span>Runtime local<small>État disponible dans Administration</small></span>{!DIRECT_LOCAL_ACCESS ? <button type="button" aria-label="Se déconnecter" onClick={() => logout.mutate()} disabled={logout.isPending} title={logout.isError ? 'Déconnexion impossible, réessayez' : undefined}><SignOutIcon size={18} aria-hidden="true" /><span>{logout.isPending ? 'Déconnexion…' : 'Se déconnecter'}</span></button> : null}</div>
    </aside>
    <main id="main-content" className="main-content">
      {!showroom && <header className="topbar"><div className="topbar-title"><p>{eyebrow}</p><h1>{title}</h1></div><div className="topbar-context"><span><small>CONTEXTE</small>Tout le périmètre</span><span><small>MODE</small>Historique sécurisé</span><Link to="/health" aria-label="Vérifier l’état des services"><i />Vérifier les services</Link></div></header>}
      <Outlet />
    </main>
  </div>;
}
