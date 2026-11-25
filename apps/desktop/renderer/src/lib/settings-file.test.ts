import { describe, expect, it } from 'vitest';

import {
  chosenOf,
  EVERY_PART,
  nothingChosen,
  PARTS,
  partsListed,
  passwordProblem,
  setUpNote,
} from './settings-file';

const NONE = { appearance: false, learning: false, voice: false, provider: false, keys: false };

describe('a settings file (ADR-064)', () => {
  it('has five parts, and the keys come last', () => {
    expect(PARTS.map((part) => part.key)).toEqual([
      'appearance',
      'learning',
      'voice',
      'provider',
      'keys',
    ]);
  });

  it('says what it holds in a few words', () => {
    expect(partsListed(EVERY_PART)).toBe('appearance, learning, voice, AI provider and API keys');
    expect(partsListed({ ...NONE, appearance: true, keys: true })).toBe('appearance and API keys');
    expect(partsListed({ ...NONE, voice: true })).toBe('voice');
    expect(partsListed(NONE)).toBe('');
  });

  it('knows when there is nothing to save or bring in', () => {
    expect(nothingChosen(NONE)).toBe(true);
    expect(nothingChosen({ ...NONE, voice: true })).toBe(false);
  });

  it('never asks for a part a file does not have', () => {
    expect(chosenOf(EVERY_PART, { ...NONE, learning: true, keys: true })).toEqual({
      ...NONE,
      learning: true,
      keys: true,
    });
    expect(chosenOf({ ...EVERY_PART, keys: false }, EVERY_PART).keys).toBe(false);
  });

  it('wants a password long enough, typed the same twice', () => {
    expect(passwordProblem('short', 'short')).toBe('Use 8 characters or more.');
    expect(passwordProblem('long enough', 'long enoufh')).toBe('The two passwords are different.');
    expect(passwordProblem('long enough', 'long enough')).toBeNull();
  });

  it('says what setting a voice up downloads, and from where', () => {
    const plan = {
      name: 'Natural',
      setUp: true,
      downloadBytes: 561_000_000,
      sources: [],
      note: '',
    };
    expect(setUpNote(plan)).toBe('Downloads about 0.6 GB.');
    expect(
      setUpNote({ ...plan, sources: ['Hugging Face', 'the Python Package Index', 'GitHub'] }),
    ).toBe('Downloads about 0.6 GB from Hugging Face, the Python Package Index and GitHub.');
    expect(setUpNote({ ...plan, downloadBytes: 40_000_000, sources: ['GitHub'] })).toBe(
      'Downloads about 40 MB from GitHub.',
    );
  });
});
