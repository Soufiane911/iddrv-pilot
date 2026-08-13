import { CheckIcon } from '@phosphor-icons/react/Check';
import { XIcon } from '@phosphor-icons/react/X';
import type { AuthRole } from '../../lib/api';

const ROLES: AuthRole[] = ['viewer', 'analyst', 'supervisor', 'admin'];

const ROLE_LABELS: Record<AuthRole, string> = {
  viewer: 'Lecteur',
  analyst: 'Analyste',
  supervisor: 'Superviseur',
  admin: 'Administrateur',
};

const CAPABILITIES = [
  { key: 'read_workshop', label: 'Lire atelier' },
  { key: 'run_investigation', label: 'Lancer investigation' },
  { key: 'comment_incident', label: 'Commenter incident' },
  { key: 'validate_action', label: 'Valider action' },
  { key: 'manage_accounts', label: 'Gérer comptes' },
] as const;

const MATRIX: Record<AuthRole, Record<(typeof CAPABILITIES)[number]['key'], boolean>> = {
  viewer: {
    read_workshop: true,
    run_investigation: false,
    comment_incident: false,
    validate_action: false,
    manage_accounts: false,
  },
  analyst: {
    read_workshop: true,
    run_investigation: true,
    comment_incident: true,
    validate_action: false,
    manage_accounts: false,
  },
  supervisor: {
    read_workshop: true,
    run_investigation: true,
    comment_incident: true,
    validate_action: true,
    manage_accounts: false,
  },
  admin: {
    read_workshop: true,
    run_investigation: true,
    comment_incident: true,
    validate_action: true,
    manage_accounts: true,
  },
};

export function PermissionMatrix() {
  return (
    <div className="incident-table-wrap">
      <table className="incident-table">
        <caption className="visually-hidden">Matrice des permissions par rôle</caption>
        <thead>
          <tr>
            <th scope="col">Rôle</th>
            {CAPABILITIES.map((cap) => (
              <th key={cap.key} scope="col">{cap.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {ROLES.map((role) => (
            <tr key={role}>
              <td data-label="Rôle">
                <strong>{ROLE_LABELS[role]}</strong>
              </td>
              {CAPABILITIES.map((cap) => {
                const granted = MATRIX[role][cap.key];
                return (
                  <td key={cap.key} data-label={cap.label}>
                    {granted ? (
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', color: '#059669' }}>
                        <CheckIcon size={18} weight="bold" aria-hidden="true" />
                        <span className="visually-hidden">Autorisé</span>
                      </span>
                    ) : (
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', color: '#94A3B8' }}>
                        <XIcon size={18} weight="bold" aria-hidden="true" />
                        <span className="visually-hidden">Non autorisé</span>
                      </span>
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
