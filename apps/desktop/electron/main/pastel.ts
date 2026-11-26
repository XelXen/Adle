/**
 * What the window draws itself in the Pastel themes (ADR-074): its ground before the page
 * paints, and the strip its buttons sit on, in the colors the page has. The page's colors
 * are the tokens of `tokens.css`, written in OKLCH with the learner's hue; these are the
 * same two of them, worked out the same way, because the window takes only a hex color.
 * `pastel.test.ts` checks that the numbers here are the ones in the tokens.
 */

/** [lightness, chroma] of the canvas and the ink, in each scheme. */
export const PASTEL_WINDOW = {
  light: { canvas: [0.925, 0.034], ink: [0.25, 0.03] },
  dark: { canvas: [0.17, 0.02], ink: [0.95, 0.012] },
} as const;

/** An OKLCH color as the hex sRGB color a screen shows, clipped to what sRGB can show. */
export function oklchToHex(lightness: number, chroma: number, hue: number): string {
  const radians = (hue * Math.PI) / 180;
  const a = chroma * Math.cos(radians);
  const b = chroma * Math.sin(radians);
  const l = (lightness + 0.3963377774 * a + 0.2158037573 * b) ** 3;
  const m = (lightness - 0.1055613458 * a - 0.0638541728 * b) ** 3;
  const s = (lightness - 0.0894841775 * a - 1.291485548 * b) ** 3;
  const linear = [
    4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
    -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
    -0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s,
  ];
  return `#${linear
    .map((value) => (value <= 0.0031308 ? 12.92 * value : 1.055 * value ** (1 / 2.4) - 0.055))
    .map((value) => Math.round(Math.min(1, Math.max(0, value)) * 255))
    .map((value) => value.toString(16).padStart(2, '0').toUpperCase())
    .join('')}`;
}

/** The canvas and the ink of a Pastel theme in the given hue. */
export function pastelWindowColors(hue: number, dark: boolean): { canvas: string; ink: string } {
  const { canvas, ink } = PASTEL_WINDOW[dark ? 'dark' : 'light'];
  return { canvas: oklchToHex(canvas[0], canvas[1], hue), ink: oklchToHex(ink[0], ink[1], hue) };
}
