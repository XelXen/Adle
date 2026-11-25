import path from 'node:path';

import { describe, expect, it } from 'vitest';

import {
  handedOverPath,
  parseCourseFileRequest,
  parseCourseOpenPath,
  parseCourseSavePath,
  parseFileToken,
  parseHolds,
} from './course-file-rules';

const root = path.resolve(path.sep, 'adle-test');
const dataDir = path.join(root, 'data');
const ALL = { lessons: true, materials: true, progress: true, notes: true };

describe('what the page may say a course file holds', () => {
  it('is exactly four choices, each true or false', () => {
    expect(parseHolds(ALL)).toEqual(ALL);
    expect(parseHolds({ lessons: true, materials: false, progress: false, notes: false })).toEqual({
      lessons: true,
      materials: false,
      progress: false,
      notes: false,
    });
  });

  it('is refused with a choice missing, one too many, or one that is not true or false', () => {
    expect(parseHolds({ lessons: true, materials: true, progress: true })).toBeNull();
    expect(parseHolds({ ...ALL, path: 'C:\\Users' })).toBeNull();
    expect(parseHolds({ ...ALL, notes: 'yes' })).toBeNull();
    expect(parseHolds({ ...ALL, lessons: 1 })).toBeNull();
    expect(parseHolds(null)).toBeNull();
    expect(parseHolds([true, true, true, true])).toBeNull();
    expect(parseHolds('all')).toBeNull();
    // An object of another making can answer for a name in ways a plain one cannot.
    expect(parseHolds(Object.create({ lessons: true }))).toBeNull();
  });
});

describe('what the page may ask to be saved', () => {
  it('is a kind of file and what it holds, and nothing else', () => {
    expect(parseCourseFileRequest({ kind: 'template', holds: ALL })).toEqual({
      kind: 'template',
      holds: ALL,
    });
    expect(parseCourseFileRequest({ kind: 'transfer', holds: ALL })?.kind).toBe('transfer');
  });

  it('never carries a place to save to, or a kind Adle does not make', () => {
    expect(parseCourseFileRequest({ kind: 'template', holds: ALL, path: 'C:\\x.zip' })).toBeNull();
    expect(parseCourseFileRequest({ kind: 'everything', holds: ALL })).toBeNull();
    expect(parseCourseFileRequest({ kind: 'template' })).toBeNull();
    expect(parseCourseFileRequest({ holds: ALL })).toBeNull();
    expect(parseCourseFileRequest('template')).toBeNull();
    expect(parseCourseFileRequest(undefined)).toBeNull();
  });
});

describe('a file the core left to be handed over', () => {
  it('is found only by a name of the kind the core makes, inside its own folder', () => {
    const name = `course-${'0a'.repeat(10)}.zip`;
    expect(handedOverPath(dataDir, name)).toBe(path.join(dataDir, 'handover', name));
  });

  it('is not found by any other name', () => {
    for (const name of [
      '../adle.db',
      '..\\adle.db',
      'course-0a0a0a0a0a0a0a0a0a0a.zip/../../x',
      'course-XYZ.zip',
      `course-${'0a'.repeat(10)}.exe`,
      `${'0a'.repeat(10)}.zip`,
      path.join(dataDir, 'adle.db'),
      '',
      null,
      42,
    ]) {
      expect(handedOverPath(dataDir, name)).toBeNull();
    }
  });
});

describe('where a course file is saved', () => {
  it('takes the place the learner chose, and adds the ending a dialog left off', () => {
    const chosen = path.join(root, 'Documents', 'Limits.adle-course.zip');
    expect(parseCourseSavePath(chosen, dataDir)).toEqual({
      ok: true,
      path: chosen,
      amended: false,
    });
    const bare = path.join(root, 'Documents', 'Limits');
    expect(parseCourseSavePath(bare, dataDir)).toEqual({
      ok: true,
      path: `${bare}.zip`,
      amended: true,
    });
  });

  it('is never inside Adle’s own data, and never a path that is not whole', () => {
    expect(parseCourseSavePath(path.join(dataDir, 'handover', 'x.zip'), dataDir).ok).toBe(false);
    expect(parseCourseSavePath(path.join(dataDir, 'x.zip'), dataDir).ok).toBe(false);
    expect(parseCourseSavePath('Limits.zip', dataDir).ok).toBe(false);
    expect(parseCourseSavePath(`${path.join(root, 'x')}\0.zip`, dataDir).ok).toBe(false);
    expect(parseCourseSavePath('', dataDir).ok).toBe(false);
    expect(parseCourseSavePath(undefined, dataDir).ok).toBe(false);
    expect(parseCourseSavePath(path.join(root, 'x'.repeat(5000)), dataDir).ok).toBe(false);
  });
});

describe('the file a course is brought in from', () => {
  it('is a zip the learner chose', () => {
    const chosen = path.join(root, 'Downloads', 'Limits.adle-course.zip');
    expect(parseCourseOpenPath(chosen)).toEqual({ ok: true, path: chosen });
    expect(parseCourseOpenPath(path.join(root, 'Downloads', 'LIMITS.ZIP')).ok).toBe(true);
  });

  it('is nothing else', () => {
    expect(parseCourseOpenPath(path.join(root, 'Downloads', 'Limits.adle')).ok).toBe(false);
    expect(parseCourseOpenPath(path.join(root, 'Downloads', 'Limits')).ok).toBe(false);
    expect(parseCourseOpenPath('Limits.zip').ok).toBe(false);
    expect(parseCourseOpenPath(null).ok).toBe(false);
  });
});

describe('the token the page knows a chosen file by', () => {
  it('is thirty-two hexadecimal characters and nothing else', () => {
    expect(parseFileToken('0123456789abcdef0123456789abcdef')).toBe(
      '0123456789abcdef0123456789abcdef',
    );
    expect(parseFileToken('0123456789abcdef')).toBeNull();
    expect(parseFileToken('C:\\Users\\me\\course.zip')).toBeNull();
    expect(parseFileToken('0123456789ABCDEF0123456789ABCDEF')).toBeNull();
    expect(parseFileToken(undefined)).toBeNull();
  });
});
