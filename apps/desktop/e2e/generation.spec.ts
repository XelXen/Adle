/**
 * Asking the AI for a curriculum and for a lesson, through the whole real path
 * (interface, main process, core, quota, jobs) with one substitution: the
 * provider is a server on this computer. No request leaves the machine, and
 * no test in this suite ever reaches the real provider.
 */
import type { Page } from '@playwright/test';

import { expect, launchApp, type LaunchedApp, test, waitForCore } from './support/app';
import {
  courseCard,
  createCourse,
  expectNoAccessibilityViolations,
  openCourseTab,
  providerKeyField,
  saveProviderKey,
  screenshot,
  showNarrationAsText,
} from './support/courses';
import { type FakeProvider, HANG, startFakeProvider } from './support/fake-provider';

/** A recognisable fake key. It only ever reaches the fake provider. */
const KEY = 'sk-e2e-not-a-real-key-7Hq2mZx94Wd1';

const pathList = (page: Page) => page.getByRole('list', { name: 'Learning path' });
const detail = (page: Page, title: string) => page.getByRole('region', { name: title });

interface Session {
  adle: LaunchedApp;
  page: Page;
  provider: FakeProvider;
}

async function open(
  profileDir: string,
  options: { key?: boolean; theme?: 'light' | 'dark' } = {},
): Promise<Session> {
  const provider = await startFakeProvider();
  const adle = await launchApp(profileDir, {
    onboarded: true,
    theme: options.theme ?? 'light',
    env: { ADLE_PROVIDER_BASE_URL: provider.baseUrl },
  });
  const { page } = adle;
  await waitForCore(page);
  await showNarrationAsText(page);
  if (options.key !== false) {
    await page.getByRole('button', { name: 'Settings' }).click();
    await saveProviderKey(page, /Custom endpoint/, KEY);
    await page.getByRole('button', { name: 'Library', exact: true }).click();
  }
  return { adle, page, provider };
}

async function close({ adle, provider }: Session): Promise<void> {
  await adle.close();
  await provider.close();
}

async function addConcept(page: Page, name: string): Promise<void> {
  await page.getByRole('button', { name: 'Add a concept' }).click();
  const dialog = page.getByRole('dialog', { name: 'Add a concept' });
  await dialog.getByLabel('Name').fill(name);
  await dialog.getByRole('textbox', { name: 'Objective 1' }).fill('Estimate a limit from a table.');
  await dialog.getByRole('button', { name: 'Add concept' }).click();
  await expect(detail(page, name)).toBeVisible();
}

test.describe('generation with the AI provider', () => {
  test('suggest concepts, choose among them, then have a lesson written and play it', async ({
    profileDir,
  }) => {
    test.setTimeout(180_000);
    const session = await open(profileDir);
    const { page, provider } = session;

    // The learner is told where requests go: this is not the default provider.
    await page.getByRole('button', { name: 'Settings' }).click();
    await expect(
      page.getByRole('heading', { name: 'Custom endpoint (127.0.0.1)', exact: true }),
    ).toBeVisible();
    // It is the only provider there is, so there is nothing to choose between.
    await expect(page.getByRole('group', { name: 'Which provider to use' })).toHaveCount(0);
    await expect(page.getByText('0 of 90', { exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Library', exact: true }).click();

    await createCourse(page, 'Calculus refresher', { topic: 'Limits and derivatives.' });

    // ---- Suggestions: what will be sent is said before anything is sent ----
    await page.getByRole('button', { name: 'Suggest concepts with AI' }).click();
    const ask = page.getByRole('dialog', { name: 'Ask the AI for concepts?' });
    await expect(ask).toContainText("this course's name, topic, and description");
    await expect(ask).toContainText('Custom endpoint (127.0.0.1)');
    await expect(ask).toContainText('Nothing is added to the course until you have looked');
    expect(provider.requests).toHaveLength(0);
    await ask.getByRole('button', { name: 'Send and suggest' }).click();

    // ---- The suggestions open for review; nothing is in the course yet ----
    const review = page.getByRole('dialog', { name: 'Suggested concepts' });
    await expect(review).toBeVisible({ timeout: 30_000 });
    await expect(review).toContainText('It did not see any of your materials.');
    await expect(review.getByRole('checkbox')).toHaveCount(3);
    await expect(review.getByRole('checkbox', { name: 'Limits' })).toBeChecked();
    await expect(review).toContainText(
      'Needs first: Limits (The derivative is defined as a limit.)',
    );
    await expectNoAccessibilityViolations(page);
    await screenshot(page, 'generation-proposal');

    // Dropping a suggestion that another builds on is said, not silently repaired.
    await review.getByRole('checkbox', { name: 'The derivative as a limit' }).uncheck();
    await expect(
      review.getByText('It builds on a suggestion you have not kept. That link will not be added.'),
    ).toBeVisible();
    await review.getByRole('button', { name: 'Add 2 concepts' }).click();

    await expect(pathList(page).getByRole('listitem')).toHaveCount(2);
    await expect(page.getByRole('status').filter({ hasText: '2 concepts added' })).toBeVisible();
    await expect(pathList(page).getByRole('listitem').nth(1)).toContainText('Needs Limits');
    await expect(detail(page, 'Limits')).toContainText('Proposed by the AI.');
    await expect(page.getByText('Suggestions are ready')).toHaveCount(0);

    expect(provider.requests.map((request) => request.kind)).toEqual(['curriculum']);
    expect(provider.requests[0]?.authorization).toBe(`Bearer ${KEY}`);
    expect(provider.requests[0]?.prompt).toContain('Calculus refresher');
    expect(provider.requests[0]?.prompt).not.toContain(KEY);

    // ---- A lesson: what is sent is beside the button; progress can be watched ----
    const limits = detail(page, 'Limits');
    await expect(limits).toContainText('No lesson has been made for this concept yet.');
    await expect(limits).toContainText(
      "Sends to Custom endpoint (127.0.0.1): this course's name, this concept and its " +
        'objectives, where you stand on it in a few words, your preferences for pace and ' +
        'depth, and your goal.',
    );
    await limits.getByRole('button', { name: 'Create a lesson with AI' }).click();
    await expect(limits.getByRole('progressbar')).toBeVisible();
    await expect(limits.getByRole('button', { name: 'Cancel' })).toBeVisible();

    await expect(page.getByRole('status').filter({ hasText: 'Lesson ready' })).toBeVisible({
      timeout: 60_000,
    });
    const lessons = limits.getByRole('list', { name: 'Lessons for this concept' });
    await expect(lessons.getByRole('listitem')).toHaveCount(1);
    await expect(lessons).toContainText('How a neuron weighs its inputs');
    await expect(
      limits.getByRole('button', { name: 'Create another lesson with AI' }),
    ).toBeVisible();
    // One request for the lesson and one complete file for each of its two scenes.
    expect(provider.requests.map((request) => request.kind)).toEqual([
      'curriculum',
      'lesson',
      'scene',
      'scene',
    ]);
    await expectNoAccessibilityViolations(page);
    await screenshot(page, 'generation-lesson-ready');

    // ---- The generated lesson plays like any other: scenes, questions, scoring ----
    await lessons.getByRole('button', { name: /^Start lesson/ }).click();
    await expect(
      page.getByRole('heading', { name: 'How a neuron weighs its inputs' }),
    ).toBeVisible();
    await expect(page.getByText('From general knowledge, not from your materials.')).toBeVisible();
    await expect(page.getByText('Part 1 of 8')).toBeVisible();
    const next = page.getByRole('button', { name: 'Continue', exact: true });
    await next.click();
    const picture = page.getByRole('figure', { name: 'The weighted sum' });
    await expect(picture.getByText('Preparing the visualization…')).toBeHidden({ timeout: 30_000 });
    await expect(picture.getByText('The animation could not be shown')).toHaveCount(0);
    await next.click();
    await page.getByRole('radio', { name: 'The first input' }).check();
    await page.getByRole('button', { name: 'Check answer' }).click();
    await expect(page.getByText('That is right')).toBeVisible();

    // ---- The local count of what was sent ----
    // A lesson has the whole window; the way to the rest of the app is back through the course.
    await page.getByRole('button', { name: 'Back to the course' }).click();
    await page.getByRole('navigation').getByRole('button', { name: 'Settings' }).click();
    await expect(page.getByText('4 of 90', { exact: true })).toBeVisible();
    await expect(page.getByText(/about 7,200 of 900,000/)).toBeVisible();
    await expectNoAccessibilityViolations(page);
    await screenshot(page, 'generation-usage');

    // ---- The library offers the way back in: the same suggestion the course would make ----
    await page
      .getByRole('navigation')
      .getByRole('button', { name: 'Library', exact: true })
      .click();
    await expect(page.getByRole('heading', { name: 'Pick up where you left off' })).toBeVisible();
    const pickUp = page.getByRole('region', {
      name: 'Continue "How a neuron weighs its inputs"',
    });
    await expect(pickUp).toContainText('Calculus refresher');
    await expect(pickUp).toContainText('Why:');
    await expect(pickUp.getByRole('button', { name: 'Continue lesson' })).toBeVisible();
    await expectNoAccessibilityViolations(page);
    await screenshot(page, 'library-pick-up');

    // ---- A lesson a model wrote can be removed, after being asked ----
    await courseCard(page, /Calculus refresher/).click();
    await openCourseTab(page, 'Curriculum');
    await pathList(page)
      .getByRole('button', { name: /Limits/ })
      .first()
      .click();
    await limits
      .getByRole('button', { name: 'Remove lesson: How a neuron weighs its inputs' })
      .click();
    const removal = page.getByRole('dialog', { name: /^Remove “How a neuron weighs its inputs”/ });
    await expect(removal).toContainText('What you have shown you know about the concept stays');
    await removal.getByRole('button', { name: 'Keep it' }).click();
    await expect(lessons.getByRole('listitem')).toHaveCount(1);
    await limits
      .getByRole('button', { name: 'Remove lesson: How a neuron weighs its inputs' })
      .click();
    await removal.getByRole('button', { name: 'Remove lesson' }).click();
    await expect(page.getByRole('status').filter({ hasText: 'Lesson removed' })).toBeVisible();
    await expect(limits).toContainText('No lesson has been made for this concept yet.');

    expect(session.adle.problems).toEqual([]);
    await close(session);
  });

  test('without a key nothing is sent, and the way to add one is offered', async ({
    profileDir,
  }) => {
    const session = await open(profileDir, { key: false });
    const { page, provider } = session;
    await createCourse(page, 'Calculus refresher', { topic: 'Limits.' });
    await addConcept(page, 'Limits');

    await detail(page, 'Limits').getByRole('button', { name: 'Create a lesson with AI' }).click();
    const refusal = detail(page, 'Limits').getByRole('alert');
    await expect(refusal).toContainText('The lesson could not be made');
    await expect(refusal).toContainText('Add your AI provider key in Settings to use this.');
    expect(provider.requests).toHaveLength(0);

    await refusal.getByRole('button', { name: 'Open AI settings' }).click();
    await expect(providerKeyField(page, /Custom endpoint/)).toBeVisible();
    await close(session);
  });

  test('a notice from the provider in the model’s place is shown as the provider’s own words', async ({
    profileDir,
  }) => {
    test.setTimeout(120_000);
    const session = await open(profileDir);
    const { page, provider } = session;
    await createCourse(page, 'Calculus refresher', { topic: 'Limits.' });
    await addConcept(page, 'Limits');
    const limits = detail(page, 'Limits');

    // What the real provider sent to an account that had not been topped up: a successful
    // answer, in the model's place, that is a sentence about the account.
    const notice =
      'Sorry, to prevent abuse of free resources, accounts that have not been recharged can ' +
      'only try 10 times. You can increase the free quota after recharging; ' +
      'https://console.aihubmix.com/topup';
    provider.queue({ notice });
    await limits.getByRole('button', { name: 'Create a lesson with AI' }).click();

    const failure = limits.getByRole('alert');
    await expect(failure).toContainText('The lesson could not be made', { timeout: 30_000 });
    // Whose words they are, the words themselves, and what they are about.
    await expect(failure).toContainText(
      'The AI provider answered with a notice of its own instead of passing this to the model.',
    );
    await expect(failure).toContainText(`It said: "${notice}"`);
    await expect(failure).toContainText(
      'This is about your account with the provider, not about Adle. Nothing was changed.',
    );
    // The address in it is text. Nothing in a provider's words becomes something to press.
    await expect(failure.getByRole('link')).toHaveCount(0);
    await expect(limits).toContainText('No lesson has been made for this concept yet.');
    // It was not mistaken for a bad draft and asked for again: one request, not two.
    expect(provider.requests).toHaveLength(1);
    // Asking again cannot help, so that is not what is offered.
    await expect(failure.getByRole('button', { name: 'Try again' })).toHaveCount(0);
    await expectNoAccessibilityViolations(page);
    await screenshot(page, 'generation-provider-notice');

    await failure.getByRole('button', { name: 'Open AI settings' }).click();
    await expect(page.getByRole('tab', { name: 'AI provider' })).toHaveAttribute(
      'aria-selected',
      'true',
    );

    expect(session.adle.problems).toEqual([]);
    await close(session);
  });

  test('a provider failure is explained and can be tried again; work can be cancelled', async ({
    profileDir,
  }) => {
    test.setTimeout(120_000);
    const session = await open(profileDir, { theme: 'dark' });
    const { page, provider } = session;
    await createCourse(page, 'Calculus refresher', { topic: 'Limits.' });
    await addConcept(page, 'Limits');
    const limits = detail(page, 'Limits');

    // ---- The provider fails: said plainly, nothing saved, one click to try again ----
    provider.queue({ status: 500 });
    await limits.getByRole('button', { name: 'Create a lesson with AI' }).click();
    const failure = limits.getByRole('alert');
    await expect(failure).toContainText('The lesson could not be made', { timeout: 30_000 });
    await expect(failure).toContainText('The AI provider reported a problem on its side.');
    await expect(limits).toContainText('No lesson has been made for this concept yet.');
    await expectNoAccessibilityViolations(page);
    await screenshot(page, 'generation-failed-dark');
    // A failed request is not repeated by itself.
    expect(provider.requests).toHaveLength(1);

    await failure.getByRole('button', { name: 'Try again' }).click();
    await expect(page.getByRole('status').filter({ hasText: 'Lesson ready' })).toBeVisible({
      timeout: 60_000,
    });
    await expect(limits.getByRole('alert')).toHaveCount(0);
    expect(provider.requests).toHaveLength(4);

    // ---- Four requests in a minute is the limit Adle keeps: the fifth waits, and says so ----
    await limits.getByRole('button', { name: 'Create another lesson with AI' }).click();
    await expect(
      limits.getByText(/Waiting about \d+ seconds to stay within the provider's rate limit/),
    ).toBeVisible({ timeout: 15_000 });
    expect(provider.requests).toHaveLength(4);

    // ---- Cancelling while it waits sends nothing and leaves nothing behind ----
    await limits.getByRole('button', { name: 'Cancel' }).click();
    await expect(limits.getByText('Cancelled')).toBeVisible({ timeout: 30_000 });
    await expect(limits).toContainText('Nothing was added.');
    await expect(
      limits.getByRole('list', { name: 'Lessons for this concept' }).getByRole('listitem'),
    ).toHaveCount(1);
    await limits.getByRole('button', { name: 'Dismiss' }).click();
    await expect(limits.getByText('Cancelled')).toHaveCount(0);
    expect(provider.requests).toHaveLength(4);

    expect(session.adle.problems).toEqual([]);
    await close(session);
  });

  test('suggestions that arrive while the learner is elsewhere wait to be reviewed', async ({
    profileDir,
  }) => {
    test.setTimeout(120_000);
    const session = await open(profileDir);
    const { page, provider } = session;
    await createCourse(page, 'Calculus refresher', { topic: 'Limits.' });

    provider.queue(HANG);
    await page.getByRole('button', { name: 'Suggest concepts with AI' }).click();
    await page.getByRole('button', { name: 'Send and suggest' }).click();
    await expect(page.getByRole('progressbar')).toBeVisible();
    await expect.poll(() => provider.requests.length).toBe(1);
    // Asking again while it runs is not possible, so the same work cannot be started twice.
    await expect(
      page.getByRole('button', { name: 'Suggest concepts with AI' }).first(),
    ).toBeDisabled();

    // The learner leaves; the answer arrives while they are in the library.
    await page.getByRole('main').getByRole('button', { name: 'Library', exact: true }).click();
    provider.release();
    await page.waitForTimeout(1500);
    await courseCard(page, /Calculus refresher/).click();

    const ready = page.getByRole('status').filter({ hasText: 'Suggestions are ready' });
    await expect(ready).toBeVisible({ timeout: 30_000 });
    await expect(ready).toContainText('suggested 3 concepts for this course');
    await expect(page.getByRole('heading', { name: 'No concepts yet' })).toBeVisible();
    await ready.getByRole('button', { name: 'Review suggestions' }).click();

    const review = page.getByRole('dialog', { name: 'Suggested concepts' });
    await review.getByRole('button', { name: 'Decide later' }).click();
    await expect(ready).toBeVisible();

    await ready.getByRole('button', { name: 'Review suggestions' }).click();
    await review.getByRole('button', { name: 'Discard suggestions' }).click();
    await expect(page.getByText('Suggestions are ready')).toHaveCount(0);
    await expect(page.getByRole('heading', { name: 'No concepts yet' })).toBeVisible();
    expect(provider.requests).toHaveLength(1);

    expect(session.adle.problems).toEqual([]);
    await close(session);
  });
});
