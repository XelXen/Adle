/**
 * Asking Adle a question in the middle of a lesson (ADR-024), through the whole real
 * path: the lesson screen, the core's job, a provider standing in on this computer, and
 * the record it leaves. No request leaves the machine.
 *
 * What these journeys are about: what is sent is said first and nothing is sent before
 * the learner asks; the answer is kept beside the part it was about; a question the
 * lesson is asking is never answered for the learner, and asking about it counts as help;
 * and the learner never has to wait in front of it.
 */
import path from 'node:path';
import { DatabaseSync } from 'node:sqlite';

import type { Page } from '@playwright/test';

import { expect, launchApp, type LaunchedApp, test, waitForCore } from './support/app';
import {
  expectNoAccessibilityViolations,
  saveProviderKey,
  screenshot,
  showNarrationAsText,
} from './support/courses';
import { type FakeProvider, HANG, startFakeProvider } from './support/fake-provider';

/** A recognisable fake key. It only ever reaches the server on this computer. */
const KEY = 'sk-e2e-not-a-real-key-7Hq2mZx94Wd1';
const PROVIDER = 'Custom endpoint (127.0.0.1)';
const LESSON = 'Weights and bias: how a neuron adds things up';
const QUESTION = 'Why does a bigger weight count for more?';
const ANSWER_STARTS = 'A weight says how much one input counts.';

const continueButton = (page: Page) => page.getByRole('button', { name: 'Continue', exact: true });
const askButton = (page: Page) => page.getByRole('button', { name: 'Ask a question' });
const askDialog = (page: Page) => page.getByRole('dialog', { name: 'Ask about this part' });
// Exactly: "Answering your question" is the dialog before this one.
const answerDialog = (page: Page) => page.getByRole('dialog', { name: 'Answer', exact: true });
const kept = (page: Page) => page.getByRole('region', { name: 'Your questions about this part' });

interface Session {
  adle: LaunchedApp;
  page: Page;
  provider: FakeProvider;
}

/** The app with a provider on this computer, the sample course, and its first lesson open. */
async function inTheLesson(
  profileDir: string,
  options: { key?: boolean; theme?: 'light' | 'dark' } = {},
): Promise<Session> {
  const provider = await startFakeProvider();
  const adle = await launchApp(profileDir, {
    onboarded: true,
    theme: options.theme ?? 'light',
    env: { ADLE_PROVIDER_BASE_URL: provider.baseUrl },
  });
  const { page } = adle;
  await waitForCore(page);
  await showNarrationAsText(page);
  if (options.key !== false) {
    await page.getByRole('button', { name: 'Settings' }).click();
    await saveProviderKey(page, /Custom endpoint/, KEY);
    await page.getByRole('button', { name: 'Library', exact: true }).click();
  }
  await page.getByRole('button', { name: 'Try the sample course' }).click();
  await page.getByRole('button', { name: 'Start lesson' }).first().click();
  await expect(page.getByRole('heading', { name: LESSON, level: 1 })).toBeVisible();
  await expect(page.getByText('Part 1 of 10')).toBeVisible();
  return { adle, page, provider };
}

async function close({ adle, provider }: Session): Promise<void> {
  await adle.close();
  await provider.close();
}

/** Whether each answer the learner gave was recorded as an aided one, oldest first. */
function aidedAnswers(profileDir: string): boolean[] {
  const database = new DatabaseSync(path.join(profileDir, 'data', 'adle.db'), { readOnly: true });
  try {
    return database
      .prepare('SELECT hinted FROM attempts ORDER BY id')
      .all()
      .map((row) => Boolean((row as { hinted: number }).hinted));
  } finally {
    database.close();
  }
}

test.describe('asking a question during a lesson', () => {
  test('ask about a part, read the answer, and find it kept beside that part', async ({
    profileDir,
  }) => {
    test.setTimeout(240_000);
    const session = await inTheLesson(profileDir);
    const { adle, page, provider } = session;

    // ---- Asking pauses nothing that was not playing, and sends nothing by itself ----
    await page.getByRole('button', { name: 'Start', exact: true }).click();
    await expect(page.getByRole('button', { name: 'Pause' })).toBeVisible();
    await askButton(page).click();
    const dialog = askDialog(page);
    await expect(dialog).toBeVisible();
    await expect(dialog).toContainText('Part 1: Not every input counts the same');
    // What will be sent, and where, is said before anything is.
    await expect(dialog).toContainText(
      'Sends your question, this part of the lesson, the lesson outline, the course name, ' +
        `this concept, and any related passages from your materials to ${PROVIDER}.`,
    );
    await expect(dialog).toContainText('AI answers can be wrong.');
    expect(provider.requests).toHaveLength(0);
    // The lesson waits while the learner asks.
    await expect(page.getByRole('button', { name: 'Resume' })).toBeVisible();
    await expectNoAccessibilityViolations(page);
    await screenshot(page, 'ask-compose');

    // ---- An empty question is not sent ----
    await dialog.getByRole('button', { name: 'Ask', exact: true }).click();
    await expect(dialog.getByRole('alert')).toContainText('Type a question');
    expect(provider.requests).toHaveLength(0);

    // ---- A question in the learner's own words ----
    await dialog.getByRole('textbox', { name: 'Your question' }).fill(QUESTION);
    await dialog.getByRole('button', { name: 'Ask', exact: true }).click();
    const answer = answerDialog(page);
    await expect(answer).toBeVisible({ timeout: 30_000 });
    await expect(answer).toContainText(QUESTION);
    await expect(answer).toContainText(ANSWER_STARTS);
    // Mathematics in an answer is typeset like the lesson's own.
    await expect(answer.locator('.katex').first()).toBeVisible();
    await expect(answer).toContainText(
      `Answered by Coding Kimi K3 (free) on ${PROVIDER}. AI can make mistakes.`,
    );
    await expectNoAccessibilityViolations(page);
    await screenshot(page, 'ask-answer');

    // ---- What was actually sent: one request, with the part and the question as quoted text ----
    expect(provider.requests.map((request) => request.kind)).toEqual(['ask']);
    const sent = provider.requests[0]!;
    expect(sent.authorization).toBe(`Bearer ${KEY}`);
    expect(sent.prompt).toContain(`<learner_material kind="question">\n${QUESTION}\n`);
    expect(sent.prompt).toContain('Not every input counts the same');
    expect(sent.prompt).toContain('Suppose you are deciding whether to go for a run.');
    expect(sent.prompt).toContain('The learner is at part 1.');
    expect(sent.prompt).not.toContain(KEY);

    // ---- Back in the lesson, the answer is kept beside the part ----
    await answer.getByRole('button', { name: 'Back to lesson' }).click();
    await expect(answer).toBeHidden();
    const toggle = page.getByRole('button', { name: 'Your questions about this part (1)' });
    await expect(toggle).toHaveAttribute('aria-expanded', 'true');
    await expect(kept(page)).toContainText(QUESTION);
    await expect(kept(page)).toContainText(ANSWER_STARTS);
    await toggle.click();
    await expect(toggle).toHaveAttribute('aria-expanded', 'false');
    await expect(kept(page)).not.toContainText(ANSWER_STARTS);

    // ---- A ready-made question: the usual ways of having something explained again ----
    await askButton(page).click();
    await expect(askDialog(page).getByRole('list')).toContainText('Explain this more simply.');
    await askDialog(page).getByRole('button', { name: 'Give me an example.' }).click();
    await expect(answerDialog(page)).toContainText('Give me an example.', { timeout: 30_000 });
    expect(provider.requests.at(-1)?.prompt).toContain('Give me an example.');
    await answerDialog(page).getByRole('button', { name: 'Back to lesson' }).click();
    await expect(
      page.getByRole('button', { name: 'Your questions about this part (2)' }),
    ).toBeVisible();
    await expectNoAccessibilityViolations(page);
    await screenshot(page, 'ask-kept-beside-the-part');

    // ---- One of them can be removed; the other stays ----
    await kept(page)
      .getByRole('listitem')
      .filter({ hasText: 'Give me an example.' })
      .getByRole('button', { name: 'Remove question' })
      .click();
    await expect(
      page.getByRole('button', { name: 'Your questions about this part (1)' }),
    ).toBeVisible();
    await expect(kept(page)).toContainText(QUESTION);

    // ---- They belong to their part: the next part has none, and they are there on return ----
    await continueButton(page).click();
    await expect(page.getByText('Part 2 of 10')).toBeVisible();
    await expect(kept(page)).toHaveCount(0);
    await page.getByRole('button', { name: 'Previous' }).click();
    await expect(page.getByText('Part 1 of 10')).toBeVisible();
    await expect(
      page.getByRole('button', { name: 'Your questions about this part (1)' }),
    ).toBeVisible();

    // ---- And they are still there when the lesson is opened another day ----
    expect(adle.problems).toEqual([]);
    await adle.close();
    const again = await launchApp(profileDir, {
      env: { ADLE_PROVIDER_BASE_URL: provider.baseUrl },
    });
    await waitForCore(again.page);
    await again.page
      .getByRole('main')
      .getByRole('button', { name: /Introduction to neural/ })
      .click();
    await again.page.getByRole('button', { name: 'Continue lesson' }).first().click();
    await expect(again.page.getByRole('heading', { name: LESSON, level: 1 })).toBeVisible();
    // A lesson opens again at the furthest part reached; the question is beside part 1.
    await expect(again.page.getByText('Part 2 of 10')).toBeVisible();
    await again.page.getByRole('button', { name: 'Previous' }).click();
    const later = again.page.getByRole('button', { name: 'Your questions about this part (1)' });
    await expect(later).toBeVisible();
    await later.click();
    await expect(kept(again.page)).toContainText(ANSWER_STARTS);
    // Opening the lesson again asked nobody anything.
    expect(provider.requests).toHaveLength(2);
    await again.close();
    await provider.close();
  });

  test('a question the lesson is asking is not answered for the learner, and asking about it counts as help', async ({
    profileDir,
  }) => {
    test.setTimeout(240_000);
    // In the dark theme, so that asking and its answer are checked for contrast there too.
    const session = await inTheLesson(profileDir, { theme: 'dark' });
    const { adle, page, provider } = session;
    for (const part of [1, 2, 3]) {
      await expect(page.getByText(`Part ${part} of 10`)).toBeVisible();
      await continueButton(page).click();
    }
    await expect(page.getByText('Part 4 of 10')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Which input matters more?' })).toBeVisible();

    // ---- The learner is told, before asking, what asking here means ----
    await askButton(page).click();
    const dialog = askDialog(page);
    await expect(dialog).toContainText('You haven’t answered this question yet');
    await expect(dialog).toContainText(
      'You’ll get help thinking it through, not the answer. Like a hint, asking makes a ' +
        'correct answer count a little less.',
    );
    // Nothing offered asks for the answer.
    await expect(dialog.getByRole('list')).not.toContainText(/right answer|which option/i);
    await expectNoAccessibilityViolations(page);
    await screenshot(page, 'ask-about-a-question');
    await dialog.getByRole('button', { name: 'Give me a nudge, not the answer.' }).click();
    await expect(answerDialog(page)).toBeVisible({ timeout: 30_000 });

    // ---- What was sent has the question and its choices, and nothing that settles it ----
    const prompt = provider.requests.at(-1)!.prompt;
    expect(prompt).toContain('they have NOT answered it yet');
    expect(prompt).toContain('Do not give its answer or say which choice is right');
    expect(prompt).toContain('The first input');
    expect(prompt).toContain('The second input');
    // Neither what each choice gets right or wrong, nor the explanation shown afterwards.
    expect(prompt).not.toContain('Its weight is the smaller one');
    expect(prompt).not.toContain('Influence comes from the weight');
    await expectNoAccessibilityViolations(page);
    await screenshot(page, 'ask-answer-dark');
    await answerDialog(page).getByRole('button', { name: 'Back to lesson' }).click();

    // ---- The answer the learner then gives is theirs, recorded as an aided one ----
    const question = page.locator('form');
    await question.getByRole('radio', { name: 'The first input' }).check();
    await question.getByRole('button', { name: 'Check answer' }).click();
    await expect(
      question.getByRole('status').or(question.getByRole('alert')).first(),
    ).toBeVisible();
    await expect.poll(() => aidedAnswers(profileDir)).toEqual([true]);

    // ---- Asking afterwards is curiosity: the next answer counts in full ----
    await askButton(page).click();
    await expect(askDialog(page)).not.toContainText('You haven’t answered this question yet');
    await askDialog(page).getByRole('button', { name: 'Why is that the right answer?' }).click();
    await expect(answerDialog(page)).toBeVisible({ timeout: 30_000 });
    expect(provider.requests.at(-1)!.prompt).toContain('they have answered it');
    await answerDialog(page).getByRole('button', { name: 'Back to lesson' }).click();
    await continueButton(page).click();
    await continueButton(page).click();
    await expect(page.getByText('Part 6 of 10')).toBeVisible();
    await page.locator('form').getByRole('button', { name: 'Skip question' }).click();
    expect(aidedAnswers(profileDir)[0]).toBe(true);

    expect(adle.problems).toEqual([]);
    await close(session);
  });

  test('the learner does not have to wait: carry on, and be told when the answer arrives; or stop it', async ({
    profileDir,
  }) => {
    test.setTimeout(240_000);
    const session = await inTheLesson(profileDir);
    const { adle, page, provider } = session;

    // ---- A slow answer: the learner goes back to the lesson meanwhile ----
    provider.queue(HANG);
    await askButton(page).click();
    await askDialog(page).getByRole('textbox', { name: 'Your question' }).fill(QUESTION);
    await askDialog(page).getByRole('button', { name: 'Ask', exact: true }).click();
    const waiting = page.getByRole('dialog', { name: 'Answering your question' });
    await expect(waiting).toBeVisible();
    await expect(waiting).toContainText('No need to wait here.');
    await expect(waiting.getByRole('progressbar')).toBeVisible();
    await expectNoAccessibilityViolations(page);
    await screenshot(page, 'ask-waiting');
    await waiting.getByRole('button', { name: 'Continue lesson' }).click();
    await expect(waiting).toBeHidden();
    // The lesson is theirs again, and the control says an answer is on its way.
    await expect(page.getByRole('button', { name: 'Answering' })).toBeVisible();
    await continueButton(page).click();
    await expect(page.getByText('Part 2 of 10')).toBeVisible();

    // ---- It arrives while they are on another part, and in another window ----
    await adle.setFocused(false);
    provider.release();
    const told = page.getByRole('status').filter({ hasText: 'Your answer is ready' });
    await expect(told).toBeVisible({ timeout: 30_000 });
    await expect(told).toContainText('See part 1 of this lesson.');
    // The computer says so too, in fixed words with nothing of the lesson in them.
    await expect
      .poll(() => adle.notices())
      .toEqual([
        {
          title: 'Your answer is ready',
          body: 'It’s next to the part of the lesson you asked about.',
        },
      ]);
    await adle.setFocused(true);
    await page.getByRole('button', { name: 'Previous' }).click();
    await expect(kept(page)).toContainText(ANSWER_STARTS);
    await expect(askButton(page)).toBeVisible();

    // ---- Stopping a question that is taking too long: nothing is kept ----
    provider.queue(HANG);
    await askButton(page).click();
    await askDialog(page).getByRole('button', { name: 'Explain this more simply.' }).click();
    const again = page.getByRole('dialog', { name: 'Answering your question' });
    await expect(again).toBeVisible();
    await again.getByRole('button', { name: 'Stop' }).click();
    await expect(askDialog(page)).toBeVisible({ timeout: 30_000 });
    await askDialog(page).getByRole('button', { name: 'Cancel' }).click();
    await expect(
      page.getByRole('button', { name: 'Your questions about this part (1)' }),
    ).toBeVisible();

    // ---- A provider that fails costs the learner nothing but the question ----
    provider.queue({ status: 500 });
    await askButton(page).click();
    await askDialog(page).getByRole('button', { name: 'Give me an example.' }).click();
    await expect(
      askDialog(page).getByRole('alert').filter({ hasText: 'Couldn’t get an answer' }),
    ).toBeVisible({
      timeout: 30_000,
    });
    await askDialog(page).getByRole('button', { name: 'Cancel' }).click();
    await expect(
      page.getByRole('button', { name: 'Your questions about this part (1)' }),
    ).toBeVisible();

    expect(adle.problems).toEqual([]);
    await close(session);
  });

  test('without a key the lesson works as before, and asking says what is missing', async ({
    profileDir,
  }) => {
    const session = await inTheLesson(profileDir, { key: false });
    const { adle, page, provider } = session;

    await askButton(page).click();
    const dialog = askDialog(page);
    await expect(dialog).toContainText('no provider key is set up yet');
    await expect(dialog).toContainText('The rest of the lesson works without one.');
    await expect(dialog.getByRole('textbox')).toHaveCount(0);
    await expectNoAccessibilityViolations(page);
    await dialog.getByRole('button', { name: 'Back to lesson' }).click();
    await expect(dialog).toBeHidden();
    await expect(continueButton(page)).toBeEnabled();
    expect(provider.requests).toHaveLength(0);

    expect(adle.problems).toEqual([]);
    await close(session);
  });
});
