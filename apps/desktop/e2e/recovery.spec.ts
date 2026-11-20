/**
 * When the app itself fails: its page crashes, and the learner looks for the log.
 *
 * The page is crashed for real, by Chromium's own means. The question the main process then
 * asks is put by the operating system, so here it is answered by a stand-in, as elsewhere.
 */
import { readFileSync } from 'node:fs';
import path from 'node:path';

import type { ElectronApplication } from '@playwright/test';

import { expect, test, waitForCore } from './support/app';
import { createCourse, expectNoAccessibilityViolations } from './support/courses';

/** Answer the next native question with this button, keeping what was asked. */
async function answerQuestions(app: ElectronApplication, button: number): Promise<void> {
  await app.evaluate(({ dialog }, response) => {
    const asked: unknown[] = [];
    (globalThis as Record<string, unknown>).adleQuestions = asked;
    dialog.showMessageBox = (...args: unknown[]) => {
      asked.push(args.at(-1));
      return Promise.resolve({ response, checkboxChecked: false });
    };
  }, button);
}

interface ReloadedPage {
  heading: string | null;
  text: string;
  core: { state: string };
}

/**
 * What the window shows now, read through the main process. Playwright's own handle on a
 * page does not survive that page's process crashing, even once the window has reloaded.
 */
async function reloadedPage(app: ElectronApplication): Promise<ReloadedPage | null> {
  return app.evaluate(async ({ BrowserWindow }) => {
    const contents = BrowserWindow.getAllWindows()[0]?.webContents;
    if (!contents || contents.isCrashed() || contents.isLoading()) return null;
    try {
      return (await contents.executeJavaScript(
        `(async () => ({
          heading: document.querySelector('h1')?.textContent ?? null,
          text: document.body.innerText,
          core: await window.adle.core.status(),
        }))()`,
      )) as ReloadedPage;
    } catch {
      return null;
    }
  });
}

const questions = (app: ElectronApplication) =>
  app.evaluate(
    () =>
      (globalThis as Record<string, unknown>).adleQuestions as {
        title: string;
        message: string;
        detail: string;
        buttons: string[];
      }[],
  );

test.describe('when the app itself fails', () => {
  test('a page that crashes is reloaded, and nothing the learner did is lost', async ({
    adle,
    profileDir,
  }) => {
    const { app, page } = adle;
    await waitForCore(page);
    await createCourse(page, 'Still here after a crash', { topic: 'Anything.' });
    await answerQuestions(app, 0);

    // ---- The page's process dies ----
    await app.evaluate(({ BrowserWindow }) => {
      BrowserWindow.getAllWindows()[0]?.webContents.forcefullyCrashRenderer();
    });

    // ---- The learner is told, in plain words, and chooses to reload ----
    await expect.poll(async () => (await questions(app)).length, { timeout: 15_000 }).toBe(1);
    const [asked] = await questions(app);
    expect(asked).toMatchObject({
      title: 'Adle stopped working',
      message: 'The window stopped working and has to be reloaded.',
      buttons: ['Reload', 'Quit Adle'],
    });
    expect(asked!.detail).toContain('Your answers and your progress were saved as you went');
    expect(asked!.detail).toContain('Nothing about this is sent anywhere.');

    // ---- The window comes back, on the library, with the course in it ----
    await expect
      .poll(async () => (await reloadedPage(app))?.heading, { timeout: 20_000 })
      .toBe('Library');
    await expect
      .poll(async () => (await reloadedPage(app))?.text ?? '', { timeout: 10_000 })
      .toContain('Still here after a crash');
    const after = await reloadedPage(app);
    expect(after?.text).toContain('Local service ready');
    // The core was never touched: it is the page that failed.
    expect(after?.core).toMatchObject({ state: 'ready' });
    // One crash, one question: the reload did not set off another.
    expect(await questions(app)).toHaveLength(1);

    // ---- What happened was noted on this computer, as an event and nothing more ----
    const log = readFileSync(path.join(profileDir, 'logs', 'app.log'), 'utf8');
    const events = log
      .trim()
      .split('\n')
      .map((line) => JSON.parse(line) as Record<string, unknown>);
    expect(events).toHaveLength(1);
    expect(events[0]).toMatchObject({ event: 'page-gone', reason: 'crashed' });
    expect(Object.keys(events[0]!).sort()).toEqual(['at', 'event', 'exitCode', 'reason']);
    expect(log).not.toContain('Still here after a crash');
  });

  test('the log files can be found from Settings, and are said to stay here', async ({
    adle,
    profileDir,
  }) => {
    const { app, page } = adle;
    await app.evaluate(({ shell }) => {
      const opened: string[] = [];
      (globalThis as Record<string, unknown>).adleOpened = opened;
      shell.openPath = (target: string) => {
        opened.push(target);
        return Promise.resolve('');
      };
    });

    await page.getByRole('navigation').getByRole('button', { name: 'Settings' }).click();
    await page.getByRole('tab', { name: 'About & diagnostics' }).click();
    const section = page.getByRole('tabpanel');
    await expect(
      section.getByRole('heading', { name: 'If something goes wrong', level: 2 }),
    ).toBeVisible();
    await expect(section).toContainText('It is never sent anywhere.');
    await expect(section).toContainText('never what you typed, opened, or answered');
    await section.getByRole('button', { name: 'Show log files' }).click();

    await expect
      .poll(() => app.evaluate(() => (globalThis as Record<string, unknown>).adleOpened))
      .toEqual([path.join(profileDir, 'logs')]);
    await expectNoAccessibilityViolations(page);
    expect(adle.problems).toEqual([]);
  });
});
