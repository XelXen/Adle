/**
 * Taking a lesson: the sample course's first lesson from start to finish, with
 * its narration, a live scene, questions scored by the core, and the record it
 * leaves. No AI is involved, and the test session has no network.
 */
import path from 'node:path';
import { DatabaseSync } from 'node:sqlite';

import type { Locator, Page } from '@playwright/test';

import { expect, launchApp, test, waitForCore } from './support/app';
import {
  expectNoAccessibilityViolations,
  screenshot,
  showNarrationAsText,
} from './support/courses';
import { fixtureScene } from './support/player';

const COURSE = 'Introduction to neural networks';
const LESSON = 'Weights and bias: how a neuron adds things up';

const detail = (page: Page, title: string) => page.getByRole('region', { name: title });
const lessons = (page: Page) =>
  detail(page, 'Weights and bias').getByRole('list', { name: 'Lessons for this concept' });
const parts = (page: Page) => page.getByRole('list', { name: 'Parts of this lesson' });
const transcript = (page: Page) => page.getByRole('complementary', { name: 'Transcript' });
const continueButton = (page: Page) => page.getByRole('button', { name: 'Continue', exact: true });

async function addSampleCourse(page: Page): Promise<void> {
  await waitForCore(page);
  await showNarrationAsText(page);
  await page.getByRole('button', { name: 'Try the sample course' }).click();
  await expect(page.getByRole('heading', { name: COURSE, level: 1 })).toBeVisible();
}

async function expectPart(page: Page, number: number, title: string): Promise<void> {
  await expect(page.getByText(`Part ${number} of 10`)).toBeVisible();
  await expect(page.getByRole('heading', { name: title, level: 2 })).toBeVisible();
}

/** Wait until the scene of the current part has loaded (or has given up). */
async function sceneSettled(figure: Locator): Promise<void> {
  await expect(figure.getByText('Preparing the visualization…')).toBeHidden({ timeout: 30_000 });
}

/** Replace a stored scene's source, as a restored or hand-edited database would. */
function replaceSceneSource(profileDir: string, sceneId: string, source: string): void {
  const database = new DatabaseSync(path.join(profileDir, 'data', 'adle.db'));
  try {
    const result = database
      .prepare(
        "UPDATE lesson_scenes SET document = json_set(document, '$.source', ?) WHERE scene_id = ?",
      )
      .run(source, sceneId);
    expect(result.changes).toBe(1);
  } finally {
    database.close();
  }
}

test.describe('lesson', () => {
  test('take the sample lesson from start to finish', async ({ adle }) => {
    test.setTimeout(180_000);
    const { page } = adle;
    await addSampleCourse(page);

    // ---- The course says which concept has a lesson, and how long it is ----
    const learningPath = page.getByRole('list', { name: 'Learning path' });
    await expect(learningPath.getByRole('listitem')).toHaveCount(8);
    await expect(learningPath.getByRole('listitem').first()).toContainText('Lesson ready');
    await expect(lessons(page).getByRole('listitem')).toHaveCount(1);
    await expect(lessons(page)).toContainText(LESSON);
    await expect(lessons(page)).toContainText('About 8 minutes · Not started');
    await screenshot(page, 'course-with-lesson');
    await lessons(page)
      .getByRole('button', { name: /^Start lesson: Weights and bias/ })
      .click();

    // ---- Nothing plays until the learner asks ----
    await expect(page.getByRole('heading', { name: LESSON, level: 1 })).toBeVisible();
    await expect(page.getByText('A sample lesson written by Adle.')).toBeVisible();
    await expect(parts(page).getByRole('button')).toHaveCount(10);
    await expectPart(page, 1, 'Not every input counts the same');
    await expect(transcript(page).getByRole('listitem')).toHaveCount(3);
    await expect(page.getByText('Press Start when you are ready.')).toBeVisible();
    // Only the part the learner is on can be reached so far.
    await expect(parts(page).getByRole('button', { name: /^Part 2:/ })).toBeDisabled();
    await expectNoAccessibilityViolations(page);
    await screenshot(page, 'lesson-ready');

    // ---- Narration: start, pause, resume ----
    await page.getByRole('button', { name: 'Start', exact: true }).click();
    await expect(page.getByRole('button', { name: 'Pause' })).toBeVisible();
    const firstBeat = transcript(page).getByRole('listitem').first();
    await expect(firstBeat).toHaveAttribute('aria-current', 'true');
    await page.getByRole('button', { name: 'Pause' }).click();
    await expect(page.getByRole('button', { name: 'Resume' })).toBeVisible();
    await page.getByRole('button', { name: 'Resume' }).click();
    await expect(page.getByRole('button', { name: 'Pause' })).toBeVisible();

    // ---- A narrated picture, with the same thing available in words ----
    await continueButton(page).click();
    await expectPart(page, 2, 'The weighted sum');
    const picture = page.getByRole('figure', { name: 'The weighted sum' });
    await sceneSettled(picture);
    await expect(picture.getByText('The animation could not be shown')).toHaveCount(0);
    // Having pressed Start once, later parts begin by themselves.
    await expect(page.getByRole('button', { name: 'Pause' })).toBeVisible();
    await page.getByRole('button', { name: 'Describe this picture in words' }).click();
    await expect(page.getByText(/A diagram shows two inputs on the left/)).toBeVisible();
    await expectNoAccessibilityViolations(page);
    await screenshot(page, 'lesson-scene');

    // ---- Something to try, operable from the keyboard ----
    await continueButton(page).click();
    await expectPart(page, 3, 'Change a weight yourself');
    await expect(page.getByText(/Drag the weight below zero and back/)).toBeVisible();
    const live = page.getByRole('figure', { name: 'Change a weight yourself' });
    await sceneSettled(live);
    const weight = live.getByRole('slider', { name: 'Weight' });
    await expect(weight).toBeVisible({ timeout: 20_000 });
    await expect(live.getByRole('switch', { name: 'Bias on' })).toBeVisible();
    await weight.focus();
    await page.keyboard.press('ArrowRight');
    await expect(page.getByText('You tried it.')).toBeVisible();
    await screenshot(page, 'lesson-interaction');

    // ---- A question must be answered or skipped; a wrong answer is explained, not punished ----
    await continueButton(page).click();
    await expectPart(page, 4, 'Which input matters more?');
    await expect(continueButton(page)).toBeDisabled();
    await expect(page.getByText('Answer or skip the question to continue.')).toBeVisible();
    await page.getByRole('button', { name: 'Check answer' }).click();
    await expect(page.getByText('Choose one of the options first.')).toBeVisible();
    await expect(page.getByRole('radio')).toHaveCount(3);
    await page.getByRole('radio', { name: 'The second input' }).check();
    await page.getByRole('button', { name: 'Check answer' }).click();
    await expect(page.getByText('Not quite')).toBeVisible();
    await expect(page.getByText(/Its weight is the smaller one/)).toBeVisible();
    await expect(page.getByText(/Influence comes from the weight/)).toBeVisible();
    // The options stay readable and say what each turned out to be, in words.
    await expect(page.getByRole('radio', { name: 'The second input' })).toBeDisabled();
    await expect(page.getByRole('radio', { name: 'The second input' })).toHaveAccessibleDescription(
      'Your answer',
    );
    await expect(page.getByRole('radio', { name: 'The first input' })).toHaveAccessibleDescription(
      'The right answer',
    );
    await expect(continueButton(page)).toBeEnabled();
    await expectNoAccessibilityViolations(page);
    await screenshot(page, 'lesson-question');

    // ---- A worked example builds up step by step, with typeset mathematics ----
    await continueButton(page).click();
    await expectPart(page, 5, 'A weighted sum by hand');
    await expect(page.locator('ol .katex').first()).toBeVisible();
    await screenshot(page, 'lesson-worked-example');

    // ---- A numeric answer, after asking for a hint ----
    await continueButton(page).click();
    await expectPart(page, 6, 'Your turn to compute');
    await page.getByRole('button', { name: 'Show a hint' }).click();
    await expect(page.getByText(/Multiply each input by its own weight first/)).toBeVisible();
    await page.getByRole('textbox', { name: 'Your answer' }).fill('three');
    await page.getByRole('button', { name: 'Check answer' }).click();
    await expect(page.getByText('Enter a number, for example 2.5 or 1/2.')).toBeVisible();
    await page.getByRole('textbox', { name: 'Your answer' }).fill('3');
    await page.keyboard.press('Enter');
    await expect(page.getByText('That is right')).toBeVisible();

    await continueButton(page).click();
    await expectPart(page, 7, 'What the bias is for');

    // ---- Skipping is allowed, and said plainly ----
    await continueButton(page).click();
    await expectPart(page, 8, 'A neuron with nothing coming in');
    await page.getByRole('button', { name: 'Skip this question' }).click();
    await expect(page.getByText('Skipped', { exact: true })).toBeVisible();

    // ---- A part comes to rest by itself when its narration is over ----
    await continueButton(page).click();
    await expectPart(page, 9, 'Something to think about');
    await expect(page.getByText(/A weight of exactly zero/)).toBeVisible();
    await expect(page.getByRole('button', { name: 'Play again' })).toBeVisible({ timeout: 20_000 });

    // ---- Finishing: what it was for, and what the answers showed ----
    await continueButton(page).click();
    await expectPart(page, 10, 'In short');
    await page.getByRole('button', { name: 'Finish lesson' }).click();
    const finished = page.getByRole('region', { name: 'Lesson complete' });
    await expect(finished).toBeVisible();
    await expect(finished).toContainText("Compute a neuron's weighted sum");
    await expect(finished).toContainText('Where this concept stands:');
    await expect(finished).toContainText('Building understanding');
    await expect(finished).toContainText('Still needed:');
    await expectNoAccessibilityViolations(page);
    await screenshot(page, 'lesson-finished');

    // ---- Back in the course, the record shows what happened and why ----
    await finished.getByRole('button', { name: 'Back to the course' }).click();
    await expect(page.getByRole('heading', { name: COURSE, level: 1 })).toBeVisible();
    await expect(learningPath.getByRole('listitem').first()).toContainText(
      'Building understanding',
    );
    await expect(lessons(page)).toContainText('About 8 minutes · Completed');
    const concept = detail(page, 'Weights and bias');
    await concept.getByRole('button', { name: 'Show the record' }).click();
    const record = concept.getByRole('list', { name: 'Record for this concept, newest first' });
    await expect(record.getByRole('listitem')).not.toHaveCount(0);
    await expect(record).toContainText(/hint/i);

    // ---- A finished lesson is open from end to end, and its questions no longer block ----
    await lessons(page)
      .getByRole('button', { name: /^Go through it again: Weights and bias/ })
      .click();
    await expectPart(page, 1, 'Not every input counts the same');
    await parts(page)
      .getByRole('button', { name: /^Part 4:/ })
      .click();
    await expectPart(page, 4, 'Which input matters more?');
    await expect(continueButton(page)).toBeEnabled();
    await expect(page.getByText('Answer or skip the question to continue.')).toHaveCount(0);

    expect(adle.problems).toEqual([]);
  });

  test('a lesson resumes where it was left, and survives scenes that cannot run', async ({
    profileDir,
  }) => {
    test.setTimeout(180_000);
    const first = await launchApp(profileDir, { onboarded: true, theme: 'light' });
    await addSampleCourse(first.page);
    await lessons(first.page)
      .getByRole('button', { name: /^Start lesson/ })
      .click();
    await expectPart(first.page, 1, 'Not every input counts the same');

    // Moving on without pressing Start: the next part waits too, holding its scene still.
    await continueButton(first.page).click();
    await expectPart(first.page, 2, 'The weighted sum');
    const picture = first.page.getByRole('figure', { name: 'The weighted sum' });
    await sceneSettled(picture);
    await expect(
      first.page.getByText('Press Start to play the animation with its narration.'),
    ).toBeVisible();
    await first.page.waitForTimeout(800);
    const held = await picture.screenshot();
    await first.page.waitForTimeout(1200);
    expect(Buffer.compare(held, await picture.screenshot())).toBe(0);

    await first.page.getByRole('button', { name: 'Start', exact: true }).click();
    await expect(first.page.getByRole('button', { name: 'Pause' })).toBeVisible();
    await first.page.waitForTimeout(5000);
    expect(Buffer.compare(held, await picture.screenshot())).not.toBe(0);

    await first.page.getByRole('button', { name: 'Back to the course' }).click();
    await expect(lessons(first.page)).toContainText('About 8 minutes · Part 2 of 10');
    await expect(lessons(first.page).getByRole('button', { name: /^Continue: / })).toBeVisible();
    expect(first.problems).toEqual([]);
    await first.close();

    // One scene now fails while it plays; the other is something Adle will not run at all.
    replaceSceneSource(profileDir, 'scn_weighted_sum', fixtureScene('stops_half_way.py'));
    replaceSceneSource(profileDir, 'scn_neuron_weight', fixtureScene('bad_import.py'));

    const second = await launchApp(profileDir, { onboarded: true, theme: 'dark' });
    const { page } = second;
    await waitForCore(page);
    await page.getByRole('button', { name: new RegExp(COURSE) }).click();
    await lessons(page)
      .getByRole('button', { name: /^Continue: / })
      .click();
    await expectPart(page, 2, 'The weighted sum');

    // ---- A scene that breaks while playing: the same idea in words, and the lesson goes on ----
    await page.getByRole('button', { name: 'Start', exact: true }).click();
    const broken = page.getByRole('figure', { name: 'The weighted sum' });
    await expect(
      broken.getByText('The animation could not be shown, so here is the same idea in words.'),
    ).toBeVisible({ timeout: 30_000 });
    await expect(broken.getByText(/A diagram shows two inputs on the left/)).toBeVisible();
    await expect(broken.getByRole('button', { name: 'Try the animation again' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Pause' })).toBeVisible();
    await expectNoAccessibilityViolations(page);
    await screenshot(page, 'lesson-scene-fallback-dark');

    // ---- A scene the core withholds: no player at all, only the description ----
    await continueButton(page).click();
    await expectPart(page, 3, 'Change a weight yourself');
    await expect(
      page.getByText(
        'The picture for this part is not available, so here is the same idea in words.',
      ),
    ).toBeVisible();
    await expect(page.getByText(/A bar shows the output/)).toBeVisible();
    await expect(page.locator('iframe')).toHaveCount(0);
    await expect(page.getByText(/Drag the weight below zero and back/)).toBeVisible();
    await expectNoAccessibilityViolations(page);

    // The rest of the lesson is untouched.
    await continueButton(page).click();
    await expectPart(page, 4, 'Which input matters more?');
    await page.getByRole('radio', { name: 'The first input' }).check();
    await page.getByRole('button', { name: 'Check answer' }).click();
    await expect(page.getByText('That is right')).toBeVisible();
    await expect(page.getByRole('radio', { name: 'The first input' })).toHaveAccessibleDescription(
      'Your answer, and the right one',
    );
    await screenshot(page, 'lesson-question-dark');
    await second.close();
  });
});
