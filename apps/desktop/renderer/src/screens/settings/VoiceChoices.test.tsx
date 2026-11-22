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
};

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
      case 'voice.choose': {
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
  core.jobs.clear();
  core.status = {
    tiers: [
      aTier('kokoro', 'Natural', {
        speakers: [
          { id: 'af_heart', name: 'Heart', description: 'A warm American voice.' },
          { id: 'bf_emma', name: 'Emma', description: 'A calm British voice.' },
        ],
      }),
      aTier('standard', 'Rich', { model_bytes: 2_880_000_000, program_bytes: 2_909_000_000 }),
      aTier('expressive', 'Expressive', {
        fits: false,
        why: 'It needs an NVIDIA graphics card with 8 GB of memory; this one has 6 GB.',
      }),
    ],
    tier: null,
    enabled: false,
    speakers: { kokoro: 'af_heart', standard: 'Aiden' },
    recommended: 'standard',
    gpu: 'A small card',
    borrowed: false,
    setting_up: null,
  };
});

afterEach(() => {
  vi.useRealTimers();
});

describe('the voices to choose from', () => {
  it('go from the computer’s own to the richest, and say why one cannot run here', async () => {
    show();
    await look();
    const names = within(screen.getByRole('list', { name: 'Voices' }))
      .getAllByRole('heading')
      .map((heading) => heading.textContent);
    expect(names).toEqual(['Computer’s voice', 'Natural', 'Rich', 'Expressive']);
    expect(within(card('Computer’s voice')).getByText('In use')).toBeInTheDocument();
    expect(within(card('Natural')).getByText('about 0.6 GB')).toBeInTheDocument();
    expect(within(card('Rich')).getByText('Best for this computer')).toBeInTheDocument();
    expect(within(card('Rich')).getByText('about 5.8 GB')).toBeInTheDocument();
    const expressive = card('Expressive');
    expect(
      within(expressive).getByText(
        'It needs an NVIDIA graphics card with 8 GB of memory; this one has 6 GB.',
      ),
    ).toBeInTheDocument();
    expect(within(expressive).queryByRole('button')).toBeNull();
  });

  it('set one up in the background, show how far it has come, and say when it is ready', async () => {
    show();
    await look();
    await press('Set up the Rich voice');
    expect(core.asked).toContain('voice.install');
    // One at a time: the other waits.
    expect(screen.getByRole('button', { name: 'Set up the Natural voice' })).toBeDisabled();
    expect(within(card('Natural')).getByText('Another voice is being set up.')).toBeVisible();
    expect(
      within(card('Rich')).getByRole('progressbar', { name: 'Waiting to start' }),
    ).toBeVisible();

    const job = core.jobs.get('job_setup')!;
    Object.assign(job, {
      status: 'running',
      progress_message: 'Downloading the voice',
      progress_done: 1_200_000_000,
      progress_total: 2_880_000_000,
    });
    await look();
    const bar = within(card('Rich')).getByRole('progressbar', { name: 'Downloading the voice' });
    expect(bar).toHaveAttribute('aria-valuetext', '1.2 of 2.9 GB');

    Object.assign(job, { status: 'succeeded', progress_message: 'Done' });
    core.status.setting_up = null;
    core.status.tiers[1]!.ready = true;
    Object.assign(core.status, { tier: 'standard', enabled: true });
    await look();
    expect(within(card('Rich')).getByText('In use')).toBeInTheDocument();
    expect(within(card('Computer’s voice')).queryByText('In use')).toBeNull();
    expect(screen.getByRole('status')).toHaveTextContent('The Rich voice is ready');
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
    const speaker = within(card('Natural')).getByRole('combobox', { name: 'Speaker' });
    await act(async () => {
      fireEvent.change(speaker, { target: { value: 'bf_emma' } });
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(core.status.speakers.kokoro).toBe('bf_emma');
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
