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
  ['stage-ink', 'stage', 7],
  ['stage-muted', 'stage', TEXT],
  ['stage-ink', 'stage-mark', 7],
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

/**
 * Pastel and Pastel dark (ADR-074): the light and the dark theme with some of their tokens
 * in OKLCH, at the learner's hue. Each is worked out as a screen shows it, for every hue.
 */
const pastelStart = tokensCss.indexOf('/* ---- Pastel and Pastel dark');
const pastelDarkStart = tokensCss.indexOf('@media (prefers-color-scheme: dark)', pastelStart);
const PASTEL_VALUE = /^oklch\(([0-9.]+) ([0-9.]+) var\(--ad-pastel-hue\)\)$/;

/** An OKLCH color in linear sRGB, unclipped, so that what sRGB cannot show can be seen. */
function oklchToLinear(lightness: number, chroma: number, hue: number): [number, number, number] {
  const a = chroma * Math.cos((hue * Math.PI) / 180);
  const b = chroma * Math.sin((hue * Math.PI) / 180);
  const l = (lightness + 0.3963377774 * a + 0.2158037573 * b) ** 3;
  const m = (lightness - 0.1055613458 * a - 0.0638541728 * b) ** 3;
  const s = (lightness - 0.0894841775 * a - 1.291485548 * b) ** 3;
  return [
    4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
    -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
    -0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s,
  ];
}

function oklchToHex(lightness: number, chroma: number, hue: number): string {
  return `#${oklchToLinear(lightness, chroma, hue)
    .map((value) => (value <= 0.0031308 ? 12.92 * value : 1.055 * value ** (1 / 2.4) - 0.055))
    .map((value) => Math.round(Math.min(1, Math.max(0, value)) * 255))
    .map((value) => value.toString(16).padStart(2, '0'))
    .join('')}`;
}

const pastelLight = declarations(tokensCss.slice(pastelStart, pastelDarkStart));
const pastelDark = declarations(tokensCss.slice(pastelDarkStart));

/** A theme as it is in one hue: its own tokens, and Pastel's worked out at that hue. */
function inHue(base: Map<string, string>, pastel: Map<string, string>, hue: number) {
  const theme = new Map(base);
  for (const [name, value] of pastel) {
    const found = PASTEL_VALUE.exec(value);
    if (found) theme.set(name, oklchToHex(Number(found[1]), Number(found[2]), hue));
  }
  return theme;
}

const HUES = Array.from({ length: 360 }, (_, hue) => hue);

describe('Pastel dark', () => {
  it('sets again everything Pastel sets, so nothing light is left in it', () => {
    // Pastel's own block applies in the dark scheme too: Pastel dark must cover all of it.
    expect([...pastelLight.keys()].filter((name) => !pastelDark.has(name))).toEqual([]);
  });
});

describe.each([
  ['Pastel', light, pastelLight],
  ['Pastel dark', dark, pastelDark],
])('the %s theme', (_name, base, pastel) => {
  it('tints the grounds, the text, the borders and the one color, and nothing else', () => {
    const tinted = [...pastel.keys()].filter((name) => name.startsWith('--ad-color-'));
    expect(tinted).toEqual(
      expect.arrayContaining([
        '--ad-color-canvas',
        '--ad-color-page',
        '--ad-color-surface',
        '--ad-color-ink',
        '--ad-color-muted',
        '--ad-color-border-strong',
        '--ad-color-action',
        '--ad-color-primary-text',
      ]),
    );
    // What a color means is the same in every theme, and so are the scene's colors.
    for (const name of tinted) {
      expect(name).toMatch(
        /^--ad-color-(canvas|page|surface|ink|muted|faint|border|primary|action|on-action)/,
      );
      expect(pastel.get(name), name).toMatch(PASTEL_VALUE);
    }
  });

  it('has colors a screen can show, in every hue', () => {
    const outside: string[] = [];
    for (const [name, value] of pastel) {
      const found = PASTEL_VALUE.exec(value);
      if (!found) continue;
      for (const hue of HUES) {
        const channels = oklchToLinear(Number(found[1]), Number(found[2]), hue);
        if (channels.some((channel) => channel < -0.0005 || channel > 1.0005)) {
          outside.push(`${name} at ${hue}`);
          break;
        }
      }
    }
    expect(outside).toEqual([]);
  });

  it.each(PAIRS)('%s on %s has at least %s:1 contrast in every hue', (fg, bg, minimum) => {
    let worst = Number.POSITIVE_INFINITY;
    let at = 0;
    for (const hue of HUES) {
      const theme = inHue(base, pastel, hue);
      const ratio = contrast(theme.get(`--ad-color-${fg}`)!, theme.get(`--ad-color-${bg}`)!);
      if (ratio < worst) [worst, at] = [ratio, hue];
    }
    expect(worst, `at hue ${at}`).toBeGreaterThanOrEqual(minimum);
  });
});

describe('dark theme', () => {
  it('redefines every colour rather than inheriting a light value', () => {
    const darkOnly = declarations(tokensCss.slice(darkStart, darkEnd));
    const missing = [...light.keys()].filter(
      (name) =>
        name.startsWith('--ad-color-') &&
        // The lesson's screen is one dark surface in either theme, on purpose.
        !name.startsWith('--ad-color-stage') &&
        !darkOnly.has(name),
    );
    expect(missing).toEqual([]);
    expect([...darkOnly.keys()].filter((name) => name.startsWith('--ad-color-stage'))).toEqual([]);
  });
});

describe('the lesson’s screen', () => {
  it('is the dark scene palette’s stage, in both themes', () => {
    // A lesson's pictures are always drawn with the dark palette (ADR-035): the surface
    // around them has to be the one they were drawn for, whatever the theme.
    for (const theme of [light, dark]) {
      expect(theme.get('--ad-color-stage')?.toUpperCase()).toBe(SCENE_PALETTE.dark.background);
      expect(theme.get('--ad-color-stage-ink')?.toUpperCase()).toBe(SCENE_PALETTE.dark.ink);
      expect(theme.get('--ad-color-stage-muted')?.toUpperCase()).toBe(SCENE_PALETTE.dark.muted);
    }
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
