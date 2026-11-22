/**
 * The learner's own choices about how they like to be taught. They are stored
 * by the local service, not in the browser, and survive a restart.
 */
import { expect, launchApp, test, waitForCore } from './support/app';

test.describe('learning preferences', () => {
  test('can be changed with mouse or keyboard and are remembered', async ({ profileDir }) => {
    const first = await launchApp(profileDir, { onboarded: true });
    const { page } = first;
    await waitForCore(page);
    await page.getByRole('button', { name: 'Settings' }).click();
    await page.getByRole('tab', { name: 'Learning' }).click();

    // Defaults: a steady pace, balanced explanations, narration and captions on.
    await expect(page.getByRole('radio', { name: 'Standard' })).toBeChecked();
    await expect(page.getByRole('radio', { name: 'Balanced' })).toBeChecked();
    await expect(page.getByRole('switch', { name: 'Narration' })).toBeChecked();
    await expect(page.getByRole('switch', { name: 'Captions' })).toBeChecked();
    await expect(page.getByRole('button', { name: 'Save goal' })).toBeDisabled();

    // Each choice says what it means.
    await page.getByRole('radio', { name: 'Relaxed' }).click();
    await expect(page.getByText('Smaller steps, more pauses')).toBeVisible();
    // The keyboard moves through a group with the arrow keys.
    await page.getByRole('radio', { name: 'Balanced' }).focus();
    await page.keyboard.press('ArrowRight');
    await expect(page.getByRole('radio', { name: 'Detailed' })).toBeChecked();
    await expect(page.getByText('Fuller explanations with intermediate steps')).toBeVisible();

    await page.getByRole('switch', { name: 'Narration' }).click();
    await expect(page.getByRole('switch', { name: 'Narration' })).not.toBeChecked();

    await page
      .getByLabel('What are you working toward?')
      .fill('Understand backpropagation well enough to implement it.');
    await page.getByRole('button', { name: 'Save goal' }).click();
    await expect(page.getByText('Goal saved')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Save goal' })).toBeDisabled();
    expect(first.problems).toEqual([]);
    await first.close();

    const second = await launchApp(profileDir);
    await waitForCore(second.page);
    await second.page.getByRole('button', { name: 'Settings' }).click();
    await second.page.getByRole('tab', { name: 'Learning' }).click();
    await expect(second.page.getByRole('radio', { name: 'Relaxed' })).toBeChecked();
    await expect(second.page.getByRole('radio', { name: 'Detailed' })).toBeChecked();
    await expect(second.page.getByRole('switch', { name: 'Narration' })).not.toBeChecked();
    await expect(second.page.getByRole('switch', { name: 'Captions' })).toBeChecked();
    await expect(second.page.getByLabel('What are you working toward?')).toHaveValue(
      'Understand backpropagation well enough to implement it.',
    );
    await second.close();
  });
});
