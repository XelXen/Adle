import { describe, expect, it } from 'vitest';

import type { Job } from '@adle/contracts';

import {
  authorName,
  hasLessonToStart,
  isDrawingPictures,
  isWritingTheRest,
  jobFailure,
  jobProgress,
  keptNeeds,
  KIND_LESSON,
  KIND_PROPOSAL,
  lessonDisclosure,
  lessonNotice,
  readLessonOutcome,
  titled,
  readProposal,
} from './generation';

function job(changes: Partial<Job> = {}): Job {
  return {
    id: 'job_00000000000000000001',
    kind: KIND_PROPOSAL,
    course_id: 'crs_00000000000000000001',
    subject_id: 'crs_00000000000000000001',
    status: 'succeeded',
    progress_done: 0,
    progress_total: 0,
    progress_message: '',
    result: null,
    error_code: null,
    error_message: null,
    ...changes,
  };
}

const PROPOSAL = {
  kind: KIND_PROPOSAL,
  concepts: [
    {
      title: 'Limits',
      summary: 'What a function approaches.',
      objectives: ['Estimate a limit.'],
      needs: [],
      section_ids: [],
    },
    {
      title: 'Derivatives',
      summary: '',
      objectives: ['Compute a derivative.', 7],
      needs: [{ index: 0, reason: 'A derivative is a limit.' }, { index: 'x' }, null],
      section_ids: ['sec_1'],
    },
  ],
  grounded_in_materials: true,
  accepted: false,
};

describe('lessonDisclosure', () => {
  it('names what is said about the learner, not only what is said about the concept', () => {
    for (const materials of ['some', 'none', 'unknown'] as const) {
      const said = lessonDisclosure(materials);
      for (const item of ['your level', 'preferences', 'goal', 'course name', 'objectives']) {
        expect(said).toContain(item);
      }
    }
  });

  it('mentions passages from the materials only when there may be some', () => {
    expect(lessonDisclosure('none')).not.toContain('materials');
    expect(lessonDisclosure('some')).toContain('a few passages from your materials');
    expect(lessonDisclosure('unknown')).toContain('any related passages from your materials');
  });
});

describe('readProposal', () => {
  it('reads the concepts, what each needs, and where the proposal came from', () => {
    const proposal = readProposal(job({ result: PROPOSAL }));
    expect(proposal).toEqual({
      concepts: [
        {
          title: 'Limits',
          summary: 'What a function approaches.',
          objectives: ['Estimate a limit.'],
          needs: [],
        },
        {
          title: 'Derivatives',
          summary: '',
          // Anything that is not text is dropped rather than shown.
          objectives: ['Compute a derivative.'],
          needs: [{ index: 0, reason: 'A derivative is a limit.' }],
        },
      ],
      groundedInMaterials: true,
      closed: false,
      // A proposal made before authors were recorded does not say who made it.
      writtenBy: null,
    });
  });

  it('reads who suggested it, and whether another model stood in', () => {
    const note = 'Kimi K3.1 Pro was not available, so Mistral Large 4 wrote this in its place.';
    const proposal = readProposal(
      job({
        result: {
          ...PROPOSAL,
          written_by: {
            provider: 'NVIDIA NIM',
            models: ['Mistral Large 4', 7],
            instead_of: 'Kimi K3.1 Pro',
            note,
          },
        },
      }),
    );
    expect(proposal?.writtenBy).toEqual({
      provider: 'NVIDIA NIM',
      models: ['Mistral Large 4'],
      note,
    });
  });

  it.each([
    ['text', 'NVIDIA NIM'],
    ['no provider', { models: ['Mistral Large 4'] }],
    ['an empty provider', { provider: '', models: [] }],
  ])('does not name an author from %s', (_label, value) => {
    expect(readProposal(job({ result: { ...PROPOSAL, written_by: value } }))?.writtenBy).toBeNull();
  });
});

describe('authorName', () => {
  it('names the model and the provider when one model wrote it', () => {
    expect(
      authorName({ provider: 'NVIDIA NIM', models: ['Mistral Large 4'], note: '' }, 'AIHubMix'),
    ).toBe('Mistral Large 4 on NVIDIA NIM');
  });

  it('names the provider alone when several models wrote it, or none is known', () => {
    expect(authorName({ provider: 'NVIDIA NIM', models: ['A', 'B'], note: '' }, 'x')).toBe(
      'NVIDIA NIM',
    );
    expect(authorName({ provider: 'NVIDIA NIM', models: [], note: '' }, 'x')).toBe('NVIDIA NIM');
  });

  it('falls back to the name it was given for work recorded before authors were', () => {
    expect(authorName(null, 'AIHubMix')).toBe('AIHubMix');
  });

  it('knows when a proposal has been used or set aside', () => {
    expect(readProposal(job({ result: { ...PROPOSAL, accepted: true } }))?.closed).toBe(true);
    expect(readProposal(job({ result: { ...PROPOSAL, dismissed: true } }))?.closed).toBe(true);
  });

  it.each([
    ['another kind of job', job({ kind: KIND_LESSON, result: PROPOSAL })],
    ['a job that is still running', job({ status: 'running', result: PROPOSAL })],
    ['a failed job', job({ status: 'failed', result: PROPOSAL })],
    ['no result', job({ result: null })],
    ['a result of the wrong shape', job({ result: { concepts: 'none' } })],
    ['a concept without a title', job({ result: { concepts: [{ summary: 'x' }] } })],
    ['an empty proposal', job({ result: { concepts: [] } })],
  ])('is null for %s', (_label, value) => {
    expect(readProposal(value)).toBeNull();
  });

  it('is null when there is no job', () => {
    expect(readProposal(null)).toBeNull();
  });
});

describe('readLessonOutcome', () => {
  it('reads the lesson that was made and anything worth mentioning about it', () => {
    const outcome = readLessonOutcome(
      job({
        kind: KIND_LESSON,
        result: {
          kind: KIND_LESSON,
          lesson_id: 'les_00000000000000000001',
          title: 'Weights',
          pictures_planned: 2,
          pictures_made: 1,
          notes: ['One picture could not be made.', 3],
        },
      }),
    );
    expect(outcome).toEqual({
      lessonId: 'les_00000000000000000001',
      title: 'Weights',
      notes: ['One picture could not be made.'],
      picturesPending: 0,
      voicing: false,
    });
  });

  it('reads a lesson that can be started while its pictures are still being drawn', () => {
    const drawing = job({
      kind: KIND_LESSON,
      status: 'running',
      result: { lesson_id: 'les_1', title: 'Weights', pictures_pending: 2, notes: [] },
    });
    expect(readLessonOutcome(drawing)).toEqual({
      lessonId: 'les_1',
      title: 'Weights',
      notes: [],
      picturesPending: 2,
      voicing: false,
    });
    expect(isDrawingPictures(drawing)).toBe(true);
    // Once the work has ended nothing is still to come, whatever the last word on the way was.
    const ended = { ...drawing, status: 'succeeded' as const };
    expect(readLessonOutcome(ended)?.picturesPending).toBe(0);
    expect(isDrawingPictures(ended)).toBe(false);
    // Still writing the text: there is no lesson yet.
    const writing = job({ kind: KIND_LESSON, status: 'running', result: null });
    expect(readLessonOutcome(writing)).toBeNull();
    expect(isDrawingPictures(writing)).toBe(false);
    expect(isDrawingPictures(null)).toBe(false);
  });

  it('tells a lesson whose later parts are still written from one that has its pictures drawn', () => {
    const result = { lesson_id: 'les_1', title: 'Weights', pictures_pending: 1, notes: [] };
    // Begun at its first part, while the model writes the rest (ADR-048).
    const begun = job({
      kind: KIND_LESSON,
      status: 'running',
      result,
      progress_detail: { stage: 'writing', title: 'Weights', outline: ['Why weights'] },
    });
    expect(hasLessonToStart(begun)).toBe(true);
    expect(isWritingTheRest(begun)).toBe(true);
    expect(isDrawingPictures(begun)).toBe(false);
    // All of it written: what is left is its pictures.
    const drawing = { ...begun, progress_detail: { stage: 'drawing' as const } };
    expect(hasLessonToStart(drawing)).toBe(true);
    expect(isWritingTheRest(drawing)).toBe(false);
    expect(isDrawingPictures(drawing)).toBe(true);
    // Without a lesson there is nothing to start, however far the writing has come.
    const before = { ...begun, result: null };
    expect(hasLessonToStart(before)).toBe(false);
    expect(isWritingTheRest(before)).toBe(false);
    // Nor once the work has ended.
    expect(isWritingTheRest({ ...begun, status: 'succeeded' })).toBe(false);
    expect(hasLessonToStart(null)).toBe(false);
  });

  it('has a lesson in a natural voice to start once its first part can be heard', () => {
    const result = { lesson_id: 'les_1', title: 'Weights', notes: [], voicing: true };
    const written = job({
      kind: KIND_LESSON,
      status: 'running',
      result,
      progress_detail: { stage: 'writing', title: 'Weights', outline: ['Why weights'] },
    });
    // There is a lesson, and it is not ready: its first part is still being recorded.
    expect(readLessonOutcome(written)?.voicing).toBe(true);
    expect(hasLessonToStart(written)).toBe(false);
    expect(isWritingTheRest(written)).toBe(false);
    expect(lessonNotice(written, false)).toBeNull();
    // All of it written, and waiting for its voice.
    const recording = { ...written, progress_detail: { stage: 'voicing' as const } };
    expect(hasLessonToStart(recording)).toBe(false);
    expect(isDrawingPictures(recording)).toBe(false);
    // Heard: ready, while the rest is written.
    const heard = { ...written, result: { ...result, voicing: false } };
    expect(hasLessonToStart(heard)).toBe(true);
    expect(isWritingTheRest(heard)).toBe(true);
    expect(lessonNotice(heard, false)?.title).toBe('Lesson ready');
    // A job that has ended has nothing left to wait for.
    expect(readLessonOutcome({ ...written, status: 'succeeded' })?.voicing).toBe(false);
  });

  it('is null unless a lesson job has a lesson', () => {
    expect(readLessonOutcome(job({ result: { lesson_id: 'les_1' } }))).toBeNull();
    expect(readLessonOutcome(job({ kind: KIND_LESSON, status: 'cancelled' }))).toBeNull();
    expect(readLessonOutcome(job({ kind: KIND_LESSON, result: { title: 'no id' } }))).toBeNull();
    expect(readLessonOutcome(null)).toBeNull();
    // A job that failed, or was stopped before there was a lesson, has none: not even
    // if it named one on the way.
    for (const status of ['failed', 'cancelled', 'queued'] as const) {
      expect(
        readLessonOutcome(job({ kind: KIND_LESSON, status, result: { lesson_id: 'les_1' } })),
      ).toBeNull();
    }
  });
});

describe('lessonNotice', () => {
  const drawing = job({
    kind: KIND_LESSON,
    status: 'running',
    result: { lesson_id: 'les_1', title: 'Weights', pictures_pending: 2, notes: [] },
  });
  const done = (notes: string[]): Job =>
    job({ kind: KIND_LESSON, result: { lesson_id: 'les_1', title: 'Weights', notes } });

  it('says a lesson is ready as soon as it can be started', () => {
    expect(lessonNotice(drawing, false)).toEqual({
      tone: 'success',
      title: 'Lesson ready',
      description: 'Weights. Its pictures are still being drawn.',
    });
  });

  it('says the rest of it is being written when it can be started at its first part', () => {
    const begun = {
      ...drawing,
      progress_detail: { stage: 'writing' as const, title: 'Weights', outline: ['Why weights'] },
    };
    expect(lessonNotice(begun, false)).toEqual({
      tone: 'success',
      title: 'Lesson ready',
      description: 'Weights. The rest of it is being written.',
    });
    expect(lessonNotice(begun, true)).toBeNull();
  });

  it('does not say it a second time when the pictures are done', () => {
    expect(lessonNotice(drawing, true)).toBeNull();
    expect(lessonNotice(done([]), true)).toBeNull();
  });

  it('says so afterwards if a picture did not arrive', () => {
    const note = 'The picture for “The weighted sum” couldn’t be made.';
    expect(lessonNotice(done([note]), true)).toEqual({
      tone: 'info',
      title: 'About the lesson',
      description: note,
    });
  });

  it('says everything at once when the work ended before anyone was told', () => {
    expect(lessonNotice(done(['One picture is in words.']), false)).toEqual({
      tone: 'success',
      title: 'Lesson ready',
      description: 'Weights. One picture is in words.',
    });
  });

  it('has nothing to say about work that produced no lesson', () => {
    expect(lessonNotice(job({ kind: KIND_LESSON, status: 'failed' }), false)).toBeNull();
    expect(lessonNotice(job({ kind: KIND_LESSON, status: 'running' }), false)).toBeNull();
    expect(lessonNotice(job({ kind: KIND_PROPOSAL }), false)).toBeNull();
  });
});

describe('titled', () => {
  it('keeps a title and what is said about it apart', () => {
    expect(titled('Weights', [])).toBe('Weights');
    expect(titled('Weights', ['It has two pictures.'])).toBe('Weights. It has two pictures.');
    // A title that ends a sentence already is left as it is.
    expect(titled('What is a weight?', ['One note.'])).toBe('What is a weight? One note.');
    expect(titled('', ['One note.', ''])).toBe('One note.');
  });
});

describe('jobProgress', () => {
  it('has nothing to measure until the job reports a total', () => {
    expect(jobProgress(job({ status: 'running' }), 'Waiting to start')).toEqual({
      value: undefined,
      message: 'Waiting to start',
    });
  });

  it('says a queued job is waiting, whatever an earlier message said', () => {
    const queued = job({ status: 'queued', progress_message: 'old', progress_total: 3 });
    expect(jobProgress(queued, 'Waiting for another task to finish').message).toBe(
      'Waiting for another task to finish',
    );
  });

  it('reports how far along a running job is, never outside zero to one', () => {
    const running = job({
      status: 'running',
      progress_done: 1,
      progress_total: 3,
      progress_message: 'Drawing picture 1 of 2',
    });
    expect(jobProgress(running, 'x')).toEqual({ value: 1 / 3, message: 'Drawing picture 1 of 2' });
    expect(jobProgress(job({ progress_done: 9, progress_total: 3 }), 'x').value).toBe(1);
    expect(jobProgress(job({ progress_done: -1, progress_total: 3 }), 'x').value).toBe(0);
  });
});

describe('jobFailure', () => {
  const failed = (error_code: string, error_message: string | null = 'Because.') =>
    job({ status: 'failed', error_code, error_message });

  it('sends the learner to the settings when the key is the problem', () => {
    expect(jobFailure(failed('provider_key_missing'))?.remedy).toBe('settings');
    expect(jobFailure(failed('provider_key_rejected'))?.remedy).toBe('settings');
  });

  it('does not offer to try again when the allowance for today is used up', () => {
    expect(jobFailure(failed('quota_exhausted'))).toEqual({ message: 'Because.', remedy: 'wait' });
  });

  it('offers another try for anything else, with a sentence even if none was given', () => {
    expect(jobFailure(failed('provider_unavailable'))?.remedy).toBe('retry');
    expect(jobFailure(failed('generation_failed', null))).toEqual({
      message: 'Something went wrong. Please try again.',
      remedy: 'retry',
    });
  });

  it('is not a failure when the job succeeded, was cancelled, or is still going', () => {
    expect(jobFailure(job())).toBeNull();
    expect(jobFailure(job({ status: 'cancelled' }))).toBeNull();
    expect(jobFailure(job({ status: 'running' }))).toBeNull();
    expect(jobFailure(null)).toBeNull();
  });
});

describe("a notice from the provider in the model's place", () => {
  it('is shown in its own words and leads to the settings, not to trying again', () => {
    const message =
      'The AI provider answered with a notice of its own instead of passing this to the ' +
      'model. It said: "Top up to go on." This is about your account with the provider, not ' +
      'about Adle. Nothing was changed.';
    expect(
      jobFailure(job({ status: 'failed', error_code: 'provider_notice', error_message: message })),
    ).toEqual({ message, remedy: 'settings' });
  });
});

describe('keptNeeds', () => {
  it('keeps only the needs that are themselves selected', () => {
    const proposal = readProposal(job({ result: PROPOSAL }))!;
    expect(keptNeeds(proposal, new Set([0, 1]), 1)).toEqual([
      { index: 0, reason: 'A derivative is a limit.' },
    ]);
    expect(keptNeeds(proposal, new Set([1]), 1)).toEqual([]);
    expect(keptNeeds(proposal, new Set([0, 1]), 5)).toEqual([]);
  });
});
