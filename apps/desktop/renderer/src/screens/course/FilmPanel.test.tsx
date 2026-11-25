import { act, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { Course, CourseFilm, FilmMakerStatus, Job } from '@adle/contracts';
import { ToastProvider } from '@adle/design-system';

import { FilmPanel } from './FilmPanel';

/**
 * The Film tab against a stand-in for the core (ADR-065). A journey makes a film with a
 * stand-in engine (`e2e/film.spec.ts`); what a journey cannot do is set the film maker up,
 * which downloads it: that is tried here, with the download failing.
 */
const core = {
  view: null as unknown as CourseFilm,
  maker: null as unknown as FilmMakerStatus,
  jobs: new Map<string, Job>(),
  asked: [] as string[],
};

vi.mock('../../lib/core-client', () => ({
  describeError: (error: unknown) => (error instanceof Error ? error.message : String(error)),
  callCore: (operation: string, request?: { path?: Record<string, string> }) => {
    core.asked.push(operation);
    const copy = <T,>(value: T): T => structuredClone(value);
    switch (operation) {
      case 'films.get':
        return Promise.resolve(copy(core.view));
      case 'films.maker_status':
        return Promise.resolve(copy(core.maker));
      case 'provider.status':
        return Promise.reject(new Error('not needed'));
      case 'films.set_up_maker': {
        const job = {
          id: 'job_setup',
          kind: 'film_setup',
          course_id: null,
          subject_id: 'film-engine',
          status: 'running',
          progress_done: 0,
          progress_total: 0,
          progress_message: 'Downloading the film maker',
          result: null,
          error_code: null,
          error_message: null,
        } as Job;
        core.jobs.set(job.id, job);
        core.maker.setting_up = job;
        return Promise.resolve(copy(job));
      }
      case 'jobs.get':
        return Promise.resolve(copy(core.jobs.get(request?.path?.job_id ?? '')!));
      default:
        return Promise.reject(new Error(`unexpected ${operation}`));
    }
  },
}));

vi.mock('../../app/FilmWatch', () => ({
  useFilmWatch: () => ({ jobs: [], refresh: () => undefined }),
}));

const COURSE = { id: `crs_${'1'.repeat(20)}`, title: 'Photosynthesis' } as Course;

beforeEach(() => {
  core.asked = [];
  core.jobs.clear();
  core.view = {
    plan: { chapters: ['Light', 'Sugar'], requests_at_most: 8, voice: null, blocked: null },
    film: null,
  };
  core.maker = {
    ready: false,
    fits: true,
    borrowed: false,
    setting_up: null,
    download_bytes: 109_523_022,
    installed_bytes: 300_000_000,
    sources: ['GitHub', 'the Python Package Index'],
  };
});

function show(): void {
  render(
    <ToastProvider>
      <FilmPanel course={COURSE} />
    </ToastProvider>,
  );
}

describe('the Film tab', () => {
  it('says what setting the film maker up downloads before anything is', async () => {
    show();
    expect(
      await screen.findByText(
        /needs the film maker on this computer: about 110 MB from GitHub and the Python Package Index, and about 300 MB once it is set up/,
      ),
    ).toBeTruthy();
    expect(core.asked).not.toContain('films.set_up_maker');
  });

  it('says a setup that failed, and offers it again', async () => {
    show();
    const setUp = await screen.findByRole('button', { name: 'Set up the film maker' });
    await act(async () => {
      setUp.click();
      await Promise.resolve();
    });
    expect(core.asked).toContain('films.set_up_maker');
    expect(await screen.findByText('Setting up the film maker')).toBeTruthy();

    // The download fails: the setup ends, and nothing is set up.
    const job = core.jobs.get('job_setup')!;
    job.status = 'failed';
    job.error_message = 'Couldn’t download the film maker. Check the connection and try again.';
    core.maker.setting_up = null;

    expect(
      await screen.findByText(
        'Couldn’t download the film maker. Check the connection and try again.',
        {},
        { timeout: 4000 },
      ),
    ).toBeTruthy();
    expect(screen.getByText('Couldn’t set up the film maker')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Set up the film maker' })).toBeTruthy();
  });

  it('says plainly where the film maker does not run', async () => {
    core.maker.fits = false;
    show();
    expect(
      await screen.findByText('The film maker doesn’t run on this kind of computer.'),
    ).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Set up the film maker' })).toBeNull();
  });
});
