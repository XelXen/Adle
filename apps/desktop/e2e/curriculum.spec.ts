/**
 * Building and inspecting a curriculum: a first draft from the headings of the
 * learner's own materials, then refining it by hand. No AI is involved, and the
 * test session has no network.
 */
import type { Page } from '@playwright/test';

import { expect, launchApp, test, waitForCore } from './support/app';
import {
  courseCard,
  createCourse,
  expectNoAccessibilityViolations,
  importAndWait,
  openCourseTab,
  screenshot,
} from './support/courses';

const pathList = (page: Page) => page.getByRole('list', { name: 'Learning path' });
const pathRow = (page: Page, title: string) =>
  pathList(page)
    .getByRole('listitem')
    .filter({ has: page.getByRole('button', { name: new RegExp(`^${title}`) }) });
const detail = (page: Page, title: string) => page.getByRole('region', { name: title });

/** The concepts in the order the path lists them, read from each row's "Move … earlier" control. */
async function pathTitles(page: Page): Promise<string[]> {
  const controls = pathList(page).getByRole('button', { name: /^Move .+ earlier$/ });
  const titles: string[] = [];
  for (const control of await controls.all()) {
    const label = (await control.getAttribute('aria-label')) ?? '';
    titles.push(label.replace(/^Move /, '').replace(/ earlier$/, ''));
  }
  return titles;
}

async function selectConcept(page: Page, title: string): Promise<void> {
  await pathRow(page, title).getByRole('button').first().click();
  await expect(detail(page, title)).toBeVisible();
}

test.describe('curriculum', () => {
  test('draft a curriculum from materials, refine it, and find it again after a restart', async ({
    profileDir,
  }) => {
    const first = await launchApp(profileDir, { onboarded: true, theme: 'light' });
    const { app, page } = first;
    await waitForCore(page);
    await createCourse(page, 'Neural networks 101');
    await importAndWait(app, page, ['neural-networks-syllabus.md', 'lecture-notes.pdf']);

    // ---- A first draft from the headings of the materials ----
    await page.getByRole('tab', { name: 'Curriculum' }).click();
    await expect(page.getByRole('heading', { name: 'No concepts yet' })).toBeVisible();
    await page.getByRole('button', { name: 'Start from your materials' }).click();
    const outline = page.getByRole('dialog', { name: 'Start from your materials' });
    await expect(outline.getByRole('checkbox')).toHaveCount(7);
    // Numbering is dropped, and headings that only organise the document are not offered.
    await expect(outline.getByRole('checkbox', { name: 'The perceptron' })).toBeChecked();
    await expect(outline.getByRole('checkbox', { name: 'Assessment' })).toHaveCount(0);
    await expect(outline.getByText('From neural-networks-syllabus.md')).toBeVisible();
    await outline.getByRole('checkbox', { name: 'Forward propagation' }).uncheck();
    await outline.getByRole('checkbox', { name: 'Derivatives and the chain rule' }).uncheck();
    await outline.getByRole('button', { name: 'Add 5 concepts' }).click();

    await expect(pathList(page).getByRole('listitem')).toHaveCount(5);
    expect(await pathTitles(page)).toEqual([
      'The perceptron',
      'Activation functions',
      'Loss',
      'Backpropagation',
      'Gradient descent',
    ]);

    // The first concept is shown, tied to the place it came from.
    const perceptron = detail(page, 'The perceptron');
    await expect(perceptron).toContainText('From a heading in your materials.');
    const linked = perceptron.getByRole('list', { name: 'Linked passages' });
    await expect(linked.getByRole('listitem')).toHaveCount(1);
    await expect(linked).toContainText('neural-networks-syllabus.md');
    await expect(linked).toContainText('Unit 1: The perceptron');
    await expect(perceptron.getByText('Not started')).toBeVisible();
    // Nothing to check understanding against yet: flagged, not blocked.
    await expect(page.getByText('Before you start')).toBeVisible();
    await expect(
      page.getByText(
        '5 concepts have no learning objective yet: The perceptron, Activation functions, Loss and 2 more.',
      ),
    ).toBeVisible();

    // ---- Refine by hand ----
    await perceptron.getByRole('button', { name: 'Edit', exact: true }).click();
    const edit = page.getByRole('dialog', { name: 'Edit concept' });
    await edit
      .getByRole('textbox', { name: 'Objective 1' })
      .fill('Compute the output of a perceptron by hand.');
    await edit.getByRole('button', { name: 'Add objective' }).click();
    await edit.getByRole('textbox', { name: 'Objective 2' }).fill('Say what the bias changes.');
    await edit.getByRole('button', { name: 'Save changes' }).click();
    await expect(perceptron.getByText('Compute the output of a perceptron by hand.')).toBeVisible();
    await expect(perceptron.getByText('Say what the bias changes.')).toBeVisible();

    await page.getByRole('button', { name: 'Add a concept' }).click();
    const create = page.getByRole('dialog', { name: 'Add a concept' });
    await create.getByRole('button', { name: 'Add concept' }).click();
    await expect(create.getByText('Enter a name.')).toBeVisible();
    await create.getByLabel('Name').fill('Chain rule');
    await create
      .getByLabel('What it covers')
      .fill('How to differentiate a function of a function.');
    await create
      .getByRole('textbox', { name: 'Objective 1' })
      .fill('Differentiate a composition of two functions.');
    await create.getByRole('button', { name: 'Add concept' }).click();
    await expect(detail(page, 'Chain rule')).toContainText('How to differentiate');
    await expect(pathList(page).getByRole('listitem')).toHaveCount(6);

    // ---- What needs what ----
    await selectConcept(page, 'Backpropagation');
    await detail(page, 'Backpropagation')
      .getByRole('button', { name: 'Edit prerequisites' })
      .click();
    const needs = page.getByRole('dialog', { name: 'Prerequisites for “Backpropagation”' });
    await needs.getByRole('checkbox', { name: 'Chain rule' }).check();
    await needs
      .getByLabel('Why “Chain rule” is needed')
      .fill('Backpropagation is the chain rule applied layer by layer.');
    await needs.getByRole('checkbox', { name: 'Loss' }).check();
    await needs.getByRole('button', { name: 'Save prerequisites' }).click();
    const backprop = detail(page, 'Backpropagation');
    await expect(backprop).toContainText('applied layer by layer');
    // The path now teaches the chain rule before backpropagation.
    const order = await pathTitles(page);
    expect(order.indexOf('Chain rule')).toBeLessThan(order.indexOf('Backpropagation'));
    await expect(pathRow(page, 'Backpropagation')).toContainText('Needs Loss, Chain rule');

    // A loop cannot be made: what builds on a concept cannot be put before it.
    await selectConcept(page, 'Chain rule');
    await detail(page, 'Chain rule').getByRole('button', { name: 'Edit prerequisites' }).click();
    const chainNeeds = page.getByRole('dialog', { name: 'Prerequisites for “Chain rule”' });
    await expect(chainNeeds.getByRole('checkbox', { name: 'Backpropagation' })).toBeDisabled();
    await expect(
      chainNeeds.getByText('Builds on “Chain rule”, so it can’t be a prerequisite.'),
    ).toBeVisible();
    await chainNeeds.getByRole('button', { name: 'Cancel' }).click();
    await expect(detail(page, 'Chain rule')).toContainText('Required for: Backpropagation.');

    // ---- Order: free where prerequisites allow, explained where they do not ----
    const before = await pathTitles(page);
    await page.getByRole('button', { name: 'Move Chain rule earlier' }).click();
    await expect
      .poll(async () => (await pathTitles(page)).indexOf('Chain rule'))
      .toBe(before.indexOf('Chain rule') - 1);
    // Walk backpropagation up until it meets something it needs.
    for (let step = 0; step < 6; step += 1) {
      await page.getByRole('button', { name: 'Move Backpropagation earlier' }).click();
      if (await page.getByText('“Backpropagation” can’t move there').isVisible()) break;
      await page.waitForTimeout(150);
    }
    await expect(page.getByText('“Backpropagation” can’t move there')).toBeVisible();
    const settled = await pathTitles(page);
    expect(settled.indexOf('Loss')).toBeLessThan(settled.indexOf('Backpropagation'));
    expect(settled.indexOf('Chain rule')).toBeLessThan(settled.indexOf('Backpropagation'));

    // ---- What the learner says they know is a claim to check, not proof ----
    await selectConcept(page, 'Backpropagation');
    await backprop.getByRole('button', { name: 'I know this well' }).click();
    await expect(backprop.getByRole('button', { name: 'I know this well' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    await expect(pathRow(page, 'Backpropagation')).toContainText('Nearly there');
    await expect(backprop).toContainText('a few questions to confirm what you know');
    await backprop.getByRole('button', { name: 'Show history' }).click();
    await expect(backprop.getByRole('list', { name: 'History, newest first' })).toContainText(
      'You said you already know this well.',
    );

    // ---- Linking a concept to the passage that covers it ----
    await selectConcept(page, 'Loss');
    const loss = detail(page, 'Loss');
    await loss.getByRole('button', { name: 'Find related passages' }).click();
    const passages = loss.getByRole('list', { name: 'Related passages' });
    // Both documents are represented, each with the place the passage comes from.
    await expect(passages.getByRole('listitem').filter({ hasText: 'syllabus.md' })).not.toHaveCount(
      0,
    );
    const fromNotes = passages.getByRole('listitem').filter({ hasText: 'lecture-notes.pdf' });
    await expect(fromNotes.first()).toContainText(/page \d/);
    // The heading the concept was drafted from is already linked.
    await expect(
      passages.getByRole('listitem').filter({ hasText: 'Unit 4: Loss' }).getByText('Linked'),
    ).toBeVisible();
    await fromNotes
      .first()
      .getByRole('button', { name: /^Link lecture-notes\.pdf/ })
      .click();
    await expect(fromNotes.first().getByText('Linked')).toBeVisible();
    const places = loss.getByRole('list', { name: 'Linked passages' });
    await expect(places.getByRole('listitem')).toHaveCount(2);
    await expect(places).toContainText('lecture-notes.pdf');
    await places.getByRole('button', { name: /^Unlink lecture-notes\.pdf/ }).click();
    await expect(places.getByRole('listitem')).toHaveCount(1);

    await expectNoAccessibilityViolations(page);
    await screenshot(page, 'curriculum-list');

    // ---- The same curriculum as a map ----
    await page.getByRole('radio', { name: 'Map' }).click();
    const map = page.getByRole('group', { name: 'Concept map' });
    await expect(map.getByRole('button')).toHaveCount(6);
    await map.getByRole('button', { name: /^Chain rule\./ }).click();
    await expect(map.getByRole('button', { name: /^Chain rule\./ })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    await expect(detail(page, 'Chain rule')).toBeVisible();
    await expect(
      map.getByRole('button', { name: 'Backpropagation. Needs Loss, Chain rule.' }),
    ).toBeVisible();
    // Prerequisites are drawn above what needs them.
    const chainBox = await map.getByRole('button', { name: /^Chain rule\./ }).boundingBox();
    const backpropBox = await map.getByRole('button', { name: /^Backpropagation\./ }).boundingBox();
    expect(chainBox!.y).toBeLessThan(backpropBox!.y);
    await expectNoAccessibilityViolations(page);
    await screenshot(page, 'curriculum-map');
    expect(first.problems).toEqual([]);
    await first.close();

    // ---- Everything is still there after a restart, in the other theme ----
    const second = await launchApp(profileDir, { onboarded: true, theme: 'dark' });
    await waitForCore(second.page);
    await courseCard(second.page, /Neural networks 101/).click();
    // A course with concepts opens on what to do next; the curriculum is one tab away.
    await expect(second.page.getByRole('tab', { name: 'Learn', exact: true })).toHaveAttribute(
      'aria-selected',
      'true',
    );
    await openCourseTab(second.page, 'Curriculum');
    await expect(pathList(second.page).getByRole('listitem')).toHaveCount(6);
    expect(await pathTitles(second.page)).toEqual(settled);
    await expect(pathRow(second.page, 'Backpropagation')).toContainText('Nearly there');
    await selectConcept(second.page, 'The perceptron');
    await expect(detail(second.page, 'The perceptron')).toContainText('Say what the bias changes.');
    await expectNoAccessibilityViolations(second.page);
    await screenshot(second.page, 'curriculum-list-dark');

    // ---- Removing a concept removes the links to it, with a clear confirmation ----
    await selectConcept(second.page, 'Chain rule');
    await detail(second.page, 'Chain rule').getByRole('button', { name: 'Remove' }).click();
    const confirm = second.page.getByRole('dialog', { name: 'Remove “Chain rule”?' });
    await expect(confirm).toContainText('Concepts that depended on it no longer will.');
    await confirm.getByRole('button', { name: 'Remove concept' }).click();
    await expect(pathList(second.page).getByRole('listitem')).toHaveCount(5);
    await expect(pathRow(second.page, 'Backpropagation')).toContainText('Needs Loss');
    await expect(pathRow(second.page, 'Backpropagation')).not.toContainText('Chain rule');
    expect(second.problems).toEqual([]);
    await second.close();
  });

  test('a course from a topic starts empty and can be built with the keyboard alone', async ({
    adle,
  }) => {
    const { page } = adle;
    await waitForCore(page);
    await createCourse(page, 'Calculus refresher', { topic: 'Limits and derivatives.' });

    // A topic course opens on its curriculum; with no materials there is nothing to draft from.
    await expect(page.getByRole('tab', { name: 'Curriculum' })).toHaveAttribute(
      'aria-selected',
      'true',
    );
    await expect(page.getByRole('heading', { name: 'No concepts yet' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Start from your materials' })).toHaveCount(0);

    await page.getByRole('button', { name: 'Add a concept' }).focus();
    await page.keyboard.press('Enter');
    const dialog = page.getByRole('dialog', { name: 'Add a concept' });
    await expect(dialog.getByLabel('Name')).toBeFocused();
    await page.keyboard.type('Limits');
    await page.keyboard.press('Tab');
    await page.keyboard.type('What a function approaches.');
    await page.keyboard.press('Tab');
    await page.keyboard.type('Evaluate a limit from a table of values.');
    await page.keyboard.press('Enter');

    const limits = detail(page, 'Limits');
    await expect(limits).toContainText('Evaluate a limit from a table of values.');
    await expect(limits).toContainText('No materials imported.');
    await expect(limits).toContainText('None. You can start here.');
    await expect(pathList(page).getByRole('listitem')).toHaveCount(1);
    // With one concept there is nowhere to move it.
    await expect(page.getByRole('button', { name: 'Move Limits earlier' })).toBeDisabled();
    await expect(page.getByRole('button', { name: 'Move Limits later' })).toBeDisabled();
    await expectNoAccessibilityViolations(page);
    expect(adle.problems).toEqual([]);
  });
});
