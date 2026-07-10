import { NavLink, Outlet, useLocation } from 'react-router-dom';
import './layout.css';

const links = [
  { to: '/sites', label: 'Sites', icon: '⌂' },
  { to: '/incidents', label: 'Incidents', icon: '!' },
  { to: '/imports', label: 'Imports', icon: '⇩' },
];

function pageTitle(pathname: string): { eyebrow: string; title: string } {
  if (pathname.startsWith('/incidents/')) return { eyebrow: 'INVESTIGATION', title: 'Incident' };
  if (pathname.startsWith('/incidents')) return { eyebrow: 'SUPERVISION', title: 'Incidents' };
  if (pathname.startsWith('/imports')) return { eyebrow: 'TRAÇABILITÉ', title: 'Imports' };
  if (pathname.startsWith('/health')) return { eyebrow: 'CONNECTIVITÉ', title: 'Santé API' };
  if (pathname.includes('/workshop')) return { eyebrow: 'ATELIER · REPLAY', title: 'Vue atelier' };
  return { eyebrow: 'SUPERVISION INDUSTRIELLE', title: 'Sites' };
}

export function Layout() {
  const location = useLocation();
  const heading = pageTitle(location.pathname);
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">Aller au contenu</a>
      <aside className="sidebar" aria-label="Navigation principale">
        <div className="brand" aria-label="IDDVR, Industrial data vault">
          <span className="brand-mark" aria-hidden="true">I</span>
          <span><strong>IDDRV</strong><small>Industrial data vault</small></span>
        </div>
        <div className="sidebar-label">PILOTAGE</div>
        <nav className="primary-nav">
          {links.map((link) => (
            <NavLink key={link.to} to={link.to} className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
              <span className="nav-icon" aria-hidden="true">{link.icon}</span>
              <span>{link.label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-divider" />
        <nav className="secondary-nav" aria-label="Administration">
          <NavLink to="/health" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
            <span className="nav-icon" aria-hidden="true">◌</span><span>Santé API</span>
          </NavLink>
        </nav>
        <div className="sidebar-foot">
          <span className="status-pulse" aria-hidden="true" /> Pilote local
          <small>G3 · interface atelier</small>
        </div>
      </aside>
      <main id="main-content" className="main-content">
        <header className="topbar">
          <div>
            <p className="eyebrow">{heading.eyebrow}</p>
            <h1>{heading.title}</h1>
          </div>
          <div className="header-meta"><span className="live-dot" aria-hidden="true" /> Données API · environnement local</div>
        </header>
        <Outlet />
      </main>
    </div>
  );
}
