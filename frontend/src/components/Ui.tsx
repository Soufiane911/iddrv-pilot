import { ArchiveIcon } from '@phosphor-icons/react/Archive';
import { CheckIcon } from '@phosphor-icons/react/Check';
import { HourglassIcon } from '@phosphor-icons/react/Hourglass';
import { WarningIcon } from '@phosphor-icons/react/Warning';
import type { ReactNode } from 'react';

export function formatDate(value?: string | null, withTime = true): string {
  if (!value) return 'N/D';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('fr-FR', withTime ? { dateStyle: 'medium', timeStyle: 'short' } : { dateStyle: 'medium' }).format(date);
}

export function formatNumber(value?: number | null, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return 'N/D';
  return new Intl.NumberFormat('fr-FR', { maximumFractionDigits: digits, minimumFractionDigits: digits }).format(value);
}

export function formatPercent(value?: number | null, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return 'N/D';
  const normalized = value > 1 ? value : value * 100;
  return `${formatNumber(normalized, digits)} %`;
}

export function machineStatusLabel(value?: string | null): string {
  if (value === 'running') return 'En production';
  if (value === 'warning') return 'À surveiller';
  if (value === 'stopped') return 'Arrêtée';
  if (value === 'offline') return 'Hors ligne';
  return 'Statut inconnu';
}

export function incidentSeverityLabel(value: string): string {
  return ({ low: 'Faible', medium: 'Moyenne', high: 'Haute', critical: 'Critique' } as Record<string, string>)[value] ?? value;
}

export function incidentSymptomLabel(value: string): string {
  return ({ short_shot_increase: 'Hausse des pièces incomplètes', flash_increase: 'Hausse des bavures', bubbles_increase: 'Hausse des bulles', warpage_increase: 'Hausse des déformations', dimension_drift: 'Dérive dimensionnelle', quality_anomaly: 'Anomalie qualité' } as Record<string, string>)[value] ?? value.split('_').join(' ');
}

export function defectTypeLabel(value?: string | null): string {
  if (!value) return 'Défaut non classé';
  return ({ short_shot: 'Pièce incomplète', flash: 'Bavure', bubbles: 'Bulles', warpage: 'Déformation', dimension_out_of_tolerance: 'Hors tolérance dimensionnelle', multiple: 'Défauts multiples' } as Record<string, string>)[value] ?? value.split('_').join(' ');
}

export function incidentConfidenceLabel(value?: string | null): string {
  if (!value) return 'Non renseignée';
  return ({ low: 'Faible', medium: 'Moyenne', high: 'Élevée' } as Record<string, string>)[value] ?? value;
}

export function incidentStatusLabel(value: string): string {
  return ({ open: 'Ouvert', reviewed: 'Revu', closed: 'Clos' } as Record<string, string>)[value] ?? value;
}

function StateGlyph({ tone }: { tone: 'loading' | 'error' | 'empty' | 'success' | 'warning' }) {
  if (tone === 'success') return <CheckIcon size={20} weight="bold" />;
  if (tone === 'loading') return <HourglassIcon size={20} />;
  if (tone === 'empty') return <ArchiveIcon size={20} />;
  return <WarningIcon size={20} />;
}

export function StatePanel({ tone, title, text, action, onAction }: { tone: 'loading' | 'error' | 'empty' | 'success' | 'warning'; title: string; text: string; action?: string; onAction?: () => void }) {
  return <div className={`state-card ${tone}`} role={tone === 'error' ? 'alert' : 'status'} aria-live={tone === 'loading' ? 'polite' : undefined}><span className="state-icon" aria-hidden="true"><StateGlyph tone={tone} /></span><div><strong>{title}</strong><p>{text}</p></div>{action && <button type="button" onClick={onAction}>{action}</button>}</div>;
}

export function MetricCard({ label, value, detail, tone = 'neutral' }: { label: string; value: ReactNode; detail?: ReactNode; tone?: 'neutral' | 'good' | 'warning' | 'danger' }) {
  return <div className={`metric-card ${tone}`}><p>{label}</p><strong>{value}</strong>{detail && <span>{detail}</span>}</div>;
}

export function StatusBadge({ value, label }: { value?: string | null; label?: string }) {
  const safe = value ?? 'unknown';
  return <span className={`status-badge status-${safe}`}><span className="status-badge-dot" aria-hidden="true" />{label ?? machineStatusLabel(value)}</span>;
}

export function SectionTitle({ eyebrow, title, children }: { eyebrow?: string; title: string; children?: ReactNode }) {
  return <div className="section-title"><div>{eyebrow && <p className="eyebrow">{eyebrow}</p>}<h2>{title}</h2></div>{children}</div>;
}

export function EmptyPanel({ title, text, action, onAction }: { title: string; text: string; action?: string; onAction?: () => void }) {
  return <div className="empty-panel"><span className="empty-icon" aria-hidden="true"><ArchiveIcon size={22} /></span><h3>{title}</h3><p>{text}</p>{action && <button type="button" onClick={onAction}>{action}</button>}</div>;
}
