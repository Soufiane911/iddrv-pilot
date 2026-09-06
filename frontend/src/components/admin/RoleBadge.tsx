import type { AuthRole } from '../../lib/api';

const ROLE_STYLES: Record<AuthRole, { background: string; color: string; label: string }> = {
  admin: { background: '#059669', color: '#FFFFFF', label: 'Administrateur' },
  supervisor: { background: '#475569', color: '#FFFFFF', label: 'Superviseur' },
  analyst: { background: '#334155', color: '#FFFFFF', label: 'Analyste' },
  viewer: { background: '#64748B', color: '#FFFFFF', label: 'Lecteur' },
};

interface RoleBadgeProps {
  role: AuthRole;
}

export function RoleBadge({ role }: RoleBadgeProps) {
  const style = ROLE_STYLES[role];
  return (
    <span
      aria-label={`Rôle : ${style.label}`}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '6px',
        padding: '4px 10px',
        borderRadius: '2px',
        background: style.background,
        color: style.color,
        fontSize: '13px',
        fontWeight: 600,
        lineHeight: 1.4,
      }}
    >
      <span
        aria-hidden="true"
        style={{
          width: '7px',
          height: '7px',
          borderRadius: '50%',
          background: style.color,
          opacity: 0.9,
        }}
      />
      {style.label}
    </span>
  );
}
