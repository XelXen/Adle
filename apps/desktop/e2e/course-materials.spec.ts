/**
 * Creating a course, importing materials, inspecting where text came from, and
 * removing things again. Everything here happens locally: the test session has
 * no network at all (see security.spec.ts).
 */
import path from 'node:path';

import AxeBuilder from '@axe-core/playwright';
import type { ElectronApplication, Page } from '@playwright/test';

import { desktopDir, expect, launchApp, repoRoot, test, waitForCore } from './support/app';

const DOCUMENTS = path.join(repoRoot, 'fixtures', 'sample-documents');
const doc = (name: string): string => path.join(DOCUMENTS, name);

/** Make the native file dialog return these paths, as if the learner had picked them. */
async function chooseInFileDialog(app: ElectronApplication, paths: string[] | null): Promise<void> {
  await app.evaluate(({ dialog }, chosen) => {
    dialog.showOpenDialog = () =>
      Promise.resolve(
        chosen === null
          ? { canceled: true, filePaths: [] }
          : { canceled: false, filePaths: chosen },
      );
  }, paths);
}

async function createCourse(
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

async function importWithDialog(
  app: ElectronApplication,
  page: Page,
  names: string[],
): Promise<void> {
  await chooseInFileDialog(app, names.map(doc));
  await page.getByRole('button', { name: 'Choose files' }).click();
}

const sourceList = (page: Page) => page.getByRole('list', { name: 'Materials in this course' });
const sourceRow = (page: Page, name: string) =>
  sourceList(page)
    .getByRole('listitem')
    .filter({ has: page.getByText(name, { exact: true }) });

test.describe('course materials', () => {
  test('import a syllabus and notes, see what was extracted, and find passages by location', async ({
    adle,
  }) => {
    const { app, page } = adle;
    await waitForCore(page);
    await createCourse(page, 'Neural networks 101');
    await expect(page.getByText('From your materials')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'No materials yet' })).toBeVisible();
    // The local-only promise is stated where the import happens.
    await expect(page.getByText('Nothing is uploaded when you import.')).toBeVisible();

    await importWithDialog(app, page, [
      'neural-networks-syllabus.md',
      'lecture-notes.pdf',
      'partly-scanned.pdf',
      'scanned-handout.pdf',
    ]);

    // One summary says what happened to every file, including the one that failed and why.
    const summary = page.getByRole('status').filter({ hasText: 'imported' });
    await expect(summary).toContainText('3 files imported · 1 could not be imported', {
      timeout: 30_000,
    });
    await expect(summary).toContainText('scanned-handout.pdf');
    await expect(summary).toContainText('no selectable text');
    await expect(summary).toContainText('never uploads');

    await expect(sourceRow(page, 'neural-networks-syllabus.md')).toContainText('Ready');
    await expect(sourceRow(page, 'neural-networks-syllabus.md')).toContainText('Markdown');
    await expect(sourceRow(page, 'lecture-notes.pdf')).toContainText('PDF · 3 pages');
    // Low-confidence extraction is flagged, with the reason, not hidden.
    const partly = sourceRow(page, 'partly-scanned.pdf');
    await expect(partly).toContainText('Check extraction');
    await expect(partly).toContainText('1 of 3 pages had no selectable text');
    await expect(sourceRow(page, 'scanned-handout.pdf')).toHaveCount(0);

    // Search shows the source and the exact place each passage comes from.
    const search = page.getByRole('searchbox', { name: 'Search your materials' });
    await search.fill('worked example updated weight');
    const results = page.getByRole('list', { name: /Results for/ });
    const first = results.getByRole('listitem').first();
    await expect(first).toContainText('lecture-notes.pdf');
    await expect(first).toContainText('page 3');
    await expect(first.locator('mark').first()).toBeVisible();

    await search.fill('bias shifts');
    await expect(results.getByRole('listitem').first()).toContainText(
      'neural-networks-syllabus.md',
    );
    await expect(results.getByRole('listitem').first()).toContainText('Weights and bias');

    await search.fill('xylophone');
    await expect(page.getByText('Nothing in your materials matches “xylophone”.')).toBeVisible();

    const axe = await new AxeBuilder({ page })
      .setLegacyMode(true)
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'])
      .analyze();
    expect(axe.violations.map((violation) => violation.id)).toEqual([]);
    await page.screenshot({
      path: path.join(desktopDir, 'test-results', 'screens', 'course-materials.png'),
      fullPage: false,
    });
    expect(adle.problems).toEqual([]);
  });

  test('imports survive a restart; sources and courses can be removed', async ({ profileDir }) => {
    const first = await launchApp(profileDir, { onboarded: true });
    await waitForCore(first.page);
    await createCourse(first.page, 'Persistent course');
    await importWithDialog(first.app, first.page, ['study-notes.txt', 'course-outline.docx']);
    await expect(
      first.page.getByRole('status').filter({ hasText: '2 files imported' }),
    ).toBeVisible({
      timeout: 30_000,
    });
    await first.close();

    const second = await launchApp(profileDir);
    const { page } = second;
    // The library lists the course, with its real contents, without any import.
    const card = page.getByRole('button', { name: /Persistent course/ });
    await expect(card).toContainText('2 sources');
    await card.click();
    await expect(sourceRow(page, 'study-notes.txt')).toBeVisible();
    await expect(sourceRow(page, 'course-outline.docx')).toContainText('Word document');

    // Remove one source: confirmation first, and cancel does nothing.
    await page.getByRole('button', { name: 'Remove study-notes.txt' }).click();
    const removal = page.getByRole('dialog', { name: /Remove “study-notes.txt”/ });
    await expect(removal).toContainText('original file on your computer is not touched');
    await removal.getByRole('button', { name: 'Keep it' }).click();
    await expect(sourceRow(page, 'study-notes.txt')).toBeVisible();

    await page.getByRole('button', { name: 'Remove study-notes.txt' }).click();
    await removal.getByRole('button', { name: 'Remove source' }).click();
    await expect(sourceRow(page, 'study-notes.txt')).toHaveCount(0);
    await expect(sourceRow(page, 'course-outline.docx')).toBeVisible();

    // Delete the course: explicit about what goes and what is untouched.
    await page.getByRole('button', { name: 'Delete course' }).click();
    const deletion = page.getByRole('dialog', { name: /Delete “Persistent course”/ });
    await expect(deletion).toContainText('cannot be undone');
    await expect(deletion).toContainText('original files you imported from are not touched');
    await deletion.getByRole('button', { name: 'Delete course' }).click();
    await expect(page.getByRole('heading', { name: 'Library', level: 1 })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'No courses yet' })).toBeVisible();
    await second.close();

    // Still gone after another restart.
    const third = await launchApp(profileDir);
    await waitForCore(third.page);
    await expect(third.page.getByRole('heading', { name: 'No courses yet' })).toBeVisible();
    await third.close();
  });

  test('files can be dropped onto the course, and duplicates are recognised', async ({ adle }) => {
    const { app, page } = adle;
    await waitForCore(page);
    await createCourse(page, 'Dropped materials');

    // Build a real drop: file-backed File objects, as the operating system provides them.
    const picker = await page.evaluateHandle(() => {
      const input = document.createElement('input');
      input.type = 'file';
      input.multiple = true;
      input.id = 'e2e-drop-source';
      input.hidden = true;
      document.body.appendChild(input);
      return input;
    });
    await picker.asElement().setInputFiles([doc('study-notes.txt'), doc('lecture-notes.pdf')]);
    await page.evaluate(() => {
      const input = document.getElementById('e2e-drop-source') as HTMLInputElement;
      const transfer = new DataTransfer();
      for (const file of input.files ?? []) transfer.items.add(file);
      const zone = [...document.querySelectorAll('div')].find((element) =>
        element.className.includes('dropzone'),
      )!;
      zone.dispatchEvent(new DragEvent('dragenter', { bubbles: true, dataTransfer: transfer }));
      zone.dispatchEvent(new DragEvent('drop', { bubbles: true, dataTransfer: transfer }));
    });
    await expect(page.getByRole('status').filter({ hasText: '2 files imported' })).toBeVisible({
      timeout: 30_000,
    });
    await expect(sourceRow(page, 'study-notes.txt')).toBeVisible();

    // Importing one of them again adds nothing and says so.
    await importWithDialog(app, page, ['study-notes.txt']);
    await expect(
      page.getByRole('status').filter({ hasText: '1 already in this course' }),
    ).toBeVisible({ timeout: 30_000 });
    await expect(sourceRow(page, 'study-notes.txt')).toHaveCount(1);

    // Dismissing the file dialog is not an error and changes nothing.
    await chooseInFileDialog(app, null);
    await page.getByRole('button', { name: 'Choose files' }).click();
    await expect(page.getByText('The import could not start')).toHaveCount(0);
    await expect(sourceList(page).getByRole('listitem')).toHaveCount(2);
  });

  test('a course from a topic needs a name and a topic, and works from the keyboard', async ({
    adle,
  }) => {
    const { page } = adle;
    await waitForCore(page);
    await page.getByRole('button', { name: 'New course' }).click();
    const dialog = page.getByRole('dialog', { name: 'New course' });

    await dialog.getByRole('button', { name: 'Create course' }).click();
    await expect(dialog.getByText('Give the course a name.')).toBeVisible();
    await expect(dialog.getByText('Describe what you want to learn')).toBeVisible();
    await expect(dialog.getByLabel('Course name')).toHaveAttribute('aria-invalid', 'true');

    await dialog.getByLabel('Course name').fill('Calculus refresher');
    await dialog.getByLabel('What do you want to learn?').fill('Limits and derivatives.');
    await page.keyboard.press('Control+Enter').catch(() => undefined);
    await dialog.getByLabel('Course name').press('Enter');
    await expect(page.getByRole('heading', { name: 'Calculus refresher', level: 1 })).toBeVisible();
    await expect(page.getByText('From a topic')).toBeVisible();
    await expect(page.getByText('Limits and derivatives.')).toBeVisible();

    // Back to the library with the page's own back control (the navigation rail has
    // a button of the same name); the course is listed.
    await page.getByRole('main').getByRole('button', { name: 'Library', exact: true }).click();
    await expect(page.getByRole('button', { name: /Calculus refresher/ })).toContainText(
      'No sources yet',
    );
  });

  test('a course that no longer exists says so and offers a way back', async ({ adle }) => {
    const { page } = adle;
    await waitForCore(page);
    await createCourse(page, 'Short-lived');
    // Delete it behind the screen's back, then reload the route.
    await page.evaluate(async () => {
      const list = (await window.adle!.core.invoke('courses.list')) as {
        ok: true;
        data: { courses: { id: string }[] };
      };
      await window.adle!.core.invoke('courses.delete', {
        path: { course_id: list.data.courses[0]!.id },
      });
    });
    await page.reload();
    await expect(page.getByRole('heading', { name: 'This course no longer exists' })).toBeVisible();
    await page.getByRole('button', { name: 'Back to the library' }).click();
    await expect(page.getByRole('heading', { name: 'Library', level: 1 })).toBeVisible();
  });
});
