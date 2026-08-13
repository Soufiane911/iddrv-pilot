import { useQuery } from '@tanstack/react-query';
import { InfoIcon } from '@phosphor-icons/react/Info';
import { ShieldCheckIcon } from '@phosphor-icons/react/ShieldCheck';
import { UserIcon } from '@phosphor-icons/react/User';
import { useApi } from '../App';
import { MetricCard, SectionTitle, StatePanel } from '../components/Ui';
import { PermissionMatrix } from '../components/admin/PermissionMatrix';
import { RoleBadge } from '../components/admin/RoleBadge';
import { authRoleForSite } from '../lib/api';

export function AdminPage() {
  const api = useApi();
  const authQuery = useQuery({ queryKey: ['auth-me'], queryFn: api.getCurrentUser });
  const sitesQuery = useQuery({ queryKey: ['sites'], queryFn: api.getSites });

  const user = authQuery.data;
  const sites = sitesQuery.data ?? [];
  const siteMap = new Map(sites.map((s) => [s.id, s]));

  return (
    <section className="page page-wide">
      <div className="page-intro">
        <div>
          <p className="eyebrow">GOUVERNANCE</p>
          <h2>Administration</h2>
          <p className="muted">Vue d’ensemble de votre profil, de vos permissions et de la documentation des rôles.</p>
        </div>
      </div>

      {authQuery.isPending && (
        <StatePanel tone="loading" title="Chargement du profil" text="Récupération de votre identité et de vos permissions." />
      )}
      {authQuery.isError && (
        <StatePanel
          tone="error"
          title="Profil indisponible"
          text={authQuery.error instanceof Error ? authQuery.error.message : 'Impossible de récupérer votre profil.'}
        />
      )}

      {user && (
        <>
          <div className="metric-grid metric-grid-three">
            <MetricCard
              label="Email"
              value={user.email}
              detail={user.displayName ?? 'Nom non renseigné'}
            />
            <MetricCard
              label="Rôle global"
              value={<RoleBadge role={user.role} />}
              detail="appliqué par défaut"
            />
            <MetricCard
              label="Sites autorisés"
              value={user.siteIds.length}
              detail={user.siteIds.length === 1 ? 'site unique' : 'sites multi-permis'}
              tone={user.siteIds.length ? 'good' : 'warning'}
            />
          </div>

          <section className="surface-card" style={{ marginBottom: '24px' }}>
            <SectionTitle eyebrow="PÉRIMÈTRE" title="Votre profil" />
            <div style={{ padding: '0 20px 20px' }}>
              <div style={{ display: 'grid', gap: '16px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <UserIcon size={20} aria-hidden="true" />
                  <div>
                    <p className="muted" style={{ fontSize: '12px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.04em', margin: '0 0 4px' }}>Identifiant</p>
                    <p style={{ margin: 0, fontSize: '14px' }}>{user.email}</p>
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <UserIcon size={20} aria-hidden="true" />
                  <div>
                    <p className="muted" style={{ fontSize: '12px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.04em', margin: '0 0 4px' }}>Nom affiché</p>
                    <p style={{ margin: 0, fontSize: '14px' }}>{user.displayName ?? 'Non renseigné'}</p>
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <ShieldCheckIcon size={20} aria-hidden="true" />
                  <div>
                    <p className="muted" style={{ fontSize: '12px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.04em', margin: '0 0 4px' }}>Rôle global</p>
                    <div style={{ margin: 0, fontSize: '14px' }}><RoleBadge role={user.role} /></div>
                  </div>
                </div>
              </div>
            </div>
          </section>

          <section className="surface-card" style={{ marginBottom: '24px' }}>
            <SectionTitle eyebrow="PORTÉE" title="Permissions par site" />
            <div style={{ padding: '0 20px 20px' }}>
              {sitesQuery.isPending && (
                <p className="muted">Chargement des sites…</p>
              )}
              {sitesQuery.isError && (
                <p className="helper-error">Impossible de charger la liste des sites.</p>
              )}
              {!sitesQuery.isPending && !sitesQuery.isError && user.siteIds.length === 0 && (
                <p className="muted">Aucun site associé à votre compte.</p>
              )}
              {!sitesQuery.isPending && !sitesQuery.isError && user.siteIds.length > 0 && (
                <div className="incident-table-wrap">
                  <table className="incident-table">
                    <caption className="visually-hidden">Permissions par site</caption>
                    <thead>
                      <tr>
                        <th scope="col">Site</th>
                        <th scope="col">Rôle affecté</th>
                      </tr>
                    </thead>
                    <tbody>
                      {user.siteIds.map((siteId) => {
                        const site = siteMap.get(siteId);
                        const role = authRoleForSite(user, siteId) ?? user.role;
                        return (
                          <tr key={siteId}>
                            <td data-label="Site">
                              <strong>{site?.name ?? `Site ${siteId}`}</strong>
                              {site?.timezone && <small>{site.timezone}</small>}
                            </td>
                            <td data-label="Rôle affecté">
                              <RoleBadge role={role} />
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </section>

          {user.role === 'admin' && (
            <div
              role="status"
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: '12px',
                padding: '16px 20px',
                marginBottom: '24px',
                border: '1px solid var(--color-border)',
                borderRadius: 'var(--radius)',
                background: 'var(--color-card)',
              }}
            >
              <InfoIcon size={20} style={{ flexShrink: 0, marginTop: '2px', color: 'var(--color-accent)' }} aria-hidden="true" />
              <p style={{ margin: 0, fontSize: '14px', lineHeight: 1.5 }}>
                Gestion des comptes utilisateurs disponible côté API uniquement dans cette version pilote.
              </p>
            </div>
          )}

          <section className="surface-card" style={{ marginBottom: '24px' }}>
            <SectionTitle eyebrow="RÉFÉRENCE" title="Matrice des rôles" />
            <div style={{ padding: '0 20px 20px' }}>
              <PermissionMatrix />
            </div>
          </section>

          <section className="surface-card" style={{ marginBottom: '24px' }}>
            <SectionTitle eyebrow="SÉCURITÉ" title="Bonnes pratiques" />
            <div style={{ padding: '0 20px 20px' }}>
              <ul style={{ margin: 0, paddingLeft: '20px', fontSize: '14px', lineHeight: 1.7, color: 'var(--color-card-foreground)' }}>
                <li>Les sessions utilisent des cookies <strong>HttpOnly</strong> et <strong>Secure</strong> pour limiter les risques de vol de jeton.</li>
                <li>La session expire automatiquement après une période d’inactivité ; une reconnexion est requise.</li>
                <li>Les mots de passe sont hachés avec <strong>Argon2id</strong> côté serveur ; aucun secret en clair n’est conservé.</li>
                <li>Privilégiez un rôle minimal (principe du moindre privilège) pour chaque utilisateur et chaque site.</li>
              </ul>
            </div>
          </section>
        </>
      )}
    </section>
  );
}
