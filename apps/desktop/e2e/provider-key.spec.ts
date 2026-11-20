import path from 'node:path';

import { expect, filesContaining, launchApp, test, waitForCore } from './support/app';
import { providerCard, providerKeyField, saveProviderKey } from './support/courses';

/** A recognisable fake key. It is never sent anywhere: these tests make no provider calls. */
const KEY = 'sk-e2e-not-a-real-key-7Hq2mZx94Wd1';

test.describe('configuring the AI provider', () => {
  test('saves the key encrypted, never exposes it, and can remove it', async ({ profileDir }) => {
    const first = await launchApp(profileDir, { onboarded: true });
    const { page } = first;
    await waitForCore(page);
    await page.getByRole('button', { name: 'Settings' }).click();

    const aihubmix = providerCard(page, 'AIHubMix');
    await expect(aihubmix).toContainText('No key yet');
    const field = page.getByRole('textbox', { name: 'AIHubMix API key' });
    await expect(field).toHaveAttribute('type', 'password');
    await saveProviderKey(page, 'AIHubMix', KEY);
    await expect(page.getByRole('status').filter({ hasText: 'Key saved' }).first()).toBeVisible();
    // With one key, "automatic" is simply that provider, and it says so.
    await expect(aihubmix).toContainText('In use');
    await expect(providerCard(page, 'NVIDIA NIM')).not.toContainText('In use');

    // 1. The renderer no longer holds the key anywhere in the document.
    await expect(page.getByRole('textbox', { name: 'Replace the AIHubMix key' })).toHaveValue('');
    expect(await page.content()).not.toContain(KEY);
    // 2. Nothing on the bridge returns it.
    const keyState = await page.evaluate(() => window.adle!.provider.keyState());
    // It is the key of the provider in use, and of no other.
    expect(keyState).toEqual({
      aihubmix: { stored: true, hint: '4Wd1' },
      nvidia: { stored: false, hint: null },
    });
    const provider = await page.evaluate(() => window.adle!.core.invoke('provider.status'));
    expect(JSON.stringify(provider)).not.toContain(KEY);
    expect(provider).toMatchObject({ ok: true, data: { key_configured: true } });
    // 3. It is not on disk in the clear: not in the credential file, logs, or database.
    expect(filesContaining(profileDir, KEY)).toEqual([]);

    expect(first.problems).toEqual([]);
    await first.close();
    // After exit the core log is complete; the key must not be in it either.
    expect(filesContaining(path.join(profileDir, 'logs'), KEY)).toEqual([]);

    // The key survives a restart and is handed to the new core process.
    const second = await launchApp(profileDir);
    await waitForCore(second.page);
    await expect
      .poll(async () => second.page.evaluate(() => window.adle!.core.invoke('provider.status')))
      .toMatchObject({ ok: true, data: { key_configured: true } });

    await second.page.getByRole('button', { name: 'Settings' }).click();
    await providerCard(second.page, 'AIHubMix').getByRole('button', { name: 'Remove key' }).click();
    const dialog = second.page.getByRole('dialog', { name: 'Remove the saved AIHubMix key?' });
    await expect(dialog).toBeVisible();
    await dialog.getByRole('button', { name: 'Remove key' }).click();
    await expect(providerCard(second.page, 'AIHubMix')).toContainText('No key yet');
    expect(await second.page.evaluate(() => window.adle!.provider.keyState())).toEqual({
      aihubmix: { stored: false, hint: null },
      nvidia: { stored: false, hint: null },
    });
    await expect
      .poll(async () => second.page.evaluate(() => window.adle!.core.invoke('provider.status')))
      .toMatchObject({ ok: true, data: { key_configured: false } });
    await second.close();
  });

  test('explains an invalid key instead of saving it', async ({ adle }) => {
    const { page } = adle;
    await page.getByRole('button', { name: 'Settings' }).click();
    const aihubmix = providerCard(page, 'AIHubMix');

    await aihubmix.getByRole('button', { name: 'Save key' }).click();
    await expect(
      page.getByRole('alert').filter({ hasText: 'Enter your API key first.' }),
    ).toBeVisible();

    await providerKeyField(page, 'AIHubMix').fill('short');
    await aihubmix.getByRole('button', { name: 'Save key' }).click();
    await expect(page.getByRole('alert').filter({ hasText: 'looks too short' })).toBeVisible();
    await expect(providerKeyField(page, 'AIHubMix')).toHaveAttribute('aria-invalid', 'true');
    await expect(aihubmix).toContainText('No key yet');
    // A mistake made at one provider says nothing at the other.
    await expect(providerKeyField(page, 'NVIDIA NIM')).not.toHaveAttribute('aria-invalid', 'true');
  });

  test('the removal dialog can be cancelled with Escape and traps focus', async ({ adle }) => {
    const { page } = adle;
    await waitForCore(page);
    await page.getByRole('button', { name: 'Settings' }).click();
    await saveProviderKey(page, 'AIHubMix', KEY);

    await providerCard(page, 'AIHubMix').getByRole('button', { name: 'Remove key' }).click();
    const dialog = page.getByRole('dialog', { name: 'Remove the saved AIHubMix key?' });
    await expect(dialog).toBeVisible();
    // Focus stays inside the modal while tabbing.
    for (let presses = 0; presses < 6; presses += 1) {
      await page.keyboard.press('Tab');
      expect(await dialog.evaluate((element) => element.contains(document.activeElement))).toBe(
        true,
      );
    }
    await page.keyboard.press('Escape');
    await expect(dialog).toBeHidden();
    await expect(providerCard(page, 'AIHubMix')).toContainText('Key saved · ends in 4Wd1');
  });
});
