import { describe, expect, it } from 'vitest';

import type { LessonRules } from '@adle/contracts';

import { AUTO, choiceOf, subjectChoices, subjectOf, taughtAs, waysFor } from './lesson-rules';

const RULES: LessonRules = {
  rules: ['Each part starts with something to look at.', 'The rule comes after.'],
  subjects: [
    {
      key: 'chemistry',
      name: 'Chemistry',
      steps: ['An experiment', 'The particles', 'The equation'],
      strategies: ['visual', 'worked_example', 'analogy', 'socratic', 'mathematical'],
    },
    {
      key: 'history',
      name: 'History',
      steps: ['One moment', 'What led to it', 'The claim'],
      strategies: ['visual', 'analogy', 'worked_example', 'socratic'],
    },
    {
      key: 'general',
      name: 'General',
      steps: ['One example', 'The idea', 'The rule'],
      strategies: [
        'visual',
        'worked_example',
        'analogy',
        'mathematical',
        'computational',
        'socratic',
      ],
    },
  ],
};

const STYLES = [
  { value: '', label: 'Automatic' },
  { value: 'visual', label: 'Visual first' },
  { value: 'worked_example', label: 'Worked example' },
  { value: 'analogy', label: 'Everyday analogy' },
  { value: 'mathematical', label: 'Step-by-step math' },
  { value: 'computational', label: 'Calculation by hand' },
  { value: 'socratic', label: 'Guided questions' },
] as const;

describe('what a course is taught as', () => {
  it('names the subject once the course has one that says something', () => {
    expect(taughtAs({ subject: 'chemistry' }, RULES)).toBe('Taught as Chemistry');
    expect(taughtAs({ subject: 'general' }, RULES)).toBe('How lessons are formed');
    // Before the rules are read, and for a subject this version does not know.
    expect(taughtAs({ subject: 'chemistry' }, null)).toBe('How lessons are formed');
    expect(taughtAs({ subject: 'alchemy' as never }, RULES)).toBe('How lessons are formed');
    expect(subjectOf(RULES, 'history')?.steps).toEqual([
      'One moment',
      'What led to it',
      'The claim',
    ]);
  });

  it('says whose choice the subject is', () => {
    expect(choiceOf({ subject: 'chemistry', subject_by_adle: true })).toBe(AUTO);
    expect(choiceOf({ subject: 'chemistry', subject_by_adle: false })).toBe('chemistry');
    expect(choiceOf({ subject: 'general', subject_by_adle: false })).toBe('general');
  });

  it('offers Adle’s own choice first, saying what it chose', () => {
    const adle = subjectChoices({ subject: 'chemistry', subject_by_adle: true }, RULES);
    expect(adle.map((choice) => choice.label)).toEqual([
      'Let Adle choose (now: Chemistry)',
      'Chemistry',
      'History',
      'General',
    ]);
    expect(adle[0]?.value).toBe(AUTO);
    // Nothing to say of a course Adle has not placed, or of one the learner placed.
    for (const course of [
      { subject: 'general', subject_by_adle: true },
      { subject: 'history', subject_by_adle: false },
    ] as const) {
      expect(subjectChoices(course, RULES)[0]?.label).toBe('Let Adle choose');
    }
  });
});

describe('the teaching styles offered', () => {
  it('are those that suit the subject, in the order the app lists them', () => {
    expect(waysFor(STYLES, RULES, 'history').map((style) => style.label)).toEqual([
      'Automatic',
      'Visual first',
      'Worked example',
      'Everyday analogy',
      'Guided questions',
    ]);
    expect(waysFor(STYLES, RULES, 'chemistry').map((style) => style.value)).not.toContain(
      'computational',
    );
    expect(waysFor(STYLES, RULES, 'general')).toEqual([...STYLES]);
  });

  it('are all of them while the rules or the subject are not known', () => {
    expect(waysFor(STYLES, null, 'history')).toEqual([...STYLES]);
    expect(waysFor(STYLES, RULES, null)).toEqual([...STYLES]);
    expect(waysFor(STYLES, RULES, 'alchemy')).toEqual([...STYLES]);
  });
});
