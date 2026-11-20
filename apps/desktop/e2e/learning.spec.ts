/**
 * The adaptive loop, as a learner meets it: the course says what to do next and
 * why; answers become evidence; a pattern of wrong answers becomes a hypothesis
 * that is checked rather than assumed; the learner can set it aside; a review
 * comes due after a gap; and an explanation that did not help leads somewhere
 * other than back into itself.
 *
 * Everything here runs on the sample course. The provider, where one is
 * needed, is a server on this computer.
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
import { startFakeProvider } from './support/fake-provider';

const COURSE = 'Introduction to neural networks';
const CONCEPT = 'Weights and bias';
const LESSON = 'Weights and bias: how a neuron adds things up';
/** A recognisable fake key. It only ever reaches the fake provider. */
const KEY = 'sk-e2e-not-a-real-key-7Hq2mZx94Wd1';

const continueButton = (page: Page) => page.getByRole('button', { name: 'Continue', exact: true });
const concepts = (page: Page) => page.getByRole('list', { name: 'Concepts, in learning order' });
/** The suggestion on screen, found by what it says to do. */
const suggestion = (page: Page, title: string | RegExp) =>
  page.getByRole('region', { name: title }).filter({ hasText: 'Suggested next step' });

async function addSampleCourse(page: Page): Promise<void> {
  await waitForCore(page);
  await showNarrationAsText(page);
  await page.getByRole('button', { name: 'Try the sample course' }).click();
  await expect(page.getByRole('heading', { name: COURSE, level: 1 })).toBeVisible();
  // A course with something to learn opens on what to do next.
  await expect(page.getByRole('tab', { name: 'Learn', exact: true })).toHaveAttribute(
    'aria-selected',
    'true',
  );
}

async function expectPart(page: Page, number: number): Promise<void> {
  await expect(page.getByText(`Part ${number} of 10`)).toBeVisible();
}

async function check(form: Locator): Promise<void> {
  await form.getByRole('button', { name: 'Check answer' }).click();
  await expect(form.getByText(/^(That is right|Partly right|Not quite)$/)).toBeVisible();
}

/** Answer whichever of the sample concept's questions is on screen, correctly. */
async function answerCorrectly(page: Page): Promise<void> {
  const form = page.locator('form');
  const stem = (await form.locator('p').first().textContent()) ?? '';
  const type = (text: string) => form.getByRole('textbox', { name: 'Your answer' }).fill(text);

  if (stem.includes('In your own words')) {
    await form
      .getByRole('textbox', { name: 'Your explanation' })
      .fill('The bias is added whatever the inputs are, so it shifts the sum.');
    await form.getByRole('button', { name: 'Compare with a good answer' }).click();
    await form.getByRole('checkbox').first().check();
    await form.getByRole('button', { name: 'Record this' }).click();
    await expect(form.getByText('That is right')).toBeVisible();
    return;
  }
  if (stem.includes('Which input has more influence')) {
    await form.getByRole('radio', { name: 'The first input' }).check();
  } else if (stem.includes('should output')) {
    await form.getByRole('radio', { name: /Its bias is/ }).check();
  } else if (stem.includes('True or false')) {
    await form.getByRole('radio', { name: 'True', exact: true }).check();
  } else if (stem.includes('The input rises')) {
    await form.getByRole('radio', { name: /It falls from/ }).check();
  } else if (stem.includes('Which part of the neuron')) {
    await type('bias');
  } else if (stem.includes('x_3')) {
    await type('1.5');
  } else if (stem.includes('What is')) {
    await type('3');
  } else {
    throw new Error(`No answer is known for the question: ${stem}`);
  }
  await check(form);
  await expect(form.getByText('That is right')).toBeVisible();
}

/** Answer every question of a practice set correctly and open its summary. */
async function finishPractice(page: Page, questions: number): Promise<void> {
  for (let number = 1; number <= questions; number += 1) {
    await expect(page.getByText(`Question ${number} of ${questions}`)).toBeVisible();
    await answerCorrectly(page);
    await page
      .getByRole('button', { name: number === questions ? 'See how it went' : 'Next question' })
      .click();
  }
  await expect(page.getByRole('region', { name: 'Done' })).toBeVisible();
}

/** Make everything the learner did happen this much earlier, as if time had passed. */
function letTimePass(profileDir: string, days: number): void {
  const database = new DatabaseSync(path.join(profileDir, 'data', 'adle.db'));
  const earlier = `-${days} days`;
  try {
    const due = database
      .prepare(
        'SELECT count(*) AS scheduled FROM learner_concept_states WHERE review_due_at IS NOT NULL',
      )
      .get() as { scheduled: number };
    // The journey so far must have earned a review, or this test is not testing one.
    expect(due.scheduled).toBe(1);
    for (const [table, column] of [
      ['attempts', 'created_at'],
      ['learner_observations', 'occurred_at'],
      ['learner_events', 'occurred_at'],
      ['learner_concept_states', 'review_due_at'],
      ['learner_concept_states', 'last_observed_at'],
      ['lesson_progress', 'updated_at'],
    ] as const) {
      database
        .prepare(
          `UPDATE ${table} SET ${column} = datetime(${column}, ?) WHERE ${column} IS NOT NULL`,
        )
        .run(earlier);
    }
  } finally {
    database.close();
  }
}

test.describe('learning', () => {
  test('from the first suggestion to a review that comes due', async ({ profileDir }) => {
    test.setTimeout(240_000);
    const first = await launchApp(profileDir, { onboarded: true, theme: 'light' });
    const { page } = first;
    await addSampleCourse(page);

    // ---- A new course: one suggestion, with its reason, and an honest picture of progress ----
    const start = suggestion(page, `Start "${LESSON}"`);
    await expect(start).toContainText(
      `Why: "${CONCEPT}" is next in your course. It needs nothing first.`,
    );
    await expect(concepts(page).getByRole('listitem')).toHaveCount(8);
    await expect(page.getByText('8 concepts: 8 not assessed yet.')).toBeVisible();
    await expect(page.getByText('they are never a grade')).toBeVisible();
    await expectNoAccessibilityViolations(page);
    await screenshot(page, 'learn-first-visit');

    // ---- The lesson, with two answers that point the same way ----
    await start.getByRole('button', { name: 'Start lesson' }).click();
    await expect(page.getByRole('heading', { name: LESSON, level: 1 })).toBeVisible();
    for (const part of [1, 2, 3]) {
      await expectPart(page, part);
      await continueButton(page).click();
    }
    await expectPart(page, 4);
    const question = page.locator('form');
    await question.getByRole('radio', { name: /They have the same influence/ }).check();
    await check(question);
    await expect(question).toContainText(
      'That answer could mean that what causes what may be the other way round. ' +
        'One answer is not enough to say',
    );
    await continueButton(page).click();
    await expectPart(page, 5);
    await continueButton(page).click();
    await expectPart(page, 6);
    await answerCorrectly(page);
    await continueButton(page).click();
    await expectPart(page, 7);
    await continueButton(page).click();
    await expectPart(page, 8);
    await question.getByRole('radio', { name: /Every weight is/ }).check();
    await check(question);
    await expect(question).toContainText(
      'This is the second answer suggesting that what causes what may be the other way round',
    );
    await continueButton(page).click();
    await expectPart(page, 9);
    await continueButton(page).click();
    await expectPart(page, 10);
    await page.getByRole('button', { name: 'Finish lesson' }).click();

    // ---- The lesson ends with what to do next: a check, not a verdict, and no pressure ----
    const finished = page.getByRole('region', { name: 'Lesson complete' });
    await expect(finished).toBeVisible();
    const checkStep = suggestion(page, `Check "${CONCEPT}"`);
    await expect(checkStep).toContainText(
      `More than one answer on "${CONCEPT}" suggests that what causes what may be the other way round.`,
    );
    await expect(checkStep).toContainText('It is also fine to stop here for today.');
    await expectNoAccessibilityViolations(page);
    await screenshot(page, 'lesson-finished-what-next');
    await checkStep.getByRole('button', { name: 'Answer a few questions' }).click();

    // ---- The check asks the question that would show it ----
    await expect(
      page.getByRole('heading', { name: `A quick check: ${CONCEPT}`, level: 1 }),
    ).toBeVisible();
    await expect(page.getByText('Why these questions:')).toBeVisible();
    await expect(page.getByText('Question 1 of 3')).toBeVisible();
    await expect(page.locator('form')).toContainText('The input rises from');
    await expectNoAccessibilityViolations(page);
    await screenshot(page, 'practice-question');
    await answerCorrectly(page);
    await expect(page.locator('form')).toContainText(
      'This one goes against that; one more like it settles it.',
    );
    await page.getByRole('button', { name: 'Next question' }).click();
    await expect(page.getByText('Question 2 of 3')).toBeVisible();
    await answerCorrectly(page);
    await page.getByRole('button', { name: 'Next question' }).click();
    await expect(page.getByText('Question 3 of 3')).toBeVisible();
    await answerCorrectly(page);
    await page.getByRole('button', { name: 'See how it went' }).click();

    const done = page.getByRole('region', { name: 'Done' });
    await expect(done).toContainText('3 of 3 answers right.');
    await expect(done).toContainText(`Where “${CONCEPT}” stands:`);
    await expect(
      done.getByRole('list', { name: 'Your answers' }).getByRole('listitem'),
    ).toHaveCount(3);
    await expect(page.getByText('Suggested next step')).toBeVisible();
    await expectNoAccessibilityViolations(page);
    await screenshot(page, 'practice-done');
    await page.getByRole('button', { name: 'Back to the course' }).click();

    // ---- The course shows what was noticed, as a hypothesis the learner can set aside ----
    const row = concepts(page).getByRole('listitem').filter({ hasText: CONCEPT }).first();
    const noticed = page.getByRole('list', { name: `What Adle has noticed about ${CONCEPT}` });
    await expect(noticed).toContainText('Seen more than once');
    await expect(noticed).toContainText(
      'More than one answer suggests that what causes what may be the other way round.',
    );
    await expect(row).toContainText('1 of 1 lesson finished.');
    await expectNoAccessibilityViolations(page);
    await screenshot(page, 'learn-hypothesis');
    await noticed.getByRole('button', { name: 'That was a slip' }).click();
    await expect(page.getByRole('status').filter({ hasText: 'Set aside' })).toBeVisible();
    await expect(noticed).toContainText('You said it was a slip, so it is set aside.');
    await expect(noticed.getByRole('button', { name: 'That was a slip' })).toHaveCount(0);
    // Nothing is due yet: it was all answered a moment ago.
    await expect(row).toContainText('Next review tomorrow');
    await expect(row.getByText('A review is due')).toHaveCount(0);

    expect(first.problems).toEqual([]);
    await first.close();

    // ---- Two days later ----
    letTimePass(profileDir, 2);
    const second = await launchApp(profileDir, { onboarded: true, theme: 'dark' });
    const later = second.page;
    await waitForCore(later);
    await later.getByRole('button', { name: new RegExp(COURSE) }).click();
    await expect(later.getByRole('tab', { name: 'Learn', exact: true })).toHaveAttribute(
      'aria-selected',
      'true',
    );

    const review = suggestion(later, `Review "${CONCEPT}"`);
    await expect(review).toContainText(
      `Why: A review of "${CONCEPT}" was due a day ago. ` +
        'Answering from memory after a gap is what makes it last.',
    );
    const laterRow = concepts(later).getByRole('listitem').filter({ hasText: CONCEPT }).first();
    await expect(laterRow).toContainText('A review is due');
    await expect(later.getByText('1 review is due.')).toBeVisible();
    await expectNoAccessibilityViolations(later);
    await screenshot(later, 'learn-review-due-dark');

    await review.getByRole('button', { name: 'Start review' }).click();
    await expect(
      later.getByRole('heading', { name: `Review: ${CONCEPT}`, level: 1 }),
    ).toBeVisible();
    await finishPractice(later, 3);
    await expect(later.getByRole('region', { name: 'Done' })).toContainText(
      '3 of 3 answers right.',
    );
    await later.getByRole('button', { name: 'Back to the course' }).click();

    // ---- The review is done, and the next one is further away than the last ----
    await expect(laterRow).toContainText(/Next review in \d+ days/);
    await expect(laterRow.getByText('A review is due')).toHaveCount(0);
    await expect(later.getByText('1 review is due.')).toHaveCount(0);
    await expect(suggestion(later, `Review "${CONCEPT}"`)).toHaveCount(0);

    expect(second.problems).toEqual([]);
    await second.close();
  });

  test('an explanation that did not help leads somewhere else', async ({ adle }) => {
    test.setTimeout(120_000);
    const { page } = adle;
    await addSampleCourse(page);
    await suggestion(page, `Start "${LESSON}"`)
      .getByRole('button', { name: 'Start lesson' })
      .click();
    await expectPart(page, 1);

    // ---- Saying so is taken at face value, and nothing sends the learner back ----
    await page.getByRole('button', { name: 'This did not help' }).click();
    const dialog = page.getByRole('dialog', { name: 'Thanks for saying so' });
    await expect(dialog).toContainText('That says something about the explanation, not about you.');
    await expect(dialog).toContainText('It has been noted');
    await expect(dialog).toContainText('Go straight to the next question');
    // Without a key, another explanation is offered honestly: it needs setting up.
    await expect(dialog).toContainText('no key is set up yet');
    await expect(dialog.getByRole('button', { name: 'Set up the AI provider' })).toBeVisible();
    await expect(dialog.getByRole('button', { name: 'Go to the course' })).toBeVisible();
    await expectNoAccessibilityViolations(page);
    await screenshot(page, 'lesson-did-not-help');

    await dialog.getByRole('button', { name: 'Skip to the question' }).click();
    await expect(dialog).toBeHidden();
    await expectPart(page, 4);
    await expect(page.locator('form')).toContainText('Which input has more influence');
    // What was skipped stays open.
    const parts = page.getByRole('list', { name: 'Parts of this lesson' });
    await expect(parts.getByRole('button', { name: /^Part 2:/ })).toBeEnabled();
    // A question explains nothing, so there is nothing to report on it.
    await expect(page.getByRole('button', { name: 'This did not help' })).toHaveCount(0);

    // ---- Back in the course, the suggestion has changed ----
    await page.getByRole('button', { name: 'Back to the course' }).click();
    // Something that can be done without a key comes first, and it is not the lesson that
    // did not help: a concept that needs nothing before it.
    await expect(suggestion(page, 'Start "Derivatives and the chain rule"')).toContainText(
      'It needs nothing first.',
    );
    // Another explanation is offered beside it, with the reason, and with what it needs.
    const instead = page.getByRole('region', { name: 'Or instead' });
    const another = instead
      .getByRole('listitem')
      .filter({ hasText: `Try another explanation of "${CONCEPT}"` });
    await expect(another).toContainText(`You said an explanation of "${CONCEPT}" did not help.`);
    await expect(another).toContainText(
      'Writing a lesson needs the AI provider, and no key is set up yet.',
    );
    // The lesson is still there to continue, as the last thing offered.
    await expect(instead.getByRole('listitem').last()).toContainText(`Continue "${LESSON}"`);
    await expectNoAccessibilityViolations(page);
    await screenshot(page, 'learn-another-explanation');

    await another.getByRole('button', { name: 'Set up the AI provider' }).click();
    await expect(page.getByRole('heading', { name: 'Settings', level: 1 })).toBeVisible();
    expect(adle.problems).toEqual([]);
  });

  test('another explanation is written a different way, then suggested', async ({ profileDir }) => {
    test.setTimeout(180_000);
    const provider = await startFakeProvider();
    const adle = await launchApp(profileDir, {
      onboarded: true,
      theme: 'light',
      env: { ADLE_PROVIDER_BASE_URL: provider.baseUrl },
    });
    try {
      const { page } = adle;
      await waitForCore(page);
      await page.getByRole('button', { name: 'Settings' }).click();
      await page.getByLabel('API key', { exact: true }).fill(KEY);
      await page.getByRole('button', { name: 'Save key' }).click();
      await expect(page.getByText('Saved · ends in 4Wd1')).toBeVisible();
      await page.getByRole('button', { name: 'Library', exact: true }).click();
      await addSampleCourse(page);

      await suggestion(page, `Start "${LESSON}"`)
        .getByRole('button', { name: 'Start lesson' })
        .click();
      await expectPart(page, 1);
      await page.getByRole('button', { name: 'This did not help' }).click();
      const dialog = page.getByRole('dialog', { name: 'Thanks for saying so' });

      // ---- The learner chooses the kind of explanation; what is sent is said first ----
      const how = dialog.getByRole('combobox', { name: 'How should it explain?' });
      // The lesson they are in is a visual one, so that is not offered again.
      await expect(how.getByRole('option', { name: 'Pictures first' })).toHaveCount(0);
      await how.selectOption({ label: 'An everyday comparison' });
      await expect(dialog).toContainText(
        'Sends this concept and its objectives to Custom endpoint (127.0.0.1).',
      );
      expect(provider.requests).toHaveLength(0);
      await dialog.getByRole('button', { name: 'Create that lesson' }).click();

      // ---- The course shows the work, then suggests the new lesson ahead of the old one ----
      await expect(page.getByRole('tab', { name: 'Learn', exact: true })).toHaveAttribute(
        'aria-selected',
        'true',
      );
      const fresh = suggestion(page, 'Try "How a neuron weighs its inputs"');
      await expect(fresh).toBeVisible({ timeout: 90_000 });
      await expect(fresh).toContainText(
        `Why: There is another explanation of "${CONCEPT}" that you have not tried yet.`,
      );
      await expect(page.getByRole('region', { name: 'Or instead' })).toContainText(
        `Continue "${LESSON}"`,
      );
      await screenshot(page, 'learn-new-explanation');

      expect(provider.requests.map((request) => request.kind)).toEqual([
        'lesson',
        'scene',
        'scene',
      ]);
      const prompt = provider.requests[0]?.prompt ?? '';
      expect(prompt).toContain('Teach it the "analogy" way');
      expect(prompt).toContain('already had a lesson on this concept ("visual")');
      expect(prompt).not.toContain(KEY);

      await fresh.getByRole('button', { name: 'Start lesson' }).click();
      await expect(
        page.getByRole('heading', { name: 'How a neuron weighs its inputs', level: 1 }),
      ).toBeVisible();
      expect(adle.problems).toEqual([]);
    } finally {
      await adle.close();
      await provider.close();
    }
  });
});
