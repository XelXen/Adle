import { describe, expect, it } from 'vitest';

import {
  heldBy,
  holdsFor,
  KIND_CHOICES,
  leftOutOfCourse,
  leftOutOfFile,
  originLabel,
  sameHolds,
  whatItHolds,
} from './course-files';

const COUNTS = { concepts: 8, lessons: 8, materials: 1, files: 1, progress: true, notes: 2 };

describe('a course as a file (ADR-063)', () => {
  it('is a template with nothing of the learner in it, or everything', () => {
    expect(holdsFor('template')).toEqual({
      lessons: true,
      materials: false,
      progress: false,
      notes: false,
    });
    expect(holdsFor('transfer')).toEqual({
      lessons: true,
      materials: true,
      progress: true,
      notes: true,
    });
    expect(KIND_CHOICES.map((choice) => choice.value)).toEqual(['template', 'transfer']);
  });

  it('offers to bring in only what a file has', () => {
    expect(heldBy(COUNTS)).toEqual({ lessons: true, materials: true, progress: true, notes: true });
    expect(
      heldBy({ concepts: 3, lessons: 0, materials: 0, files: 0, progress: false, notes: 0 }),
    ).toEqual({ lessons: false, materials: false, progress: false, notes: false });
  });

  it('knows when what is chosen is what a kind of file holds anyway', () => {
    expect(sameHolds(holdsFor('template'), holdsFor('template'))).toBe(true);
    expect(sameHolds(holdsFor('template'), holdsFor('transfer'))).toBe(false);
    expect(sameHolds({ ...holdsFor('transfer'), notes: false }, holdsFor('transfer'))).toBe(false);
  });

  it('says what a file holds in a sentence', () => {
    expect(whatItHolds(COUNTS)).toBe('8 concepts, 8 lessons, 1 source, progress and 2 notes.');
    expect(
      whatItHolds({ concepts: 1, lessons: 1, materials: 0, files: 0, progress: false, notes: 0 }),
    ).toBe('1 concept and 1 lesson.');
    expect(
      whatItHolds({ concepts: 12, lessons: 0, materials: 0, files: 0, progress: false, notes: 0 }),
    ).toBe('12 concepts.');
  });

  it('says what was left out, and says nothing when nothing was', () => {
    expect(leftOutOfFile(0)).toBeUndefined();
    expect(leftOutOfFile(1)).toBe('1 lesson is still being written and was left out.');
    expect(leftOutOfFile(3)).toBe('3 lessons are still being written and were left out.');
    expect(leftOutOfCourse(0)).toBeUndefined();
    expect(leftOutOfCourse(1)).toBe('1 lesson couldn’t be used and was left out.');
    expect(leftOutOfCourse(2)).toBe('2 lessons couldn’t be used and were left out.');
  });

  it('calls a course that came in a file imported, whatever it was made from', () => {
    expect(originLabel({ origin: 'topic', brought_in: false })).toBe('From a topic');
    expect(originLabel({ origin: 'materials', brought_in: false })).toBe('From your materials');
    expect(originLabel({ origin: 'sample', brought_in: false })).toBe('Sample course');
    expect(originLabel({ origin: 'topic', brought_in: true })).toBe('Imported');
    expect(originLabel({ origin: 'materials', brought_in: true })).toBe('Imported');
  });
});
