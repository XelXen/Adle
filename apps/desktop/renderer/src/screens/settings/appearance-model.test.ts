import { describe, expect, it } from 'vitest';

import { hueName, isPastelTheme, PASTEL_SWATCHES } from './appearance-model';

describe('the colors of Pastel (ADR-074)', () => {
  it('are hues a Pastel theme can be in, each once, with a name of its own', () => {
    const hues = PASTEL_SWATCHES.map((swatch) => swatch.hue);
    expect(new Set(hues).size).toBe(hues.length);
    for (const hue of hues) expect(Number.isInteger(hue) && hue >= 0 && hue <= 359).toBe(true);
    const names = PASTEL_SWATCHES.map((swatch) => swatch.name);
    expect(new Set(names).size).toBe(names.length);
    // The one Pastel starts in is offered.
    expect(hues).toContain(295);
  });

  it('say a hue by the name of its swatch, or of the one it is nearest', () => {
    expect(hueName(160)).toBe('Mint');
    expect(hueName(170)).toBe('Near mint');
    // The short way round the circle: 5 is nearer pink (355) than peach (50).
    expect(hueName(5)).toBe('Near pink');
    expect(hueName(359)).toBe('Near pink');
  });

  it('are offered for Pastel and Pastel dark only', () => {
    expect(isPastelTheme('pastel')).toBe(true);
    expect(isPastelTheme('pastel-dark')).toBe(true);
    expect(isPastelTheme('dark')).toBe(false);
    expect(isPastelTheme('system')).toBe(false);
  });
});
