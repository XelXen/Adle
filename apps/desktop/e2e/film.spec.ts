/**
 * A film of a whole course (ADR-065): a chapter for each concept, written by the AI,
 * checked by the film maker at every moment, put together and made into a video.
 *
 * The film maker here is a stand-in (services/core/tests/support/fake_film_engine.py):
 * ManimGX's command line and report, nothing drawn, and a small real video handed back.
 * The provider is the stand-in on this computer, whose chapter is
 * fixtures/model-answers/film-chapter.py. The window that asks where to save is replaced
 * with an answer, as everywhere. Everything else is the real path: the core writes, checks
 * and puts the film together in a lane of its own, the page fetches the video a part at a
 * time and plays it with its words, and the shell saves it where the learner chose.
 */
import { existsSync, mkdirSync, readFileSync } from 'node:fs';
import path from 'node:path';

import type { ElectronApplication, Page } from '@playwright/test';

import { expect, launchApp, repoRoot, test, waitForCore } from './support/app';
import {
  closeWhatIsSent,
  createCourse,
  expectNoAccessibilityViolations,
  openCourseTab,
  openWhatIsSent,
  saveProviderKey,
  screenshot,
} from './support/courses';
import { startFakeProvider } from './support/fake-provider';

const core = path.join(repoRoot, 'services', 'core');
const corePython =
  process.platform === 'win32'
    ? path.join(core, '.venv', 'Scripts', 'python.exe')
    : path.join(core, '.venv', 'bin', 'python');
const standIn = path.join(core, 'tests', 'support', 'fake_film_engine.py');
const VIDEO = readFileSync(path.join(core, 'tests', 'support', 'film.mp4'));

/** A recognisable fake key. It only ever reaches the fake provider. */
const KEY = 'sk-e2e-not-a-real-key-Fm3kQ8zR2vY6';
const NVIDIA_KEY = 'nvapi-e2e-not-a-real-key-Fm8wQ2kR5tZ1';
const NVIDIA = 'NVIDIA NIM (custom endpoint 127.0.0.1)';
const COURSE = 'Area and volume';
/** The chapter the stand-in provider writes, which runs clean. */
const CHAPTER = readFileSync(
  path.join(repoRoot, 'fixtures', 'model-answers', 'film-chapter.py'),
  'utf8',
);

const now = (page: Page) => page.getByRole('navigation').getByRole('group', { name: 'Now' });

async function addConcept(page: Page, name: string, objective: string): Promise<void> {
  await page.getByRole('button', { name: 'Add a concept' }).click();
  const dialog = page.getByRole('dialog', { name: 'Add a concept' });
  await dialog.getByLabel('Name').fill(name);
  await dialog.getByRole('textbox', { name: 'Objective 1' }).fill(objective);
  await dialog.getByRole('button', { name: 'Add concept' }).click();
  await expect(page.getByRole('region', { name })).toBeVisible();
}

/** Make the native save dialog answer with this path, and keep what it was asked. */
async function chooseInSaveDialog(app: ElectronApplication, filePath: string): Promise<void> {
  await app.evaluate(({ dialog }, chosen) => {
    dialog.showSaveDialog = (...asked: unknown[]) => {
      (globalThis as Record<string, unknown>).adleSaveAsked = asked.at(-1);
      return Promise.resolve({ canceled: false, filePath: chosen });
    };
  }, filePath);
}

test.describe('a film of the whole course', () => {
  test('is made chapter by chapter, stopped and continued, watched with its words, and saved', async ({
    profileDir,
  }) => {
    test.setTimeout(180_000);
    const provider = await startFakeProvider();
    const adle = await launchApp(profileDir, {
      onboarded: true,
      env: {
        ADLE_PROVIDER_BASE_URL: provider.baseUrl,
        ADLE_FILM_PYTHON: corePython,
        ADLE_FILM_ENGINE: standIn,
      },
    });
    const { app, page } = adle;
    try {
      await waitForCore(page);
      await page.getByRole('button', { name: 'Settings' }).click();
      await saveProviderKey(page, /Custom endpoint/, KEY);
      await page.getByRole('button', { name: 'Library', exact: true }).click();
      await createCourse(page, COURSE, { topic: 'Measuring shapes.' });

      // ---- A course with nothing in it has no film to make, and says why ----
      await openCourseTab(page, 'Film');
      await expect(page.getByText('Add concepts to the course first')).toBeVisible();
      await expect(page.getByRole('button', { name: 'Make the film' })).toHaveCount(0);

      await openCourseTab(page, 'Curriculum');
      await addConcept(page, 'Area', 'Find the area of a rectangle by counting squares.');
      await addConcept(page, 'Volume', 'Find the volume of a box by counting cubes.');

      // ---- What it would be, and what it sends, before anything is sent ----
      await openCourseTab(page, 'Film');
      await expect(page.getByRole('heading', { name: 'A film of the whole course' })).toBeVisible();
      await expect(
        page.getByText(/2 chapters\. Making it takes at least \d+ minutes/),
      ).toBeVisible();
      await expect(page.getByText(/its words show as it plays/)).toBeVisible();
      const note = await openWhatIsSent(page);
      await expect(note).toContainText(
        'Sends each concept’s title, summary and objectives, and passages of your materials ' +
          'about it to Custom endpoint (127.0.0.1)',
      );
      await expect(note).toContainText('At most 8 requests');
      await closeWhatIsSent(page);
      expect(provider.requests).toHaveLength(0);

      // ---- Made in the background: the rail says so, and it can be stopped ----
      provider.hold('film');
      await page.getByRole('button', { name: 'Make the film' }).click();
      await expect(page.getByRole('heading', { name: 'Making the film' })).toBeVisible();
      await expect(now(page).getByRole('button', { name: 'Making a film' })).toBeVisible();
      const chapters = page.getByRole('list', { name: 'Chapters' });
      const [first, second] = [0, 1].map((index) => chapters.getByRole('listitem').nth(index));
      await expect(first!).toContainText('1. Area');
      // What it is doing, on its own line (ADR-076); the bar says how many are written.
      await expect(first!).toContainText('Writing');
      await expect(second!).toContainText('2. Volume');
      await expect(second!).toContainText('Waiting');
      await expect(page.getByText('Writing chapters: 0 of 2 done')).toBeVisible();
      await expect
        .poll(() => provider.requests.filter((each) => each.kind === 'film').length)
        .toBe(1);
      const asked = provider.requests.find((each) => each.kind === 'film')!;
      expect(asked.prompt).toContain('Write chapter 1 of 2');
      expect(asked.prompt).toContain('Find the area of a rectangle by counting squares.');
      await expectNoAccessibilityViolations(page);
      await screenshot(page, 'film-making');

      await page.getByRole('button', { name: 'Stop', exact: true }).click();
      await expect(page.getByRole('heading', { name: 'The film isn’t finished' })).toBeVisible();
      await expect(page.getByText('Stopped. What was made is kept')).toBeVisible();
      await expect(now(page).getByRole('button', { name: 'Making a film' })).toHaveCount(0);

      // ---- Continued, and ready: said by the operating system too, if Adle is behind ----
      provider.release();
      await adle.setFocused(false);
      await page.getByRole('button', { name: 'Continue', exact: true }).click();
      const marks = page.getByRole('navigation', { name: 'Chapters of the film' });
      await expect(marks).toBeVisible({ timeout: 60_000 });
      await expect(page.getByRole('heading', { name: COURSE, level: 2 })).toBeVisible();
      await expect(marks.getByRole('button', { name: /^Introduction 0:00$/ })).toBeVisible();
      await expect(marks.getByRole('button', { name: /^1\. Area \d+:\d\d$/ })).toBeVisible();
      await expect(marks.getByRole('button', { name: /^2\. Volume \d+:\d\d$/ })).toBeVisible();
      await expect(page.getByText(/2 chapters · No voice/)).toBeVisible();
      await expect(page.getByText(/It has no voice/)).toBeVisible();
      await expect
        .poll(async () => ((await adle.notices()) ?? []).map((notice) => notice.title))
        .toContain('Your film is ready');
      await adle.setFocused(true);
      // The chapter being written when the film was stopped was asked for again, whole:
      // nothing of it had been kept. The other was asked for once.
      expect(provider.requests.filter((each) => each.kind === 'film')).toHaveLength(3);

      // ---- The video came, part by part, and plays with its words ----
      const video = page.getByLabel(`Film: ${COURSE}`);
      await expect
        .poll(() => video.evaluate((element: HTMLVideoElement) => element.readyState))
        .toBeGreaterThanOrEqual(1);
      const played = await video.evaluate((element: HTMLVideoElement) => ({
        duration: element.duration,
        source: element.currentSrc.split(':')[0],
        tracks: element.textTracks.length,
      }));
      expect(played.duration).toBeGreaterThan(1);
      expect(played.source).toBe('blob');
      expect(played.tracks).toBe(1);
      await expect
        .poll(() =>
          video.evaluate((element: HTMLVideoElement) => {
            const track = element.textTracks[0];
            if (track) track.mode = 'hidden';
            return track?.cues?.[0] ? (track.cues[0] as VTTCue).text : null;
          }),
        )
        .toBe(`This film goes through ${COURSE}, in 2 chapters.`);
      await expectNoAccessibilityViolations(page);
      await screenshot(page, 'film-ready');

      // ---- Saved where the learner chose, its words beside it ----
      const target = test.info().outputPath('saved', `${COURSE}.mp4`);
      // A folder the learner can choose is one that is there.
      mkdirSync(path.dirname(target), { recursive: true });
      await chooseInSaveDialog(app, target);
      await page.getByRole('button', { name: 'Save the film' }).click();
      await expect(page.getByRole('status').filter({ hasText: 'Film saved' })).toContainText(
        `${COURSE}.mp4, with its subtitles beside it.`,
      );
      const question = await app.evaluate(
        () => (globalThis as Record<string, unknown>).adleSaveAsked as { defaultPath: string },
      );
      expect(question.defaultPath).toBe(`${COURSE}.mp4`);
      expect(readFileSync(target).equals(VIDEO)).toBe(true);
      const words = readFileSync(target.replace(/\.mp4$/, '.srt'), 'utf8');
      expect(words).toContain('How much floor does a rug cover? Let us count it.');

      // ---- Removed: its files go, and a new one can be made ----
      await page.getByRole('button', { name: 'Remove the film' }).click();
      const removing = page.getByRole('dialog', { name: 'Remove the film?' });
      await removing.getByRole('button', { name: 'Remove' }).click();
      await expect(page.getByRole('button', { name: 'Make the film' })).toBeVisible();
      expect(existsSync(target)).toBe(true);
    } finally {
      await adle.close();
      await provider.close();
    }
  });

  test('has each chapter’s pictures checked by a model that sees them, where one has a key', async ({
    profileDir,
  }) => {
    test.setTimeout(150_000);
    const aihubmix = await startFakeProvider();
    const nvidia = await startFakeProvider();
    const adle = await launchApp(profileDir, {
      onboarded: true,
      env: {
        ADLE_PROVIDER_ENDPOINTS: JSON.stringify({
          aihubmix: aihubmix.baseUrl,
          nvidia: nvidia.baseUrl,
        }),
        ADLE_FILM_PYTHON: corePython,
        ADLE_FILM_ENGINE: standIn,
      },
    });
    const { page } = adle;
    try {
      await waitForCore(page);
      await page.getByRole('button', { name: 'Settings' }).click();
      await saveProviderKey(page, NVIDIA, NVIDIA_KEY);
      await page.getByRole('button', { name: 'Library', exact: true }).click();
      await createCourse(page, COURSE, { topic: 'Measuring shapes.' });
      await openCourseTab(page, 'Curriculum');
      await addConcept(page, 'Area', 'Find the area of a rectangle by counting squares.');

      // ---- Said before anything is sent: the pictures, where they go, and the bound ----
      await openCourseTab(page, 'Film');
      const note = await openWhatIsSent(page);
      await expect(note).toContainText(
        `Sends pictures of each chapter to ${NVIDIA} to be checked.`,
      );
      await expect(note).toContainText(
        'At most 5 requests: one for each chapter, up to three more for each to fix it, and ' +
          'one for each to check its pictures.',
      );
      await closeWhatIsSent(page);
      expect(nvidia.requests).toHaveLength(0);

      // ---- Looked over once it ran clean, and mended for what was seen (ADR-066) ----
      nvidia.queue(
        CHAPTER,
        '#1: The label "2 tall" sits far from the grid; put it beside the grid.',
        CHAPTER,
      );
      await page.getByRole('button', { name: 'Make the film' }).click();
      const marks = page.getByRole('navigation', { name: 'Chapters of the film' });
      await expect(marks).toBeVisible({ timeout: 90_000 });
      await expect(marks.getByRole('button', { name: /^1\. Area \d+:\d\d$/ })).toBeVisible();
      expect(nvidia.requests.map((each) => each.kind)).toEqual(['film', 'storyboard', 'film']);
      expect(aihubmix.requests).toHaveLength(0);
      const look = nvidia.requests[1]!;
      expect(look.body.model).toBe('nvidia/nemotron-3.5-super-vl-120b-a12b');
      // The storyboard the film maker drew of the chapter: a sheet for every six animations.
      expect(look.pictures).toHaveLength(3);
      for (const sheet of look.pictures) expect(sheet).toMatch(/^data:image\/png;base64,/);
      expect(look.prompt).toContain('#0: "How much floor does a rug cover? Let us count it."');
      const mend = nvidia.requests[2]!.prompt;
      expect(mend).toContain('looked at a picture of the screen at the end of each animation');
      expect(mend).toContain('The label "2 tall" sits far from the grid; put it beside the grid.');
    } finally {
      await adle.close();
      await aihubmix.close();
      await nvidia.close();
    }
  });

  test('says what each chapter made at the same time is doing, on its own line', async ({
    profileDir,
  }) => {
    test.setTimeout(120_000);
    const aihubmix = await startFakeProvider();
    const nvidia = await startFakeProvider();
    const adle = await launchApp(profileDir, {
      onboarded: true,
      env: {
        ADLE_PROVIDER_ENDPOINTS: JSON.stringify({
          aihubmix: aihubmix.baseUrl,
          nvidia: nvidia.baseUrl,
        }),
        ADLE_FILM_PYTHON: corePython,
        ADLE_FILM_ENGINE: standIn,
      },
    });
    const { page } = adle;
    try {
      await waitForCore(page);
      await page.getByRole('button', { name: 'Settings' }).click();
      await saveProviderKey(page, NVIDIA, NVIDIA_KEY);
      await page.getByRole('button', { name: 'Library', exact: true }).click();
      await createCourse(page, COURSE, { topic: 'Measuring shapes.' });
      await openCourseTab(page, 'Curriculum');
      await addConcept(page, 'Area', 'Find the area of a rectangle by counting squares.');
      await addConcept(page, 'Volume', 'Find the volume of a box by counting cubes.');

      // NVIDIA takes several requests at once (ADR-068): both chapters are written together,
      // and each says what it is doing on its own line (ADR-076).
      nvidia.hold('film');
      await openCourseTab(page, 'Film');
      await page.getByRole('button', { name: 'Make the film' }).click();
      await expect(page.getByRole('heading', { name: 'Making the film' })).toBeVisible();
      await expect
        .poll(() => nvidia.requests.filter((each) => each.kind === 'film').length)
        .toBe(2);
      const chapters = page.getByRole('list', { name: 'Chapters' });
      for (const [index, title] of ['1. Area', '2. Volume'].entries()) {
        const row = chapters.getByRole('listitem').nth(index);
        await expect(row).toContainText(title);
        await expect(row).toContainText('Writing');
      }
      await expect(page.getByText('Writing chapters: 0 of 2 done')).toBeVisible();
      await expectNoAccessibilityViolations(page);
      await screenshot(page, 'film-making-side-by-side');

      await page.getByRole('button', { name: 'Stop', exact: true }).click();
      await expect(page.getByRole('heading', { name: 'The film isn’t finished' })).toBeVisible();
    } finally {
      await adle.close();
      await aihubmix.close();
      await nvidia.close();
    }
  });

  test('needs the film maker, set up only at the learner’s word, and says what it downloads', async ({
    adle,
  }) => {
    const { page } = adle;
    await waitForCore(page);
    await createCourse(page, COURSE, { topic: 'Measuring shapes.' });
    await openCourseTab(page, 'Film');
    await expect(page.getByRole('heading', { name: 'A film of the whole course' })).toBeVisible();
    await expect(
      page.getByText(
        /needs the film maker on this computer: about \d+ MB from GitHub and the Python Package Index, and about \d+ MB once it is set up/,
      ),
    ).toBeVisible();
    await expect(page.getByRole('button', { name: 'Set up the film maker' })).toBeVisible();
    // Nothing is downloaded, or even asked for, until the learner presses it.
    const maker = await page.evaluate(() => window.adle!.core.invoke('films.maker_status', {}));
    expect(maker).toMatchObject({ ok: true, data: { ready: false, setting_up: null } });
    await expectNoAccessibilityViolations(page);
  });
});
