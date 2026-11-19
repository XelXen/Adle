import path from 'node:path';

import AxeBuilder from '@axe-core/playwright';
import type { ElectronApplication, Page } from '@playwright/test';

import { desktopDir, expect, repoRoot } from './app';

const DOCUMENTS = path.join(repoRoot, 'fixtures', 'sample-documents');

/** The absolute path of a sample document. */
export const doc = (name: string): string => path.join(DOCUMENTS, name);

/** Make the native file dialog return these paths, as if the learner had picked them. */
export async function chooseInFileDialog(
  app: ElectronApplication,
  paths: string[] | null,
): Promise<void> {
  await app.evaluate(({ dialog }, chosen) => {
    dialog.showOpenDialog = () =>
      Promise.resolve(
        chosen === null
          ? { canceled: true, filePaths: [] }
          : { canceled: false, filePaths: chosen },
      );
  }, paths);
}

/** Create a course from the library. Without a topic it is a course "from your materials". */
export async function createCourse(
  page: Page,
  name: string,
  options: { topic?: string } = {},
): Promise<void> {
  await page
    .getByRole('button', { name: /New course|Create your first course/ })
    .first()
    .click();
  const dialog = page.getByRole('dialog', { name: 'New course' });
  await expect(dialog).toBeVisible();
  if (options.topic === undefined) {
    await dialog.getByRole('radio', { name: 'Import my materials' }).click();
  }
  await dialog.getByLabel('Course name').fill(name);
  if (options.topic !== undefined) {
    await dialog.getByLabel('What do you want to learn?').fill(options.topic);
  }
  await dialog.getByRole('button', { name: 'Create course' }).click();
  await expect(page.getByRole('heading', { name, level: 1 })).toBeVisible();
}

/** Import sample documents through the (replaced) file dialog. Call on the Materials tab. */
export async function importWithDialog(
  app: ElectronApplication,
  page: Page,
  names: string[],
): Promise<void> {
  await chooseInFileDialog(app, names.map(doc));
  await page.getByRole('button', { name: 'Choose files' }).click();
}

/** Import documents and wait until the summary says they are in. */
export async function importAndWait(
  app: ElectronApplication,
  page: Page,
  names: string[],
): Promise<void> {
  await importWithDialog(app, page, names);
  await expect(page.getByRole('status').filter({ hasText: 'imported' })).toContainText(
    `${names.length} file${names.length === 1 ? '' : 's'} imported`,
    { timeout: 30_000 },
  );
}

/** Fail on any WCAG 2.2 AA violation axe can detect on the current screen. */
export async function expectNoAccessibilityViolations(page: Page): Promise<void> {
  const axe = await new AxeBuilder({ page })
    .setLegacyMode(true)
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'])
    .analyze();
  expect(
    axe.violations.map((violation) => ({
      id: violation.id,
      nodes: violation.nodes.map((node) => node.target.join(' ')),
    })),
  ).toEqual([]);
}

/** Save a screenshot of the window for visual review (not compared against a baseline). */
export async function screenshot(page: Page, name: string): Promise<void> {
  await page.screenshot({
    path: path.join(desktopDir, 'test-results', 'screens', `${name}.png`),
    fullPage: false,
  });
}

/**
 * Have lessons show their narration as text instead of reading it aloud.
 *
 * Narration is on by default and the test machine may well have a voice, so a
 * journey that is not about speech turns it off first: the lesson then keeps
 * time by reading pace, the same on every machine, and nothing is played
 * through the speakers. `narration.spec.ts` covers reading aloud.
 */
export async function showNarrationAsText(page: Page): Promise<void> {
  const saved = await page.evaluate(() =>
    window.adle!.core.invoke('learner.update_preferences', { body: { narration: false } }),
  );
  expect(saved).toMatchObject({ ok: true, data: { narration: false } });
}
