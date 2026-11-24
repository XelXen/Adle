/**
 * A lesson read in a natural voice recorded on this computer (ADR-042), and made with it
 * (ADR-051): ready once its first part can be heard, and a line still being recorded is
 * waited for rather than read in another voice.
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
  createCourse,
  expectNoAccessibilityViolations,
  openCourseTab,
  saveProviderKey,
  screenshot,
} from './support/courses';
import { cannedAnswer, startFakeProvider } from './support/fake-provider';

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

/** What each of the Expressive voice's two models is made of. */
const QWEN_FILES = [
  'config.json',
  'model.safetensors',
  'generation_config.json',
  'merges.txt',
  'preprocessor_config.json',
  'speech_tokenizer/config.json',
  'speech_tokenizer/configuration.json',
  'speech_tokenizer/model.safetensors',
  'speech_tokenizer/preprocessor_config.json',
  'tokenizer_config.json',
  'vocab.json',
];

/** The Expressive voice where an installation leaves it, its aligner too: every file empty. */
function anExpressiveVoice(folder: string): string {
  const models = path.join(folder, 'models');
  const files = [
    ...['Qwen3-TTS-12Hz-1.7B-VoiceDesign', 'Qwen3-TTS-12Hz-1.7B-Base'].flatMap((repo) =>
      QWEN_FILES.map((file) => path.join(models, repo, file)),
    ),
    path.join(folder, 'aligner', 'hub', 'checkpoints', 'wav2vec2_fairseq_base_ls960_asr_ls960.pth'),
  ];
  for (const at of files) {
    mkdirSync(path.dirname(at), { recursive: true });
    writeFileSync(at, '');
  }
  return models;
}

/** A recognisable fake key. It only ever reaches the fake provider. */
const KEY = 'sk-e2e-not-a-real-key-7Hq2mZx94Wd1';

/**
 * The app with a stand-in voice that takes `delay` seconds over each line, as a voice
 * slower than the lesson's words, and a provider on this computer; a course with a concept,
 * and the provider's key. Narration is read aloud, as the learner left it.
 */
async function aLessonToMake(profileDir: string, delay: number) {
  const provider = await startFakeProvider();
  const models = aVoice(test.info().outputPath('voice'));
  const adle = await launchApp(profileDir, {
    onboarded: true,
    env: {
      ADLE_PROVIDER_BASE_URL: provider.baseUrl,
      ADLE_VOICE_KOKORO_PYTHON: corePython,
      ADLE_VOICE_ENGINE: standIn,
      ADLE_VOICE_MODELS: models,
      ADLE_FAKE_VOICE_DELAY: String(delay),
    },
  });
  const { page } = adle;
  await waitForCore(page);
  await page.getByRole('button', { name: 'Settings' }).click();
  await saveProviderKey(page, /Custom endpoint/, KEY);
  await page.getByRole('button', { name: 'Library', exact: true }).click();
  await createCourse(page, 'Calculus refresher', { topic: 'Limits.' });
  await page.getByRole('button', { name: 'Add a concept' }).click();
  const dialog = page.getByRole('dialog', { name: 'Add a concept' });
  await dialog.getByLabel('Name').fill('Limits');
  await dialog.getByRole('textbox', { name: 'Objective 1' }).fill('Estimate a limit from a table.');
  await dialog.getByRole('button', { name: 'Add concept' }).click();
  const concept = page.getByRole('region', { name: 'Limits' });
  await expect(concept).toBeVisible();
  provider.queue(cannedAnswer('lesson'));
  return { adle, page, provider, concept };
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

  test('a lesson in the natural voice is ready once its first part can be heard', async ({
    profileDir,
  }) => {
    test.setTimeout(180_000);
    const { adle, page, provider, concept } = await aLessonToMake(profileDir, 4);
    await concept.getByRole('button', { name: 'Create a lesson with AI' }).click();
    const lessons = concept.getByRole('list', { name: 'Lessons for this concept' });
    // Its first part is written, and listed, before it can be heard: not ready yet.
    await expect(lessons.getByRole('button', { name: /^Start lesson/ })).toBeVisible({
      timeout: 60_000,
    });
    const ready = page.getByRole('status').filter({ hasText: 'Lesson ready' });
    await expect(ready).toHaveCount(0);
    await expect(ready).toBeVisible({ timeout: 90_000 });
    // Ready means heard: every line of its first part is recorded by then.
    const courses = await invoke<{ courses: { id: string; title: string }[] }>(
      page,
      'courses.list',
    );
    const course = courses.courses.find((item) => item.title === 'Calculus refresher')!;
    const listed = await invoke<{ lessons: { id: string }[] }>(page, 'lessons.list', {
      path: { course_id: course.id },
    });
    const lessonId = listed.lessons[0]!.id;
    const view = await invoke<{ lesson: { segments: { narration?: { text: string }[] }[] } }>(
      page,
      'lessons.get',
      { path: { lesson_id: lessonId } },
    );
    const first = view.lesson.segments.find((segment) => (segment.narration ?? []).length > 0)!;
    const recorded = await invoke<{ lines: { text: string }[] }>(page, 'narration.get', {
      path: { lesson_id: lessonId },
    });
    const heard = new Set(recorded.lines.map((line) => line.text));
    for (const beat of first.narration ?? []) expect(heard.has(beat.text)).toBe(true);

    // Started, it is played from its recording at once: nothing is waited for.
    await lessons.getByRole('button', { name: /^Start lesson/ }).click();
    const transcript = page.getByRole('complementary', { name: 'Transcript' });
    await expect(transcript).toBeVisible();
    const said = transcript.evaluate(async (element) => {
      const until = performance.now() + 20_000;
      while (performance.now() < until) {
        if (element.querySelector('li[aria-current="true"] mark')) return true;
        await new Promise((resolve) => requestAnimationFrame(resolve));
      }
      return false;
    });
    await page.getByRole('button', { name: 'Start', exact: true }).click();
    expect(await said).toBe(true);
    await expect(page.getByText('Recording the voice for this part.')).toHaveCount(0);
    expect(adle.problems).toEqual([]);
    await adle.close();
    await provider.close();
  });

  test('a line still being recorded is waited for, and the other voice can be chosen instead', async ({
    profileDir,
  }) => {
    test.setTimeout(180_000);
    // Far slower than anyone would wait.
    const { adle, page, provider, concept } = await aLessonToMake(profileDir, 45);
    await concept.getByRole('button', { name: 'Create a lesson with AI' }).click();
    // Its words are all written, its pictures drawn: what it waits for is its voice.
    await expect(concept.getByRole('progressbar', { name: 'Recording the voice' })).toBeVisible({
      timeout: 90_000,
    });
    await expect(page.getByRole('status').filter({ hasText: 'Lesson ready' })).toHaveCount(0);
    // The lesson is there before its voice is: opened, it waits at its first line.
    const lessons = concept.getByRole('list', { name: 'Lessons for this concept' });
    await lessons.getByRole('button', { name: /^Start lesson/ }).click();
    await page.getByRole('button', { name: 'Start', exact: true }).click();
    const waiting = page.getByText('Recording the voice for this part.');
    await expect(waiting).toBeVisible();
    await expect(page.getByRole('button', { name: 'Pause' })).toBeVisible();
    await expectNoAccessibilityViolations(page);
    await screenshot(page, 'lesson-waiting-for-its-voice');
    // Nothing is said meanwhile, in any voice.
    expect(await page.evaluate(() => speechSynthesis.speaking)).toBe(false);
    await page
      .getByRole('button', { name: /^(Use the computer’s voice|Read the words instead)$/ })
      .click();
    await expect(waiting).toHaveCount(0);
    // Read on in the other voice: the lesson goes on.
    const transcript = page.getByRole('complementary', { name: 'Transcript' });
    await expect(transcript.locator('li[aria-current="true"]')).toBeVisible();
    expect(adle.problems).toEqual([]);
    await adle.close();
    await provider.close();
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
    // Rich is no longer offered (ADR-057).
    await expect(voices.getByRole('heading')).toHaveText([
      'Computer’s voice',
      'Natural',
      'Expressive',
    ]);
    const natural = voices.getByRole('listitem', { name: 'Natural' });
    await expect(natural.getByText('In use').first()).toBeVisible();
    // Set up by hand, as here: nothing is offered to set it up or take it away.
    await expect(voices.getByRole('button', { name: /^(Set up|Remove)/ })).toHaveCount(0);

    // A speaker heard before it is chosen: a sample, made by the voice and played here.
    await natural.getByRole('button', { name: 'Listen to Emma' }).click();
    await expect(natural.getByRole('button', { name: 'Listen to Emma' })).toBeEnabled({
      timeout: 30_000,
    });
    await expect(page.getByRole('alert')).toHaveCount(0);
    expect(
      (await invoke<{ speakers: Record<string, string> }>(page, 'voice.status')).speakers.kokoro,
    ).toBe('af_heart');
    // Then chosen.
    await natural.getByRole('button', { name: 'Use Emma' }).click();
    await expect(natural.getByRole('button', { name: 'Use Emma' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
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

  test('the Expressive voice is put together from parts, heard, and saved; or written in the learner’s own words', async ({
    profileDir,
  }) => {
    const folder = test.info().outputPath('voice');
    const models = anExpressiveVoice(folder);
    const adle = await launchApp(profileDir, {
      onboarded: true,
      env: {
        ADLE_VOICE_QWEN_PYTHON: corePython,
        ADLE_VOICE_ENGINE: standIn,
        ADLE_VOICE_MODELS: models,
        ADLE_VOICE_ALIGNER: path.join(folder, 'aligner'),
      },
    });
    const { page } = adle;
    await waitForCore(page);
    await page.getByRole('button', { name: 'Settings' }).click();
    await page.getByRole('tab', { name: 'Learning' }).click();

    interface Voice {
      design: string;
      design_parts: Record<string, string>;
    }
    const own = (await invoke<Voice>(page, 'voice.status')).design;
    const expressive = page
      .getByRole('list', { name: 'Voices' })
      .getByRole('listitem', { name: 'Expressive' });
    await expect(expressive.getByText('In use').first()).toBeVisible();
    const from = expressive.getByRole('combobox', { name: 'Start from' });
    const parts = expressive.getByRole('group', { name: 'What the voice is made of' });
    const words = expressive.getByRole('textbox', { name: 'In your own words' });
    // Nothing chosen yet: Adle's own voice, every part of it left to the voice.
    await expect(from).toHaveValue('Adle’s own');
    await expect(words).toHaveValue(own);
    await expect(parts.getByRole('combobox')).toHaveText([
      /^Any/,
      /^Any/,
      /^Any/,
      /^Any/,
      /^Any/,
      /^Any/,
      /^Any/,
      /^Any/,
      /^Any/,
    ]);
    await expect(expressive.getByRole('button', { name: 'Save' })).toBeDisabled();

    // Part by part: the description is written for the learner as they choose.
    await parts.getByRole('combobox', { name: 'Speaker' }).selectOption({ label: 'Man' });
    await expect(words).toHaveValue(
      'A man with a clear voice, speaking natural English at an easy pace.',
    );
    await parts.getByRole('combobox', { name: 'Pace' }).selectOption({ label: 'Slow' });
    await parts.getByRole('combobox', { name: 'Tone' }).selectOption({ label: 'Deep' });
    await parts.getByRole('combobox', { name: 'Style' }).selectOption({
      label: 'Documentary narrator',
    });
    const described =
      'A man with a deep voice, speaking natural English at a slow pace, like a documentary narrator.';
    await expect(words).toHaveValue(described);
    await expect(from).toHaveValue('');

    // Heard before it is kept: a sample, and nothing chosen by it.
    await expressive.getByRole('button', { name: 'Listen to this voice' }).click();
    await expect(expressive.getByRole('button', { name: 'Listen to this voice' })).toBeEnabled({
      timeout: 30_000,
    });
    await expect(page.getByRole('alert')).toHaveCount(0);
    expect((await invoke<Voice>(page, 'voice.status')).design).toBe(own);

    await expressive.getByRole('button', { name: 'Save' }).click();
    await expect(page.getByText('Voice saved')).toBeVisible();
    const saved = await invoke<Voice>(page, 'voice.status');
    expect(saved.design).toBe(described);
    expect(saved.design_parts).toEqual({
      speaker: 'man',
      pace: 'slow',
      tone: 'deep',
      style: 'documentary',
    });
    await expect(expressive.getByRole('button', { name: 'Save' })).toBeDisabled();
    await expectNoAccessibilityViolations(page);
    await expressive.scrollIntoViewIfNeeded();
    await screenshot(page, 'settings-voice-parts');

    // A voice to start from sets every part at once, and the learner can go on from it.
    await from.selectOption({ label: 'Bright and lively' });
    await expect(parts.getByRole('combobox', { name: 'Speaker' })).toHaveValue('woman');
    await expect(parts.getByRole('combobox', { name: 'Feeling' })).toHaveValue('lively');
    await expect(words).toHaveValue(/^A lively young woman with a crisp, clear voice/);

    // In the learner's own words, the most exact way: the parts are let go.
    await words.fill('A soft, low voice with a smile in it.');
    await expect(parts.getByRole('combobox', { name: 'Speaker' })).toHaveValue('');
    await expect(from).toHaveValue('');
    await expressive.getByRole('button', { name: 'Save' }).click();
    await expect
      .poll(async () => (await invoke<Voice>(page, 'voice.status')).design)
      .toBe('A soft, low voice with a smile in it.');
    expect((await invoke<Voice>(page, 'voice.status')).design_parts).toEqual({});

    // And back to Adle's own.
    await from.selectOption({ label: 'Adle’s own' });
    await expressive.getByRole('button', { name: 'Save' }).click();
    await expect.poll(async () => (await invoke<Voice>(page, 'voice.status')).design).toBe(own);

    expect(adle.problems).toEqual([]);
    await adle.close();
  });
});
