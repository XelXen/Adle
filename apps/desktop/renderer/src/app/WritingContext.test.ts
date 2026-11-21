/**
 * When something that was being written is said to have arrived, and when it is put away.
 * The journeys through the real app are in `e2e/break.spec.ts`.
 */
import { describe, expect, it } from 'vitest';

import type { Job } from '@adle/contracts';

import { KIND_LESSON, KIND_PROPOSAL } from '../lib/generation';
import type { Route } from './router';
import {
  arrivalNotice,
  isWhereItIs,
  leavesTellingToScreen,
  newsOf,
  showsOutcome,
} from './WritingContext';

const COURSE = 'crs_00000000000000000001';
const OTHER = 'crs_00000000000000000002';

function job(kind: string, result: unknown = null): Job {
  return {
    id: 'job_1',
    kind,
    course_id: COURSE,
    subject_id: 'con_1',
    status: 'succeeded',
    progress_done: 1,
    progress_total: 1,
    progress_message: '',
    result,
    error_code: null,
    error_message: null,
    created_at: null,
  };
}

const lesson = job(KIND_LESSON, {
  kind: KIND_LESSON,
  lesson_id: 'les_00000000000000000009',
  title: 'Weights',
});
const concepts = job(KIND_PROPOSAL);
const course = (tab: 'learn' | 'curriculum' | 'sources', courseId = COURSE): Route => ({
  name: 'course',
  courseId,
  tab,
});

/** The same lesson while its pictures are still being drawn: it can be started already. */
const drawing: Job = {
  ...lesson,
  status: 'running',
  result: { ...(lesson.result as object), pictures_pending: 2 },
};

describe('newsOf', () => {
  it('has something to say when work has ended well or badly, and not before', () => {
    expect(newsOf(lesson)).toBe('usable');
    expect(newsOf(concepts)).toBe('usable');
    expect(newsOf({ ...lesson, status: 'failed', result: null })).toBe('failed');
    expect(newsOf({ ...lesson, status: 'queued', result: null })).toBeNull();
    expect(newsOf({ ...lesson, status: 'running', result: null })).toBeNull();
    // Stopped by the learner: they know.
    expect(newsOf({ ...lesson, status: 'cancelled', result: null })).toBeNull();
  });

  it('says a lesson is there as soon as it can be started', () => {
    expect(newsOf(drawing)).toBe('usable');
    // Suggestions have nothing to use until they are all there.
    expect(newsOf({ ...concepts, status: 'running', result: { concepts: [] } })).toBeNull();
  });
});

describe('arrivalNotice', () => {
  it('names the lesson, and says so if its pictures are still on their way', () => {
    expect(arrivalNotice(lesson)).toEqual({
      title: 'Your lesson is ready',
      description: 'Weights',
    });
    expect(arrivalNotice(drawing)).toEqual({
      title: 'Your lesson is ready',
      description: 'Weights. Its pictures are still being drawn.',
    });
  });

  it('says where suggested concepts are to be found', () => {
    expect(arrivalNotice(concepts)).toEqual({
      title: 'Suggested concepts are ready',
      description: 'Open the course to review them.',
    });
  });
});

describe('showsOutcome', () => {
  it('counts a break as showing whatever arrives', () => {
    expect(showsOutcome({ name: 'break' }, lesson)).toBe(true);
    expect(showsOutcome({ name: 'break' }, concepts)).toBe(true);
  });

  it('counts only the tab of the course that the work changes', () => {
    expect(showsOutcome(course('learn'), lesson)).toBe(true);
    expect(showsOutcome(course('curriculum'), lesson)).toBe(true);
    // The materials say nothing of a lesson, or of suggested concepts.
    expect(showsOutcome(course('sources'), lesson)).toBe(false);
    expect(showsOutcome(course('sources'), concepts)).toBe(false);
    // Suggested concepts are shown where the curriculum is.
    expect(showsOutcome(course('curriculum'), concepts)).toBe(true);
    expect(showsOutcome(course('learn'), concepts)).toBe(false);
  });

  it('never counts another course, or another screen', () => {
    expect(showsOutcome(course('learn', OTHER), lesson)).toBe(false);
    expect(showsOutcome({ name: 'home' }, lesson)).toBe(false);
    expect(showsOutcome({ name: 'settings', tab: 'ai' }, concepts)).toBe(false);
    expect(showsOutcome({ name: 'lesson', courseId: COURSE, lessonId: 'les_other' }, lesson)).toBe(
      false,
    );
  });
});

describe('leavesTellingToScreen', () => {
  it('leaves it to a tab of the course that shows the lesson', () => {
    expect(leavesTellingToScreen(course('learn'), lesson)).toBe(true);
    expect(leavesTellingToScreen(course('curriculum'), lesson)).toBe(true);
  });

  it('counts a break, and everywhere else, as told by the app itself', () => {
    // A break shows it without anyone saying it: it is not said again afterwards.
    expect(leavesTellingToScreen({ name: 'break' }, lesson)).toBe(false);
    expect(leavesTellingToScreen({ name: 'home' }, lesson)).toBe(false);
    expect(leavesTellingToScreen(course('sources'), lesson)).toBe(false);
    expect(leavesTellingToScreen(course('learn', OTHER), lesson)).toBe(false);
  });
});

describe('isWhereItIs', () => {
  it('is the course it belongs to, on any tab', () => {
    expect(isWhereItIs(course('sources'), lesson)).toBe(true);
    expect(isWhereItIs(course('learn'), drawing)).toBe(true);
    // A lesson that is still getting its pictures is where it is, too.
    expect(
      isWhereItIs(
        { name: 'lesson', courseId: COURSE, lessonId: 'les_00000000000000000009' },
        drawing,
      ),
    ).toBe(true);
    expect(isWhereItIs(course('learn', OTHER), lesson)).toBe(false);
  });

  it('is the lesson that was written, and no other', () => {
    expect(
      isWhereItIs(
        { name: 'lesson', courseId: COURSE, lessonId: 'les_00000000000000000009' },
        lesson,
      ),
    ).toBe(true);
    expect(isWhereItIs({ name: 'lesson', courseId: COURSE, lessonId: 'les_other' }, lesson)).toBe(
      false,
    );
  });

  it('is nowhere else', () => {
    expect(isWhereItIs({ name: 'home' }, lesson)).toBe(false);
    expect(isWhereItIs({ name: 'break' }, lesson)).toBe(false);
  });
});
