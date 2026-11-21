import { mkdirSync } from 'node:fs';
import path from 'node:path';

import AxeBuilder from '@axe-core/playwright';
import type { Page } from '@playwright/test';

import { desktopDir, expect, expectReadyOnPage, launchApp, test } from './support/app';
import { pressableUnderTheStrip, providerKeyField, settled } from './support/courses';

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
  expect(await pressableUnderTheStrip(page), `under the window's strip on ${context}`).toEqual([]);
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
    await expect.poll(() => canvasColour(page)).toBe('rgb(10, 10, 10)');

    await page.getByRole('radio', { name: 'Light' }).click();
    await expect.poll(() => prefersDark(page)).toBe(false);
    await expect.poll(() => canvasColour(page)).toBe('rgb(243, 243, 243)');

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
      await expectReadyOnPage(page);
      await expectNoAxeViolations(page, 'library');
      await capture(page, `${theme}-library`);

      await page.getByRole('button', { name: 'Settings' }).click();
      for (const [tab, slug] of [
        ['AI provider', 'settings-ai'],
        ['Learning', 'settings-learning'],
        ['Appearance', 'settings-appearance'],
        ['Privacy & data', 'settings-privacy'],
        ['About', 'settings-about'],
      ] as const) {
        await page.getByRole('tab', { name: tab }).click();
        await expect(page.getByRole('tabpanel')).toBeVisible();
        if (tab === 'AI provider')
          await expect(page.getByText('coding-kimi-k3-free')).toBeVisible();
        if (tab === 'Learning') await expect(page.getByRole('switch').first()).toBeVisible();
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
    await expect(page.getByRole('tab', { name: 'About' })).toBeAttached();
    expect(await overflowsHorizontally()).toBe(false);
    await capture(page, 'narrow-settings');

    // 200% text: content reflows instead of clipping or scrolling sideways.
    await page.evaluate(() => {
      document.documentElement.style.fontSize = '200%';
    });
    await page.setViewportSize({ width: 1280, height: 832 });
    await expect(providerKeyField(page, 'AIHubMix')).toBeVisible();
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

test.describe('the window’s own title bar', () => {
  test('the page keeps a strip to move the window by, with nothing to press under it', async ({
    adle,
  }) => {
    const { page, app } = adle;
    const owns = process.platform === 'win32' || process.platform === 'darwin';

    const found = await page.evaluate(() => {
      const strip = [...document.querySelectorAll<HTMLElement>('body *')].find((element) => {
        const style = getComputedStyle(element) as CSSStyleDeclaration & { appRegion?: string };
        const region = style.appRegion ?? style.getPropertyValue('-webkit-app-region');
        return region === 'drag';
      });
      const box = strip?.getBoundingClientRect();
      const height = box?.height ?? 0;
      // Whatever can be pressed must start below the strip: under it, a press moves the window.
      const pressable = [...document.querySelectorAll<HTMLElement>('button, a[href], input')]
        .filter((element) => element.offsetParent !== null)
        .filter((element) => !element.matches('a[href="#ad-main"]'));
      const highest = Math.min(...pressable.map((element) => element.getBoundingClientRect().top));
      return {
        told: document.documentElement.dataset.adTitlebar ?? null,
        height,
        spansTheTop: box ? box.top === 0 && box.width > window.innerWidth / 2 : false,
        highest,
      };
    });

    if (!owns) {
      // The window keeps the frame it is given: there is no strip, and nothing moved down.
      expect(found.told).toBeNull();
      expect(found.height).toBe(0);
      return;
    }
    expect(found.told).toBe(process.platform);
    expect(found.height).toBeGreaterThanOrEqual(24);
    expect(found.spansTheTop).toBe(true);
    expect(found.highest).toBeGreaterThanOrEqual(found.height);

    // The window itself has no title bar: what it shows is all page, from its top edge.
    const sizes = await app.evaluate(({ BrowserWindow }) => {
      const window = BrowserWindow.getAllWindows()[0]!;
      return { outer: window.getBounds().height, inner: window.getContentBounds().height };
    });
    expect(sizes.outer - sizes.inner).toBeLessThan(16);
  });

  test('a dialog as tall as the window allows stays clear of the strip, and can be pressed', async ({
    profileDir,
  }) => {
    const { page, close } = await launchApp(profileDir, {
      onboarded: true,
      viewport: { width: 960, height: 640 },
    });
    const owns = process.platform === 'win32' || process.platform === 'darwin';
    await expectReadyOnPage(page);
    await page
      .getByRole('button', { name: /New course|Create your first course/ })
      .first()
      .click();
    const dialog = page.getByRole('dialog', { name: 'New course' });
    await expect(dialog).toBeVisible();
    // Large text makes the dialog as tall as it is ever allowed to be.
    await page.evaluate(() => {
      document.documentElement.style.fontSize = '200%';
    });
    await settled(page);

    const measured = await page.evaluate(() => {
      const strip = [...document.querySelectorAll<HTMLElement>('body *')].find((element) => {
        const style = getComputedStyle(element) as CSSStyleDeclaration & { appRegion?: string };
        return (style.appRegion ?? style.getPropertyValue('-webkit-app-region')) === 'drag';
      });
      const open = document.querySelector<HTMLElement>('dialog[open]');
      const box = open?.getBoundingClientRect();
      const style = open
        ? (getComputedStyle(open) as CSSStyleDeclaration & { appRegion?: string })
        : null;
      return {
        strip: strip?.getBoundingClientRect().height ?? 0,
        top: box?.top ?? -1,
        bottom: box?.bottom ?? -1,
        scrolls: open ? open.scrollHeight > open.clientHeight + 1 : false,
        region: style ? (style.appRegion ?? style.getPropertyValue('-webkit-app-region')) : '',
        height: window.innerHeight,
      };
    });
    // It really is at its limit here: taller than it may be, so it scrolls inside itself.
    expect(measured.scrolls).toBe(true);
    expect(measured.bottom).toBeLessThanOrEqual(measured.height);
    // Wherever a dialog lies, a press on it is a press on it.
    expect(measured.region).toBe('no-drag');
    if (owns) {
      expect(measured.strip).toBeGreaterThanOrEqual(24);
      expect(measured.top).toBeGreaterThanOrEqual(measured.strip);
    }
    expect(await pressableUnderTheStrip(page)).toEqual([]);

    // And it still works: Escape closes it, and focus goes back to what opened it.
    await page.keyboard.press('Escape');
    await expect(dialog).toBeHidden();
    await close();
  });
});
