/**
 * Narration read aloud by a voice installed on the computer.
 *
 * What a machine can say depends on the machine, so these journeys first ask
 * the app's own window which voices it has. With a voice, narration is spoken
 * (at zero volume here, so the suite stays quiet) and the voice keeps the
 * lesson's time. Without one, the lesson says so and shows the words instead.
 * Both are real paths a learner can be on.
 *
 * There is a third: a machine that lists voices and cannot keep one speaking. A
 * build machine with nowhere to play sound is one (GitHub's Windows machine, first
 * seen 2026-11-21). The app then stands in for the voice line by line, with the
 * words at reading pace, and the journey follows it down that path.
 */
import type { Page } from '@playwright/test';

import { expect, test, waitForCore } from './support/app';
import {
  courseCard,
  expectNoAccessibilityViolations,
  openCourseTab,
  screenshot,
} from './support/courses';

/** The voices that speak on this computer, as the app would list them. */
async function localVoices(page: Page): Promise<string[]> {
  return page.evaluate(
    () =>
      new Promise<string[]>((resolve) => {
        const read = (): string[] =>
          speechSynthesis
            .getVoices()
            .filter((voice) => voice.localService)
            .map((voice) => voice.name);
        const now = read();
        if (now.length > 0) {
          resolve(now);
          return;
        }
        const timer = setTimeout(() => resolve(read()), 1500);
        speechSynthesis.addEventListener(
          'voiceschanged',
          () => {
            clearTimeout(timer);
            resolve(read());
          },
          { once: true },
        );
      }),
  );
}

/**
 * Whether a voice here can be held and let go again, asked of the machine itself: a line
 * is begun, silently, and paused. A machine with nowhere to play sound may list voices,
 * begin a line, and fail it or run through it without ever holding it.
 */
async function voiceCanBeHeld(page: Page): Promise<boolean> {
  return page.evaluate(
    () =>
      new Promise<boolean>((resolve) => {
        const line = new SpeechSynthesisUtterance(
          'One, two, three, four, five, six, seven, eight, nine, ten, eleven, twelve.',
        );
        line.volume = 0;
        let answered = false;
        const answer = (held: boolean): void => {
          if (answered) return;
          answered = true;
          // Nothing of this may be left for the lesson: not a line, and not a hold.
          speechSynthesis.cancel();
          speechSynthesis.resume();
          resolve(held);
        };
        const tooLong = setTimeout(() => answer(false), 6000);
        line.onerror = () => {
          clearTimeout(tooLong);
          answer(false);
        };
        line.onstart = () => {
          speechSynthesis.pause();
          setTimeout(() => {
            clearTimeout(tooLong);
            answer(speechSynthesis.paused && speechSynthesis.speaking);
          }, 700);
        };
        speechSynthesis.speak(line);
      }),
  );
}

async function openSampleLesson(page: Page): Promise<void> {
  await page.getByRole('button', { name: 'Library', exact: true }).click();
  const sample = courseCard(page, /Introduction to neural networks/);
  if (await sample.isVisible()) await sample.click();
  else await page.getByRole('button', { name: 'Try the sample course' }).click();
  await expect(
    page.getByRole('heading', { name: 'Introduction to neural networks', level: 1 }),
  ).toBeVisible();
  await openCourseTab(page, 'Curriculum');
  // The lesson's own button, by what it does. Not "anything that says lesson": the button
  // that asks for a new one says that too.
  await page
    .getByRole('region', { name: 'Weights and bias' })
    .getByRole('list', { name: 'Lessons for this concept' })
    .getByRole('button', { name: /^(Start lesson|Continue|Replay lesson):/ })
    .first()
    .click();
  await expect(page.getByText('Part 1 of 10')).toBeVisible();
}

test.describe('narration aloud', () => {
  test('a voice on this computer reads the lesson, and can be switched off', async ({ adle }) => {
    test.setTimeout(120_000);
    const { page } = adle;
    await waitForCore(page);
    const voices = await localVoices(page);

    // ---- The voice and its volume are the learner's to choose ----
    await page.getByRole('button', { name: 'Settings' }).click();
    await page.getByRole('tab', { name: 'Learning' }).click();
    await expect(page.getByRole('switch', { name: 'Narration' })).toBeChecked();

    if (voices.length === 0) {
      // No voice here: said plainly, and lessons still work, as text.
      await expect(page.getByText('No voice found')).toBeVisible();
      await openSampleLesson(page);
      await expect(
        page.getByText('No voice is installed, so narration is shown as text.'),
      ).toBeVisible();
      await expect(page.getByRole('button', { name: 'Read aloud' })).toHaveCount(0);
      await page.getByRole('button', { name: 'Start', exact: true }).click();
      await expect(page.getByRole('button', { name: 'Pause' })).toBeVisible();
      expect(adle.problems).toEqual([]);
      return;
    }

    const voice = page.getByRole('combobox', { name: 'Voice' });
    await expect(voice).toBeVisible();
    await expect(voice.getByRole('option')).toHaveCount(voices.length + 1);
    await expect(page.getByText('Nothing is sent anywhere.')).toBeVisible();

    // Silent for the rest of this test: the voice still speaks, nothing is heard.
    const volume = page.getByRole('slider', { name: 'Volume' });
    await volume.focus();
    await page.keyboard.press('Home');
    await expect(page.getByText('Silent', { exact: true })).toBeVisible();
    await expect
      .poll(async () => {
        const saved = await page.evaluate(() =>
          window.adle!.core.invoke('learner.get_preferences'),
        );
        return saved.ok ? (saved.data as { volume: number }).volume : null;
      })
      .toBe(0);

    await page.getByRole('button', { name: 'Play a sample' }).click();
    await expect(page.getByRole('button', { name: 'Stop the sample' })).toBeVisible();
    await page.getByRole('button', { name: 'Stop the sample' }).click();
    await expect(page.getByRole('button', { name: 'Play a sample' })).toBeVisible();
    await expectNoAccessibilityViolations(page);
    await screenshot(page, 'settings-voice');

    const held = await voiceCanBeHeld(page);

    // ---- In a lesson: nothing is said until Start, then the voice keeps the time ----
    await openSampleLesson(page);
    const aloud = page.getByRole('button', { name: 'Read aloud' });
    await expect(aloud).toHaveAttribute('aria-pressed', 'true');
    expect(await page.evaluate(() => speechSynthesis.speaking)).toBe(false);

    if (!held) {
      // This machine lists voices and cannot keep one speaking. The lesson must not stall
      // on that: each line is shown for as long as it takes to read, and the lesson's own
      // controls hold it and let it go.
      test.info().annotations.push({
        type: 'voice',
        description: 'listed, but cannot be held here: the journey took the stand-in path',
      });
      await page.getByRole('button', { name: 'Start', exact: true }).click();
      const stood = page.getByRole('complementary', { name: 'Transcript' });
      await expect(stood.getByRole('listitem').first()).toHaveAttribute('aria-current', 'true');
      await page.getByRole('button', { name: 'Pause' }).click();
      await expect(page.getByRole('button', { name: 'Resume' })).toBeVisible();
      await page.getByRole('button', { name: 'Resume' }).click();
      await expect(page.getByRole('button', { name: 'Pause' })).toBeVisible();
      // Switched off, the words stay; and leaving never leaves a voice talking.
      await aloud.click();
      await expect(aloud).toHaveAttribute('aria-pressed', 'false');
      await expect(stood).toBeVisible();
      await page.getByRole('button', { name: 'Back to course' }).click();
      await expect.poll(() => page.evaluate(() => speechSynthesis.speaking)).toBe(false);
      expect(adle.problems).toEqual([]);
      return;
    }

    await page.getByRole('button', { name: 'Start', exact: true }).click();
    await expect.poll(() => page.evaluate(() => speechSynthesis.speaking)).toBe(true);
    const transcript = page.getByRole('complementary', { name: 'Transcript' });
    await expect(transcript.getByRole('listitem').first()).toHaveAttribute('aria-current', 'true');

    // Pausing the lesson pauses the voice itself.
    await page.getByRole('button', { name: 'Pause' }).click();
    await expect.poll(() => page.evaluate(() => speechSynthesis.paused)).toBe(true);
    await page.getByRole('button', { name: 'Resume' }).click();
    await expect.poll(() => page.evaluate(() => speechSynthesis.paused)).toBe(false);

    // The words can be put away while listening, and brought back.
    const words = page.getByRole('button', { name: 'Transcript' });
    await expect(words).toHaveAttribute('aria-pressed', 'true');
    await words.click();
    await expect(transcript).toHaveCount(0);
    await words.click();
    await expect(transcript).toBeVisible();
    await screenshot(page, 'lesson-read-aloud');

    // ---- Switched off: the voice stops, the words stay, and the choice is remembered ----
    await aloud.click();
    await expect(aloud).toHaveAttribute('aria-pressed', 'false');
    await expect.poll(() => page.evaluate(() => speechSynthesis.speaking)).toBe(false);
    await expect(transcript).toBeVisible();
    // With nothing spoken there is no transcript to hide: the words are the narration.
    await expect(page.getByRole('button', { name: 'Transcript' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Pause' })).toBeVisible();

    // Leaving a lesson never leaves a voice talking.
    await aloud.click();
    await expect.poll(() => page.evaluate(() => speechSynthesis.speaking)).toBe(true);
    await page.getByRole('button', { name: 'Back to course' }).click();
    await expect.poll(() => page.evaluate(() => speechSynthesis.speaking)).toBe(false);

    await page.getByRole('button', { name: 'Settings' }).click();
    await page.getByRole('tab', { name: 'Learning' }).click();
    await expect(page.getByRole('switch', { name: 'Narration' })).toBeChecked();
    expect(adle.problems).toEqual([]);
  });
});
