import type { ReactNode } from 'react';

export function formatDate(value?: string | null, withTime = true): string {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('fr-FR', withTime ? { dateStyle: 'medium', timeStyle: 'short' } : { dateStyle: 'medium' }).format(date);
}

export function formatNumber(value?: number | null, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return new Intl.NumberFormat('fr-FR', { maximumFractionDigits: digits, minimumFractionDigits: digits }).format(value);
}

export function formatPercent(value?: number | null, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  const normalized = value > 1 ? value : value * 100;
  return `${formatNumber(normalized, digits)} %`;
}

export function machineStatusLabel(value?: string | null): string {
  if (value === 'running') return 'En production';
  if (value === 'warning') return 'À surveiller';
  if (value === 'stopped') return 'Arrêtée';
  return 'Hors ligne';
}

export function incidentSeverityLabel(value: string): string {
  return ({ low: 'Faible', medium: 'Moyenne', high: 'Haute', critical: 'Critique' } as Record<string, string>)[value] ?? value;
}

export function incidentStatusLabel(value: string): string {
  return ({ open: 'Ouvert', reviewed: 'Revu', closed: 'Clos' } as Record<string, string>)[value] ?? value;
}

export function StatePanel({ tone, title, text, action, onAction }: { tone: 'loading' | 'error' | 'empty' | 'success' | 'warning'; title: string; text: string; action?: string; onAction?: () => void }) {
  const icon = tone === 'success' ? '✓' : tone === 'error' ? '!' : tone === 'empty' ? '∅' : tone === 'warning' ? '!' : '…';
  return <div className={`state-card ${tone}`} role={tone === 'error' ? 'alert' : undefined}><span className="state-icon" aria-hidden="true">{icon}</span><div><strong>{title}</strong><p>{text}</p></div>{action && <button type="button" onClick={onAction}>{action}</button>}</div>;
}

export function MetricCard({ label, value, detail, tone = 'neutral' }: { label: string; value: ReactNode; detail?: ReactNode; tone?: 'neutral' | 'good' | 'warning' | 'danger' }) {
  return <div className={`metric-card ${tone}`}><p>{label}</p><strong>{value}</strong>{detail && <span>{detail}</span>}</div>;
}

export function StatusBadge({ value, label }: { value?: string | null; label?: string }) {
  const safe = value ?? 'offline';
  return <span className={`status-badge status-${safe}`}><span className="status-badge-dot" aria-hidden="true" />{label ?? machineStatusLabel(value)}</span>;
}

export function SectionTitle({ eyebrow, title, children }: { eyebrow?: string; title: string; children?: ReactNode }) {
  return <div className="section-title"><div>{eyebrow && <p className="eyebrow">{eyebrow}</p>}<h2>{title}</h2></div>{children}</div>;
}

export function EmptyPanel({ title, text, action, onAction }: { title: string; text: string; action?: string; onAction?: () => void }) {
  return <div className="empty-panel"><span className="empty-icon" aria-hidden="true">∅</span><h3>{title}</h3><p>{text}</p>{action && <button type="button" onClick={onAction}>{action}</button>}</div>;
}
