/**
 * A course saved as a file, and brought in from one (ADR-063).
 *
 * The windows of the operating system that ask where to save and which file to open are
 * replaced with answers, as everywhere (never driven). Everything else is the real path:
 * the core writes the file, the shell moves it to the place chosen, and bringing it in
 * makes a new course through the same gates every course goes through.
 */
import { existsSync, readdirSync, writeFileSync } from 'node:fs';
import path from 'node:path';

import type { ElectronApplication, Page } from '@playwright/test';

import { expect, test, waitForCore } from './support/app';
import {
  chooseInFileDialog,
  courseCard,
  expectNoAccessibilityViolations,
  openCourseTab,
  screenshot,
  showNarrationAsText,
} from './support/courses';

const SAMPLE = 'Introduction to neural networks';

/** Make the native save dialog answer with this path, or as if it had been cancelled. */
async function chooseInSaveDialog(app: ElectronApplication, filePath: string | null) {
  await app.evaluate(({ dialog }, chosen) => {
    dialog.showSaveDialog = (...asked: unknown[]) => {
      (globalThis as Record<string, unknown>).adleSaveAsked = asked.at(-1);
      return Promise.resolve(
        chosen === null ? { canceled: true, filePath: '' } : { canceled: false, filePath: chosen },
      );
    };
  }, filePath);
}

const saveQuestion = (app: ElectronApplication) =>
  app.evaluate(
    () =>
      (globalThis as Record<string, unknown>).adleSaveAsked as {
        title: string;
        defaultPath: string;
        filters: { name: string; extensions: string[] }[];
      },
  );

async function invoke<T>(page: Page, operation: string, request?: unknown): Promise<T> {
  const answer = await page.evaluate(
    ([name, body]) => window.adle!.core.invoke(name as never, body as never),
    [operation, request] as const,
  );
  expect(answer.ok, JSON.stringify(answer)).toBe(true);
  return (answer as { data: T }).data;
}

interface Listed {
  id: string;
  title: string;
  brought_in: boolean;
  origin: string;
}

const courses = async (page: Page): Promise<Listed[]> =>
  (await invoke<{ courses: Listed[] }>(page, 'courses.list')).courses;

async function openLibrary(page: Page): Promise<void> {
  await page.getByRole('main').getByRole('button', { name: 'Library' }).click();
  await expect(page.getByRole('heading', { name: 'Library', level: 1 })).toBeVisible();
}

/** The sample course with one question of its first lesson answered. */
async function aCourseWithProgress(page: Page): Promise<string> {
  await page.getByRole('button', { name: 'Try the sample course' }).click();
  await expect(page.getByRole('heading', { name: SAMPLE, level: 1 })).toBeVisible();
  const [course] = await courses(page);
  const { lessons } = await invoke<{ lessons: { id: string }[] }>(page, 'lessons.list', {
    path: { course_id: course!.id },
  });
  await invoke(page, 'lessons.answer', {
    path: { lesson_id: lessons[0]!.id, question_id: 'q_influence' },
    body: { option_id: 'a' },
  });
  return course!.id;
}

test.describe('a course as a file', () => {
  test('a course is saved as a template and brought in as a new course, with nothing of the learner in it', async ({
    adle,
    profileDir,
  }) => {
    const { app, page } = adle;
    await waitForCore(page);
    await showNarrationAsText(page);
    const original = await aCourseWithProgress(page);
    const file = test.info().outputPath('Neural networks.adle-course.zip');

    // Saved from the course's own page. The window that asks where is the system's.
    await chooseInSaveDialog(app, file);
    await page.getByRole('button', { name: 'Save as a file' }).click();
    const saving = page.getByRole('dialog', { name: `Save “${SAMPLE}” as a file` });
    await expect(saving.getByRole('radio', { name: /A template/ })).toBeChecked();
    await expectNoAccessibilityViolations(page);
    await saving.getByText('Advanced').click();
    await expect(saving.getByRole('checkbox', { name: 'Lessons' })).toBeChecked();
    await expect(saving.getByRole('checkbox', { name: 'Progress' })).not.toBeChecked();
    await screenshot(page, 'course-save-as-a-file');
    await saving.getByRole('button', { name: 'Save…' }).click();
    await expect(page.getByText('Course saved')).toBeVisible();
    await expect(saving).toBeHidden();
    expect(existsSync(file)).toBe(true);
    const asked = await saveQuestion(app);
    // The name offered is the course's, and it is a name: the core's folder is not shown.
    expect(asked.defaultPath).toBe(`${SAMPLE}.adle-course.zip`);
    expect(asked.filters).toEqual([{ name: 'Adle course', extensions: ['zip'] }]);
    // Nothing is left behind in Adle's own folder once the file has been handed over.
    const handover = path.join(profileDir, 'data', 'handover');
    expect(existsSync(handover) ? readdirSync(handover) : []).toEqual([]);

    // Brought in from the library: first what the file holds, then a new course.
    await openLibrary(page);
    await chooseInFileDialog(app, [file]);
    await page.getByRole('button', { name: 'Import course' }).click();
    const importing = page.getByRole('dialog', { name: `Import “${SAMPLE}”?` });
    await expect(importing).toContainText('Neural networks.adle-course.zip holds 8 concepts');
    await expect(importing).toContainText('It becomes a new course.');
    await expectNoAccessibilityViolations(page);
    await importing.getByText('Advanced').click();
    await expect(importing.getByRole('checkbox', { name: /^Lessons/ })).toBeChecked();
    await expect(importing.getByRole('checkbox', { name: 'Progress' })).toHaveCount(0);
    await screenshot(page, 'course-import');
    await importing.getByRole('button', { name: 'Import' }).click();
    await expect(page.getByText('Course imported')).toBeVisible();

    // It opens, says where it came from, and has the plan and the lessons.
    await expect(page.getByRole('heading', { name: SAMPLE, level: 1 })).toBeVisible();
    await expect(page.getByRole('main').getByText('Imported', { exact: true })).toBeVisible();
    const listed = await courses(page);
    expect(listed).toHaveLength(2);
    const brought = listed.find((course) => course.id !== original)!;
    expect(brought).toMatchObject({ title: SAMPLE, brought_in: true, origin: 'topic' });
    const theirs = await invoke<{ lessons: unknown[] }>(page, 'lessons.list', {
      path: { course_id: original },
    });
    const ours = await invoke<{ lessons: { id: string }[] }>(page, 'lessons.list', {
      path: { course_id: brought.id },
    });
    expect(ours.lessons).toHaveLength(theirs.lessons.length);

    // Nothing of the learner came with it: every concept is as it is for someone new.
    const overview = await invoke<{ concepts: { knowledge: { state: string } }[] }>(
      page,
      'learning.overview',
      { path: { course_id: brought.id } },
    );
    expect(new Set(overview.concepts.map((concept) => concept.knowledge.state))).toEqual(
      new Set(['not_assessed']),
    );

    // And a lesson that came in a file is taken like any other.
    await openCourseTab(page, 'Curriculum');
    const lesson = await invoke<{ lesson: { title: string; course_id: string } }>(
      page,
      'lessons.get',
      { path: { lesson_id: ours.lessons[0]!.id } },
    );
    expect(lesson.lesson.course_id).toBe(brought.id);

    // The two are told apart in the library.
    await openLibrary(page);
    await expect(courseCard(page, SAMPLE)).toHaveCount(2);
    await expect(page.getByRole('main').getByText('Imported', { exact: true })).toHaveCount(1);
    await expect(page.getByRole('main').getByText('Sample course').first()).toBeVisible();
    await expectNoAccessibilityViolations(page);
    await screenshot(page, 'library-with-an-imported-course');
    expect(adle.problems).toEqual([]);
  });

  test('everything is saved to move a course, and what is brought in is the learner’s choice', async ({
    adle,
  }) => {
    const { app, page } = adle;
    await waitForCore(page);
    await showNarrationAsText(page);
    const original = await aCourseWithProgress(page);
    const file = test.info().outputPath('moved.zip');

    await chooseInSaveDialog(app, file);
    await page.getByRole('button', { name: 'Save as a file' }).click();
    const saving = page.getByRole('dialog', { name: `Save “${SAMPLE}” as a file` });
    await saving.getByRole('radio', { name: /Everything/ }).check();
    await saving.getByText('Advanced').click();
    await expect(saving.getByRole('checkbox', { name: 'Progress' })).toBeChecked();
    await saving.getByRole('button', { name: 'Save…' }).click();
    await expect(page.getByText('Course saved')).toBeVisible();

    // With its progress: the concept answered about is where the learner left it.
    await openLibrary(page);
    await chooseInFileDialog(app, [file]);
    await page.getByRole('button', { name: 'Import course' }).click();
    const importing = page.getByRole('dialog', { name: `Import “${SAMPLE}”?` });
    await expect(importing).toContainText('progress');
    await importing.getByRole('button', { name: 'Import' }).click();
    await expect(page.getByText('Course imported')).toBeVisible();
    await expect(page.getByRole('heading', { name: SAMPLE, level: 1 })).toBeVisible();
    const states = async (courseId: string): Promise<string[]> =>
      (
        await invoke<{ concepts: { knowledge: { state: string } }[] }>(page, 'learning.overview', {
          path: { course_id: courseId },
        })
      ).concepts.map((concept) => concept.knowledge.state);
    const withProgress = (await courses(page)).find(
      (course) => course.id !== original && course.brought_in,
    )!;
    expect(await states(withProgress.id)).toEqual(await states(original));
    expect(await states(original)).toContain('building');

    // Without it, when the learner unticks it under "Advanced".
    await openLibrary(page);
    await chooseInFileDialog(app, [file]);
    await page.getByRole('button', { name: 'Import course' }).click();
    await importing.getByText('Advanced').click();
    await importing.getByRole('checkbox', { name: 'Progress' }).uncheck();
    await importing.getByRole('button', { name: 'Import' }).click();
    await expect(page.getByText('Course imported').last()).toBeVisible();
    await expect(page.getByRole('heading', { name: SAMPLE, level: 1 })).toBeVisible();
    const known = new Set([original, withProgress.id]);
    const without = (await courses(page)).find((course) => !known.has(course.id))!;
    expect(new Set(await states(without.id))).toEqual(new Set(['not_assessed']));
    expect(adle.problems).toEqual([]);
  });

  test('backing out, and a file that is not a course, change nothing', async ({
    adle,
    profileDir,
  }) => {
    const { app, page } = adle;
    await waitForCore(page);
    await aCourseWithProgress(page);

    // Backing out of the window that asks where: nothing is written, the dialog stays.
    await chooseInSaveDialog(app, null);
    await page.getByRole('button', { name: 'Save as a file' }).click();
    const saving = page.getByRole('dialog', { name: `Save “${SAMPLE}” as a file` });
    await saving.getByRole('button', { name: 'Save…' }).click();
    await expect(saving.getByRole('button', { name: 'Save…' })).toBeEnabled();
    await expect(page.getByText('Course saved')).toHaveCount(0);
    const handover = path.join(profileDir, 'data', 'handover');
    expect(existsSync(handover) ? readdirSync(handover) : []).toEqual([]);
    await saving.getByRole('button', { name: 'Cancel' }).click();

    // Backing out of the window that asks which file: nothing is asked.
    await openLibrary(page);
    await chooseInFileDialog(app, null);
    await page.getByRole('button', { name: 'Import course' }).click();
    await expect(page.getByRole('dialog')).toHaveCount(0);

    // A zip that is not a course: said, and nothing made.
    const stray = test.info().outputPath('holiday.zip');
    writeFileSync(stray, 'PK not really a zip');
    await chooseInFileDialog(app, [stray]);
    await page.getByRole('button', { name: 'Import course' }).click();
    const alert = page.getByRole('alert').filter({ hasText: 'Couldn’t open that file' });
    await expect(alert).toContainText('This file isn’t an Adle course, or it is damaged.');
    // What went wrong is said without where the file is.
    await expect(alert).not.toContainText(path.dirname(stray));
    await expect(page.getByRole('dialog')).toHaveCount(0);
    expect(await courses(page)).toHaveLength(1);

    // A file that is not a zip at all is turned away before it is read.
    const other = test.info().outputPath('notes.txt');
    writeFileSync(other, 'notes');
    await chooseInFileDialog(app, [other]);
    await page.getByRole('button', { name: 'Import course' }).click();
    await expect(
      page.getByRole('alert').filter({ hasText: 'Choose a course saved by Adle' }),
    ).toBeVisible();
    expect(await courses(page)).toHaveLength(1);
    expect(adle.problems).toEqual([]);
  });
});
