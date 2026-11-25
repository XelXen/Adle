/**
 * Settings saved as a file, and brought in on another computer (ADR-064).
 *
 * Two profiles stand for two computers. The windows of the operating system that ask where
 * to save and which file to open are replaced with answers (never driven); the provider is
 * a stand-in on this computer, so the key saved here is a made-up one that goes nowhere.
 */
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';

import type { ElectronApplication, Page } from '@playwright/test';

import { expect, launchApp, repoRoot, test, waitForCore } from './support/app';
import {
  chooseInFileDialog,
  expectNoAccessibilityViolations,
  providerCard,
  saveProviderKey,
  screenshot,
} from './support/courses';
import { startFakeProvider } from './support/fake-provider';

/** A recognisable fake key. It only ever reaches the fake provider. */
const KEY = 'sk-e2e-not-a-real-key-6Jd3pQv82Lm5';
const PASSWORD = 'a password for the journey';

const core = path.join(repoRoot, 'services', 'core');
const corePython =
  process.platform === 'win32'
    ? path.join(core, '.venv', 'Scripts', 'python.exe')
    : path.join(core, '.venv', 'bin', 'python');
const standIn = path.join(core, 'tests', 'support', 'fake_voice_engine.py');

const KOKORO_FILES = [
  'config.json',
  'kokoro-v1_0.pth',
  'voices/af_heart.pt',
  'voices/af_bella.pt',
  'voices/bf_emma.pt',
  'voices/am_michael.pt',
  'voices/am_fenrir.pt',
];

/** The lightest natural voice where an installation leaves it: every file empty. */
function aVoice(folder: string): string {
  const models = path.join(folder, 'models');
  for (const file of KOKORO_FILES) {
    const at = path.join(models, 'Kokoro-82M', file);
    mkdirSync(path.dirname(at), { recursive: true });
    writeFileSync(at, '');
  }
  return models;
}

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

async function invoke<T>(page: Page, operation: string, request?: unknown): Promise<T> {
  const answer = await page.evaluate(
    ([name, body]) => window.adle!.core.invoke(name as never, body as never),
    [operation, request] as const,
  );
  expect(answer.ok, JSON.stringify(answer)).toBe(true);
  return (answer as { data: T }).data;
}

async function openPrivacy(page: Page): Promise<void> {
  await page.getByRole('navigation').getByRole('button', { name: 'Settings' }).click();
  await page.getByRole('tab', { name: 'Privacy & data' }).click();
  await expect(page.getByRole('heading', { name: 'Your settings', level: 2 })).toBeVisible();
}

const prefersDark = (page: Page): Promise<boolean> =>
  page.evaluate(() => window.matchMedia('(prefers-color-scheme: dark)').matches);

test.describe('settings as a file', () => {
  test('settings are saved with the keys locked, and set another computer up as this one is', async ({
    profileDir,
  }) => {
    const provider = await startFakeProvider();
    const env = { ADLE_PROVIDER_BASE_URL: provider.baseUrl };
    const file = test.info().outputPath('Adle settings.json');
    const other = mkdtempSync(path.join(os.tmpdir(), 'adle-e2e-second-'));

    // -- this computer: a key, a theme, a way of learning, a natural voice in use ----------
    const models = aVoice(test.info().outputPath('voice'));
    const first = await launchApp(profileDir, {
      onboarded: true,
      theme: 'light',
      env: {
        ...env,
        ADLE_VOICE_KOKORO_PYTHON: corePython,
        ADLE_VOICE_ENGINE: standIn,
        ADLE_VOICE_MODELS: models,
      },
    });
    try {
      const { app, page } = first;
      await waitForCore(page);
      await page.getByRole('navigation').getByRole('button', { name: 'Settings' }).click();
      await saveProviderKey(page, /Custom endpoint/, KEY);
      await page.getByRole('tab', { name: 'Appearance' }).click();
      await page.getByRole('radio', { name: 'Dark' }).click();
      await expect.poll(() => prefersDark(page)).toBe(true);
      await invoke(page, 'learner.update_preferences', {
        body: { pace: 'brisk', volume: 35, goal: 'Pass the exam in June.' },
      });
      await invoke(page, 'voice.choose', { body: { tier: 'kokoro', speaker: 'bf_emma' } });

      await openPrivacy(page);
      await chooseInSaveDialog(app, file);
      await page.getByRole('button', { name: 'Save settings' }).click();
      const saving = page.getByRole('dialog', { name: 'Save your settings to a file' });
      await expect(saving.getByRole('checkbox', { name: 'Include my API keys' })).toBeChecked();
      // No password, no file: the keys are never saved in the clear.
      await saving.getByRole('button', { name: 'Save…' }).click();
      await expect(saving.getByText('Use 8 characters or more.')).toBeVisible();
      await saving.getByLabel('Password for the keys').fill(PASSWORD);
      await saving.getByLabel('The password again').fill(PASSWORD);
      await saving.getByText('Advanced').click();
      await expectNoAccessibilityViolations(page);
      await screenshot(page, 'settings-save-to-a-file');
      await saving.getByRole('button', { name: 'Save…' }).click();
      await expect(page.getByText('Settings saved')).toBeVisible();
      await expect(saving).toBeHidden();
    } finally {
      await first.close();
    }

    // What is in the file: the settings, readable; the key, not.
    const text = readFileSync(file, 'utf8');
    const saved = JSON.parse(text) as Record<string, Record<string, unknown>>;
    expect(saved.format).toBe('adle-settings');
    expect(saved.appearance).toEqual({ theme: 'dark', notifications: true });
    expect(saved.learning).toMatchObject({ pace: 'brisk', volume: 35 });
    expect(saved.voice).toMatchObject({ enabled: true, tier: 'kokoro' });
    expect(saved.provider).toEqual({ selection: 'auto' });
    expect(saved.keys!.providers).toEqual(['custom']);
    expect(text).not.toContain(KEY);
    expect(text).not.toContain(KEY.slice(-6));
    expect(text).not.toContain(PASSWORD);
    // A key is named by its provider and never by where it is sent.
    expect(text).not.toContain(provider.baseUrl);
    expect(text).not.toContain('127.0.0.1');

    // -- another computer: nothing set, no natural voice on it -----------------------------
    const second = await launchApp(other, { onboarded: true, theme: 'light', env });
    try {
      const { app, page } = second;
      await waitForCore(page);
      expect(await prefersDark(page)).toBe(false);
      expect(await page.evaluate(() => window.adle!.provider.keyState())).toEqual({
        custom: { stored: false, hint: null },
      });

      await openPrivacy(page);
      await chooseInFileDialog(app, [file]);
      await page.getByRole('button', { name: 'Import settings' }).click();
      const importing = page.getByRole('dialog', { name: 'Import these settings?' });
      await expect(importing).toContainText(
        'Adle settings.json holds appearance, learning, voice, AI provider and API keys.',
      );
      await expect(importing).toContainText(
        /Keys for Custom endpoint \([^)]+\)\. They replace yours\./,
      );
      // The voice is not on this computer. What setting it up downloads is said first, and
      // nothing is downloaded unless the learner leaves that ticked: here they do not.
      const setUp = importing.getByRole('checkbox', { name: /^Set up the \w+ voice$/ });
      await expect(setUp).toBeChecked();
      await expect(importing.getByText(/^Downloads about [\d.]+ (MB|GB) from /)).toBeVisible();
      await expectNoAccessibilityViolations(page);
      await screenshot(page, 'settings-import');
      await setUp.uncheck();

      // A wrong password changes nothing, and can be tried again.
      await importing.getByLabel('Password for the keys').fill('not the password at all');
      await importing.getByRole('button', { name: 'Import' }).click();
      await expect(
        importing.getByText('That password doesn’t open the keys in this file.'),
      ).toBeVisible();
      expect(await prefersDark(page)).toBe(false);
      expect((await page.evaluate(() => window.adle!.provider.keyState())).custom).toEqual({
        stored: false,
        hint: null,
      });

      await importing.getByLabel('Password for the keys').fill(PASSWORD);
      await importing.getByRole('button', { name: 'Import' }).click();
      const done = page.getByRole('dialog', { name: 'Settings imported' });
      await expect(done).toContainText(
        'Brought in: appearance, learning, voice, AI provider and API keys.',
      );
      // What could not be had as it was is said: the voice is not set up here.
      await expect(done.getByRole('listitem')).toContainText([
        /voice isn’t set up on this computer/,
      ]);
      await done.getByRole('button', { name: 'Done' }).click();

      // The app begins again where the learner was, set up as the other one is.
      await expect(page.getByRole('dialog')).toHaveCount(0);
      await expect(page.getByRole('heading', { name: 'Your settings', level: 2 })).toBeVisible();
      await waitForCore(page);
      await expect.poll(() => prefersDark(page)).toBe(true);
      // The key is kept here for this provider, and the core has it: never the page.
      expect((await page.evaluate(() => window.adle!.provider.keyState())).custom).toEqual({
        stored: true,
        hint: KEY.slice(-4),
      });
      const status = await invoke<{ key_configured: boolean; selection: string }>(
        page,
        'provider.status',
      );
      expect(status).toMatchObject({ key_configured: true, selection: 'auto' });
      const preferences = await invoke<Record<string, unknown>>(page, 'learner.get_preferences');
      expect(preferences).toMatchObject({
        pace: 'brisk',
        volume: 35,
        goal: 'Pass the exam in June.',
      });
      // No voice was downloaded: the computer's own reads, and nothing is being set up.
      const voice = await invoke<{ enabled: boolean; setting_up: unknown }>(page, 'voice.status');
      expect(voice).toMatchObject({ enabled: false, setting_up: null });
      await page.getByRole('navigation').getByRole('button', { name: 'Settings' }).click();
      await expect(providerCard(page, /Custom endpoint/)).toContainText(
        `Key saved · ends in ${KEY.slice(-4)}`,
      );
      expect(second.problems).toEqual([]);
    } finally {
      await second.close();
      await provider.close();
      rmSync(other, { recursive: true, force: true, maxRetries: 20, retryDelay: 250 });
    }
  });

  test('settings can be saved without the keys, and a file that is not settings changes nothing', async ({
    adle,
  }) => {
    const { app, page } = adle;
    await waitForCore(page);
    const file = test.info().outputPath('plain.json');
    await openPrivacy(page);

    await chooseInSaveDialog(app, file);
    await page.getByRole('button', { name: 'Save settings' }).click();
    const saving = page.getByRole('dialog', { name: 'Save your settings to a file' });
    await saving.getByRole('checkbox', { name: 'Include my API keys' }).uncheck();
    await expect(saving.getByLabel('Password for the keys')).toHaveCount(0);
    await saving.getByRole('button', { name: 'Save…' }).click();
    await expect(page.getByText('Settings saved')).toBeVisible();
    const saved = JSON.parse(readFileSync(file, 'utf8')) as Record<string, unknown>;
    expect(Object.keys(saved).sort()).toEqual([
      'appearance',
      'format',
      'learning',
      'made_at',
      'made_by',
      'provider',
      'version',
      'voice',
    ]);

    // Backing out of the window that asks which file: nothing is asked.
    await chooseInFileDialog(app, null);
    await page.getByRole('button', { name: 'Import settings' }).click();
    await expect(page.getByRole('dialog')).toHaveCount(0);

    // A file that is not settings: said, and nothing changed.
    const stray = test.info().outputPath('package.json');
    writeFileSync(stray, JSON.stringify({ name: 'something-else', version: '1.0.0' }));
    await chooseInFileDialog(app, [stray]);
    await page.getByRole('button', { name: 'Import settings' }).click();
    const alert = page.getByRole('alert').filter({ hasText: 'Couldn’t open that file' });
    await expect(alert).toContainText('This file isn’t settings saved by Adle');
    await expect(alert).not.toContainText(path.dirname(stray));
    await expect(page.getByRole('dialog')).toHaveCount(0);

    // Its own file, brought back in with a part left out under "Advanced".
    await invoke(page, 'learner.update_preferences', { body: { pace: 'relaxed' } });
    await chooseInFileDialog(app, [file]);
    await page.getByRole('button', { name: 'Import settings' }).click();
    const importing = page.getByRole('dialog', { name: 'Import these settings?' });
    await expect(importing).toContainText('holds appearance, learning, voice and AI provider.');
    await expect(importing.getByLabel('Password for the keys')).toHaveCount(0);
    await importing.getByText('Advanced').click();
    await importing.getByRole('checkbox', { name: 'Learning' }).uncheck();
    await importing.getByRole('button', { name: 'Import' }).click();
    const done = page.getByRole('dialog', { name: 'Settings imported' });
    await expect(done).toContainText('Brought in: appearance, voice and AI provider.');
    await done.getByRole('button', { name: 'Done' }).click();
    await expect(page.getByRole('dialog')).toHaveCount(0);
    await expect(page.getByRole('heading', { name: 'Your settings', level: 2 })).toBeVisible();
    await waitForCore(page);
    // What was left out is as the learner had it.
    expect(await invoke<{ pace: string }>(page, 'learner.get_preferences')).toMatchObject({
      pace: 'relaxed',
    });
    expect(adle.problems).toEqual([]);
  });
});
