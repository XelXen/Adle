/**
 * Waiting for something to be written (ADR-026): the wait is said honestly, a break is
 * offered and belongs to the learner, what is being written is visible from anywhere, and
 * the learner is told when it is ready, by the app and by the computer.
 *
 * The provider is a server on this computer. No request leaves the machine, and no
 * notification is ever really shown: what the app would have shown is recorded.
 */
import type { Page } from '@playwright/test';

import { expect, launchApp, type LaunchedApp, test, waitForCore } from './support/app';
import {
  expectNoAccessibilityViolations,
  openCourseTab,
  saveProviderKey,
  screenshot,
  showNarrationAsText,
} from './support/courses';
import { type FakeProvider, HANG, startFakeProvider } from './support/fake-provider';

const KEY = 'sk-e2e-not-a-real-key-7Hq2mZx94Wd1';
const CONCEPT = 'Weights and bias';
const WRITTEN = 'How a neuron weighs its inputs';

const detail = (page: Page) => page.getByRole('region', { name: CONCEPT });
const now = (page: Page) => page.getByRole('navigation').getByRole('group', { name: 'Now' });
const timer = (page: Page) => page.getByRole('timer');
const meanwhile = (page: Page) => page.getByRole('region', { name: 'What Adle is writing' });

interface Session {
  adle: LaunchedApp;
  page: Page;
  provider: FakeProvider;
}

/** The app with a provider on this computer and the sample course open on its curriculum. */
async function withTheSampleCourse(
  profileDir: string,
  theme: 'light' | 'dark' = 'light',
): Promise<Session> {
  const provider = await startFakeProvider();
  const adle = await launchApp(profileDir, {
    onboarded: true,
    theme,
    env: { ADLE_PROVIDER_BASE_URL: provider.baseUrl },
  });
  const { page } = adle;
  await waitForCore(page);
  await showNarrationAsText(page);
  await page.getByRole('button', { name: 'Settings' }).click();
  await saveProviderKey(page, /Custom endpoint/, KEY);
  await page.getByRole('button', { name: 'Library', exact: true }).click();
  await page.getByRole('button', { name: 'Try the sample course' }).click();
  await openCourseTab(page, 'Curriculum');
  await expect(detail(page)).toBeVisible();
  return { adle, page, provider };
}

test.describe('waiting for something to be written', () => {
  test('take a break while a lesson is written, see it from anywhere, and be told when it is ready', async ({
    profileDir,
  }) => {
    test.setTimeout(240_000);
    const { adle, page, provider } = await withTheSampleCourse(profileDir);

    // ---- The wait is said honestly, with something better to do than watch it ----
    provider.queue(HANG);
    await detail(page).getByRole('button', { name: 'Create another lesson with AI' }).click();
    await expect(detail(page).getByRole('progressbar')).toBeVisible();
    await expect(detail(page)).toContainText(
      'This usually takes about 3 minutes. You do not have to wait here: Adle will tell you ' +
        'when it is ready.',
    );
    // What is being written is in the rail, one click from anywhere.
    await expect(now(page).getByRole('button', { name: 'Writing a lesson' })).toBeVisible();
    await expectNoAccessibilityViolations(page);
    await screenshot(page, 'writing-with-a-break-offered');

    // ---- A break sized to the wait: one clock, and what Adle is doing meanwhile ----
    await detail(page).getByRole('button', { name: 'Take a break' }).click();
    await expect(page.getByRole('heading', { name: 'Taking a break', level: 1 })).toBeVisible();
    await expect(timer(page)).toHaveAccessibleName(
      /^Time left: (3 minutes|2 minutes \d+ seconds?)$/,
    );
    await expect(meanwhile(page)).toContainText('A lesson is being written');
    await expect(meanwhile(page).getByRole('progressbar')).toBeVisible();
    // A lesson and a break each have the window: no rail here, and a way back.
    await expect(page.getByRole('navigation')).toHaveCount(0);
    await expectNoAccessibilityViolations(page);
    await screenshot(page, 'break');

    // ---- It is the learner's: longer, shorter, or left running in the background ----
    await page.getByRole('button', { name: 'A minute more' }).click();
    await expect(timer(page)).toHaveAccessibleName(
      /^Time left: (4 minutes|3 minutes \d+ seconds?)$/,
    );
    await page.getByRole('button', { name: 'A minute less' }).click();
    await expect(timer(page)).toHaveAccessibleName(
      /^Time left: (3 minutes|2 minutes \d+ seconds?)$/,
    );
    await page.getByRole('button', { name: 'Back', exact: true }).click();
    await expect(detail(page)).toBeVisible();
    await expect(now(page).getByRole('button', { name: /^On a break · \d:\d\d$/ })).toBeVisible();
    await expect(detail(page).getByRole('button', { name: 'Back to your break' })).toBeVisible();

    // ---- It is ready while the learner is elsewhere, in another window ----
    await page.getByRole('navigation').getByRole('button', { name: 'Settings' }).click();
    await adle.setFocused(false);
    provider.release();
    const told = page.getByRole('status').filter({ hasText: 'Your lesson is ready' });
    await expect(told).toBeVisible({ timeout: 60_000 });
    await expect(told).toContainText(WRITTEN);
    // The computer says so too. Its words are fixed: nothing of the lesson is in them.
    await expect
      .poll(() => adle.notices())
      .toEqual([{ title: 'Your lesson is ready', body: 'Adle has finished writing it.' }]);
    await adle.setFocused(true);
    await expect(now(page).getByRole('button', { name: 'Writing a lesson' })).toHaveCount(0);

    // ---- The break has it waiting, and opening it ends the break ----
    await now(page)
      .getByRole('button', { name: /^On a break/ })
      .click();
    await expect(meanwhile(page)).toContainText('Your lesson is ready');
    await expect(meanwhile(page)).toContainText(`"${WRITTEN}" is there whenever you want it.`);
    await screenshot(page, 'break-with-the-lesson-ready');
    await meanwhile(page).getByRole('button', { name: 'Open the lesson' }).click();
    await expect(page.getByRole('heading', { name: WRITTEN, level: 1 })).toBeVisible();
    await page.getByRole('button', { name: 'Back to the course' }).click();
    await expect(now(page)).toHaveCount(0);

    // What was sent: the lesson and its pictures, to the one provider, and nothing else.
    expect(provider.requests.map((request) => request.kind)).toEqual(['lesson', 'scene', 'scene']);
    expect(adle.problems).toEqual([]);
    await adle.close();
    await provider.close();
  });

  test('a break ends by itself, says so once, and asks for nothing', async ({ profileDir }) => {
    test.setTimeout(240_000);
    // In the dark theme, so that the break is checked for contrast there too.
    const { adle, page, provider } = await withTheSampleCourse(profileDir, 'dark');

    provider.queue(HANG);
    await detail(page).getByRole('button', { name: 'Create another lesson with AI' }).click();
    await detail(page).getByRole('button', { name: 'Take a break' }).click();
    await expectNoAccessibilityViolations(page);
    await screenshot(page, 'break-dark');
    await expect(page.getByRole('heading', { name: 'Taking a break', level: 1 })).toBeVisible();

    // ---- The time passes (here, all at once) ----
    await adle.setFocused(false);
    await page.clock.install();
    await page.clock.fastForward('04:00');
    await page.clock.resume();
    await expect(page.getByRole('heading', { name: 'Your break is over', level: 1 })).toBeVisible({
      timeout: 20_000,
    });
    await expect(timer(page)).toHaveAccessibleName('The break is over');
    await expect(page.getByText('Ready when you are. There is no hurry.')).toBeVisible();
    await expect
      .poll(() => adle.notices())
      .toEqual([{ title: 'Your break is over', body: 'Ready when you are.' }]);
    await adle.setFocused(true);
    await expectNoAccessibilityViolations(page);
    await screenshot(page, 'break-over');

    // ---- More rest is as welcome as going back ----
    await page.getByRole('button', { name: '5 more minutes' }).click();
    await expect(page.getByRole('heading', { name: 'Taking a break', level: 1 })).toBeVisible();
    await page.getByRole('button', { name: 'End the break' }).click();
    await expect(detail(page)).toBeVisible();
    await expect(now(page).getByRole('button', { name: /break/i })).toHaveCount(0);
    // It was said once, and ending a break early says nothing at all.
    expect(await adle.notices()).toHaveLength(1);

    // ---- The lesson that was being written can still be stopped ----
    await detail(page).getByRole('button', { name: 'Cancel' }).click();
    await expect(detail(page).getByText('Cancelled')).toBeVisible({ timeout: 30_000 });
    await expect(now(page)).toHaveCount(0);

    expect(adle.problems).toEqual([]);
    await adle.close();
    await provider.close();
  });

  test('notifications can be turned off, and then the computer says nothing', async ({
    profileDir,
  }) => {
    test.setTimeout(180_000);
    const { adle, page, provider } = await withTheSampleCourse(profileDir);

    await page.getByRole('navigation').getByRole('button', { name: 'Settings' }).click();
    await page.getByRole('tab', { name: 'Appearance' }).click();
    const toggle = page.getByRole('switch', { name: 'Tell me when something is ready' });
    await expect(toggle).toBeChecked();
    await expect(page.getByText('never with anything from your lessons in it')).toBeVisible();
    await expectNoAccessibilityViolations(page);
    await toggle.click();
    await expect(toggle).not.toBeChecked();

    await page
      .getByRole('navigation')
      .getByRole('button', { name: /Introduction to neural/ })
      .click();
    await openCourseTab(page, 'Curriculum');
    await adle.setFocused(false);
    await detail(page).getByRole('button', { name: 'Create another lesson with AI' }).click();
    // The app itself still says so, where the learner is looking.
    await expect(detail(page).getByText(WRITTEN).first()).toBeVisible({ timeout: 60_000 });
    expect(await adle.notices()).toEqual([]);

    // The page cannot ask for words of its own, or for a kind Adle does not have.
    const refused = await page.evaluate(async () => {
      const notify = window.adle!.app.notify as unknown as (...args: unknown[]) => Promise<unknown>;
      const outcome = async (...args: unknown[]): Promise<string> =>
        notify(...args).then(
          (shown) => String(shown),
          () => 'refused',
        );
      return {
        unknown: await outcome('you_have_won'),
        text: await outcome({ title: 'Anything', body: 'at all' }),
        extra: await outcome('lesson_ready', 'Some other title'),
      };
    });
    // Off is off, and a kind Adle has no words for is refused outright.
    expect(refused).toEqual({ unknown: 'refused', text: 'refused', extra: 'false' });
    expect(await adle.notices()).toEqual([]);

    expect(adle.problems).toEqual([]);
    await adle.close();
    await provider.close();
  });
});
