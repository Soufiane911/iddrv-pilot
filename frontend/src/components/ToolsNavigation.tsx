import { NavLink } from 'react-router-dom';

export function ToolsNavigation() {
  return <nav className="tools-navigation" aria-label="Outils techniques">
    <NavLink to="/health">Santé des services</NavLink>
    <NavLink to="/monitoring">Suivi HDT</NavLink>
    <NavLink to="/admin">Profil et accès</NavLink>
  </nav>;
}
