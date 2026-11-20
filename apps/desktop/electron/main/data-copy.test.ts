import path from 'node:path';

import { describe, expect, it } from 'vitest';

import {
  canErase,
  defaultCopyName,
  isInside,
  parseRestorePath,
  parseSavePath,
  safetyCopiesDir,
} from './data-copy';

/** An absolute path that is valid on the platform running the test. */
const absolute = (...parts: string[]): string => path.resolve('profile-root', ...parts);
const dataDir = absolute('Adle', 'data');

describe('defaultCopyName', () => {
  it('says what the file is and sorts by date', () => {
    expect(defaultCopyName(new Date(2026, 10, 19, 23, 59))).toBe('Adle data 2026-11-19.adle');
    expect(defaultCopyName(new Date(2027, 0, 5))).toBe('Adle data 2027-01-05.adle');
  });
});

describe('isInside', () => {
  it('holds for the folder itself and anything beneath it', () => {
    expect(isInside(dataDir, dataDir)).toBe(true);
    expect(isInside(dataDir, path.join(dataDir, 'backups', 'copy.adle'))).toBe(true);
    expect(isInside(dataDir, path.join(dataDir, 'a', '..', 'b.adle'))).toBe(true);
  });

  it('does not hold for a neighbour, a parent, or a name that merely starts the same', () => {
    expect(isInside(dataDir, absolute('Adle', 'copy.adle'))).toBe(false);
    expect(isInside(dataDir, absolute('Adle'))).toBe(false);
    expect(isInside(dataDir, absolute('Adle', 'data-old', 'copy.adle'))).toBe(false);
    expect(isInside(dataDir, path.join(dataDir, '..', 'copy.adle'))).toBe(false);
  });
});

describe('parseSavePath', () => {
  it('accepts a file with the right ending outside the data folder', () => {
    const chosen = absolute('Documents', 'Adle data 2026-11-19.adle');
    expect(parseSavePath(chosen, dataDir)).toEqual({ ok: true, path: chosen, amended: false });
    const shouted = absolute('Documents', 'COPY.ADLE');
    expect(parseSavePath(shouted, dataDir)).toEqual({ ok: true, path: shouted, amended: false });
  });

  it('adds the ending when the dialog did not, and says so', () => {
    // The dialog asked about replacing "my copy", not "my copy.adle".
    expect(parseSavePath(absolute('Documents', 'my copy'), dataDir)).toEqual({
      ok: true,
      path: absolute('Documents', 'my copy.adle'),
      amended: true,
    });
    expect(parseSavePath(absolute('Documents', 'notes.txt'), dataDir)).toEqual({
      ok: true,
      path: absolute('Documents', 'notes.txt.adle'),
      amended: true,
    });
  });

  it.each([
    ['the data folder', path.join(dataDir, 'copy.adle')],
    ['the folder of safety copies', path.join(dataDir, 'backups', 'copy.adle')],
    ['the data folder by a roundabout way', path.join(dataDir, '..', 'data', 'copy.adle')],
    ['the data folder once the ending is added', path.join(dataDir, 'copy')],
  ])('refuses a place inside %s', (_label, chosen) => {
    const parsed = parseSavePath(chosen, dataDir);
    expect(parsed.ok).toBe(false);
    expect(parsed).toHaveProperty('message', "Choose a place outside Adle's own data folder.");
  });

  it.each([
    ['a relative path', 'copy.adle'],
    ['an empty string', ''],
    ['a NUL in the name', `${absolute('copy')}\0.adle`],
    ['a path of absurd length', absolute('x'.repeat(5000) + '.adle')],
    ['a number', 42],
    ['nothing', undefined],
    ['a list', [absolute('copy.adle')]],
  ])('refuses %s without repeating it', (_label, chosen) => {
    const parsed = parseSavePath(chosen, dataDir);
    expect(parsed).toEqual({ ok: false, message: 'That file name cannot be used.' });
  });
});

describe('parseRestorePath', () => {
  it('accepts a saved copy, wherever it is', () => {
    const chosen = absolute('Documents', 'Adle data 2026-11-19.adle');
    expect(parseRestorePath(chosen)).toEqual({ ok: true, path: chosen });
  });

  it('accepts one of the safety copies Adle keeps itself', () => {
    const safetyCopy = path.join(safetyCopiesDir(dataDir), 'adle-replaced-20261119T101500Z.db');
    expect(parseRestorePath(safetyCopy)).toEqual({ ok: true, path: safetyCopy });
  });

  it.each([
    ['a document', absolute('Documents', 'lecture-notes.pdf')],
    ['a file with no ending', absolute('Documents', 'copy')],
    ['a near miss', absolute('Documents', 'copy.adle.txt')],
  ])('refuses %s and says what a copy looks like', (_label, chosen) => {
    expect(parseRestorePath(chosen)).toEqual({
      ok: false,
      message: 'Choose a copy of your data: a file that ends in .adle.',
    });
  });

  it.each([
    ['a relative path', 'copy.adle'],
    ['a NUL in the name', `${absolute('copy')}\0.adle`],
    ['a number', 7],
    ['nothing', null],
  ])('refuses %s', (_label, chosen) => {
    expect(parseRestorePath(chosen)).toEqual({ ok: false, message: 'That file cannot be used.' });
  });
});

describe('safetyCopiesDir', () => {
  it('is the folder the core calls "backups", inside the data folder', () => {
    expect(safetyCopiesDir(dataDir)).toBe(path.join(dataDir, 'backups'));
    expect(isInside(dataDir, safetyCopiesDir(dataDir))).toBe(true);
  });
});

describe('canErase', () => {
  it('allows a folder of its own, well below the root of a disk', () => {
    expect(canErase(dataDir)).toBe(true);
  });

  it.each([
    ['a relative path', path.join('Adle', 'data')],
    ['the root of a disk', path.parse(dataDir).root],
    ['a folder directly under the root', path.join(path.parse(dataDir).root, 'data')],
    ['an empty string', ''],
  ])('refuses %s', (_label, folder) => {
    expect(canErase(folder)).toBe(false);
  });
});
