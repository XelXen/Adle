import { describe, expect, it } from 'vitest';

import { noReader } from './read-pictures-model';

const provider = (display_name: string, reads_pictures: boolean, key_configured: boolean) => ({
  display_name,
  reads_pictures,
  key_configured,
});

describe('noReader (ADR-060)', () => {
  it('says whose key would let the pictures be read', () => {
    expect(
      noReader([provider('AIHubMix', false, true), provider('NVIDIA NIM', true, false)], 2),
    ).toBe('To read them, add a key for NVIDIA NIM in Settings.');
  });

  it('says to choose the provider that reads pictures when it has a key already', () => {
    expect(
      noReader([provider('AIHubMix', false, true), provider('NVIDIA NIM', true, true)], 1),
    ).toBe('To read it, choose NVIDIA NIM or Automatic in Settings.');
  });

  it('says plainly when no provider reads pictures at all', () => {
    expect(noReader([provider('Custom endpoint', false, true)], 3)).toBe(
      'None of your AI providers can read pictures.',
    );
  });
});
