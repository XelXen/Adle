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
  courseCard,
  expectNoAccessibilityViolations,
  saveProviderKey,
  screenshot,
  showNarrationAsText,
  openWhatIsSent,
  closeWhatIsSent,
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
// The suggested step is the one region named by its title that also gives its reason.
const suggestion = (page: Page, title: string | RegExp) =>
  page.getByRole('region', { name: title }).filter({ hasText: 'Why:' });

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
  await expect(form.getByText(/^(Correct|Partly right|Not quite)$/)).toBeVisible();
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
    await expect(form.getByText('Correct', { exact: true })).toBeVisible();
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
  await expect(form.getByText('Correct', { exact: true })).toBeVisible();
}

/** Answer every question of a practice set correctly and open its summary. */
async function finishPractice(page: Page, questions: number): Promise<void> {
  for (let number = 1; number <= questions; number += 1) {
    await expect(page.getByText(`Question ${number} of ${questions}`)).toBeVisible();
    await answerCorrectly(page);
    await page
      .getByRole('button', { name: number === questions ? 'See results' : 'Next question' })
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
    const start = suggestion(page, `Start “${LESSON}”`);
    await expect(start).toContainText(
      `Why: “${CONCEPT}” is next in your course. It has no prerequisites.`,
    );
    await expect(concepts(page).getByRole('listitem')).toHaveCount(8);
    await expect(page.getByText('8 concepts: 8 not started.')).toBeVisible();
    await expect(page.getByText('it’s never a grade')).toBeVisible();
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
        'A follow-up question will check.',
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
    const checkStep = suggestion(page, `Check “${CONCEPT}”`);
    await expect(checkStep).toContainText(
      `More than one answer on “${CONCEPT}” suggests that what causes what may be the other way round.`,
    );
    await expect(checkStep).toContainText('It’s also fine to stop for today.');
    await expectNoAccessibilityViolations(page);
    await screenshot(page, 'lesson-finished-what-next');
    await checkStep.getByRole('button', { name: 'Answer a few questions' }).click();

    // ---- The check asks the question that would show it ----
    await expect(
      page.getByRole('heading', { name: `Quick check: ${CONCEPT}`, level: 1 }),
    ).toBeVisible();
    await expect(page.getByText('Why these questions:')).toBeVisible();
    await expect(page.getByText('Question 1 of 3')).toBeVisible();
    await expect(page.locator('form')).toContainText('The input rises from');
    await expectNoAccessibilityViolations(page);
    await screenshot(page, 'practice-question');
    await answerCorrectly(page);
    await expect(page.locator('form')).toContainText(
      'This one goes against that. One more like it settles it.',
    );
    await page.getByRole('button', { name: 'Next question' }).click();
    await expect(page.getByText('Question 2 of 3')).toBeVisible();
    await answerCorrectly(page);
    await page.getByRole('button', { name: 'Next question' }).click();
    await expect(page.getByText('Question 3 of 3')).toBeVisible();
    await answerCorrectly(page);
    await page.getByRole('button', { name: 'See results' }).click();

    const done = page.getByRole('region', { name: 'Done' });
    await expect(done).toContainText('3 of 3 answers right.');
    await expect(done).toContainText(`Status of “${CONCEPT}”:`);
    await expect(
      done.getByRole('list', { name: 'Your answers' }).getByRole('listitem'),
    ).toHaveCount(3);
    await expect(page.getByText('Up next')).toBeVisible();
    await expectNoAccessibilityViolations(page);
    await screenshot(page, 'practice-done');
    await page.getByRole('button', { name: 'Back to course' }).click();

    // ---- The course shows what was noticed, as a hypothesis the learner can set aside ----
    const row = concepts(page).getByRole('listitem').filter({ hasText: CONCEPT }).first();
    const noticed = page.getByRole('list', { name: `Notes on ${CONCEPT}` });
    await expect(noticed).toContainText('Seen more than once');
    await expect(noticed).toContainText(
      'More than one answer suggests that what causes what may be the other way round.',
    );
    await expect(row).toContainText('1 of 1 lesson finished.');

    // ---- This session: what it showed, as counts of what happened and never as a score ----
    const session = page.getByRole('region', { name: 'This session' });
    await expect(session).toContainText('1 lesson finished, 6 questions answered.');
    const shown = session.getByRole('list', { name: 'What you got right' });
    await expect(shown.getByRole('listitem')).toHaveCount(1);
    await expect(shown).toContainText(CONCEPT);
    // One right answer in the lesson and three in the check. The two wrong ones are not
    // mentioned: they showed nothing, and nothing is held against the learner.
    await expect(shown).toContainText('4 answers right.');
    // What is still open is said as the concept's own row says it.
    await expect(session.getByRole('list', { name: 'Still in progress' })).toContainText(
      'Still needed: a possible misunderstanding to clear up.',
    );
    await expect(session.getByText('“With help” means')).toHaveCount(0);
    await expect(session.getByRole('list', { name: 'Upcoming reviews' })).toContainText(
      'Review tomorrow.',
    );
    await expect(session).not.toContainText('%');
    await expectNoAccessibilityViolations(page);
    await screenshot(page, 'learn-hypothesis');
    await session.scrollIntoViewIfNeeded();
    await screenshot(page, 'learn-session');
    await noticed.getByRole('button', { name: 'That was a slip' }).click();
    await expect(page.getByRole('status').filter({ hasText: 'Set aside' })).toBeVisible();
    await expect(noticed).toContainText('You marked it as a slip, so it’s set aside.');
    await expect(noticed.getByRole('button', { name: 'That was a slip' })).toHaveCount(0);
    // The button is gone; the keyboard is left on the line that says what became of it.
    await expect(noticed.getByRole('listitem').first()).toBeFocused();
    // Nothing is due yet: it was all answered a moment ago.
    await expect(row).toContainText('Next review tomorrow');
    await expect(row.getByText('Review due')).toHaveCount(0);

    expect(first.problems).toEqual([]);
    await first.close();

    // ---- Two days later ----
    letTimePass(profileDir, 2);
    const second = await launchApp(profileDir, { onboarded: true, theme: 'dark' });
    const later = second.page;
    await waitForCore(later);
    await courseCard(later, new RegExp(COURSE)).click();
    await expect(later.getByRole('tab', { name: 'Learn', exact: true })).toHaveAttribute(
      'aria-selected',
      'true',
    );

    const review = suggestion(later, `Review “${CONCEPT}”`);
    await expect(review).toContainText(
      `Why: A review of “${CONCEPT}” was due a day ago. ` +
        'Recalling it after a gap is what makes it stick.',
    );
    const laterRow = concepts(later).getByRole('listitem').filter({ hasText: CONCEPT }).first();
    await expect(laterRow).toContainText('Review due');
    await expect(later.getByText('1 review due.')).toBeVisible();
    // Coming back, the same sitting is "last time": a reminder of where things were left.
    const lastTime = later.getByRole('region', { name: 'Last time, 2 days ago' });
    await expect(lastTime).toContainText('1 lesson finished, 6 questions answered.');
    await expect(lastTime.getByRole('list', { name: 'What you got right' })).toContainText(
      '4 answers right.',
    );
    await expect(lastTime.getByRole('list', { name: 'Upcoming reviews' })).toContainText(
      'Review due.',
    );
    await expect(later.getByRole('region', { name: 'This session' })).toHaveCount(0);
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
    await later.getByRole('button', { name: 'Back to course' }).click();

    // ---- The review is done, and the next one is further away than the last ----
    await expect(laterRow).toContainText(/Next review in \d+ days/);
    await expect(laterRow.getByText('Review due')).toHaveCount(0);
    // A new sitting has taken the place of the old one.
    const today = later.getByRole('region', { name: 'This session' });
    await expect(today).toContainText('3 questions answered.');
    // One of the three was an explanation the learner marked themselves: still a right
    // answer, said to be lighter evidence, with what that means underneath.
    await expect(today.getByRole('list', { name: 'What you got right' })).toContainText(
      '3 answers right, 1 with help.',
    );
    await expect(today).toContainText('“With help” means after a hint');
    await expect(today.getByRole('list', { name: 'Upcoming reviews' })).toContainText(
      /Review in \d+ days\./,
    );
    await expect(later.getByRole('region', { name: /^Last time/ })).toHaveCount(0);
    await expectNoAccessibilityViolations(later);
    await today.scrollIntoViewIfNeeded();
    await screenshot(later, 'learn-session-dark');
    await expect(later.getByText('1 review due.')).toHaveCount(0);
    await expect(suggestion(later, `Review “${CONCEPT}”`)).toHaveCount(0);

    expect(second.problems).toEqual([]);
    await second.close();
  });

  test('an explanation that did not help leads somewhere else', async ({ adle }) => {
    test.setTimeout(120_000);
    const { page } = adle;
    await addSampleCourse(page);
    await suggestion(page, `Start “${LESSON}”`)
      .getByRole('button', { name: 'Start lesson' })
      .click();
    await expectPart(page, 1);

    // ---- Saying so is taken at face value, and nothing sends the learner back ----
    await page.getByRole('button', { name: 'This didn’t help' }).click();
    const dialog = page.getByRole('dialog', { name: 'Thanks for the feedback' });
    await expect(dialog).toContainText('That’s about the explanation, not you.');
    await expect(dialog).toContainText('Adle will take it into account.');
    await expect(dialog).toContainText('Go straight to the next question');
    // Without a key, another explanation is offered honestly: it needs setting up.
    await expect(dialog).toContainText('Needs an AI provider key.');
    await expect(dialog.getByRole('button', { name: 'Set up AI provider' })).toBeVisible();
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
    await expect(page.getByRole('button', { name: 'This didn’t help' })).toHaveCount(0);

    // ---- Back in the course, the suggestion has changed ----
    await page.getByRole('button', { name: 'Back to course' }).click();
    // Something that can be done without a key comes first, and it is not the lesson that
    // did not help: a concept that needs nothing before it.
    await expect(suggestion(page, 'Start “Derivatives and the chain rule”')).toContainText(
      'It has no prerequisites.',
    );
    // Another explanation is offered beside it, with the reason, and with what it needs.
    const instead = page.getByRole('region', { name: 'Other options' });
    const another = instead
      .getByRole('listitem')
      .filter({ hasText: `Try another explanation of “${CONCEPT}”` });
    await expect(another).toContainText(`You said an explanation of “${CONCEPT}” didn’t help.`);
    await expect(another).toContainText('Add an AI provider key to create this lesson.');
    // The lesson is still there to continue, as the last thing offered.
    await expect(instead.getByRole('listitem').last()).toContainText(`Continue “${LESSON}”`);
    await expectNoAccessibilityViolations(page);
    await screenshot(page, 'learn-another-explanation');

    await another.getByRole('button', { name: 'Set up AI provider' }).click();
    await expect(page.getByRole('heading', { name: 'Settings', level: 1 })).toBeVisible();
    expect(adle.problems).toEqual([]);
  });

  test('saying an explanation did not help can be taken back', async ({ adle }) => {
    test.setTimeout(120_000);
    const { page } = adle;
    await addSampleCourse(page);
    await suggestion(page, `Start “${LESSON}”`)
      .getByRole('button', { name: 'Start lesson' })
      .click();
    await expectPart(page, 1);
    // A toggle known by its picture: its name is for hover and for assistive technology.
    const didNotHelp = page.getByRole('button', { name: 'This didn’t help' });
    await expect(didNotHelp).toHaveAttribute('aria-pressed', 'false');

    // ---- Pressed by mistake: undone from the dialog it opens ----
    await didNotHelp.click();
    const dialog = page.getByRole('dialog', { name: 'Thanks for the feedback' });
    await dialog.getByRole('button', { name: 'Undo' }).click();
    await expect(dialog).toBeHidden();
    await expect(page.getByRole('status').filter({ hasText: 'Feedback removed' })).toBeVisible();
    await expect(didNotHelp).toHaveAttribute('aria-pressed', 'false');

    // ---- As if it had never been said: the lesson is still what to continue ----
    await page.getByRole('button', { name: 'Back to course' }).click();
    const resume = suggestion(page, `Continue “${LESSON}”`);
    await expect(resume).toContainText('Why: You stopped partway through this lesson.');
    await expect(page.getByText(`Try another explanation of “${CONCEPT}”`)).toHaveCount(0);

    // ---- Said and left standing, it is still shown when the lesson is opened again ----
    await resume.getByRole('button', { name: 'Continue lesson' }).click();
    await expectPart(page, 1);
    await didNotHelp.click();
    await dialog.getByRole('button', { name: 'Continue this lesson' }).click();
    await expect(didNotHelp).toHaveAttribute('aria-pressed', 'true');
    await page.getByRole('button', { name: 'Back to course' }).click();
    const instead = page.getByRole('region', { name: 'Other options' });
    await expect(
      instead.getByRole('listitem').filter({ hasText: `Try another explanation of “${CONCEPT}”` }),
    ).toBeVisible();
    await instead
      .getByRole('listitem')
      .filter({ hasText: `Continue “${LESSON}”` })
      .getByRole('button', { name: 'Continue lesson' })
      .click();
    await expectPart(page, 1);
    await expect(didNotHelp).toHaveAttribute('aria-pressed', 'true');
    await expectNoAccessibilityViolations(page);
    await screenshot(page, 'lesson-did-not-help-said');

    // ---- Pressed again, it is taken back, with nothing to choose ----
    await didNotHelp.click();
    await expect(didNotHelp).toHaveAttribute('aria-pressed', 'false');
    await expect(dialog).toHaveCount(0);
    await page.getByRole('button', { name: 'Back to course' }).click();
    await expect(suggestion(page, `Continue “${LESSON}”`)).toBeVisible();
    await expect(page.getByText(`Try another explanation of “${CONCEPT}”`)).toHaveCount(0);
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
      await saveProviderKey(page, /Custom endpoint/, KEY);
      await page.getByRole('button', { name: 'Library', exact: true }).click();
      await addSampleCourse(page);

      await suggestion(page, `Start “${LESSON}”`)
        .getByRole('button', { name: 'Start lesson' })
        .click();
      await expectPart(page, 1);
      await page.getByRole('button', { name: 'This didn’t help' }).click();
      const dialog = page.getByRole('dialog', { name: 'Thanks for the feedback' });

      // ---- The learner chooses the kind of explanation; what is sent is said first ----
      const how = dialog.getByRole('combobox', { name: 'Teaching style' });
      // The lesson they are in is a visual one, so that is not offered again.
      await expect(how.getByRole('option', { name: 'Visual first' })).toHaveCount(0);
      await how.selectOption({ label: 'Everyday analogy' });
      const sent = await openWhatIsSent(page, dialog);
      await expect(sent).toContainText(
        'Sends the course name, this concept and its objectives, and your level, ' +
          'preferences, and goal, plus any related passages from your materials to ' +
          'Custom endpoint (127.0.0.1).',
      );
      await closeWhatIsSent(page, dialog);
      expect(provider.requests).toHaveLength(0);
      await dialog.getByRole('button', { name: 'Create lesson' }).click();

      // ---- The course shows the work, then suggests the new lesson ahead of the old one ----
      await expect(page.getByRole('tab', { name: 'Learn', exact: true })).toHaveAttribute(
        'aria-selected',
        'true',
      );
      const fresh = suggestion(page, 'Try “How a neuron weighs its inputs”');
      await expect(fresh).toBeVisible({ timeout: 90_000 });
      await expect(fresh).toContainText(
        `Why: There’s another explanation of “${CONCEPT}” you haven’t tried.`,
      );
      await expect(page.getByRole('region', { name: 'Other options' })).toContainText(
        `Continue “${LESSON}”`,
      );
      await screenshot(page, 'learn-new-explanation');

      // The lesson is offered as soon as it is written; its two pictures follow it.
      await expect
        .poll(() => provider.requests.map((request) => request.kind))
        .toEqual(['lesson', 'scene', 'scene']);
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
