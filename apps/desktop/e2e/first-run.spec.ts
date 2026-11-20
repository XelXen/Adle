import { expect, launchApp, test, waitForCore } from './support/app';

test.describe('first launch without an AI key', () => {
  test('explains what stays local, then opens the library and remembers it', async ({
    profileDir,
  }) => {
    const first = await launchApp(profileDir);
    const { page } = first;

    // The product name decides the window title and the default profile folder.
    expect(await first.app.evaluate(({ app }) => app.getName())).toBe('Adle');
    await expect(page).toHaveTitle('Adle');

    await expect(page.getByRole('heading', { level: 1 })).toHaveText(
      'Learn at your own pace. Understand for real.',
    );
    // The external data path is disclosed before any AI operation is possible.
    await expect(page.getByText('Your learning stays on this computer')).toBeVisible();
    // Both providers are named, and that text only goes to one the learner gave a key to.
    await expect(
      page.getByText(
        /sends the relevant text to an AI provider you have\s+given a key to \(AIHubMix or NVIDIA NIM\), and says which before it does/,
      ),
    ).toBeVisible();
    // No main navigation until the learner has seen the welcome.
    await expect(page.getByRole('navigation', { name: 'Primary' })).toHaveCount(0);

    await page.getByRole('button', { name: 'Get started' }).click();
    await expect(page.getByRole('heading', { name: 'Library', level: 1 })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'No courses yet' })).toBeVisible();

    // The app is usable without a key: the core starts and reports no key configured.
    await waitForCore(page);
    await expect(page.getByText('Local service ready')).toBeVisible();
    await expect(page.getByText('Not set up')).toBeVisible();
    expect(first.problems).toEqual([]);
    await first.close();

    // Second launch: straight to the library, no welcome.
    const second = await launchApp(profileDir);
    await expect(second.page.getByRole('heading', { name: 'Library', level: 1 })).toBeVisible();
    await expect(second.page.getByRole('button', { name: 'Get started' })).toHaveCount(0);
    await second.close();
  });

  test('"Set up AI first" leads to the provider settings', async ({ profileDir }) => {
    const { page, close } = await launchApp(profileDir);
    await page.getByRole('button', { name: 'Set up AI first' }).click();
    await expect(page.getByRole('heading', { name: 'Settings', level: 1 })).toBeVisible();
    await expect(page.getByRole('tab', { name: 'AI provider' })).toHaveAttribute(
      'aria-selected',
      'true',
    );
    await close();
  });

  test('can be completed with the keyboard alone', async ({ profileDir }) => {
    const { page, close } = await launchApp(profileDir);
    await page.keyboard.press('Tab');
    await expect(page.getByRole('button', { name: 'Get started' })).toBeFocused();
    await page.keyboard.press('Enter');
    await expect(page.getByRole('heading', { name: 'Library', level: 1 })).toBeVisible();

    // Skip link first, then the navigation rail.
    await page.keyboard.press('Tab');
    await expect(page.getByRole('link', { name: 'Skip to content' })).toBeFocused();
    await page.keyboard.press('Tab');
    await expect(page.getByRole('button', { name: 'Library', exact: true })).toBeFocused();
    await page.keyboard.press('Tab');
    await page.keyboard.press('Enter');
    await expect(page.getByRole('heading', { name: 'Settings', level: 1 })).toBeVisible();
    await close();
  });
});
