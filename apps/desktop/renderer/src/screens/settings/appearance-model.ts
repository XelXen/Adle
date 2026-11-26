import type { ColorSwatch } from '@adle/design-system';

import type { ThemePreference } from '../../lib/bridge';

/**
 * The colors offered for Pastel and Pastel dark (ADR-074), by their hue round the OKLCH
 * circle. Any hue between them can be had with the slider beside them.
 */
export const PASTEL_SWATCHES: readonly ColorSwatch[] = [
  { hue: 355, name: 'Pink' },
  { hue: 50, name: 'Peach' },
  { hue: 90, name: 'Butter' },
  { hue: 125, name: 'Sage' },
  { hue: 160, name: 'Mint' },
  { hue: 195, name: 'Aqua' },
  { hue: 235, name: 'Sky' },
  { hue: 265, name: 'Periwinkle' },
  { hue: 295, name: 'Lavender' },
  { hue: 330, name: 'Lilac' },
];

/** Whether the theme is one of the two the learner picks a color for. */
export function isPastelTheme(theme: ThemePreference): boolean {
  return theme === 'pastel' || theme === 'pastel-dark';
}

/** How far apart two hues are, the short way round the circle. */
function apart(one: number, other: number): number {
  const difference = Math.abs(one - other) % 360;
  return Math.min(difference, 360 - difference);
}

/** A hue in words: the name of its swatch, or of the one it is nearest. */
export function hueName(hue: number): string {
  const nearest = [...PASTEL_SWATCHES].sort((a, b) => apart(a.hue, hue) - apart(b.hue, hue))[0]!;
  return nearest.hue === hue ? nearest.name : `Near ${nearest.name.toLowerCase()}`;
}
