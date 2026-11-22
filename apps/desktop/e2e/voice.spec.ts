/**
 * A lesson read in a natural voice recorded on this computer (ADR-042).
 *
 * The voice here is a stand-in for the engine (services/core/tests/support/
 * fake_voice_engine.py): the same protocol, silence for sound, a third of a second a word.
 * Everything else is the real path: the core records the lesson's lines in the background,
 * the lesson fetches each clip, plays it, and marks each word at the time it was recorded.
 */
import { mkdirSync, writeFileSync } from 'node:fs';
import path from 'node:path';

import type { Page } from '@playwright/test';

import { expect, launchApp, repoRoot, test, waitForCore } from './support/app';
import {
  courseCard,
  expectNoAccessibilityViolations,
  openCourseTab,
  screenshot,
} from './support/courses';

const core = path.join(repoRoot, 'services', 'core');
const corePython =
  process.platform === 'win32'
    ? path.join(core, '.venv', 'Scripts', 'python.exe')
    : path.join(core, '.venv', 'bin', 'python');
const standIn = path.join(core, 'tests', 'support', 'fake_voice_engine.py');

/** The files of the lightest natural voice, where an installation leaves them: empty here. */
const KOKORO_FILES = [
  'config.json',
  'kokoro-v1_0.pth',
  'voices/af_heart.pt',
  'voices/af_bella.pt',
  'voices/bf_emma.pt',
  'voices/am_michael.pt',
  'voices/am_fenrir.pt',
];

function aVoice(folder: string): string {
  const models = path.join(folder, 'models');
  for (const file of KOKORO_FILES) {
    const at = path.join(models, 'Kokoro-82M', file);
    mkdirSync(path.dirname(at), { recursive: true });
    writeFileSync(at, '');
  }
  return models;
}

async function invoke<T>(page: Page, operation: string, request?: unknown): Promise<T> {
  const answer = await page.evaluate(
    ([name, body]) => window.adle!.core.invoke(name as never, body as never),
    [operation, request] as const,
  );
  expect(answer.ok, JSON.stringify(answer)).toBe(true);
  return (answer as { data: T }).data;
}

test.describe('the natural voice', () => {
  test('a lesson is recorded in the natural voice, then played with each word marked as it is said', async ({
    profileDir,
  }) => {
    test.setTimeout(120_000);
    const models = aVoice(test.info().outputPath('voice'));
    const adle = await launchApp(profileDir, {
      onboarded: true,
      env: {
        ADLE_VOICE_KOKORO_PYTHON: corePython,
        ADLE_VOICE_ENGINE: standIn,
        ADLE_VOICE_MODELS: models,
      },
    });
    const { page } = adle;
    await waitForCore(page);

    const voice = await invoke<{ tier: string; enabled: boolean; borrowed: boolean }>(
      page,
      'voice.status',
    );
    expect(voice).toMatchObject({ tier: 'kokoro', enabled: true, borrowed: true });

    // ---- The sample lesson, opened: its lines are recorded in the background ----
    await page.getByRole('button', { name: 'Library', exact: true }).click();
    const sample = courseCard(page, /Introduction to neural networks/);
    if (await sample.isVisible()) await sample.click();
    else await page.getByRole('button', { name: 'Try the sample course' }).click();
    await openCourseTab(page, 'Curriculum');
    await page
      .getByRole('region', { name: 'Weights and bias' })
      .getByRole('list', { name: 'Lessons for this concept' })
      .getByRole('button', { name: /^(Start lesson|Continue|Replay lesson):/ })
      .click();
    await expect(page.getByRole('button', { name: 'Start', exact: true })).toBeVisible();

    const courses = await invoke<{ courses: { id: string; title: string }[] }>(
      page,
      'courses.list',
    );
    const course = courses.courses.find((item) =>
      item.title.includes('Introduction to neural networks'),
    )!;
    const lessons = await invoke<{ lessons: { id: string }[] }>(page, 'lessons.list', {
      path: { course_id: course.id },
    });
    const lessonId = lessons.lessons[0]!.id;
    const view = await invoke<{ lesson: { segments: { narration?: { text: string }[] }[] } }>(
      page,
      'lessons.get',
      { path: { lesson_id: lessonId } },
    );
    const lines = new Set<string>();
    for (const segment of view.lesson.segments) {
      for (const beat of segment.narration ?? []) lines.add(beat.text);
    }
    await expect
      .poll(
        async () =>
          (
            await invoke<{ lines: unknown[] }>(page, 'narration.get', {
              path: { lesson_id: lessonId },
            })
          ).lines.length,
        { timeout: 60_000 },
      )
      .toBe(lines.size);

    // ---- Played: the words are marked at the times they were recorded, one after another ----
    // Long enough for the lesson to have handed the clips to its narrator.
    await page.waitForTimeout(3_000);
    const transcript = page.getByRole('complementary', { name: 'Transcript' });
    const current = transcript.locator('li[aria-current="true"]');
    const first = [...lines][0]!;
    const words = first.match(/[A-Za-z]+(?:['’][A-Za-z]+)*|\d+(?:\.\d+)?/g) ?? [];
    // Each word marked in turn, looked at on every frame of the page: a word of the stand-in
    // lasts a third of a second, which a test that asks now and then can step over.
    const marked = transcript.evaluate(async (element) => {
      const seen: string[] = [];
      const until = performance.now() + 15_000;
      while (performance.now() < until && seen.length < 3) {
        const word = element.querySelector('li[aria-current="true"] mark')?.textContent ?? '';
        if (word && seen.at(-1) !== word) seen.push(word);
        await new Promise((resolve) => requestAnimationFrame(resolve));
      }
      return seen;
    });
    await page.getByRole('button', { name: 'Start', exact: true }).click();
    expect(await marked).toEqual(words.slice(0, 3));
    // It is the recording that speaks, never the computer's own voice.
    expect(await page.evaluate(() => speechSynthesis.speaking)).toBe(false);
    await expectNoAccessibilityViolations(page);

    // Paused, the marked word stays where it is.
    await page.getByRole('button', { name: 'Pause' }).click();
    const held = await current.locator('mark').textContent();
    await page.waitForTimeout(1_200);
    await expect(current.locator('mark')).toHaveText(held ?? '');
    await page.getByRole('button', { name: 'Resume' }).click();
    await expect(current.locator('mark')).not.toHaveText(held ?? '', { timeout: 10_000 });

    expect(adle.problems).toEqual([]);
    await adle.close();
  });

  test('Settings offers the voices from the lightest to the richest, and the one chosen reads the lessons', async ({
    profileDir,
  }) => {
    const models = aVoice(test.info().outputPath('voice'));
    const adle = await launchApp(profileDir, {
      onboarded: true,
      env: {
        ADLE_VOICE_KOKORO_PYTHON: corePython,
        ADLE_VOICE_ENGINE: standIn,
        ADLE_VOICE_MODELS: models,
      },
    });
    const { page } = adle;
    await waitForCore(page);
    await page.getByRole('button', { name: 'Settings' }).click();
    await page.getByRole('tab', { name: 'Learning' }).click();

    const voices = page.getByRole('list', { name: 'Voices' });
    await expect(voices.getByRole('heading')).toHaveText([
      'Computer’s voice',
      'Natural',
      'Rich',
      'Expressive',
    ]);
    const natural = voices.getByRole('listitem', { name: 'Natural' });
    await expect(natural.getByText('In use')).toBeVisible();
    // Set up by hand, as here: nothing is offered to set it up or take it away.
    await expect(voices.getByRole('button', { name: /^(Set up|Remove)/ })).toHaveCount(0);

    // A speaker of the voice in use.
    await natural.getByRole('combobox', { name: 'Speaker' }).selectOption('bf_emma');
    await expect
      .poll(
        async () =>
          (await invoke<{ speakers: Record<string, string> }>(page, 'voice.status')).speakers
            .kokoro,
      )
      .toBe('bf_emma');
    await expectNoAccessibilityViolations(page);
    await voices.scrollIntoViewIfNeeded();
    await screenshot(page, 'settings-voices');

    // Back to the computer's own voice: no natural voice reads the lessons.
    await page.getByRole('button', { name: 'Use the computer’s voice' }).click();
    await expect(
      voices.getByRole('listitem', { name: 'Computer’s voice' }).getByText('In use'),
    ).toBeVisible();
    expect((await invoke<{ enabled: boolean }>(page, 'voice.status')).enabled).toBe(false);
    await expect(page.getByRole('button', { name: 'Use the Natural voice' })).toBeVisible();

    expect(adle.problems).toEqual([]);
    await adle.close();
  });
});
