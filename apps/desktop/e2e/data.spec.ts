/**
 * Saving a copy of everything, restoring from one, and deleting everything
 * (Settings → Privacy & data; ADR-016).
 *
 * These actions ask the learner three things: where to save, which file to restore, and
 * whether to delete. Each is asked by the operating system, in a window a test cannot
 * click and page script cannot answer. Here each is replaced, in the main process, by a
 * function that answers as a learner would.
 */
import { existsSync, mkdirSync, readdirSync, writeFileSync } from 'node:fs';
import path from 'node:path';

import type { ElectronApplication, Page } from '@playwright/test';

import { expect, filesContaining, launchApp, test, waitForCore } from './support/app';
import {
  chooseInFileDialog,
  createCourse,
  doc,
  expectNoAccessibilityViolations,
  importAndWait,
  screenshot,
} from './support/courses';

/** A recognisable fake key. It is never sent anywhere: these tests make no provider calls. */
const KEY = 'sk-e2e-not-a-real-key-5Tg8nBv31Kp7';
/** A phrase from `study-notes.txt`, to look for on disk. */
const PHRASE = 'ball rolling downhill';

/** Make the native save dialog answer with this path, or as if it had been cancelled. */
async function chooseInSaveDialog(app: ElectronApplication, filePath: string | null) {
  await app.evaluate(({ dialog }, chosen) => {
    dialog.showSaveDialog = () =>
      Promise.resolve(
        chosen === null ? { canceled: true, filePath: '' } : { canceled: false, filePath: chosen },
      );
  }, filePath);
}

/** Answer the native "are you sure?", keeping the question so the test can read it. */
async function answerConfirmation(app: ElectronApplication, answer: 'cancel' | 'delete') {
  await app.evaluate(
    ({ dialog }, response) => {
      dialog.showMessageBox = (...asked: unknown[]) => {
        (globalThis as Record<string, unknown>).adleAsked = asked.at(-1);
        return Promise.resolve({ response, checkboxChecked: false });
      };
    },
    answer === 'delete' ? 1 : 0,
  );
}

const lastQuestion = (app: ElectronApplication) =>
  app.evaluate(
    () =>
      (globalThis as Record<string, unknown>).adleAsked as {
        message: string;
        detail: string;
        buttons: string[];
        defaultId: number;
        cancelId: number;
      },
  );

/** Record the folders the app asks the file manager to show, instead of showing them. */
async function recordOpenedFolders(app: ElectronApplication): Promise<() => Promise<string[]>> {
  await app.evaluate(({ shell }) => {
    const opened: string[] = [];
    (globalThis as Record<string, unknown>).adleOpened = opened;
    shell.openPath = (target: string) => {
      opened.push(target);
      return Promise.resolve('');
    };
  });
  return () => app.evaluate(() => (globalThis as Record<string, unknown>).adleOpened as string[]);
}

async function openPrivacy(page: Page): Promise<void> {
  await page.getByRole('navigation').getByRole('button', { name: 'Settings' }).click();
  await page.getByRole('tab', { name: 'Privacy & data' }).click();
  await expect(page.getByRole('heading', { name: 'Your data', level: 2 })).toBeVisible();
}

async function openLibrary(page: Page): Promise<void> {
  await page.getByRole('navigation').getByRole('button', { name: 'Library' }).click();
  await expect(page.getByRole('heading', { name: 'Library', level: 1 })).toBeVisible();
}

const button = (page: Page, name: string) => page.getByRole('button', { name, exact: true });
/** The message that says how the last action went. */
const outcome = (page: Page, title: string) =>
  page.getByRole('main').locator('[role="status"], [role="alert"]').filter({ hasText: title });
const courseCard = (page: Page, name: string) =>
  page.getByRole('main').getByRole('button', { name: new RegExp(name) });

async function restoreFrom(app: ElectronApplication, page: Page, file: string): Promise<void> {
  await chooseInFileDialog(app, [file]);
  await button(page, 'Restore from a copy').click();
}

test.describe('your data as a whole', () => {
  test('a saved copy brings back a deleted course, and the restore can be undone', async ({
    adle,
    profileDir,
  }) => {
    test.setTimeout(150_000);
    const { app, page } = adle;
    await waitForCore(page);
    // Somewhere of the learner's own. (Inside the test profile only so that it is
    // cleaned up with it; what matters is that it is outside Adle's data folder.)
    const copies = path.join(profileDir, 'kept elsewhere');
    mkdirSync(copies);
    const copy = path.join(copies, 'Adle data 2026-11-19.adle');
    const safetyCopies = path.join(profileDir, 'data', 'backups');

    await createCourse(page, 'Thermodynamics');
    await importAndWait(app, page, ['study-notes.txt']);

    // ---- Save a copy: one file, where the learner said ----
    await openPrivacy(page);
    await chooseInSaveDialog(app, copy);
    await button(page, 'Save a copy').click();
    const saved = outcome(page, 'Saved as Adle data 2026-11-19.adle');
    await expect(saved).toBeVisible();
    await expect(saved).toContainText('It holds everything in Adle as it is now.');
    expect(readdirSync(copies)).toEqual(['Adle data 2026-11-19.adle']);
    // The copy has the text of the materials in it; the key was never in the data.
    expect(filesContaining(copies, PHRASE)).toHaveLength(1);
    await expectNoAccessibilityViolations(page);
    await screenshot(page, 'settings-data-saved');

    // ---- Lose the course ----
    await openLibrary(page);
    await courseCard(page, 'Thermodynamics').click();
    await button(page, 'Delete course').click();
    await page
      .getByRole('dialog', { name: /Delete “Thermodynamics”/ })
      .getByRole('button', { name: 'Delete course' })
      .click();
    await expect(page.getByRole('heading', { name: 'No courses yet' })).toBeVisible();

    // ---- Restore from the copy: the course is back, with what was imported into it ----
    await openPrivacy(page);
    await restoreFrom(app, page, copy);
    const restored = outcome(page, 'Your data was restored from the copy');
    await expect(restored).toBeVisible({ timeout: 60_000 });
    await expect(restored).toContainText('kept as a safety copy first');
    await expect(page.getByText('Local service ready')).toBeVisible();
    await expectNoAccessibilityViolations(page);
    await screenshot(page, 'settings-data-restored');
    // The learner's own file is untouched and still one file.
    expect(readdirSync(copies)).toEqual(['Adle data 2026-11-19.adle']);

    await restored.getByRole('button', { name: 'Go to the library' }).click();
    await expect(courseCard(page, 'Thermodynamics')).toContainText('1 source');
    await courseCard(page, 'Thermodynamics').click();
    await page.getByRole('tab', { name: 'Materials' }).click();
    const search = page.getByRole('searchbox', { name: 'Search your materials' });
    await search.fill('rolling downhill');
    await expect(page.getByRole('list', { name: /Results for/ }).getByRole('listitem')).toHaveCount(
      1,
    );

    // ---- What was replaced was kept, and the learner can be shown where ----
    await openPrivacy(page);
    const opened = await recordOpenedFolders(app);
    await button(page, 'Show safety copies').click();
    await expect.poll(opened).toEqual([safetyCopies]);
    const kept = readdirSync(safetyCopies);
    expect(kept).toHaveLength(1);
    expect(kept[0]).toMatch(/^adle-replaced-\d{8}T\d+Z\.db$/);

    // ---- A restore can be undone: the safety copy is a copy like any other ----
    await restoreFrom(app, page, path.join(safetyCopies, kept[0]!));
    await expect(outcome(page, 'Your data was restored from the copy')).toBeVisible({
      timeout: 60_000,
    });
    await openLibrary(page);
    await expect(page.getByRole('heading', { name: 'No courses yet' })).toBeVisible();

    expect(adle.problems).toEqual([]);
  });

  test('backing out, a bad place, and a file that is not a copy change nothing', async ({
    adle,
    profileDir,
  }) => {
    test.setTimeout(150_000);
    const { app, page } = adle;
    await waitForCore(page);
    const copies = path.join(profileDir, 'kept elsewhere');
    mkdirSync(copies);
    const dataDir = path.join(profileDir, 'data');
    await createCourse(page, 'Still here', { topic: 'Limits and derivatives.' });
    await openPrivacy(page);
    const messages = page.getByRole('main').locator('[role="alert"]');

    // ---- Backing out of the save dialog is not an outcome: nothing is said ----
    await chooseInSaveDialog(app, null);
    await button(page, 'Save a copy').click();
    await expect(button(page, 'Save a copy')).not.toHaveAttribute('aria-busy', 'true');
    await expect(messages).toHaveCount(0);
    await expect(page.getByText(/^Saved as/)).toHaveCount(0);

    // ---- A copy inside the folder it is a copy of would be deleted with it ----
    await chooseInSaveDialog(app, path.join(dataDir, 'copy.adle'));
    await button(page, 'Save a copy').click();
    const notSaved = outcome(page, 'The copy was not saved');
    await expect(notSaved).toContainText("Choose a place outside Adle's own data folder.");
    expect(existsSync(path.join(dataDir, 'copy.adle'))).toBe(false);

    // ---- A name typed without the ending gets it, but never over another file ----
    await chooseInSaveDialog(app, path.join(copies, 'my copy'));
    await button(page, 'Save a copy').click();
    await expect(outcome(page, 'Saved as my copy.adle')).toBeVisible();
    expect(readdirSync(copies)).toEqual(['my copy.adle']);
    await button(page, 'Save a copy').click();
    await expect(outcome(page, 'The copy was not saved')).toContainText(
      'There is already a file called my copy.adle there. Choose another name.',
    );

    // ---- Backing out of choosing a file to restore ----
    await chooseInFileDialog(app, null);
    await button(page, 'Restore from a copy').click();
    await expect(button(page, 'Restore from a copy')).not.toHaveAttribute('aria-busy', 'true');
    await expect(outcome(page, 'Nothing was restored')).toHaveCount(0);

    // ---- A file that only looks like a copy is read, refused, and nothing is replaced ----
    const notes = path.join(copies, 'lecture notes.adle');
    writeFileSync(notes, 'These are my lecture notes, not a copy of my data.');
    await restoreFrom(app, page, notes);
    const refused = outcome(page, 'Nothing was restored');
    await expect(refused).toBeVisible({ timeout: 60_000 });
    await expect(refused).toContainText(
      "That file is not a copy of Adle's data, or it is damaged.",
    );
    await expect(refused).toContainText('Your current data was not changed.');
    await waitForCore(page);
    await expect(page.getByText('Local service ready')).toBeVisible();

    // ---- A document is turned away before anything is stopped ----
    await restoreFrom(app, page, doc('lecture-notes.pdf'));
    await expect(outcome(page, 'Nothing was restored')).toContainText(
      'Choose a copy of your data: a file that ends in .adle.',
    );
    await expectNoAccessibilityViolations(page);
    await screenshot(page, 'settings-data-refused');

    // ---- Deleting asks first, in the operating system's own window, and "Cancel" is the default ----
    await answerConfirmation(app, 'cancel');
    await button(page, 'Delete everything').click();
    await expect(button(page, 'Delete everything')).not.toHaveAttribute('aria-busy', 'true');
    const asked = await lastQuestion(app);
    expect(asked.message).toBe('Delete everything Adle has stored on this computer?');
    expect(asked.detail).toContain('This cannot be undone.');
    expect(asked.detail).toContain('AI provider key');
    expect(asked.buttons).toEqual(['Cancel', 'Delete everything']);
    expect([asked.defaultId, asked.cancelId]).toEqual([0, 0]);
    await expect(page.getByText('Everything was deleted')).toHaveCount(0);

    // ---- After all of that, everything is as it was, and no safety copy was needed ----
    await openLibrary(page);
    await expect(courseCard(page, 'Still here')).toBeVisible();
    expect(readdirSync(path.join(dataDir, 'backups'))).toEqual([]);
    expect(adle.problems).toEqual([]);
  });

  test('deleting everything removes the learner’s work from the disk and keeps the key', async ({
    profileDir,
  }) => {
    test.setTimeout(150_000);
    const launched = await launchApp(profileDir, { onboarded: true, theme: 'light' });
    const { app, page } = launched;
    await waitForCore(page);
    const dataDir = path.join(profileDir, 'data');

    await page.getByRole('navigation').getByRole('button', { name: 'Settings' }).click();
    await page.getByLabel('API key', { exact: true }).fill(KEY);
    await button(page, 'Save key').click();
    await expect(page.getByText('Saved · ends in 1Kp7')).toBeVisible();

    await openLibrary(page);
    await createCourse(page, 'To be deleted');
    await importAndWait(app, page, ['study-notes.txt']);
    // Keep a safety copy around too: deleting everything includes those.
    const copies = path.join(profileDir, 'kept elsewhere');
    mkdirSync(copies);
    const copy = path.join(copies, 'before.adle');
    await openPrivacy(page);
    await chooseInSaveDialog(app, copy);
    await button(page, 'Save a copy').click();
    await expect(outcome(page, 'Saved as before.adle')).toBeVisible();
    await restoreFrom(app, page, copy);
    await expect(outcome(page, 'Your data was restored from the copy')).toBeVisible({
      timeout: 60_000,
    });
    expect(readdirSync(path.join(dataDir, 'backups'))).toHaveLength(1);
    // The text of the notes is on disk: in the database, the stored original, the safety copy.
    expect(filesContaining(dataDir, PHRASE).length).toBeGreaterThanOrEqual(2);

    // ---- Delete everything ----
    await answerConfirmation(app, 'delete');
    await button(page, 'Delete everything').click();
    const erased = outcome(page, 'Everything was deleted');
    await expect(erased).toBeVisible({ timeout: 60_000 });
    await expect(erased).toContainText('Your AI provider key and your appearance settings');
    await expect(page.getByText('Local service ready')).toBeVisible();
    await expectNoAccessibilityViolations(page);
    await screenshot(page, 'settings-data-erased');

    // Nothing of the learner's work is left in Adle's folders: not the text, not the title.
    expect(filesContaining(dataDir, PHRASE)).toEqual([]);
    expect(filesContaining(dataDir, 'To be deleted')).toEqual([]);
    expect(filesContaining(path.join(profileDir, 'logs'), PHRASE)).toEqual([]);
    expect(readdirSync(path.join(dataDir, 'backups'))).toEqual([]);
    expect(readdirSync(path.join(dataDir, 'sources'))).toEqual([]);
    // The copy the learner saved elsewhere is theirs, and is not touched.
    expect(readdirSync(copies)).toEqual(['before.adle']);

    await erased.getByRole('button', { name: 'Go to the library' }).click();
    await expect(page.getByRole('heading', { name: 'No courses yet' })).toBeVisible();

    // The key is still stored, is still nowhere in the clear, and the new core has it.
    expect(await page.evaluate(() => window.adle!.provider.keyState())).toEqual({
      stored: true,
      hint: '1Kp7',
    });
    await expect
      .poll(async () => page.evaluate(() => window.adle!.core.invoke('provider.status')))
      .toMatchObject({ ok: true, data: { key_configured: true } });
    expect(filesContaining(profileDir, KEY)).toEqual([]);

    // And Adle works from here as it did when it was first installed.
    await createCourse(page, 'A fresh start', { topic: 'Anything at all.' });
    await openLibrary(page);
    await expect(courseCard(page, 'A fresh start')).toBeVisible();

    expect(launched.problems).toEqual([]);
    await launched.close();
  });
});
