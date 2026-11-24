import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { Job, LearnerPreferences, VoiceStatus, VoiceTier } from '@adle/contracts';
import { ToastProvider } from '@adle/design-system';

/**
 * A stand-in for the core's voice: it answers the operations the cards send, and a setup
 * moves on only when a test says so.
 */
const core = {
  status: null as unknown as VoiceStatus,
  jobs: new Map<string, Job>(),
  asked: [] as string[],
  sampled: [] as Record<string, unknown>[],
};

/** What was played, by where it was played from. */
const played: string[] = [];

vi.mock('../../lib/core-client', () => ({
  describeError: (error: unknown) => (error instanceof Error ? error.message : String(error)),
  callCore: (operation: string, request?: Record<string, never>) => {
    core.asked.push(operation);
    const body = (request as { body?: Record<string, unknown> } | undefined)?.body ?? {};
    const path = (request as { path?: Record<string, string> } | undefined)?.path ?? {};
    const copy = <T,>(value: T): T => structuredClone(value);
    switch (operation) {
      case 'voice.status':
        return Promise.resolve(copy(core.status));
      case 'voice.install': {
        const job: Job = {
          id: 'job_setup',
          kind: 'voice_setup',
          course_id: null,
          subject_id: String(body.tier),
          status: 'queued',
          progress_done: 0,
          progress_total: 0,
          progress_message: '',
          result: null,
          error_code: null,
          error_message: null,
        };
        core.jobs.set(job.id, job);
        core.status.setting_up = job;
        return Promise.resolve(copy(job));
      }
      case 'jobs.get':
        return Promise.resolve(copy(core.jobs.get(path.job_id!)!));
      case 'jobs.cancel': {
        const job = core.jobs.get(path.job_id!)!;
        job.status = 'cancelled';
        core.status.setting_up = null;
        return Promise.resolve(copy(job));
      }
      case 'voice.remove': {
        const tier = core.status.tiers.find((each) => each.id === path.tier)!;
        tier.ready = false;
        if (core.status.tier === tier.id) core.status.tier = null;
        core.status.enabled = core.status.tier !== null;
        return Promise.resolve(copy(core.status));
      }
      case 'voice.sample': {
        core.sampled.push({ ...body });
        const job: Job = {
          id: `job_sample_${core.sampled.length}`,
          kind: 'voice_sample',
          course_id: null,
          subject_id: null,
          status: 'running',
          progress_done: 0,
          progress_total: 1,
          progress_message: 'Making a sample',
          result: null,
          error_code: null,
          error_message: null,
        };
        core.jobs.set(job.id, job);
        return Promise.resolve(copy(job));
      }
      case 'voice.sample_clip':
        return Promise.resolve({ mime: 'audio/wav', data: 'UklGRg==' });
      case 'voice.choose': {
        if (typeof body.design === 'string') core.status.design = body.design;
        if (typeof body.enabled === 'boolean') core.status.enabled = body.enabled;
        if (typeof body.tier === 'string') core.status.tier = body.tier as VoiceStatus['tier'];
        if (typeof body.speaker === 'string')
          core.status.speakers[String(body.tier)] = body.speaker;
        return Promise.resolve(copy(core.status));
      }
      default:
        return Promise.reject(new Error(`unexpected ${operation}`));
    }
  },
}));

const { LOOK_EVERY_MS, VoiceChoices } = await import('./VoiceChoices');

function aTier(id: VoiceTier['id'], name: string, overrides: Partial<VoiceTier> = {}): VoiceTier {
  return {
    id,
    name,
    description: `The ${name} voice.`,
    model_bytes: 330_000_000,
    program_bytes: 231_000_000,
    min_memory_gb: null,
    sources: ['Hugging Face', 'the Python Package Index', 'PyTorch'],
    speakers: [],
    ready: false,
    fits: true,
    why: '',
    ...overrides,
  };
}

const PREFERENCES: LearnerPreferences = {
  captions: true,
  explanation_density: 'balanced',
  goal: '',
  narration: true,
  pace: 'standard',
  voice: '',
  volume: 80,
};

function show(): void {
  render(
    <ToastProvider>
      <VoiceChoices preferences={PREFERENCES} onChange={() => undefined} />
    </ToastProvider>,
  );
}

const card = (name: string): HTMLElement =>
  screen.getByRole('listitem', { name: new RegExp(`^${name}`) });

async function look(): Promise<void> {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(LOOK_EVERY_MS);
  });
}

async function press(name: string): Promise<void> {
  await act(async () => {
    screen.getByRole('button', { name }).click();
    await vi.advanceTimersByTimeAsync(0);
  });
}

beforeEach(() => {
  vi.useFakeTimers();
  core.asked.length = 0;
  core.sampled.length = 0;
  played.length = 0;
  core.jobs.clear();
  vi.stubGlobal(
    'Audio',
    class {
      constructor(readonly src: string) {}
      play(): Promise<void> {
        played.push(this.src);
        return Promise.resolve();
      }
      pause(): void {
        played.push(`paused ${this.src}`);
      }
    },
  );
  URL.createObjectURL = () => 'blob:sample';
  URL.revokeObjectURL = () => undefined;
  core.status = {
    tiers: [
      aTier('kokoro', 'Natural', {
        speakers: [
          { id: 'af_heart', name: 'Heart', description: 'A warm American voice.' },
          { id: 'bf_emma', name: 'Emma', description: 'A calm British voice.' },
        ],
      }),
      aTier('expressive', 'Expressive', {
        model_bytes: 2_880_000_000,
        program_bytes: 2_909_000_000,
        fits: false,
        why: 'It needs an NVIDIA graphics card with 8 GB of memory; this one has 6 GB.',
      }),
    ],
    tier: null,
    enabled: false,
    speakers: { kokoro: 'af_heart' },
    recommended: 'kokoro',
    gpu: 'A small card',
    borrowed: false,
    setting_up: null,
    design: 'A warm, clear voice.',
    design_presets: [
      { name: 'Warm teacher', text: 'A warm, clear voice.' },
      { name: 'Calm and low', text: 'A calm, low voice.' },
    ],
    recording: [],
  };
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

/** The Expressive voice set up and fitting, in use or only ready. */
function expressiveHere(inUse: boolean): void {
  Object.assign(core.status.tiers[1]!, { fits: true, why: '', ready: true });
  if (inUse) Object.assign(core.status, { tier: 'expressive', enabled: true });
}

describe('the voices to choose from', () => {
  it('go from the computer’s own to the richest, and say why one cannot run here', async () => {
    show();
    await look();
    const names = within(screen.getByRole('list', { name: 'Voices' }))
      .getAllByRole('heading')
      .map((heading) => heading.textContent);
    expect(names).toEqual(['Computer’s voice', 'Natural', 'Expressive']);
    expect(within(card('Computer’s voice')).getByText('In use')).toBeInTheDocument();
    expect(within(card('Natural')).getByText('about 0.6 GB')).toBeInTheDocument();
    expect(within(card('Natural')).getByText('Best for this computer')).toBeInTheDocument();
    const expressive = card('Expressive');
    expect(
      within(expressive).getByText(
        'It needs an NVIDIA graphics card with 8 GB of memory; this one has 6 GB.',
      ),
    ).toBeInTheDocument();
    expect(within(expressive).queryByRole('button')).toBeNull();
  });

  it('set one up in the background, show how far it has come, and say when it is ready', async () => {
    Object.assign(core.status.tiers[1]!, { fits: true, why: '' });
    show();
    await look();
    await press('Set up the Expressive voice');
    expect(core.asked).toContain('voice.install');
    // One at a time: the other waits.
    expect(screen.getByRole('button', { name: 'Set up the Natural voice' })).toBeDisabled();
    expect(within(card('Natural')).getByText('Another voice is being set up.')).toBeVisible();
    expect(
      within(card('Expressive')).getByRole('progressbar', { name: 'Waiting to start' }),
    ).toBeVisible();

    const job = core.jobs.get('job_setup')!;
    Object.assign(job, {
      status: 'running',
      progress_message: 'Downloading the voice',
      progress_done: 1_200_000_000,
      progress_total: 2_880_000_000,
    });
    await look();
    const bar = within(card('Expressive')).getByRole('progressbar', {
      name: 'Downloading the voice',
    });
    expect(bar).toHaveAttribute('aria-valuetext', '1.2 of 2.9 GB');

    Object.assign(job, { status: 'succeeded', progress_message: 'Done' });
    core.status.setting_up = null;
    core.status.tiers[1]!.ready = true;
    Object.assign(core.status, { tier: 'expressive', enabled: true });
    await look();
    expect(within(card('Expressive')).getAllByText('In use')[0]).toBeInTheDocument();
    expect(within(card('Computer’s voice')).queryByText('In use')).toBeNull();
    expect(screen.getAllByRole('status')[0]).toHaveTextContent('The Expressive voice is ready');
  });

  it('stop a setup when asked, and offer it again', async () => {
    show();
    await look();
    await press('Set up the Natural voice');
    await press('Stop setting up the Natural voice');
    expect(core.asked).toContain('jobs.cancel');
    await look();
    expect(screen.getByRole('button', { name: 'Set up the Natural voice' })).toBeEnabled();
    expect(screen.queryByRole('progressbar')).toBeNull();
  });

  it('say why a setup failed, where it failed', async () => {
    show();
    await look();
    await press('Set up the Natural voice');
    Object.assign(core.jobs.get('job_setup')!, {
      status: 'failed',
      error_code: 'voice_setup_failed',
      error_message: 'Couldn’t download the voice. Check the connection and try again.',
    });
    core.status.setting_up = null;
    await look();
    const failed = within(card('Natural')).getByText(
      'Couldn’t download the voice. Check the connection and try again.',
    );
    expect(failed).toBeVisible();
    expect(screen.getByRole('button', { name: 'Set up the Natural voice' })).toBeEnabled();
  });

  it('choose a speaker of the voice in use, and go back to the computer’s voice', async () => {
    Object.assign(core.status, { tier: 'kokoro', enabled: true });
    core.status.tiers[0]!.ready = true;
    show();
    await look();
    const heart = within(card('Natural')).getByRole('button', { name: 'Use Heart' });
    expect(heart).toHaveAttribute('aria-pressed', 'true');
    await press('Use Emma');
    expect(core.status.speakers.kokoro).toBe('bf_emma');
    expect(within(card('Natural')).getByRole('button', { name: 'Use Emma' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    await press('Use the computer’s voice');
    expect(core.status.enabled).toBe(false);
    expect(within(card('Computer’s voice')).getByText('In use')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Use the Natural voice' })).toBeVisible();
  });

  it('remove a voice only once it is said what that frees', async () => {
    Object.assign(core.status, { tier: 'kokoro', enabled: true });
    core.status.tiers[0]!.ready = true;
    show();
    await look();
    await press('Remove the Natural voice');
    const dialog = screen.getByRole('dialog', { name: 'Remove the Natural voice?' });
    expect(dialog).toHaveTextContent('Frees about 0.6 GB at most.');
    expect(core.asked).not.toContain('voice.remove');
    await act(async () => {
      within(dialog).getByRole('button', { name: 'Remove' }).click();
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(core.asked).toContain('voice.remove');
    expect(screen.getByRole('status')).toHaveTextContent('The Natural voice was removed');
    expect(screen.getByRole('button', { name: 'Set up the Natural voice' })).toBeVisible();
  });

  it('offer nothing to set up or remove for a voice set up by hand', async () => {
    Object.assign(core.status, { tier: 'kokoro', enabled: true, borrowed: true });
    core.status.tiers[0]!.ready = true;
    show();
    await look();
    expect(screen.queryByRole('button', { name: /^Set up|^Remove/ })).toBeNull();
  });
});

describe('listening before choosing, and the voice in the learner’s words (ADR-057)', () => {
  it('plays a sample of a speaker, made by the core, without choosing it', async () => {
    core.status.tiers[0]!.ready = true;
    show();
    await look();
    // Set up and not in use: each speaker can be heard; none can be chosen yet.
    expect(within(card('Natural')).queryByRole('button', { name: 'Use Emma' })).toBeNull();
    await press('Listen to Emma');
    expect(core.sampled).toEqual([{ tier: 'kokoro', speaker: 'bf_emma' }]);
    expect(within(card('Natural')).getByRole('button', { name: 'Listen to Heart' })).toBeDisabled();
    Object.assign(core.jobs.get('job_sample_1')!, {
      status: 'succeeded',
      result: { kind: 'voice_sample', sample: 'a'.repeat(24) },
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(500);
    });
    expect(core.asked).toContain('voice.sample_clip');
    expect(played).toEqual(['blob:sample']);
    expect(core.status.speakers.kokoro).toBe('af_heart');
    expect(within(card('Natural')).getByRole('button', { name: 'Listen to Heart' })).toBeEnabled();
  });

  it('describes the Expressive voice in the learner’s words, from a preset or their own', async () => {
    expressiveHere(true);
    show();
    await look();
    const expressive = card('Expressive');
    const voice = within(expressive).getByRole('textbox', { name: 'The voice' });
    expect(voice).toHaveValue('A warm, clear voice.');
    const save = within(expressive).getByRole('button', { name: 'Save' });
    expect(save).toBeDisabled();
    const presets = within(expressive).getByRole('combobox', { name: 'Start from' });
    await act(async () => {
      fireEvent.change(presets, { target: { value: 'Calm and low' } });
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(voice).toHaveValue('A calm, low voice.');
    await act(async () => {
      fireEvent.change(voice, { target: { value: 'A deep, slow voice.' } });
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(presets).toHaveValue('');
    // Heard before it is kept.
    await press('Listen to this voice');
    expect(core.sampled).toEqual([{ tier: 'expressive', design: 'A deep, slow voice.' }]);
    await act(async () => {
      within(expressive).getByRole('button', { name: 'Save' }).click();
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(core.status.design).toBe('A deep, slow voice.');
    expect(
      screen.getAllByRole('status').some((item) => item.textContent?.includes('Voice saved')),
    ).toBe(true);
  });

  it('says which lessons are being recorded in a voice just chosen, until they are', async () => {
    Object.assign(core.status, { tier: 'kokoro', enabled: true });
    core.status.tiers[0]!.ready = true;
    core.status.recording = [{ lesson_id: 'les_1', title: 'Weights and bias', done: 3, total: 20 }];
    show();
    await look();
    const note = 'Recording “Weights and bias” in this voice (3 of 20 lines).';
    expect(within(card('Natural')).getByText(note)).toBeVisible();
    core.status.recording = [];
    await look();
    expect(within(card('Natural')).queryByText(note)).toBeNull();
  });
});
