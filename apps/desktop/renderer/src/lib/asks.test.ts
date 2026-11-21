import { describe, expect, it } from 'vitest';

import type { Ask, Job } from '@adle/contracts';

import {
  answeredAskId,
  answeredBy,
  askDisclosure,
  asksAbout,
  MAX_QUESTION_CHARACTERS,
  questionProblem,
  suggestedQuestions,
} from './asks';

const ask = (changes: Partial<Ask>): Ask => ({
  id: 'ask_1',
  lesson_id: 'les_1',
  segment_id: 'seg_1',
  question: 'Why?',
  paragraphs: ['Because.'],
  citations: [],
  written_by: { provider: 'AIHubMix', models: ['Coding Kimi K3 (free)'], authors: [], note: '' },
  created_at: '2026-11-20T10:00:00Z',
  ...changes,
});

describe('suggestedQuestions', () => {
  it('offers the usual ways of having something explained again', () => {
    const offered = suggestedQuestions('explanation', false);
    expect(offered).toContain('Explain this more simply.');
    expect(offered).toContain('Give me an example.');
    expect(offered).toContain('Show the mathematics behind this.');
    // The same for any part that is not a question of the lesson's.
    expect(suggestedQuestions('worked_example', true)).toEqual(offered);
  });

  it('never suggests asking for the answer to a question that is still open', () => {
    const open = suggestedQuestions('checkpoint', true);
    expect(open.length).toBeGreaterThan(0);
    for (const suggestion of open) {
      expect(suggestion.toLowerCase()).not.toMatch(/what is the answer|right answer|which option/);
    }
    expect(open[0]).toContain('not the answer');
    // Once it has been answered, why it is right is a fair question.
    expect(suggestedQuestions('checkpoint', false)).toContain('Why is that the right answer?');
  });

  it('offers nothing longer than a question may be', () => {
    for (const kind of ['explanation', 'checkpoint']) {
      for (const open of [true, false]) {
        for (const suggestion of suggestedQuestions(kind, open)) {
          expect(questionProblem(suggestion)).toBeNull();
        }
      }
    }
  });
});

describe('questionProblem', () => {
  it('asks for something to be typed, and for it to be one question long', () => {
    expect(questionProblem('')).toContain('Type a question');
    expect(questionProblem('   ')).toContain('Type a question');
    expect(questionProblem('ab')).toContain('too short');
    expect(questionProblem('x'.repeat(MAX_QUESTION_CHARACTERS + 1))).toContain('under 500');
    expect(questionProblem('  Why is the bias added last?  ')).toBeNull();
    expect(questionProblem('x'.repeat(MAX_QUESTION_CHARACTERS))).toBeNull();
  });
});

describe('askDisclosure', () => {
  it('names everything a question sends', () => {
    const said = askDisclosure();
    // One for each thing `ask_request` in the core puts into the request.
    for (const part of [
      'your question',
      'this part of the lesson',
      'the lesson outline',
      'the course name',
      'this concept',
      'your materials',
    ]) {
      expect(said).toContain(part);
    }
  });
});

describe('answeredAskId', () => {
  const job = (changes: Partial<Job>): Job =>
    ({
      id: 'job_1',
      kind: 'lesson_ask',
      status: 'succeeded',
      result: { kind: 'lesson_ask', ask_id: 'ask_9', segment_id: 'seg_1' },
      ...changes,
    }) as Job;

  it('is the answer a finished question produced, and nothing otherwise', () => {
    expect(answeredAskId(job({}))).toBe('ask_9');
    expect(answeredAskId(null)).toBeNull();
    expect(answeredAskId(job({ status: 'running' }))).toBeNull();
    expect(answeredAskId(job({ status: 'failed', result: null }))).toBeNull();
    expect(answeredAskId(job({ kind: 'lesson_generation' }))).toBeNull();
    expect(answeredAskId(job({ result: { ask_id: 7 } }))).toBeNull();
  });
});

describe('answeredBy', () => {
  it('names the model and the provider that wrote an answer', () => {
    expect(answeredBy(ask({}))).toBe('Coding Kimi K3 (free) on AIHubMix');
  });

  it('names the provider alone when more than one model, or none, is recorded', () => {
    const written = { provider: 'NVIDIA NIM', authors: [], note: '' };
    expect(answeredBy(ask({ written_by: { ...written, models: ['A', 'B'] } }))).toBe('NVIDIA NIM');
    expect(answeredBy(ask({ written_by: { ...written, models: [] } }))).toBe('NVIDIA NIM');
    expect(
      answeredBy(ask({ written_by: { provider: '', models: [], authors: [], note: '' } })),
    ).toBe('AI');
  });
});

describe('asksAbout', () => {
  it('keeps the questions of one part, in the order they were asked', () => {
    const all = [
      ask({ id: 'a', segment_id: 'seg_1' }),
      ask({ id: 'b', segment_id: 'seg_2' }),
      ask({ id: 'c', segment_id: 'seg_1' }),
    ];
    expect(asksAbout(all, 'seg_1').map((item) => item.id)).toEqual(['a', 'c']);
    expect(asksAbout(all, 'seg_9')).toEqual([]);
  });
});
