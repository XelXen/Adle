import { readFileSync } from 'node:fs';
import path from 'node:path';

import { describe, expect, it } from 'vitest';

import { oklchToHex, PASTEL_WINDOW, pastelWindowColors } from './pastel';
import { colorSchemeOf, isPastel } from './ui-state';

const tokens = readFileSync(
  path.resolve(
    import.meta.dirname,
    '..',
    '..',
    '..',
    '..',
    'packages',
    'design-system',
    'src',
    'styles',
    'tokens.css',
  ),
  'utf8',
);

/** [lightness, chroma] of a token in the Pastel block of one scheme. */
function pastelToken(scheme: 'light' | 'dark', name: string): [number, number] {
  const start = tokens.indexOf('/* ---- Pastel and Pastel dark');
  expect(start).toBeGreaterThan(0);
  const darkStart = tokens.indexOf('@media (prefers-color-scheme: dark)', start);
  const block = scheme === 'light' ? tokens.slice(start, darkStart) : tokens.slice(darkStart);
  const found = new RegExp(
    `--ad-color-${name}: oklch\\(([0-9.]+) ([0-9.]+) var\\(--ad-pastel-hue\\)\\);`,
  ).exec(block);
  expect(found, `${scheme} ${name}`).not.toBeNull();
  return [Number(found![1]), Number(found![2])];
}

describe('the window in a Pastel theme (ADR-074)', () => {
  it('is drawn in the canvas and the ink the page has', () => {
    for (const scheme of ['light', 'dark'] as const) {
      expect(pastelToken(scheme, 'canvas')).toEqual(PASTEL_WINDOW[scheme].canvas);
      expect(pastelToken(scheme, 'ink')).toEqual(PASTEL_WINDOW[scheme].ink);
    }
  });

  it('works out a color as a screen shows it', () => {
    // Without chroma, OKLCH is a gray: white, black, and the gray of lightness 0.5.
    expect(oklchToHex(1, 0, 0)).toBe('#FFFFFF');
    expect(oklchToHex(0, 0, 0)).toBe('#000000');
    expect(oklchToHex(0.5, 0, 123)).toBe('#636363');
    // The primaries, as CSS Color 4 gives them.
    expect(oklchToHex(0.627955, 0.257683, 29.2339)).toBe('#FF0000');
    expect(oklchToHex(0.86644, 0.294827, 142.4953)).toBe('#00FF00');
    expect(oklchToHex(0.452014, 0.313214, 264.052)).toBe('#0000FF');
  });

  it('is pale in Pastel and dark in Pastel dark, in the color chosen', () => {
    const light = pastelWindowColors(160, false);
    const dark = pastelWindowColors(160, true);
    expect(light.canvas).toBe(oklchToHex(0.925, 0.034, 160));
    expect(dark.canvas).toBe(oklchToHex(0.17, 0.02, 160));
    // A mint, not a gray: more green than red or blue.
    const [r, g, b] = [1, 3, 5].map((at) => Number.parseInt(light.canvas.slice(at, at + 2), 16));
    expect(g).toBeGreaterThan(r!);
    expect(g).toBeGreaterThan(b!);
    expect(pastelWindowColors(300, false).canvas).not.toBe(light.canvas);
  });

  it('is the light scheme in Pastel and the dark one in Pastel dark', () => {
    expect(colorSchemeOf('pastel')).toBe('light');
    expect(colorSchemeOf('pastel-dark')).toBe('dark');
    expect(colorSchemeOf('system')).toBe('system');
    expect(colorSchemeOf('dark')).toBe('dark');
    expect(isPastel('pastel-dark')).toBe(true);
    expect(isPastel('light')).toBe(false);
  });
});
