import path from 'node:path';

import { describe, expect, it } from 'vitest';

import {
  MAX_IMPORT_FILES,
  parseCourseId,
  parseImportPaths,
  SOURCE_FILE_EXTENSIONS,
} from './imports';

/** An absolute path that is valid on the platform running the test. */
const absolute = (name: string): string => path.resolve('some-folder', name);

describe('parseCourseId', () => {
  it('accepts an identifier in the form the core generates', () => {
    expect(parseCourseId('crs_0123456789abcdef0123')).toBe('crs_0123456789abcdef0123');
  });

  it.each([
    ['another kind of id', 'src_0123456789abcdef0123'],
    ['upper-case hex', 'crs_0123456789ABCDEF0123'],
    ['too short', 'crs_0123'],
    ['too long', 'crs_0123456789abcdef01234'],
    ['a path', 'crs_0123456789abcdef0123/../x'],
    ['surrounding space', ' crs_0123456789abcdef0123'],
    ['a number', 42],
    ['nothing', undefined],
    ['an object', { id: 'crs_0123456789abcdef0123' }],
  ])('rejects %s', (_label, value) => {
    expect(parseCourseId(value)).toBeNull();
  });
});

describe('parseImportPaths', () => {
  it('accepts absolute paths and removes repeats', () => {
    const notes = absolute('notes.pdf');
    const syllabus = absolute('syllabus.md');
    expect(parseImportPaths([notes, syllabus, notes])).toEqual({
      ok: true,
      paths: [notes, syllabus],
    });
  });

  it.each([
    ['not a list', 'C:/notes.pdf'],
    ['an empty list', []],
    ['nothing', undefined],
  ])('reports %s as "no files"', (_label, value) => {
    expect(parseImportPaths(value)).toMatchObject({ ok: false, code: 'no_files' });
  });

  it('limits how many files one import may carry', () => {
    const many = Array.from({ length: MAX_IMPORT_FILES + 1 }, (_, index) =>
      absolute(`file-${index}.txt`),
    );
    expect(parseImportPaths(many)).toMatchObject({ ok: false, code: 'too_many_files' });
    expect(parseImportPaths(many.slice(0, MAX_IMPORT_FILES))).toMatchObject({ ok: true });
  });

  it.each([
    ['a relative path', 'notes.pdf'],
    ['a relative path that climbs', '../../notes.pdf'],
    ['an empty string', ''],
    ['a path containing a NUL byte', `${absolute('notes')}${String.fromCharCode(0)}.pdf`],
    ['an over-long path', absolute('x'.repeat(5000))],
    ['a number', 7],
    ['an object', { path: absolute('notes.pdf') }],
  ])('rejects the whole request when it contains %s', (_label, entry) => {
    const result = parseImportPaths([absolute('fine.txt'), entry]);
    expect(result).toMatchObject({ ok: false, code: 'invalid_request' });
  });

  it('never repeats a submitted path in its error message', () => {
    const result = parseImportPaths(['relative/secret-name.pdf']);
    expect(result.ok).toBe(false);
    expect(JSON.stringify(result)).not.toContain('secret-name');
  });
});

describe('the file dialog filter', () => {
  it('offers exactly the formats the core can parse', () => {
    expect([...SOURCE_FILE_EXTENSIONS].sort()).toEqual(['docx', 'markdown', 'md', 'pdf', 'txt']);
  });
});
