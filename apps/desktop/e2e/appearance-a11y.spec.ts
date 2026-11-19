import { mkdirSync } from 'node:fs';
import path from 'node:path';

import AxeBuilder from '@axe-core/playwright';
import type { Page } from '@playwright/test';

import { desktopDir, expect, launchApp, test } from './support/app';

const SCREENSHOT_DIR = path.join(desktopDir, 'test-results', 'screens');

/** Run axe against the page. The isolated player frame is a canvas with its own text equivalent. */
async function expectNoAxeViolations(page: Page, context: string): Promise<void> {
  const results = await new AxeBuilder({ page })
    // Electron cannot open the extra page axe uses for cross-frame collection.
    .setLegacyMode(true)
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'])
    .exclude('iframe')
    .analyze();
  const summary = results.violations.map(
    (violation) => `${violation.id}: ${violation.help} (${violation.nodes.length} node(s))`,
  );
  expect(summary, `axe violations on ${context}`).toEqual([]);
}

async function capture(page: Page, name: string): Promise<void> {
  mkdirSync(SCREENSHOT_DIR, { recursive: true });
  await page.waitForTimeout(250);
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, `${name}.png`) });
}

test.describe('theme', () => {
  test('changes immediately, applies to the whole app, and is remembered', async ({
    profileDir,
  }) => {
    const first = await launchApp(profileDir, { onboarded: true });
    const { page } = first;
    const prefersDark = (target: Page): Promise<boolean> =>
      target.evaluate(() => window.matchMedia('(prefers-color-scheme: dark)').matches);
    const canvasColour = (target: Page): Promise<string> =>
      target.evaluate(() => getComputedStyle(document.body).backgroundColor);

    await page.getByRole('button', { name: 'Settings' }).click();
    await page.getByRole('tab', { name: 'Appearance' }).click();

    await page.getByRole('radio', { name: 'Dark' }).click();
    await expect.poll(() => prefersDark(page)).toBe(true);
    await expect.poll(() => canvasColour(page)).toBe('rgb(16, 23, 19)');

    await page.getByRole('radio', { name: 'Light' }).click();
    await expect.poll(() => prefersDark(page)).toBe(false);
    await expect.poll(() => canvasColour(page)).toBe('rgb(246, 248, 244)');

    await page.getByRole('radio', { name: 'Dark' }).click();
    await expect.poll(() => prefersDark(page)).toBe(true);
    await first.close();

    const second = await launchApp(profileDir);
    expect(await prefersDark(second.page)).toBe(true);
    await second.page.getByRole('button', { name: 'Settings' }).click();
    await second.page.getByRole('tab', { name: 'Appearance' }).click();
    await expect(second.page.getByRole('radio', { name: 'Dark' })).toHaveAttribute(
      'aria-checked',
      'true',
    );
    await second.close();
  });
});

for (const theme of ['light', 'dark'] as const) {
  test.describe(`${theme} theme screens`, () => {
    test('every primary screen passes axe and is captured for review', async ({ profileDir }) => {
      const { page, problems, close } = await launchApp(profileDir, { theme });
      expect(
        await page.evaluate(() => window.matchMedia('(prefers-color-scheme: dark)').matches),
      ).toBe(theme === 'dark');

      await expectNoAxeViolations(page, 'welcome');
      await capture(page, `${theme}-welcome`);

      await page.getByRole('button', { name: 'Get started' }).click();
      await page.getByRole('heading', { name: 'Library', level: 1 }).waitFor();
      await expect(page.getByText('Local service ready')).toBeVisible({ timeout: 30_000 });
      await expectNoAxeViolations(page, 'library');
      await capture(page, `${theme}-library`);

      await page.getByRole('button', { name: 'Settings' }).click();
      for (const [tab, slug] of [
        ['AI provider', 'settings-ai'],
        ['Appearance', 'settings-appearance'],
        ['Privacy & data', 'settings-privacy'],
        ['About & diagnostics', 'settings-about'],
      ] as const) {
        await page.getByRole('tab', { name: tab }).click();
        await expect(page.getByRole('tabpanel')).toBeVisible();
        if (tab === 'AI provider')
          await expect(page.getByText('coding-kimi-k3-free')).toBeVisible();
        await expectNoAxeViolations(page, tab);
        await capture(page, `${theme}-${slug}`);
      }

      await page.getByRole('button', { name: 'Run check' }).click();
      await expect(page.getByText('Rendering works')).toBeVisible({ timeout: 20_000 });
      await expectNoAxeViolations(page, 'runtime check');
      await capture(page, `${theme}-settings-scene-check`);

      expect(problems).toEqual([]);
      await close();
    });
  });
}

test.describe('layout', () => {
  test('stays usable at the minimum window size and when text is enlarged', async ({
    profileDir,
  }) => {
    const { page, close } = await launchApp(profileDir, {
      onboarded: true,
      viewport: { width: 960, height: 640 },
    });
    const overflowsHorizontally = (): Promise<boolean> =>
      page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);

    // At the minimum width the rail collapses to icons but keeps accessible names.
    await expect(page.getByRole('button', { name: 'Settings' })).toBeVisible();
    expect(await overflowsHorizontally()).toBe(false);
    await capture(page, 'narrow-library');

    await page.getByRole('button', { name: 'Settings' }).click();
    await expect(page.getByRole('tab', { name: 'About & diagnostics' })).toBeAttached();
    expect(await overflowsHorizontally()).toBe(false);
    await capture(page, 'narrow-settings');

    // 200% text: content reflows instead of clipping or scrolling sideways.
    await page.evaluate(() => {
      document.documentElement.style.fontSize = '200%';
    });
    await page.setViewportSize({ width: 1280, height: 832 });
    await expect(page.getByLabel('API key', { exact: true })).toBeVisible();
    expect(await overflowsHorizontally()).toBe(false);
    await capture(page, 'large-text-settings');
    await close();
  });

  test('honours reduced motion', async ({ profileDir }) => {
    const { page, close } = await launchApp(profileDir, { onboarded: true });
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.getByRole('button', { name: 'Settings' }).click();
    await page.getByRole('tab', { name: 'Appearance' }).click();
    await expect(page.getByText(/Reduced motion is\s+on/)).toBeVisible();
    const duration = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue('--ad-duration-base').trim(),
    );
    // Chromium may serialise the value as ".01ms".
    expect(Number.parseFloat(duration)).toBe(0.01);
    await close();
  });
});
