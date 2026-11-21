import { describe, expect, it } from 'vitest';

import type { Job, ProviderStatus } from '@adle/contracts';

import { aboutHowLong, destination, readCheck, tookHowLong, usualWait } from './provider';

const route = (sentence: string, seconds: number) => ({
  sentence,
  reason: '',
  names: [],
  provider_ids: [],
  wait_seconds: seconds,
  wait_measured: false,
});

const status = {
  routes: {
    ask: route('AIHubMix, or NVIDIA NIM if AIHubMix cannot answer', 15),
    curriculum: route('AIHubMix', 30),
    lesson: route('NVIDIA NIM', 700),
  },
} as unknown as ProviderStatus;

describe('destination', () => {
  it('is what the core plans for that kind of request, word for word', () => {
    expect(destination(status, 'ask')).toBe('AIHubMix, or NVIDIA NIM if AIHubMix cannot answer');
    expect(destination(status, 'lesson')).toBe('NVIDIA NIM');
  });

  it('names no provider while it is not known which', () => {
    expect(destination(undefined, 'lesson')).toBe('your AI provider');
  });
});

describe('aboutHowLong', () => {
  it('is never more exact than a wait can be known', () => {
    expect(aboutHowLong(8)).toBe('a few seconds');
    expect(aboutHowLong(30)).toBe('under a minute');
    expect(aboutHowLong(75)).toBe('about a minute');
    expect(aboutHowLong(150)).toBe('about 3 minutes');
    expect(aboutHowLong(700)).toBe('about 12 minutes');
  });
});

describe('usualWait', () => {
  it('puts the wait of a kind of request into words, or says nothing', () => {
    expect(usualWait(status, 'lesson')).toBe('about 12 minutes');
    expect(usualWait(status, 'ask')).toBe('a few seconds');
    expect(usualWait(undefined, 'lesson')).toBeNull();
  });
});

describe('tookHowLong', () => {
  it('says how long an answer took as a person would', () => {
    expect(tookHowLong(0.2)).toBe('in under a second');
    expect(tookHowLong(2.44)).toBe('in 2.4 seconds');
    expect(tookHowLong(41.6)).toBe('in 42 seconds');
    expect(tookHowLong(200)).toBe('in 3 minutes');
    expect(tookHowLong(Number.NaN)).toBe('in under a second');
  });
});

describe('readCheck', () => {
  const job = (changes: Partial<Job>): Job => ({
    id: 'job_1',
    kind: 'provider_check',
    course_id: null,
    subject_id: 'nvidia',
    status: 'succeeded',
    progress_done: 1,
    progress_total: 1,
    progress_message: 'Done',
    result: { provider: 'NVIDIA NIM', model: 'Kimi K3.1 Pro', seconds: 3.21, note: '' },
    error_code: null,
    error_message: null,
    ...changes,
  });

  it('reads who answered and how long it took', () => {
    expect(readCheck(job({}))).toEqual({
      provider: 'NVIDIA NIM',
      model: 'Kimi K3.1 Pro',
      took: 'in 3.2 seconds',
      note: '',
    });
  });

  it('is nothing until a check has succeeded, and nothing for another kind of job', () => {
    expect(readCheck(null)).toBeNull();
    expect(readCheck(job({ status: 'running', result: null }))).toBeNull();
    expect(readCheck(job({ status: 'failed', result: null }))).toBeNull();
    expect(readCheck(job({ kind: 'lesson_generation' }))).toBeNull();
    expect(readCheck(job({ result: { model: 'x' } }))).toBeNull();
    expect(readCheck(job({ result: 'ready' }))).toBeNull();
  });
});
