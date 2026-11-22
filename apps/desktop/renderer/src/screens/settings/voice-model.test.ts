import { describe, expect, it } from 'vitest';

import type { Job, VoiceStatus, VoiceTier } from '@adle/contracts';

import {
  aboutSize,
  computerVoiceInUse,
  downloadNote,
  isRecommended,
  setupProgress,
  tierState,
} from './voice-model';

function aTier(id: VoiceTier['id'], overrides: Partial<VoiceTier> = {}): VoiceTier {
  return {
    id,
    name: id,
    description: '',
    model_bytes: 330_000_000,
    program_bytes: 231_000_000,
    min_memory_gb: null,
    sources: ['Hugging Face', 'the Python Package Index', 'PyTorch', 'GitHub'],
    speakers: [],
    ready: false,
    fits: true,
    why: '',
    ...overrides,
  };
}

function aJob(overrides: Partial<Job> = {}): Job {
  return {
    id: 'job_1',
    kind: 'voice_setup',
    course_id: null,
    subject_id: 'kokoro',
    status: 'running',
    progress_done: 0,
    progress_total: 0,
    progress_message: '',
    result: null,
    error_code: null,
    error_message: null,
    ...overrides,
  };
}

function aStatus(overrides: Partial<VoiceStatus> = {}): VoiceStatus {
  return {
    tiers: [aTier('kokoro'), aTier('standard'), aTier('expressive')],
    tier: null,
    enabled: false,
    speakers: {},
    recommended: 'expressive',
    gpu: null,
    borrowed: false,
    setting_up: null,
    ...overrides,
  };
}

describe('the sizes of a download', () => {
  it('are said as a person would say them', () => {
    expect(aboutSize(561_000_000)).toBe('about 0.6 GB');
    expect(aboutSize(5_790_000_000)).toBe('about 5.8 GB');
    expect(aboutSize(11_670_000_000)).toBe('about 12 GB');
    expect(aboutSize(42_000_000)).toBe('about 42 MB');
  });

  it('say where a setup downloads from, and that nothing of the learner’s goes', () => {
    expect(downloadNote(aTier('kokoro'))).toBe(
      'Downloads about 0.6 GB from Hugging Face, the Python Package Index, PyTorch, and GitHub: ' +
        'the voice, and the programs it runs with. Nothing of yours is sent. Once it is set up ' +
        'it works without a connection.',
    );
  });
});

describe('where a voice stands', () => {
  it('is in use, set up, being set up, waiting, offered, or out of reach', () => {
    const job = aJob({ subject_id: 'standard' });
    const status = aStatus({
      tiers: [
        aTier('kokoro', { ready: true }),
        aTier('standard'),
        aTier('expressive', { fits: false, why: 'It needs an NVIDIA graphics card.' }),
      ],
      tier: 'kokoro',
      enabled: true,
      setting_up: job,
    });
    const [kokoro, standard, expressive] = status.tiers;
    expect(tierState(status, kokoro!)).toEqual({ kind: 'in-use' });
    expect(tierState(status, standard!)).toEqual({ kind: 'setting-up', job });
    expect(tierState(status, expressive!)).toEqual({
      kind: 'unavailable',
      why: 'It needs an NVIDIA graphics card.',
    });
    expect(computerVoiceInUse(status)).toBe(false);

    const off = { ...status, enabled: false, setting_up: null };
    expect(tierState(off, kokoro!)).toEqual({ kind: 'ready' });
    expect(tierState(off, standard!)).toEqual({ kind: 'available' });
    expect(computerVoiceInUse(off)).toBe(true);
    // One voice is set up at a time.
    const another = { ...off, setting_up: aJob({ subject_id: 'kokoro' }) };
    expect(tierState(another, standard!)).toEqual({ kind: 'waiting' });
  });

  it('offers the richest this computer runs as the best, until one is set up', () => {
    const status = aStatus({ recommended: 'standard' });
    expect(status.tiers.map((tier) => isRecommended(status, tier))).toEqual([false, true, false]);
    const one = aStatus({ tiers: [aTier('kokoro', { ready: true }), aTier('standard')] });
    expect(one.tiers.some((tier) => isRecommended(one, tier))).toBe(false);
  });
});

describe('a setup’s progress', () => {
  it('says what it is doing and how much of it is done', () => {
    expect(
      setupProgress(
        aJob({
          progress_message: 'Downloading the voice',
          progress_done: 1_200_000_000,
          progress_total: 2_880_000_000,
        }),
      ),
    ).toEqual({ label: 'Downloading the voice', value: 1.2 / 2.88, valueText: '1.2 of 2.9 GB' });
    expect(
      setupProgress(
        aJob({
          progress_message: 'Downloading the voice’s programs',
          progress_done: 40,
          progress_total: 96,
        }),
      ),
    ).toEqual({ label: 'Downloading the voice’s programs', value: 40 / 96, valueText: '40 of 96' });
  });

  it('is a bar that does not pretend to know when nobody does', () => {
    expect(setupProgress(aJob({ progress_message: 'Installing the voice’s programs' }))).toEqual({
      label: 'Installing the voice’s programs',
      value: undefined,
      valueText: undefined,
    });
    expect(setupProgress(aJob({ status: 'queued' })).label).toBe('Waiting to start');
  });
});
