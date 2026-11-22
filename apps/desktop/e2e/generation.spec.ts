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
  openWhatIsSent,
  closeWhatIsSent,
} from './support/courses';
import {
  BROKEN_SCENE,
  cannedAnswer,
  type FakeProvider,
  HANG,
  startFakeProvider,
} from './support/fake-provider';

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
    await expect(page.getByRole('group', { name: 'Provider' })).toHaveCount(0);
    await expect(page.getByText('0 of 90', { exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Library', exact: true }).click();

    await createCourse(page, 'Calculus refresher', { topic: 'Limits and derivatives.' });

    // ---- Suggestions: what will be sent is one press away, before anything is sent ----
    const sent = await openWhatIsSent(page);
    await expect(sent).toContainText('the course name, topic, and description');
    await expect(sent).toContainText('Custom endpoint (127.0.0.1)');
    await expect(sent).toContainText('Nothing is added until you review the suggestions');
    await closeWhatIsSent(page);
    expect(provider.requests).toHaveLength(0);
    // Asked for at once: there is nothing to confirm about something that is reviewed
    // before any of it is kept.
    await page.getByRole('button', { name: 'Suggest concepts with AI' }).click();

    // ---- The suggestions open for review; nothing is in the course yet ----
    const review = page.getByRole('dialog', { name: 'Suggested concepts' });
    await expect(review).toBeVisible({ timeout: 30_000 });
    await expect(review).toContainText('from your course details only');
    await expect(review.getByRole('checkbox')).toHaveCount(3);
    await expect(review.getByRole('checkbox', { name: 'Limits' })).toBeChecked();
    await expect(review).toContainText(
      'Prerequisites: Limits (The derivative is defined as a limit.)',
    );
    await expectNoAccessibilityViolations(page);
    await screenshot(page, 'generation-proposal');

    // Dropping a suggestion that another builds on is said, not silently repaired.
    await review.getByRole('checkbox', { name: 'The derivative as a limit' }).uncheck();
    await expect(
      review.getByText('Builds on a suggestion you didn’t keep, so that link won’t be added.'),
    ).toBeVisible();
    await review.getByRole('button', { name: 'Add 2 concepts' }).click();

    await expect(pathList(page).getByRole('listitem')).toHaveCount(2);
    await expect(page.getByRole('status').filter({ hasText: '2 concepts added' })).toBeVisible();
    await expect(pathList(page).getByRole('listitem').nth(1)).toContainText('Needs Limits');
    await expect(detail(page, 'Limits')).toContainText('Suggested by AI.');
    await expect(page.getByText('Suggestions are ready')).toHaveCount(0);

    expect(provider.requests.map((request) => request.kind)).toEqual(['curriculum']);
    expect(provider.requests[0]?.authorization).toBe(`Bearer ${KEY}`);
    expect(provider.requests[0]?.prompt).toContain('Calculus refresher');
    expect(provider.requests[0]?.prompt).not.toContain(KEY);

    // ---- A lesson: what is sent is beside the button; progress can be watched ----
    const limits = detail(page, 'Limits');
    await expect(limits).toContainText('No lessons yet.');
    const lessonNote = await openWhatIsSent(page, limits);
    await expect(lessonNote).toContainText(
      'Sends the course name, this concept and its objectives, and your level, ' +
        'preferences, and goal to Custom endpoint (127.0.0.1).',
    );
    await closeWhatIsSent(page, limits);
    expect(provider.requests).toHaveLength(1);
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
    await page.getByRole('button', { name: 'About this lesson' }).click();
    await expect(page.getByText('From general knowledge')).toBeVisible();
    await page.getByRole('button', { name: 'About this lesson' }).click();
    await expect(page.getByText('From general knowledge')).toBeHidden();
    await expect(page.getByText('Part 1 of 8')).toBeVisible();
    const next = page.getByRole('button', { name: 'Continue', exact: true });
    await next.click();
    const picture = page.getByRole('figure', { name: 'The weighted sum' });
    await expect(picture.getByText('Loading animation…')).toBeHidden({ timeout: 30_000 });
    await expect(picture.getByText('Couldn’t show the animation')).toHaveCount(0);
    await next.click();
    await page.getByRole('radio', { name: 'The first input' }).check();
    await page.getByRole('button', { name: 'Check answer' }).click();
    await expect(page.getByText('Correct', { exact: true })).toBeVisible();

    // ---- The local count of what was sent ----
    // A lesson has the whole window; the way to the rest of the app is back through the course.
    await page.getByRole('button', { name: 'Back to course' }).click();
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
    await expect(page.getByRole('heading', { name: 'Continue learning' })).toBeVisible();
    const pickUp = page.getByRole('region', {
      name: 'Continue “How a neuron weighs its inputs”',
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
    await expect(removal).toContainText('Your progress on the concept stays');
    await removal.getByRole('button', { name: 'Cancel' }).click();
    await expect(lessons.getByRole('listitem')).toHaveCount(1);
    await limits
      .getByRole('button', { name: 'Remove lesson: How a neuron weighs its inputs' })
      .click();
    await removal.getByRole('button', { name: 'Remove lesson' }).click();
    await expect(page.getByRole('status').filter({ hasText: 'Lesson removed' })).toBeVisible();
    await expect(limits).toContainText('No lessons yet.');

    expect(session.adle.problems).toEqual([]);
    await close(session);
  });

  test('while a lesson is written it is seen taking shape, part by part, and never its words', async ({
    profileDir,
  }) => {
    test.setTimeout(180_000);
    const session = await open(profileDir);
    const { page, provider } = session;
    await createCourse(page, 'Calculus refresher', { topic: 'Limits.' });
    await addConcept(page, 'Limits');
    const limits = detail(page, 'Limits');

    // The model thinks for a while, and then writes the lesson a part at a time.
    provider.queue({ slowly: true, thinkMs: 2_500, pieceMs: 900 });
    await limits.getByRole('button', { name: 'Create a lesson with AI' }).click();

    // ---- Thinking: said in the learner's terms, with a clock that moves ----
    const bar = limits.getByRole('progressbar');
    await expect(bar).toHaveAccessibleName('Planning the lesson');
    // Nothing can be counted yet, so the bar has no measure, rather than standing empty.
    await expect(bar).not.toHaveAttribute('aria-valuenow');
    const clock = limits.locator('[aria-hidden="true"]', { hasText: /^\d+:\d\d$/ });
    const first = await clock.textContent();
    await expect(clock).not.toHaveText(first ?? '', { timeout: 5_000 });

    // ---- Writing: the lesson by its title, and its parts as each one is begun ----
    await expect(bar).toHaveAccessibleName('Writing “How a neuron weighs its inputs”');
    const parts = limits.getByRole('list', { name: 'Parts so far' });
    await expect(parts.getByRole('listitem')).toHaveCount(2, { timeout: 15_000 });
    await expect(parts.getByRole('listitem').nth(0)).toHaveText('Why inputs are weighted');
    await expect(parts.getByRole('listitem').nth(1)).toHaveText('The weighted sum');
    // The part being written is the last, and it is said to be the present one.
    await expect(parts.getByRole('listitem').nth(1)).toHaveAttribute('aria-current', 'step');
    await expect(bar).toHaveAttribute('aria-valuetext', /^\d+ parts? so far$/);
    // Titles, and nothing of what the parts say.
    await expect(limits).not.toContainText('has to turn them into one');
    await expect(limits).not.toContainText('its own weight');
    await expectNoAccessibilityViolations(page);
    await screenshot(page, 'writing-a-lesson-part-by-part');
    await expect(parts.getByRole('listitem')).toHaveCount(5, { timeout: 15_000 });
    const moved = Number(await bar.getAttribute('aria-valuenow'));
    expect(moved).toBeGreaterThan(30);
    expect(moved).toBeLessThan(100);

    // ---- And then it is a lesson ----
    await expect(page.getByRole('status').filter({ hasText: 'Lesson ready' })).toBeVisible({
      timeout: 60_000,
    });
    await expect(parts).toHaveCount(0);
    expect(session.adle.problems).toEqual([]);
    await close(session);
  });

  test('each picture is tried before it is shown, and one that breaks is written again, told why', async ({
    profileDir,
  }) => {
    test.setTimeout(180_000);
    const session = await open(profileDir);
    const { page, provider } = session;
    await createCourse(page, 'Calculus refresher', { topic: 'Limits.' });
    await addConcept(page, 'Limits');
    const limits = detail(page, 'Limits');
    const lessons = limits.getByRole('list', { name: 'Lessons for this concept' });

    // The first picture passes every rule, and breaks halfway through when it runs.
    provider.queue(cannedAnswer('lesson'), BROKEN_SCENE);
    await limits.getByRole('button', { name: 'Create a lesson with AI' }).click();
    await expect(page.getByRole('status').filter({ hasText: 'Lesson ready' })).toBeVisible({
      timeout: 60_000,
    });
    // It was tried, failed, and written once more; then the second picture.
    await expect
      .poll(() => provider.requests.map((request) => request.kind), { timeout: 60_000 })
      .toEqual(['lesson', 'scene', 'scene', 'scene']);
    const again = provider.requests[2]!.prompt;
    expect(again).toContain('was run in the player and failed');
    expect(again).toContain('this picture breaks halfway');
    expect(again).toContain('class Broken(Scene):');
    await expect(limits.getByRole('progressbar')).toHaveCount(0, { timeout: 60_000 });
    // Every picture was made in the end, so there is nothing to say about them.
    await expect(page.getByRole('status').filter({ hasText: 'About its pictures' })).toHaveCount(0);

    // ---- In the lesson, the picture is the one that ran ----
    await lessons.getByRole('button', { name: /^Start lesson/ }).click();
    await expect(page.getByText('Part 1 of 8')).toBeVisible();
    await page.getByRole('button', { name: 'Continue', exact: true }).click();
    const first = page.getByRole('figure', { name: 'The weighted sum' });
    await expect(first).toBeVisible();
    await expect(first.getByText('Loading animation…')).toBeHidden({ timeout: 30_000 });
    await expect(first.getByText('Couldn’t show the animation')).toHaveCount(0);
    await close(session);
  });

  test('a picture that breaks twice is said in words, and the learner is told', async ({
    profileDir,
  }) => {
    test.setTimeout(180_000);
    const session = await open(profileDir);
    const { page, provider } = session;
    await createCourse(page, 'Calculus refresher', { topic: 'Limits.' });
    await addConcept(page, 'Limits');
    const limits = detail(page, 'Limits');

    provider.queue(cannedAnswer('lesson'), BROKEN_SCENE, BROKEN_SCENE);
    await limits.getByRole('button', { name: 'Create a lesson with AI' }).click();
    await expect(page.getByRole('status').filter({ hasText: 'Lesson ready' })).toBeVisible({
      timeout: 60_000,
    });
    const about = page.getByRole('status').filter({ hasText: 'About its pictures' });
    await expect(about).toBeVisible({ timeout: 60_000 });
    await expect(about).toContainText(
      'The picture for “The weighted sum” couldn’t be made, so that part is explained in words.',
    );
    // Two tries at the first picture and no more, then the second picture.
    expect(provider.requests.map((request) => request.kind)).toEqual([
      'lesson',
      'scene',
      'scene',
      'scene',
    ]);
    await close(session);
  });

  test('a lesson can be started as soon as it is written, while its pictures are drawn', async ({
    profileDir,
  }) => {
    test.setTimeout(180_000);
    const session = await open(profileDir);
    const { page, provider } = session;
    await createCourse(page, 'Calculus refresher', { topic: 'Limits.' });
    await addConcept(page, 'Limits');
    const limits = detail(page, 'Limits');
    const lessons = limits.getByRole('list', { name: 'Lessons for this concept' });
    const now = page.getByRole('navigation').getByRole('group', { name: 'Now' });

    // What is said beside the button is the wait until the lesson can be started.
    const wait = await openWhatIsSent(page, limits);
    await expect(wait).toContainText(
      'Usually takes about a minute. Its pictures follow while you start.',
    );
    await closeWhatIsSent(page, limits);

    // ---- The pictures take their time: each one waits until this test lets it go ----
    provider.hold('scene');
    await limits.getByRole('button', { name: 'Create a lesson with AI' }).click();

    // ---- Said once, as soon as the lesson is written ----
    const ready = page.getByRole('status').filter({ hasText: 'Lesson ready' });
    await expect(ready).toBeVisible({ timeout: 60_000 });
    await expect(ready).toContainText(
      'How a neuron weighs its inputs. Its pictures are still being drawn.',
    );
    await expect
      .poll(() => provider.requests.map((request) => request.kind))
      .toEqual(['lesson', 'scene']);

    // It is in the list and can be started; the rest of the work goes on beside it.
    await expect(lessons.getByRole('listitem')).toHaveCount(1);
    await expect(lessons).toContainText('Not started · Pictures on their way');
    await expect(limits.getByRole('progressbar')).toBeVisible();
    await expect(limits).toContainText(
      'You can start the lesson now. Its pictures appear in it as they’re drawn.',
    );
    await expect(limits.getByRole('button', { name: 'Stop drawing pictures' })).toBeVisible();
    // There is nothing left to wait for, so no break is offered. And one lesson is written
    // at a time: another is not offered until this one has its pictures.
    await expect(limits.getByRole('button', { name: /break/i })).toHaveCount(0);
    await expect(limits.getByRole('button', { name: /lesson with AI/ })).toHaveCount(0);
    await expect(now.getByRole('button', { name: 'Drawing pictures' })).toBeVisible();
    await expectNoAccessibilityViolations(page);
    await screenshot(page, 'generation-lesson-before-its-pictures');

    // The Learn tab says the same, once, and offers the lesson.
    await openCourseTab(page, 'Learn');
    const learn = page.getByRole('tabpanel', { name: 'Learn' });
    await expect(learn).toContainText(
      'You can start the lesson now. Its pictures appear in it as they’re drawn.',
    );
    await expect(learn.getByRole('button', { name: 'Stop drawing pictures' })).toHaveCount(1);
    await expect(learn).toContainText('How a neuron weighs its inputs');
    await expectNoAccessibilityViolations(page);
    await openCourseTab(page, 'Curriculum');

    // ---- In the lesson: a part whose picture is not there yet is said in words ----
    await lessons.getByRole('button', { name: /^Start lesson/ }).click();
    await expect(
      page.getByRole('heading', { name: 'How a neuron weighs its inputs', level: 1 }),
    ).toBeVisible();
    // Who wrote it is said in the lesson, one press away.
    await page.getByRole('button', { name: 'About this lesson' }).click();
    await expect(
      page.getByText(
        'Written by Coding Kimi K3 (free) on Custom endpoint (127.0.0.1). AI can make mistakes.',
      ),
    ).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(page.getByText('Part 1 of 8')).toBeVisible();
    const next = page.getByRole('button', { name: 'Continue', exact: true });
    await next.click();
    await expect(page.getByText('Part 2 of 8')).toBeVisible();
    const first = page.getByRole('figure', { name: 'The weighted sum' });
    const drawing = page.getByText(
      'This picture is still being drawn. It’ll appear here when it’s ready.',
    );
    await expect(drawing).toBeVisible();
    await expect(first).toHaveCount(0);
    await expectNoAccessibilityViolations(page);
    await screenshot(page, 'lesson-picture-being-drawn');

    // ---- The first picture arrives. The part had not begun, so it takes its place ----
    provider.pass();
    await expect(first).toBeVisible({ timeout: 30_000 });
    await expect(first.getByText('Loading animation…')).toBeHidden({ timeout: 30_000 });
    await expect(first.getByText('Couldn’t show the animation')).toHaveCount(0);
    await expect(drawing).toHaveCount(0);
    await expect
      .poll(() => provider.requests.map((request) => request.kind))
      .toEqual(['lesson', 'scene', 'scene']);

    // ---- The second arrives while its part is being read: offered, not sprung ----
    await next.click();
    await page.getByRole('radio', { name: 'The first input' }).check();
    await page.getByRole('button', { name: 'Check answer' }).click();
    await expect(page.getByText('Correct', { exact: true })).toBeVisible();
    await next.click();
    await expect(page.getByText('Part 4 of 8')).toBeVisible();
    const second = page.getByRole('figure', { name: 'Change a weight' });
    await expect(drawing).toBeVisible();
    await expect(second).toHaveCount(0);
    // Nothing is asked to be tried on a picture that is not there.
    await expect(page.getByText('Try it', { exact: true })).toHaveCount(0);
    await page.getByRole('button', { name: 'Start', exact: true }).click();
    provider.release();
    const offered = page.getByRole('status').filter({ hasText: 'The picture is ready.' });
    await expect(offered).toBeVisible({ timeout: 30_000 });
    await expect(second).toHaveCount(0);
    await expectNoAccessibilityViolations(page);
    await offered.getByRole('button', { name: 'Show picture' }).click();
    await expect(second).toBeVisible();
    await expect(second.getByText('Loading animation…')).toBeHidden({ timeout: 30_000 });
    await expect(second.getByText('Couldn’t show the animation')).toHaveCount(0);
    await expect(page.getByText('Try it', { exact: true })).toBeVisible();

    // ---- Back in the course the work has ended, and nothing more is said about it ----
    await page.getByRole('button', { name: 'Back to course' }).click();
    await openCourseTab(page, 'Curriculum');
    await pathList(page)
      .getByRole('button', { name: /Limits/ })
      .first()
      .click();
    await expect(limits.getByRole('button', { name: 'Create another lesson with AI' })).toBeVisible(
      { timeout: 30_000 },
    );
    await expect(limits.getByRole('progressbar')).toHaveCount(0);
    await expect(lessons.getByRole('listitem')).toHaveCount(1);
    await expect(lessons).not.toContainText('Pictures on their way');
    await expect(now).toHaveCount(0);
    await expect(page.getByRole('status').filter({ hasText: 'Lesson ready' })).toHaveCount(0);
    // One request for the text and one for each picture: the same three as ever.
    expect(provider.requests.map((request) => request.kind)).toEqual(['lesson', 'scene', 'scene']);

    expect(session.adle.problems).toEqual([]);
    await close(session);
  });

  test('stopping the pictures keeps the lesson, and removing the lesson stops the pictures', async ({
    profileDir,
  }) => {
    test.setTimeout(180_000);
    const session = await open(profileDir, { theme: 'dark' });
    const { page, provider } = session;
    await createCourse(page, 'Calculus refresher', { topic: 'Limits.' });
    await addConcept(page, 'Limits');
    const limits = detail(page, 'Limits');
    const lessons = limits.getByRole('list', { name: 'Lessons for this concept' });
    const now = page.getByRole('navigation').getByRole('group', { name: 'Now' });
    const kinds = (): string[] => provider.requests.map((request) => request.kind);

    // ---- Stop: the lesson is there already, so it stays, with those parts in words ----
    provider.hold('scene');
    await limits.getByRole('button', { name: 'Create a lesson with AI' }).click();
    await expect(page.getByRole('status').filter({ hasText: 'Lesson ready' })).toBeVisible({
      timeout: 60_000,
    });
    await expect.poll(kinds).toEqual(['lesson', 'scene']);
    await expectNoAccessibilityViolations(page);
    await limits.getByRole('button', { name: 'Stop drawing pictures' }).click();
    const about = page.getByRole('status').filter({ hasText: 'About its pictures' });
    await expect(about).toBeVisible({ timeout: 30_000 });
    await expect(about).toContainText(
      'You stopped the pictures, so 2 parts are explained in words.',
    );
    await expect(limits.getByRole('progressbar')).toHaveCount(0);
    await expect(limits.getByText('Canceled')).toHaveCount(0);
    await expect(lessons.getByRole('listitem')).toHaveCount(1);
    await expect(lessons).not.toContainText('Pictures on their way');
    await expect(now).toHaveCount(0);
    // The picture that was being drawn was let go of, and no other was asked for.
    expect(kinds()).toEqual(['lesson', 'scene']);

    // It plays, with the parts that had a picture said in words.
    await lessons.getByRole('button', { name: /^Start lesson/ }).click();
    await expect(page.getByText('Part 1 of 8')).toBeVisible();
    await page.getByRole('button', { name: 'Continue', exact: true }).click();
    await expect(page.getByText('Part 2 of 8')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'The weighted sum', level: 2 })).toBeVisible();
    await expect(page.getByRole('figure')).toHaveCount(0);
    await expect(page.getByText(/still being drawn/)).toHaveCount(0);
    await page.getByRole('button', { name: 'Back to course' }).click();
    await openCourseTab(page, 'Curriculum');
    await pathList(page)
      .getByRole('button', { name: /Limits/ })
      .first()
      .click();

    // ---- Remove a lesson whose pictures are on their way: the work stops with it ----
    await limits.getByRole('button', { name: 'Create another lesson with AI' }).click();
    await expect(lessons.getByRole('listitem')).toHaveCount(2, { timeout: 60_000 });
    await expect.poll(kinds).toEqual(['lesson', 'scene', 'lesson', 'scene']);
    const unfinished = lessons.getByRole('listitem').filter({ hasText: 'Pictures on their way' });
    await expect(unfinished).toHaveCount(1);
    await unfinished.getByRole('button', { name: /^Remove lesson:/ }).click();
    await page
      .getByRole('dialog', { name: /^Remove “How a neuron weighs its inputs”/ })
      .getByRole('button', { name: 'Remove lesson' })
      .click();
    await expect(page.getByRole('status').filter({ hasText: 'Lesson removed' })).toBeVisible();
    await expect(lessons.getByRole('listitem')).toHaveCount(1);
    await expect(lessons).not.toContainText('Pictures on their way');
    // Nothing is left under way, nothing is called cancelled, and another can be asked for.
    await expect(limits.getByRole('progressbar')).toHaveCount(0);
    await expect(limits.getByText('Canceled')).toHaveCount(0);
    await expect(now).toHaveCount(0, { timeout: 15_000 });
    await expect(
      limits.getByRole('button', { name: 'Create another lesson with AI' }),
    ).toBeVisible();
    // No picture was asked for after the lesson had gone.
    provider.release();
    await page.waitForTimeout(1500);
    expect(kinds()).toEqual(['lesson', 'scene', 'lesson', 'scene']);

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
    await expect(refusal).toContainText('Couldn’t create the lesson');
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
    await expect(failure).toContainText('Couldn’t create the lesson', { timeout: 30_000 });
    // Whose words they are, the words themselves, and what they are about.
    await expect(failure).toContainText(
      'The AI provider returned an account notice instead of an answer.',
    );
    await expect(failure).toContainText(`It said: "${notice}"`);
    await expect(failure).toContainText('This is about your account with the provider, not Adle.');
    // The address in it is text. Nothing in a provider's words becomes something to press.
    await expect(failure.getByRole('link')).toHaveCount(0);
    await expect(limits).toContainText('No lessons yet.');
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
    await expect(failure).toContainText('Couldn’t create the lesson', { timeout: 30_000 });
    await expect(failure).toContainText('The AI provider had a problem on its side.');
    await expect(limits).toContainText('No lessons yet.');
    await expectNoAccessibilityViolations(page);
    await screenshot(page, 'generation-failed-dark');
    // A failed request is not repeated by itself.
    expect(provider.requests).toHaveLength(1);

    await failure.getByRole('button', { name: 'Try again' }).click();
    await expect(page.getByRole('status').filter({ hasText: 'Lesson ready' })).toBeVisible({
      timeout: 60_000,
    });
    await expect(limits.getByRole('alert')).toHaveCount(0);
    // The lesson is announced when it is written; its two pictures follow.
    const another = limits.getByRole('button', { name: 'Create another lesson with AI' });
    await expect(another).toBeVisible({ timeout: 60_000 });
    expect(provider.requests).toHaveLength(4);

    // ---- Four requests in a minute is the limit Adle keeps: the fifth waits, and says so ----
    await another.click();
    await expect(
      limits.getByText(/Waiting about \d+ seconds to stay under the rate limit/),
    ).toBeVisible({ timeout: 15_000 });
    expect(provider.requests).toHaveLength(4);

    // ---- Cancelling while it waits sends nothing and leaves nothing behind ----
    await limits.getByRole('button', { name: 'Cancel' }).click();
    await expect(limits.getByText('Canceled')).toBeVisible({ timeout: 30_000 });
    await expect(limits).toContainText('Nothing was added.');
    await expect(
      limits.getByRole('list', { name: 'Lessons for this concept' }).getByRole('listitem'),
    ).toHaveCount(1);
    await limits.getByRole('button', { name: 'Dismiss' }).click();
    await expect(limits.getByText('Canceled')).toHaveCount(0);
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
    await expect(ready).toContainText('suggested 3 concepts. Nothing is added until you choose.');
    await expect(page.getByRole('heading', { name: 'No concepts yet' })).toBeVisible();
    await ready.getByRole('button', { name: 'Review suggestions' }).click();

    const review = page.getByRole('dialog', { name: 'Suggested concepts' });
    await review.getByRole('button', { name: 'Decide later' }).click();
    await expect(ready).toBeVisible();

    await ready.getByRole('button', { name: 'Review suggestions' }).click();
    await review.getByRole('button', { name: 'Discard' }).click();
    await expect(page.getByText('Suggestions are ready')).toHaveCount(0);
    await expect(page.getByRole('heading', { name: 'No concepts yet' })).toBeVisible();
    expect(provider.requests).toHaveLength(1);

    expect(session.adle.problems).toEqual([]);
    await close(session);
  });
});
