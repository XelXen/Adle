import type { Course } from '@adle/contracts';

import type { CourseFileCounts, CourseFileHolds, CourseFileKind } from './bridge';
import { pluralise } from './format';

/**
 * A course saved as a file, and brought in from one (ADR-063): what each kind of file
 * holds unless the learner says otherwise, and the words for what one holds. The file is
 * made, read and checked by the core; this only says what the learner asked for.
 */

/** What a course is called by where it came from, in the library and on its own page. */
export const ORIGIN_LABEL: Record<Course['origin'], string> = {
  sample: 'Sample course',
  topic: 'From a topic',
  materials: 'From your materials',
};

/** A course brought in from a file says so, whatever it was made from. */
export function originLabel(course: Pick<Course, 'origin' | 'brought_in'>): string {
  return course.brought_in ? 'Imported' : ORIGIN_LABEL[course.origin];
}

export interface KindChoice {
  value: CourseFileKind;
  label: string;
  description: string;
}

export const KIND_CHOICES: readonly KindChoice[] = [
  {
    value: 'template',
    label: 'A template',
    description: 'The plan and its lessons, for someone starting fresh. Nothing about you.',
  },
  {
    value: 'transfer',
    label: 'Everything',
    description: 'Your materials, progress and notes too, to move it to another computer.',
  },
];

/** What a kind of file holds unless the learner changes it. */
export function holdsFor(kind: CourseFileKind): CourseFileHolds {
  const whole = kind === 'transfer';
  return { lessons: true, materials: whole, progress: whole, notes: whole };
}

/** Of the things a file can hold, which this one does: there is nothing else to bring in. */
export function heldBy(counts: CourseFileCounts): CourseFileHolds {
  return {
    lessons: counts.lessons > 0,
    materials: counts.materials > 0,
    progress: counts.progress,
    notes: counts.notes > 0,
  };
}

export function sameHolds(one: CourseFileHolds, other: CourseFileHolds): boolean {
  return (
    one.lessons === other.lessons &&
    one.materials === other.materials &&
    one.progress === other.progress &&
    one.notes === other.notes
  );
}

function listed(items: string[]): string {
  if (items.length <= 1) return items.join('');
  return `${items.slice(0, -1).join(', ')} and ${items[items.length - 1]}`;
}

/** "8 concepts, 8 lessons, 1 source, your progress and 2 notes." */
export function whatItHolds(counts: CourseFileCounts): string {
  const items = [pluralise(counts.concepts, 'concept')];
  if (counts.lessons > 0) items.push(pluralise(counts.lessons, 'lesson'));
  if (counts.materials > 0) items.push(pluralise(counts.materials, 'source'));
  if (counts.progress) items.push('progress');
  if (counts.notes > 0) items.push(pluralise(counts.notes, 'note'));
  return `${listed(items)}.`;
}

/** What to say about lessons a file was saved without, or nothing. */
export function leftOutOfFile(lessons: number): string | undefined {
  if (lessons <= 0) return undefined;
  return lessons === 1
    ? '1 lesson is still being written and was left out.'
    : `${lessons.toLocaleString()} lessons are still being written and were left out.`;
}

/** What to say about lessons a course was brought in without, or nothing. */
export function leftOutOfCourse(lessons: number): string | undefined {
  if (lessons <= 0) return undefined;
  return lessons === 1
    ? '1 lesson couldn’t be used and was left out.'
    : `${lessons.toLocaleString()} lessons couldn’t be used and were left out.`;
}
