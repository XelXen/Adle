import path from 'node:path';

import AxeBuilder from '@axe-core/playwright';
import type { ElectronApplication, Locator, Page } from '@playwright/test';

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

/**
 * Create a course from the library (ADR-053): from a topic, or from files, which are chosen
 * in the (replaced) file dialog as the course is made. "Set it up for me" is left off unless
 * `setUp` is given: a journey says when it wants the AI to build its course.
 */
export async function createCourse(
  page: Page,
  name: string,
  options: { topic?: string; files?: string[]; app?: ElectronApplication; setUp?: boolean } = {},
): Promise<void> {
  await page
    .getByRole('button', { name: /New course|Create your first course/ })
    .first()
    .click();
  const dialog = page.getByRole('dialog', { name: 'New course' });
  await expect(dialog).toBeVisible();
  const fromFiles = options.topic === undefined;
  if (!fromFiles) {
    await dialog.getByRole('radio', { name: 'From a topic' }).click();
    await dialog.getByLabel('What do you want to learn?').fill(options.topic ?? '');
  } else {
    if (!options.app || !options.files) {
      throw new Error('A course from files is made with its files: pass them and the app.');
    }
    await chooseInFileDialog(options.app, options.files.map(doc));
  }
  if (name) await dialog.getByLabel('Course name').fill(name);
  const setUp = dialog.getByRole('checkbox', { name: 'Set it up for me' });
  if ((await setUp.isChecked()) !== Boolean(options.setUp) && (await setUp.isEnabled())) {
    await setUp.setChecked(Boolean(options.setUp));
  }
  await dialog.getByRole('button', { name: fromFiles ? 'Choose files…' : 'Create course' }).click();
  if (name) await expect(page.getByRole('heading', { name, level: 1 })).toBeVisible();
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

/**
 * A course's card in the library. The rail lists courses too, by the same name, so a
 * course is always asked for where it is meant: here, in the main region.
 */
export const courseCard = (page: Page, name: string | RegExp) =>
  page.getByRole('main').getByRole('button', { name });

/** The card of one provider in Settings → AI provider, by the name it is shown under. */
export const providerCard = (page: Page, name: string | RegExp) =>
  page
    .getByRole('list', { name: 'AI providers' })
    .getByRole('listitem')
    .filter({ has: page.getByRole('heading', { name, exact: typeof name === 'string' }) });

/** The field a provider's key is typed into: empty whether or not one is saved already. */
export const providerKeyField = (page: Page, name: string | RegExp) =>
  providerCard(page, name).getByRole('textbox', { name: /API key$|^Replace the .* key$/ });

/**
 * Save a key for one provider, on Settings → AI provider, and wait until it says so.
 * `name` is the provider as it is shown ("AIHubMix"); the key's last four characters
 * are what the card shows afterwards.
 */
export async function saveProviderKey(
  page: Page,
  name: string | RegExp,
  key: string,
): Promise<void> {
  await providerKeyField(page, name).fill(key);
  await providerCard(page, name).getByRole('button', { name: 'Save key' }).click();
  await expect(providerCard(page, name)).toContainText(`Key saved · ends in ${key.slice(-4)}`);
}

/** Open one of a course's tabs. A course with concepts opens on "Learn". */
export async function openCourseTab(
  page: Page,
  name: 'Learn' | 'Curriculum' | 'Materials',
): Promise<void> {
  const tab = page.getByRole('tab', { name, exact: true });
  await tab.click();
  await expect(tab).toHaveAttribute('aria-selected', 'true');
}

/**
 * Wait until nothing on the page is still moving into place.
 *
 * A panel that is fading in, or a line of text changing colour, is measured by axe as
 * the colour it has at that instant, which is a colour nobody is meant to read. Motion
 * that never ends (a spinner, a bar that slides for as long as work goes on) is left
 * alone: it is not on its way to anything.
 */
export async function settled(page: Page): Promise<void> {
  await page.evaluate(async () => {
    const finite = document
      .getAnimations()
      .filter((animation) => animation.effect?.getComputedTiming().iterations !== Infinity);
    await Promise.race([
      Promise.allSettled(finite.map((animation) => animation.finished)),
      new Promise((resolve) => setTimeout(resolve, 1500)),
    ]);
  });
}

/**
 * Open the note beside a control that sends something to an AI provider, and hand the
 * note back (ADR-036). What is sent and where it goes is one press away and not on the
 * page: a journey that checks what a learner can read before anything is sent opens it
 * as a learner would. `within` narrows it to one part of the page, where a page has
 * more than one such control.
 */
export async function openWhatIsSent(page: Page, within: Locator | Page = page): Promise<Locator> {
  await within.getByRole('button', { name: 'What is sent' }).click();
  const note = page.locator('[popover]').filter({ visible: true });
  await expect(note).toHaveCount(1);
  return note;
}

/** Put that note away again, with the button that opened it. */
export async function closeWhatIsSent(page: Page, within: Locator | Page = page): Promise<void> {
  await within.getByRole('button', { name: 'What is sent' }).click();
  await expect(page.locator('[popover]').filter({ visible: true })).toHaveCount(0);
}

/**
 * What can be pressed but lies where a press moves the window instead (ADR-030).
 *
 * Along its top the window is held to be moved (`WindowStrip`). The browser cuts every box
 * that says `no-drag` out of that region, so a control there is fine exactly when it, or
 * something around it, says so. Whether something is really drawn at a point is asked of
 * the browser, so a control scrolled out of sight under the strip is not counted.
 *
 * A real press cannot be tried from here: a test's clicks do not pass through the frame of
 * the window. This checks where things lie.
 */
export async function pressableUnderTheStrip(page: Page): Promise<string[]> {
  return page.evaluate(() => {
    const regionOf = (element: Element): string => {
      const style = getComputedStyle(element) as CSSStyleDeclaration & { appRegion?: string };
      return style.appRegion ?? style.getPropertyValue('-webkit-app-region');
    };
    const held = [...document.querySelectorAll('body *')]
      .filter((element) => regionOf(element) === 'drag')
      .map((element) => element.getBoundingClientRect())
      .filter((box) => box.width > 0 && box.height > 0);
    if (held.length === 0) return [];

    const spared = (element: Element): boolean => {
      for (let at: Element | null = element; at; at = at.parentElement) {
        if (regionOf(at) === 'no-drag') return true;
      }
      return false;
    };
    const found: string[] = [];
    const pressable = document.querySelectorAll<HTMLElement>(
      'button, a[href], input, select, textarea, summary, [role="button"], [role="tab"], ' +
        '[role="slider"], [role="switch"], [role="radio"], [role="checkbox"]',
    );
    for (const element of pressable) {
      const box = element.getBoundingClientRect();
      for (const strip of held) {
        const left = Math.max(box.left, strip.left);
        const right = Math.min(box.right, strip.right);
        const top = Math.max(box.top, strip.top);
        const bottom = Math.min(box.bottom, strip.bottom);
        if (right - left < 1 || bottom - top < 1) continue;
        // Is it drawn there at all, in front of the strip or behind it?
        const drawn = document
          .elementsFromPoint((left + right) / 2, (top + bottom) / 2)
          .some((at) => at === element || element.contains(at));
        if (!drawn || spared(element)) continue;
        const name = element.getAttribute('aria-label') ?? element.textContent ?? '';
        found.push(`${element.tagName.toLowerCase()} "${name.trim().slice(0, 40)}"`);
      }
    }
    return found;
  });
}

/**
 * Fail on any WCAG 2.2 AA violation axe can detect on the current screen, and on anything
 * that can be pressed but lies where a press would move the window.
 */
export async function expectNoAccessibilityViolations(page: Page): Promise<void> {
  await settled(page);
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
  expect(await pressableUnderTheStrip(page), 'under the strip the window is moved by').toEqual([]);
}

/** Save a screenshot of the window for visual review (not compared against a baseline). */
export async function screenshot(page: Page, name: string): Promise<void> {
  await settled(page);
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
