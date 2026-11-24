import { describe, expect, it } from 'vitest';

import type { Job, VoiceStatus, VoiceTier } from '@adle/contracts';

import {
  aboutSize,
  computerVoiceInUse,
  downloadNote,
  speedNote,
  isRecommended,
  presetOf,
  recordingNote,
  sameParts,
  setupProgress,
  tierState,
  voiceRequest,
  withPart,
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
    tiers: [aTier('kokoro'), aTier('expressive')],
    tier: null,
    enabled: false,
    speakers: {},
    recommended: 'expressive',
    gpu: null,
    borrowed: false,
    setting_up: null,
    design: 'A warm voice.',
    design_parts: {},
    design_choices: [],
    design_presets: [],
    recording: [],
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
    const job = aJob({ subject_id: 'expressive' });
    const status = aStatus({
      tiers: [aTier('kokoro', { ready: true }), aTier('expressive')],
      tier: 'kokoro',
      enabled: true,
      setting_up: job,
    });
    const [kokoro, expressive] = status.tiers;
    expect(tierState(status, kokoro!)).toEqual({ kind: 'in-use' });
    expect(tierState(status, expressive!)).toEqual({ kind: 'setting-up', job });
    expect(computerVoiceInUse(status)).toBe(false);

    const off = { ...status, enabled: false, setting_up: null };
    expect(tierState(off, kokoro!)).toEqual({ kind: 'ready' });
    expect(tierState(off, expressive!)).toEqual({ kind: 'available' });
    expect(computerVoiceInUse(off)).toBe(true);
    // One voice is set up at a time.
    const another = { ...off, setting_up: aJob({ subject_id: 'kokoro' }) };
    expect(tierState(another, expressive!)).toEqual({ kind: 'waiting' });
    const unable = aTier('expressive', { fits: false, why: 'It needs an NVIDIA graphics card.' });
    expect(tierState(off, unable)).toEqual({
      kind: 'unavailable',
      why: 'It needs an NVIDIA graphics card.',
    });
  });

  it('offers the richest this computer runs as the best, until one is set up', () => {
    const status = aStatus({ recommended: 'expressive' });
    expect(status.tiers.map((tier) => isRecommended(status, tier))).toEqual([false, true]);
    const one = aStatus({ tiers: [aTier('kokoro', { ready: true }), aTier('expressive')] });
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

describe('speedNote', () => {
  it('says so where a voice set up here is slower than speech, and says nothing otherwise', () => {
    expect(speedNote(aTier('kokoro', { ready: true, speed: 'slower' }))).toBe(
      'Slower than speech on this computer, so a lesson in it takes longer to be ready.',
    );
    expect(speedNote(aTier('kokoro', { ready: true, speed: 'faster' }))).toBeNull();
    expect(speedNote(aTier('kokoro', { ready: true }))).toBeNull();
    // Not set up here: nothing has been timed.
    expect(speedNote(aTier('expressive', { speed: 'slower' }))).toBeNull();
  });
});

describe('recordingNote', () => {
  it('says which lesson is being recorded in a voice just chosen, and how far it has come', () => {
    expect(recordingNote([])).toBeNull();
    const first = { lesson_id: 'les_1', title: 'Weights and bias', done: 3, total: 20 };
    expect(recordingNote([first])).toBe(
      'Recording “Weights and bias” in this voice (3 of 20 lines).',
    );
    expect(recordingNote([first, { ...first, lesson_id: 'les_2', done: 0 }])).toBe(
      'Recording “Weights and bias” in this voice (3 of 20 lines), then 1 more lesson.',
    );
    expect(recordingNote([{ ...first, total: 0 }])).toBe(
      'Recording “Weights and bias” in this voice.',
    );
  });
});

describe('a voice put together from parts (ADR-062)', () => {
  const presets = [
    { name: 'Adle’s own', text: 'A warm voice.', parts: {} },
    { name: 'Calm narrator', text: 'A calm man.', parts: { speaker: 'man', feeling: 'calm' } },
  ];

  it('changes one part at a time, and leaves out a part chosen as nothing', () => {
    expect(withPart({}, 'speaker', 'woman')).toEqual({ speaker: 'woman' });
    expect(withPart({ speaker: 'woman', pace: 'slow' }, 'pace', 'fast')).toEqual({
      speaker: 'woman',
      pace: 'fast',
    });
    expect(withPart({ speaker: 'woman', pace: 'slow' }, 'speaker', '')).toEqual({ pace: 'slow' });
    expect(withPart({ speaker: undefined, pace: '' }, 'tone', 'deep')).toEqual({ tone: 'deep' });
  });

  it('knows the same parts whatever order they were chosen in', () => {
    expect(sameParts({ speaker: 'man', pace: 'slow' }, { pace: 'slow', speaker: 'man' })).toBe(
      true,
    );
    expect(sameParts({ speaker: 'man' }, { speaker: 'man', pace: undefined })).toBe(true);
    expect(sameParts({ speaker: 'man' }, { speaker: 'woman' })).toBe(false);
    expect(sameParts({ speaker: 'man' }, {})).toBe(false);
  });

  it('is still the voice it started from only while its parts and its words both are', () => {
    expect(presetOf(presets, {}, 'A warm voice.')).toBe('Adle’s own');
    expect(presetOf(presets, { feeling: 'calm', speaker: 'man' }, ' A calm man. ')).toBe(
      'Calm narrator',
    );
    // A part changed, or words of the learner's own.
    expect(presetOf(presets, { feeling: 'calm' }, 'A calm speaker.')).toBe('');
    expect(presetOf(presets, {}, 'A calm man.')).toBe('');
  });

  it('is saved and heard by its parts when it has any, or else in its words', () => {
    expect(voiceRequest({ speaker: 'man', pace: undefined }, 'A man.')).toEqual({
      parts: { speaker: 'man' },
    });
    expect(voiceRequest({}, '  A deep, slow voice. ')).toEqual({ design: 'A deep, slow voice.' });
  });
});
