import { describe, expect, it } from 'vitest';

import type { Job } from '@adle/contracts';

import {
  barValue,
  elapsedSince,
  readWritingProgress,
  writingFraction,
  writingHeadline,
  type WritingProgress,
} from './writing-progress';

function job(detail: unknown): Job {
  return {
    id: 'job-1',
    kind: 'lesson',
    course_id: 'course-1',
    subject_id: 'concept-1',
    status: 'running',
    progress_done: 0,
    progress_total: 3,
    progress_message: 'Writing the lesson: Some Model is writing',
    result: null,
    error_code: null,
    error_message: null,
    created_at: '2026-11-21T10:00:00Z',
    progress_detail: detail,
  } as unknown as Job;
}

const writing = (outline: string[], title = 'How a neuron weighs its inputs'): WritingProgress => ({
  stage: 'writing',
  title,
  outline,
});

describe('readWritingProgress', () => {
  it('reads the stage, the title and the parts written so far', () => {
    expect(
      readWritingProgress(
        job({
          stage: 'writing',
          title: 'Limits',
          outline: ['What a limit is', 'A table of values'],
        }),
      ),
    ).toEqual({
      stage: 'writing',
      title: 'Limits',
      outline: ['What a limit is', 'A table of values'],
    });
  });

  it('says nothing where the job says nothing', () => {
    expect(readWritingProgress(null)).toBeNull();
    expect(readWritingProgress(job(null))).toBeNull();
    expect(readWritingProgress(job(undefined))).toBeNull();
    expect(readWritingProgress(job('writing'))).toBeNull();
    expect(readWritingProgress(job(['writing']))).toBeNull();
  });

  it('takes what a model wrote as text of unknown shape: one clean line each, and not too many', () => {
    const read = readWritingProgress(
      job({
        stage: 'dreaming',
        title: 42,
        outline: [
          '  A title\nover two lines\t',
          '',
          7,
          null,
          'x'.repeat(400),
          ...Array.from({ length: 60 }, (_, index) => `Part ${index}`),
        ],
      }),
    );
    expect(read?.stage).toBeNull();
    expect(read?.title).toBe('');
    expect(read?.outline[0]).toBe('A title over two lines');
    expect(read?.outline[1]).toHaveLength(140);
    expect(read?.outline[1]?.endsWith('…')).toBe(true);
    expect(read?.outline).toHaveLength(40);
  });
});

describe('writingHeadline', () => {
  it('says what is happening in the learner’s terms', () => {
    const none = { stage: null, title: '', outline: [] } satisfies WritingProgress;
    expect(writingHeadline({ ...none, stage: 'thinking' }, 'lesson', 'x')).toBe(
      'Planning the lesson',
    );
    expect(writingHeadline(writing([]), 'lesson', 'x')).toBe(
      'Writing “How a neuron weighs its inputs”',
    );
    expect(writingHeadline(writing([], ''), 'lesson', 'x')).toBe('Writing the lesson');
    expect(writingHeadline({ ...none, stage: 'thinking' }, 'suggestions', 'x')).toBe(
      'Thinking about your course',
    );
    expect(writingHeadline(writing(['Limits']), 'suggestions', 'x')).toBe('Choosing concepts');
    expect(writingHeadline(writing([]), 'answer', 'x')).toBe('Writing the answer');
  });

  it('keeps the core’s own sentence where that is the news', () => {
    const waiting = { stage: 'waiting', title: '', outline: [] } satisfies WritingProgress;
    const sentence = 'Waiting about 12 seconds to stay under the rate limit';
    expect(writingHeadline(waiting, 'lesson', sentence)).toBe(sentence);
    expect(
      writingHeadline({ ...waiting, stage: 'drawing' }, 'lesson', 'Drawing picture 1 of 2'),
    ).toBe('Drawing picture 1 of 2');
    expect(writingHeadline(null, 'lesson', 'Queued')).toBe('Queued');
  });

  it('says when a lesson’s words are written and its voice is being recorded', () => {
    const voicing = { stage: 'voicing', title: '', outline: [] } satisfies WritingProgress;
    expect(writingHeadline(voicing, 'lesson', 'x')).toBe('Recording the voice');
    expect(readWritingProgress(job({ stage: 'voicing', outline: [] }))?.stage).toBe('voicing');
  });
});

describe('writingFraction', () => {
  it('is not known before the first word', () => {
    expect(writingFraction(null)).toBeUndefined();
    expect(writingFraction({ stage: 'thinking', title: '', outline: [] })).toBeUndefined();
    expect(writingFraction(writing([], ''))).toBeUndefined();
  });

  it('moves on with every part and never arrives by itself', () => {
    const titles = Array.from({ length: 30 }, (_, index) => `Part ${index + 1}`);
    let before = writingFraction(writing([])) ?? 0;
    expect(before).toBeGreaterThan(0);
    for (let parts = 1; parts <= titles.length; parts += 1) {
      const now = writingFraction(writing(titles.slice(0, parts))) ?? 0;
      expect(now, `${parts} parts`).toBeGreaterThanOrEqual(before);
      expect(now).toBeLessThan(1);
      before = now;
    }
    // A lesson of the usual length is most of the way there, and not yet there.
    const usual = writingFraction(writing(titles.slice(0, 8))) ?? 0;
    expect(usual).toBeGreaterThan(0.7);
    expect(usual).toBeLessThan(0.95);
  });
});

describe('barValue', () => {
  const running = job(null);
  it('moves without a measure while nothing can be counted', () => {
    expect(barValue(null, null, undefined)).toBeUndefined();
    expect(barValue({ ...running, status: 'queued' }, null, 0.5)).toBeUndefined();
    expect(barValue(running, { stage: 'thinking', title: '', outline: [] }, 0.5)).toBeUndefined();
    expect(barValue(running, { stage: 'waiting', title: '', outline: [] }, 0.5)).toBeUndefined();
    // A count of nothing done is not shown as an empty bar that stands still.
    expect(barValue(running, null, 0)).toBeUndefined();
  });

  it('counts parts while words are written, and the job’s own steps otherwise', () => {
    expect(barValue(running, writing(['One', 'Two']), 0)).toBe(
      writingFraction(writing(['One', 'Two'])),
    );
    expect(barValue(running, { stage: 'drawing', title: '', outline: [] }, 2 / 3)).toBe(2 / 3);
    expect(barValue(running, null, 1 / 3)).toBe(1 / 3);
  });
});

describe('elapsedSince', () => {
  it('reads like a clock', () => {
    const began = '2026-11-21T10:00:00Z';
    const at = (seconds: number): number => Date.parse(began) + seconds * 1000;
    expect(elapsedSince(began, at(0))).toBe('0:00');
    expect(elapsedSince(began, at(42))).toBe('0:42');
    expect(elapsedSince(began, at(185))).toBe('3:05');
    // A clock that is behind the core's never shows a negative time.
    expect(elapsedSince(began, at(-5))).toBe('0:00');
  });

  it('says nothing when it is not known when the work began', () => {
    expect(elapsedSince(null, 0)).toBeNull();
    expect(elapsedSince(undefined, 0)).toBeNull();
    expect(elapsedSince('not a date', 0)).toBeNull();
  });
});
