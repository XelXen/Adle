/**
 * Guards the design tokens: every theme defines every colour, text and control
 * colours meet WCAG contrast, the scene palette mirrors the tokens, and no
 * component bypasses the tokens with a raw colour.
 *
 * @vitest-environment node
 */
import { type Dirent, readdirSync, readFileSync } from 'node:fs';
import path from 'node:path';

import { describe, expect, it } from 'vitest';

import { SCENE_PALETTE, SCENE_PALETTE_TOKENS } from './scene-palette';

const repoRoot = path.resolve(import.meta.dirname, '..', '..', '..');
const tokensCss = readFileSync(path.join(import.meta.dirname, 'styles', 'tokens.css'), 'utf8');

function declarations(block: string): Map<string, string> {
  const map = new Map<string, string>();
  for (const match of block.matchAll(/(--ad-[a-z0-9-]+):\s*([^;]+);/g)) {
    map.set(match[1]!, match[2]!.trim());
  }
  return map;
}

const darkStart = tokensCss.indexOf('@media (prefers-color-scheme: dark)');
const darkEnd = tokensCss.indexOf('@media (prefers-reduced-motion');
const light = declarations(tokensCss.slice(0, darkStart));
const dark = new Map([...light, ...declarations(tokensCss.slice(darkStart, darkEnd))]);

function luminance(hex: string): number {
  const channels = [1, 3, 5].map(
    (offset) => Number.parseInt(hex.slice(offset, offset + 2), 16) / 255,
  );
  const [r, g, b] = channels.map((value) =>
    value <= 0.03928 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4,
  ) as [number, number, number];
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrast(foreground: string, background: string): number {
  const [lighter, darker] = [luminance(foreground), luminance(background)].sort(
    (a, b) => b - a,
  ) as [number, number];
  return (lighter + 0.05) / (darker + 0.05);
}

const TEXT = 4.5; // WCAG 2.2 AA, normal text
const GRAPHIC = 3; // WCAG 2.2 AA, UI components and large text

/** [foreground token, background token, minimum ratio] */
const PAIRS: readonly (readonly [string, string, number])[] = [
  ['ink', 'canvas', 7],
  ['ink', 'page', 7],
  ['ink', 'surface', 7],
  ['ink', 'surface-subtle', 7],
  ['ink', 'surface-sunken', 7],
  ['muted', 'canvas', TEXT],
  ['muted', 'page', TEXT],
  ['muted', 'surface', TEXT],
  ['muted', 'surface-subtle', TEXT],
  ['muted', 'surface-sunken', TEXT],
  ['faint', 'canvas', TEXT],
  ['faint', 'page', TEXT],
  ['faint', 'surface', TEXT],
  ['faint', 'surface-subtle', TEXT],
  ['primary-text', 'page', TEXT],
  ['primary-text', 'surface-subtle', TEXT],
  ['success-text', 'page', TEXT],
  ['danger-text', 'page', TEXT],
  ['border-strong', 'page', GRAPHIC],
  ['focus', 'page', GRAPHIC],
  ['primary', 'page', GRAPHIC],
  ['action', 'page', GRAPHIC],
  ['scene-ink', 'scene-background', 7],
  ['scene-muted', 'scene-background', TEXT],
  ['on-action', 'action', TEXT],
  ['on-action', 'action-hover', TEXT],
  ['on-action', 'action-pressed', TEXT],
  ['on-danger', 'danger', TEXT],
  ['on-danger', 'danger-hover', TEXT],
  ['primary-text', 'surface', TEXT],
  ['primary-text', 'canvas', TEXT],
  ['primary-text', 'primary-soft', TEXT],
  ['success-text', 'surface', TEXT],
  ['success-text', 'success-soft', TEXT],
  ['ink', 'success-soft', TEXT],
  ['brand-ink', 'surface', 7],
  ['brand-ink', 'canvas', 7],
  ['primary', 'canvas', GRAPHIC],
  ['sun-text', 'sun-soft', TEXT],
  ['coral-text', 'coral-soft', TEXT],
  ['blue-text', 'blue-soft', TEXT],
  ['violet-text', 'violet-soft', TEXT],
  ['danger-text', 'danger-soft', TEXT],
  ['danger-text', 'surface', TEXT],
  ['ink', 'primary-soft', TEXT],
  ['ink', 'blue-soft', TEXT],
  ['ink', 'sun-soft', TEXT],
  ['ink', 'danger-soft', TEXT],
  ['border-strong', 'surface', GRAPHIC],
  ['border-strong', 'canvas', GRAPHIC],
  ['focus', 'surface', GRAPHIC],
  ['focus', 'canvas', GRAPHIC],
  ['primary', 'surface', GRAPHIC],
  ['action', 'surface', GRAPHIC],
];

describe.each([
  ['light', light],
  ['dark', dark],
])('%s theme', (_name, theme) => {
  it('defines every colour token as a hex value or an rgb() overlay', () => {
    const colours = [...theme].filter(([name]) => name.startsWith('--ad-color-'));
    expect(colours.length).toBeGreaterThan(30);
    for (const [name, value] of colours) {
      expect(value, name).toMatch(/^(#[0-9a-f]{6}|rgb\([^)]+\))$/);
    }
  });

  it.each(PAIRS)('%s on %s has at least %s:1 contrast', (foreground, background, minimum) => {
    const fg = theme.get(`--ad-color-${foreground}`);
    const bg = theme.get(`--ad-color-${background}`);
    expect(fg, foreground).toBeDefined();
    expect(bg, background).toBeDefined();
    expect(contrast(fg!, bg!)).toBeGreaterThanOrEqual(minimum);
  });
});

describe('dark theme', () => {
  it('redefines every colour rather than inheriting a light value', () => {
    const darkOnly = declarations(tokensCss.slice(darkStart, darkEnd));
    const missing = [...light.keys()].filter(
      (name) => name.startsWith('--ad-color-') && !darkOnly.has(name),
    );
    expect(missing).toEqual([]);
  });
});

describe('scene palette', () => {
  it.each(['light', 'dark'] as const)('mirrors the %s tokens exactly', (name) => {
    const theme = name === 'light' ? light : dark;
    for (const [colour, token] of Object.entries(SCENE_PALETTE_TOKENS)) {
      const expected = theme.get(token)?.toUpperCase();
      expect(SCENE_PALETTE[name][colour as keyof typeof SCENE_PALETTE_TOKENS], colour).toBe(
        expected,
      );
    }
  });

  it.each(['light', 'dark'] as const)('keeps scene text readable on the %s stage', (name) => {
    const palette = SCENE_PALETTE[name];
    expect(contrast(palette.ink, palette.background)).toBeGreaterThanOrEqual(7);
    expect(contrast(palette.muted, palette.background)).toBeGreaterThanOrEqual(TEXT);
    for (const accent of ['green', 'coral', 'blue', 'violet'] as const) {
      expect(contrast(palette[accent], palette.background), accent).toBeGreaterThanOrEqual(2.5);
    }
  });
});

describe('token discipline', () => {
  const styleRoots = [
    path.join(repoRoot, 'packages', 'design-system', 'src', 'components'),
    path.join(repoRoot, 'apps', 'desktop', 'renderer', 'src'),
  ];

  function cssFiles(directory: string): string[] {
    return readdirSync(directory, { withFileTypes: true }).flatMap((entry: Dirent) => {
      const full = path.join(directory, entry.name);
      if (entry.isDirectory()) return cssFiles(full);
      return entry.name.endsWith('.css') ? [full] : [];
    });
  }

  it('uses no raw colours outside tokens.css', () => {
    const offenders: string[] = [];
    for (const file of styleRoots.flatMap(cssFiles)) {
      const css = readFileSync(file, 'utf8').replace(/\/\*[\s\S]*?\*\//g, '');
      if (/#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(/.test(css)) {
        offenders.push(path.relative(repoRoot, file));
      }
    }
    expect(offenders).toEqual([]);
  });
});
