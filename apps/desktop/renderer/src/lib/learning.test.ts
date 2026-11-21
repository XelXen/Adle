import { describe, expect, it } from 'vitest';

import type { ConceptProgress, Hypothesis, NextStep, ProgressSummary } from '@adle/contracts';

import {
  formatWait,
  hasLighterEvidence,
  hypothesisLabel,
  LIGHTER_EVIDENCE,
  outcomeWords,
  practiceSummary,
  practiceTitle,
  reviewNote,
  reviewSentence,
  reviewWhen,
  sessionCounts,
  sessionHeading,
  shownSentence,
  stepAction,
  summarySentence,
} from './learning';

const COURSE = 'crs_00000000000000000001';
const NOW = new Date('2026-11-19T12:00:00Z');

function step(kind: NextStep['kind'], changes: Partial<NextStep> = {}): NextStep {
  return {
    kind,
    title: 'A title',
    reason: 'A reason.',
    concept_id: 'con_00000000000000000001',
    lesson_id: 'les_00000000000000000001',
    about: null,
    needs_key: false,
    ...changes,
  };
}

function concept(changes: Partial<ConceptProgress> = {}): ConceptProgress {
  return {
    concept_id: 'con_00000000000000000001',
    title: 'Weights and bias',
    knowledge: {
      state: 'building',
      label: 'Learning',
      missing: [],
      answered: 2,
      self_report: null,
      review_due_at: null,
    },
    lessons_total: 1,
    lessons_completed: 1,
    hypotheses: [],
    fresh_questions: 3,
    next_fresh_at: null,
    review_due: false,
    ...changes,
  };
}

function hypothesis(changes: Partial<Hypothesis> = {}): Hypothesis {
  return {
    kind: 'causal_confusion',
    status: 'tentative',
    description: 'One answer suggested something.',
    is_slip: false,
    can_dismiss: true,
    ...changes,
  };
}

describe('stepAction', () => {
  it('opens the lesson a lesson step is about', () => {
    for (const [kind, label] of [
      ['start_lesson', 'Start lesson'],
      ['resume_lesson', 'Continue lesson'],
      ['repeat_lesson', 'Open lesson'],
      ['revisit_prerequisite', 'Open lesson'],
    ] as const) {
      expect(stepAction(step(kind), COURSE)).toEqual({
        type: 'navigate',
        label,
        route: { name: 'lesson', courseId: COURSE, lessonId: 'les_00000000000000000001' },
      });
    }
  });

  it('opens questions on the concept for a review, practice, or a check', () => {
    expect(stepAction(step('review'), COURSE)).toEqual({
      type: 'navigate',
      label: 'Start review',
      route: { name: 'practice', courseId: COURSE, conceptId: 'con_00000000000000000001' },
    });
    expect(stepAction(step('practise'), COURSE)).toMatchObject({ label: 'Practise' });
    expect(stepAction(step('check', { about: 'causal_confusion' }), COURSE)).toEqual({
      type: 'navigate',
      label: 'Answer a few questions',
      route: {
        name: 'practice',
        courseId: COURSE,
        conceptId: 'con_00000000000000000001',
        about: 'causal_confusion',
      },
    });
  });

  it('asks for a lesson when there is a key, and leads to the settings when there is not', () => {
    for (const kind of ['create_lesson', 'another_explanation'] as const) {
      expect(stepAction(step(kind), COURSE)).toEqual({
        type: 'generate',
        label: 'Create lesson',
        conceptId: 'con_00000000000000000001',
      });
      expect(stepAction(step(kind, { needs_key: true }), COURSE)).toEqual({
        type: 'navigate',
        label: 'Set up AI provider',
        route: { name: 'settings', tab: 'ai' },
      });
    }
  });

  it('leads to the curriculum when there is nothing to learn yet', () => {
    expect(stepAction(step('add_concepts', { concept_id: null, lesson_id: null }), COURSE)).toEqual(
      {
        type: 'navigate',
        label: 'Open curriculum',
        route: { name: 'course', courseId: COURSE, tab: 'curriculum' },
      },
    );
  });

  it('offers no button for a step that only says something, or that points nowhere', () => {
    expect(stepAction(step('nothing_due'), COURSE)).toEqual({ type: 'none' });
    expect(stepAction(step('start_lesson', { lesson_id: null }), COURSE)).toEqual({ type: 'none' });
    expect(stepAction(step('review', { concept_id: null }), COURSE)).toEqual({ type: 'none' });
  });
});

describe('formatWait', () => {
  it('puts a wait into everyday words', () => {
    expect(formatWait('2026-11-19T11:00:00Z', NOW)).toBe('now');
    expect(formatWait('2026-11-19T12:40:00Z', NOW)).toBe('in less than an hour');
    expect(formatWait('2026-11-19T13:10:00Z', NOW)).toBe('in about 1 hour');
    expect(formatWait('2026-11-19T23:00:00Z', NOW)).toBe('in about 11 hours');
    expect(formatWait('2026-11-20T12:00:00Z', NOW)).toBe('tomorrow');
    expect(formatWait('2026-11-22T12:00:00Z', NOW)).toBe('in 3 days');
    expect(formatWait('not a date', NOW)).toBe('');
  });
});

describe('reviews in words', () => {
  it('says when a concept is due, or when it will be', () => {
    expect(reviewNote(concept({ review_due: true }), NOW)).toBe('Review due');
    const later = concept();
    later.knowledge.review_due_at = '2026-11-21T12:00:00Z';
    expect(reviewNote(later, NOW)).toBe('Next review in 2 days');
    expect(reviewNote(concept(), NOW)).toBeNull();
  });

  it('counts concepts by state without turning them into a score', () => {
    const summary: ProgressSummary = {
      concepts: 8,
      demonstrated: 1,
      in_progress: 2,
      not_assessed: 5,
      reviews_due: 0,
      next_review_at: null,
    };
    expect(summarySentence(summary)).toBe(
      '8 concepts: 1 understood, 2 in progress, 5 not started.',
    );
    expect(
      summarySentence({
        ...summary,
        concepts: 1,
        demonstrated: 0,
        in_progress: 0,
        not_assessed: 1,
      }),
    ).toBe('1 concept: 1 not started.');
    expect(summarySentence({ ...summary, concepts: 0 })).toBe('This course has no concepts yet.');
    expect(summarySentence(summary)).not.toContain('%');
  });

  it('says what is due, or when something will be', () => {
    const summary: ProgressSummary = {
      concepts: 3,
      demonstrated: 1,
      in_progress: 2,
      not_assessed: 0,
      reviews_due: 0,
      next_review_at: null,
    };
    expect(reviewSentence(summary, NOW)).toBeNull();
    expect(reviewSentence({ ...summary, reviews_due: 1 }, NOW)).toBe('1 review due.');
    expect(reviewSentence({ ...summary, reviews_due: 2 }, NOW)).toBe('2 reviews due.');
    expect(reviewSentence({ ...summary, next_review_at: '2026-11-20T12:00:00Z' }, NOW)).toBe(
      'Next review tomorrow.',
    );
  });
});

describe('the session summary in words', () => {
  const now = new Date(2026, 10, 19, 15, 0);
  const at = (daysAgo: number, hour = 14): string =>
    new Date(2026, 10, 19 - daysAgo, hour, 0).toISOString();

  it('is "this session" while the learner may still be in it', () => {
    expect(sessionHeading({ current: true, ended_at: at(0) }, now)).toBe('This session');
  });

  it('is named by its day once it is over', () => {
    expect(sessionHeading({ current: false, ended_at: at(0, 9) }, now)).toBe('Earlier today');
    expect(sessionHeading({ current: false, ended_at: at(1) }, now)).toBe('Last time, yesterday');
    expect(sessionHeading({ current: false, ended_at: at(3) }, now)).toBe('Last time, 3 days ago');
    expect(sessionHeading({ current: false, ended_at: at(40) }, now)).toMatch(/^Last time, on /);
    expect(sessionHeading({ current: false, ended_at: 'not a date' }, now)).toBe('Last time');
  });

  it('counts what was done, and says so plainly when nothing was answered', () => {
    expect(sessionCounts({ lessons_completed: 1, answered: 6 })).toBe(
      '1 lesson finished, 6 questions answered.',
    );
    expect(sessionCounts({ lessons_completed: 2, answered: 0 })).toBe('2 lessons finished.');
    expect(sessionCounts({ lessons_completed: 0, answered: 1 })).toBe('1 question answered.');
    expect(sessionCounts({ lessons_completed: 0, answered: 0 })).toBe('No questions answered.');
  });

  it('says what was shown as a count of right answers, never as a share of all answers', () => {
    expect(shownSentence({ right: 1, right_unaided: 1, demonstrated: false })).toBe(
      '1 answer right.',
    );
    const demonstrated = shownSentence({ right: 4, right_unaided: 4, demonstrated: true });
    expect(demonstrated).toBe('4 answers right. Understood.');
    expect(demonstrated).not.toMatch(/%|\//);
  });

  it('says which right answers were lighter evidence, without taking them away', () => {
    expect(shownSentence({ right: 3, right_unaided: 2, demonstrated: true })).toBe(
      '3 answers right, 1 with help. Understood.',
    );
    expect(shownSentence({ right: 3, right_unaided: 0, demonstrated: false })).toBe(
      '3 answers right, 3 with help.',
    );
    expect(shownSentence({ right: 1, right_unaided: 0, demonstrated: false })).toBe(
      '1 answer right, with help.',
    );
  });

  it('explains lighter evidence only when some line mentions it', () => {
    expect(hasLighterEvidence([{ right: 2, right_unaided: 2 }])).toBe(false);
    expect(
      hasLighterEvidence([
        { right: 2, right_unaided: 2 },
        { right: 1, right_unaided: 0 },
      ]),
    ).toBe(true);
    expect(hasLighterEvidence([])).toBe(false);
    expect(LIGHTER_EVIDENCE).toContain('It still counts');
  });

  it('says when a planned review comes round', () => {
    expect(reviewWhen(new Date(2026, 10, 21, 15, 0).toISOString(), now)).toBe('Review in 2 days.');
    expect(reviewWhen(new Date(2026, 10, 20, 15, 0).toISOString(), now)).toBe('Review tomorrow.');
    expect(reviewWhen(new Date(2026, 10, 18, 15, 0).toISOString(), now)).toBe('Review due.');
    expect(reviewWhen('not a date', now)).toBe('Review due.');
  });
});

describe('hypothesisLabel', () => {
  it('labels a hypothesis by how far the evidence goes', () => {
    expect(hypothesisLabel(hypothesis())).toEqual({
      status: 'Suspected',
      tone: 'info',
    });
    expect(hypothesisLabel(hypothesis({ status: 'supported' })).status).toBe('Seen more than once');
    expect(hypothesisLabel(hypothesis({ status: 'resolved', can_dismiss: false })).status).toBe(
      'Sorted',
    );
    expect(hypothesisLabel(hypothesis({ status: 'rejected', can_dismiss: false })).status).toBe(
      'Set aside',
    );
  });

  it('calls a slip a slip whatever its status', () => {
    expect(hypothesisLabel(hypothesis({ is_slip: true, status: 'supported' })).status).toBe(
      'A slip',
    );
    expect(
      hypothesisLabel(hypothesis({ is_slip: true, status: 'rejected', can_dismiss: false })).status,
    ).toBe('An earlier slip');
  });
});

describe('practice in words', () => {
  it('titles a set of questions by what it is for', () => {
    expect(practiceTitle({ purpose: 'review', concept_title: 'Weights' })).toBe('Review: Weights');
    expect(practiceTitle({ purpose: 'check', concept_title: 'Weights' })).toBe(
      'Quick check: Weights',
    );
    expect(practiceTitle({ purpose: 'practise', concept_title: 'Weights' })).toBe(
      'Practice: Weights',
    );
  });

  it('says how a set went without judging it', () => {
    expect(practiceSummary(['correct', 'correct', 'incorrect'])).toBe('2 of 3 answers right.');
    expect(practiceSummary(['correct'])).toBe('1 of 1 answer right.');
    expect(practiceSummary(['correct', 'skipped', 'partial'])).toBe(
      '1 of 2 answers right, and 1 skipped.',
    );
    expect(practiceSummary(['skipped', 'skipped'])).toBe('You skipped every question.');
    expect(practiceSummary(['skipped'])).toBe('You skipped the question.');
    expect(outcomeWords('incorrect')).toBe('Not yet');
  });
});
