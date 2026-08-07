import { Color, MeshStandardMaterial, type MeshStandardMaterialParameters } from 'three';

/**
 * docs/product/visual-system.md: Three.js materials derive only from the documented palette.
 * Tints and shades are computed as lerps toward white or the dark foreground,
 * never as new visible hues.
 */
export const PALETTE = {
  primary: '#334155',
  secondary: '#475569',
  accent: '#059669',
  background: '#F8FAFC',
  foreground: '#0F172A',
  card: '#FFFFFF',
  muted: '#F2F3F4',
  mutedForeground: '#64748B',
  border: '#E6E8EA',
  destructive: '#DC2626',
} as const;

export const STATUS_HEX: Record<string, string> = {
  running: PALETTE.accent,
  warning: PALETTE.secondary,
  stopped: PALETTE.destructive,
  offline: PALETTE.primary,
};

export function statusColor(status?: string | null): string {
  return STATUS_HEX[status ?? 'unknown'] ?? PALETTE.mutedForeground;
}

const colorCache = new Map<string, string>();
const WHITE = new Color(PALETTE.card);
const DARK = new Color(PALETTE.foreground);

function derive(hex: string, target: Color, amount: number): string {
  const key = `${hex}|${target.getHexString()}|${amount}`;
  let cached = colorCache.get(key);
  if (!cached) {
    cached = `#${new Color(hex).lerp(target, amount).getHexString()}`;
    colorCache.set(key, cached);
  }
  return cached;
}

/** Lighter palette derivation (toward white). */
export function tint(hex: string, amount: number): string {
  return derive(hex, WHITE, amount);
}

/** Darker palette derivation (toward the dark foreground). */
export function shade(hex: string, amount: number): string {
  return derive(hex, DARK, amount);
}

const materialCache = new Map<string, MeshStandardMaterial>();

/**
 * Shared static materials: one GPU program per paint/steel finish for the whole
 * scene instead of one per mesh. Per-status emissive parts stay declarative.
 */
export function sharedMaterial(key: string, params: MeshStandardMaterialParameters): MeshStandardMaterial {
  let material = materialCache.get(key);
  if (!material) {
    material = new MeshStandardMaterial(params);
    materialCache.set(key, material);
  }
  return material;
}
