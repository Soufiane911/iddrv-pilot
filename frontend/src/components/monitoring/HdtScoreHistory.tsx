import { useMemo } from 'react';

interface HdtHistoryEntry {
  id: string;
  timestamp: string;
  anomalyScore: number;
  threshold: number;
  alert: boolean;
  machineErpRef: string;
  signals: { feature: string; volatility: number }[];
}

const STORAGE_KEY = 'iddrv:hdt-history';
const MAX_ENTRIES = 20;
const SVG_WIDTH = 600;
const SVG_HEIGHT = 160;
const PADDING = { top: 16, right: 16, bottom: 32, left: 40 };

function loadHistory(): HdtHistoryEntry[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as HdtHistoryEntry[];
    return Array.isArray(parsed) ? parsed.slice(0, MAX_ENTRIES).reverse() : [];
  } catch {
    return [];
  }
}

interface Props {
  refreshKey?: number;
}

export function HdtScoreHistory({ refreshKey = 0 }: Props) {
  // Intentional external-key re-computation pattern; localStorage is the source of truth.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const history = useMemo(() => loadHistory(), [refreshKey]);

  if (history.length === 0) {
    return (
      <div style={{ padding: '16px', color: 'var(--color-muted-foreground)', fontSize: '14px' }}>
        Aucune prédiction dans l'historique. Utilisez le simulateur pour générer des scores.
      </div>
    );
  }

  const plotWidth = SVG_WIDTH - PADDING.left - PADDING.right;
  const plotHeight = SVG_HEIGHT - PADDING.top - PADDING.bottom;

  const maxScore = Math.max(...history.map((h) => h.anomalyScore), ...history.map((h) => h.threshold), 1);
  const minScore = Math.min(...history.map((h) => h.anomalyScore), 0);
  const scoreRange = maxScore - minScore || 1;

  const xFor = (index: number) => PADDING.left + (index / Math.max(history.length - 1, 1)) * plotWidth;
  const yFor = (value: number) => PADDING.top + plotHeight - ((value - minScore) / scoreRange) * plotHeight;

  const thresholdY = yFor(history[0]?.threshold ?? 0.41);

  const pathD = history
    .map((entry, index) => `${index === 0 ? 'M' : 'L'} ${xFor(index)} ${yFor(entry.anomalyScore)}`)
    .join(' ');

  return (
    <div role="region" aria-label="Graphique d'évolution des scores HDT">
      <svg
        viewBox={`0 0 ${SVG_WIDTH} ${SVG_HEIGHT}`}
        style={{ width: '100%', height: 'auto', maxWidth: '600px' }}
        aria-hidden="false"
        role="img"
        aria-label={`Évolution des scores HDT sur les ${history.length} dernières prédictions`}
      >
        {/* Axes */}
        <line x1={PADDING.left} y1={PADDING.top + plotHeight} x2={PADDING.left + plotWidth} y2={PADDING.top + plotHeight} stroke="var(--color-border)" strokeWidth={1} />
        <line x1={PADDING.left} y1={PADDING.top} x2={PADDING.left} y2={PADDING.top + plotHeight} stroke="var(--color-border)" strokeWidth={1} />

        {/* Threshold line */}
        <line x1={PADDING.left} y1={thresholdY} x2={PADDING.left + plotWidth} y2={thresholdY} stroke="#DC2626" strokeWidth={1.5} strokeDasharray="4 4" />
        <text x={PADDING.left + plotWidth + 4} y={thresholdY + 4} fill="#DC2626" fontSize={10} fontWeight={600}>Seuil</text>

        {/* Score line */}
        <path d={pathD} fill="none" stroke="#334155" strokeWidth={2} />

        {/* Data points */}
        {history.map((entry, index) => (
          <g key={entry.id}>
            <circle
              cx={xFor(index)}
              cy={yFor(entry.anomalyScore)}
              r={4}
              fill={entry.alert ? '#DC2626' : '#059669'}
              stroke="#FFFFFF"
              strokeWidth={1.5}
            />
            <title>
              {`Score: ${entry.anomalyScore.toFixed(3)} — ${entry.alert ? 'Alerte' : 'Normal'} (${new Date(entry.timestamp).toLocaleString('fr-FR')})`}
            </title>
          </g>
        ))}

        {/* Y axis labels */}
        <text x={PADDING.left - 8} y={PADDING.top + 4} textAnchor="end" fill="var(--color-muted-foreground)" fontSize={10}>{maxScore.toFixed(2)}</text>
        <text x={PADDING.left - 8} y={PADDING.top + plotHeight + 4} textAnchor="end" fill="var(--color-muted-foreground)" fontSize={10}>{minScore.toFixed(2)}</text>

        {/* X axis label */}
        <text x={PADDING.left + plotWidth / 2} y={SVG_HEIGHT - 4} textAnchor="middle" fill="var(--color-muted-foreground)" fontSize={10}>Prédictions (temps)</text>
      </svg>
    </div>
  );
}
