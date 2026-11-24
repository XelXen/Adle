import type { Course, LessonRules } from '@adle/contracts';

import { callCore } from './core-client';
import { type ResourceHandle, useResource } from './use-resource';

/** One kind of subject, and how a lesson of it goes (ADR-061). */
export type SubjectWay = LessonRules['subjects'][number];
/** A kind of subject, as the core names it. */
export type SubjectKey = SubjectWay['key'];
/** What a course is set to: a subject of the learner's choosing, or left to Adle. */
export type SubjectChoice = SubjectKey | 'auto';

/** Left to Adle: it places the course by its name, and by what the AI says with its plan. */
export const AUTO: SubjectChoice = 'auto';

/**
 * How Adle forms a lesson: the rules of every lesson and what each subject needs besides,
 * as the core has them written down. They change only with the app, so one reading serves
 * a screen for as long as it is open.
 */
export function useLessonRules(): ResourceHandle<LessonRules> {
  return useResource('lesson-rules', () => callCore('lessons.rules'));
}

export function subjectOf(rules: LessonRules | null, key: string): SubjectWay | null {
  return rules?.subjects.find((subject) => subject.key === key) ?? null;
}

/** What the control on a course says: its subject, once it has one that says something. */
export function taughtAs(course: Pick<Course, 'subject'>, rules: LessonRules | null): string {
  const subject = subjectOf(rules, course.subject ?? 'general');
  if (subject === null || subject.key === 'general') return 'How lessons are formed';
  return `Taught as ${subject.name}`;
}

/** What the learner has chosen for a course: a subject, or to leave it to Adle. */
export function choiceOf(course: Pick<Course, 'subject' | 'subject_by_adle'>): SubjectChoice {
  return course.subject_by_adle === false ? (course.subject ?? 'general') : AUTO;
}

/** The choices of a subject: Adle's own first, saying what it chose, then every subject. */
export function subjectChoices(
  course: Pick<Course, 'subject' | 'subject_by_adle'>,
  rules: LessonRules,
): { value: SubjectChoice; label: string }[] {
  const placed = subjectOf(rules, course.subject ?? 'general');
  const adle =
    course.subject_by_adle !== false && placed !== null && placed.key !== 'general'
      ? `Let Adle choose (now: ${placed.name})`
      : 'Let Adle choose';
  return [
    { value: AUTO, label: adle },
    ...rules.subjects.map((subject) => ({ value: subject.key, label: subject.name })),
  ];
}

/**
 * The ways of teaching offered for a course: those that suit its subject, in the order the
 * app lists them. Every way while the rules are not known yet, so that nothing the learner
 * could have asked for is missing because something was slow to load.
 */
export function waysFor<Way extends { value: string }>(
  choices: readonly Way[],
  rules: LessonRules | null,
  subject: string | null | undefined,
): Way[] {
  const suited = subjectOf(rules, subject ?? 'general')?.strategies;
  if (suited === undefined) return [...choices];
  const allowed = new Set<string>(suited);
  return choices.filter((choice) => choice.value === '' || allowed.has(choice.value));
}
