/**
 * Choosing between AI providers, through the whole real path (interface, main process,
 * key store, core, jobs), with two servers on this computer standing in for AIHubMix and
 * for NVIDIA. No request leaves the machine, and no test here reaches a real provider.
 *
 * What these journeys are about (ADR-021): the learner chooses the provider and nothing
 * else does; a key is only ever sent to the provider and the address it was given for;
 * and when a provider's first model is away and another stands in, that is said.
 */
import type { Page } from '@playwright/test';

import {
  expect,
  filesContaining,
  launchApp,
  type LaunchedApp,
  test,
  waitForCore,
} from './support/app';
import {
  courseCard,
  createCourse,
  expectNoAccessibilityViolations,
  openCourseTab,
  screenshot,
  showNarrationAsText,
} from './support/courses';
import { type FakeProvider, HANG, startFakeProvider } from './support/fake-provider';

/** Recognisable fake keys. Each only ever reaches a server on this computer. */
const AIHUBMIX_KEY = 'sk-e2e-not-a-real-key-7Hq2mZx94Wd1';
const NVIDIA_KEY = 'nvapi-e2e-not-a-real-key-Qm81xTz5Lp2k';

const AIHUBMIX = 'AIHubMix (custom endpoint 127.0.0.1)';
const NVIDIA = 'NVIDIA NIM (custom endpoint 127.0.0.1)';
const KIMI = 'moonshotai/kimi-k3.1-pro';
const MISTRAL = 'mistralai/mistral-large-4-1t-a52b';

interface Servers {
  aihubmix: FakeProvider;
  nvidia: FakeProvider;
}

const endpoints = (servers: Servers): Record<string, string> => ({
  ADLE_PROVIDER_ENDPOINTS: JSON.stringify({
    aihubmix: servers.aihubmix.baseUrl,
    nvidia: servers.nvidia.baseUrl,
  }),
});

async function launch(profileDir: string, servers: Servers, first = true): Promise<LaunchedApp> {
  const adle = await launchApp(
    profileDir,
    first
      ? { onboarded: true, theme: 'light', env: endpoints(servers) }
      : { env: endpoints(servers) },
  );
  await waitForCore(adle.page);
  return adle;
}

/** The card of one provider in the list of providers. */
const card = (page: Page, name: string) =>
  page
    .getByRole('list', { name: 'AI providers' })
    .getByRole('listitem')
    .filter({ has: page.getByRole('heading', { name, exact: true }) });

const keyStates = (page: Page) => page.evaluate(() => window.adle!.provider.keyState());

const providerStatus = async (
  page: Page,
): Promise<{
  provider_id: string;
  providers: { provider_id: string; key_configured: boolean }[];
}> => {
  const result = await page.evaluate(() => window.adle!.core.invoke('provider.status'));
  if (!result.ok) throw new Error(result.error.message);
  return result.data as never;
};

test.describe('choosing between AI providers', () => {
  test('choose NVIDIA, give it its own key, and have it write: only NVIDIA is sent anything, and a stand-in is said', async ({
    profileDir,
  }) => {
    test.setTimeout(240_000);
    const servers: Servers = {
      aihubmix: await startFakeProvider(),
      nvidia: await startFakeProvider(),
    };
    const adle = await launch(profileDir, servers);
    const { page } = adle;
    await showNarrationAsText(page);

    // ---- Both providers are shown, with where each is and what each asks ----
    await page.getByRole('button', { name: 'Settings' }).click();
    await expect(card(page, AIHUBMIX)).toContainText('In use');
    await expect(card(page, NVIDIA)).not.toContainText('In use');
    await expect(card(page, NVIDIA)).toContainText(servers.nvidia.baseUrl);
    // The models, in the order they are asked, and what that order means.
    await expect(card(page, NVIDIA).getByRole('list').getByRole('listitem')).toHaveText([
      /Kimi K3\.1 Pro\s*moonshotai\/kimi-k3\.1-pro/,
      /Mistral Large 4\s*mistralai\/mistral-large-4-1t-a52b/,
      /GLM 5\.3 Flash\s*z-ai\/glm-5\.3-flash/,
    ]);
    await expect(card(page, NVIDIA)).toContainText(
      'Requests go to Kimi K3.1 Pro. While it is not available, Mistral Large 4 and GLM 5.3 ' +
        'Flash stand in, in that order, and Adle tells you when that happened.',
    );
    await expect(card(page, AIHUBMIX).getByRole('button')).toHaveAttribute('aria-pressed', 'true');
    await expect(card(page, NVIDIA).getByRole('button')).toHaveAttribute('aria-pressed', 'false');
    await expectNoAccessibilityViolations(page);
    await screenshot(page, 'settings-provider-choice');

    // ---- A key for the provider in use ----
    await page.getByLabel('API key', { exact: true }).fill(AIHUBMIX_KEY);
    await page.getByRole('button', { name: 'Save key' }).click();
    await expect(page.getByText('Saved · ends in 4Wd1')).toBeVisible();
    await expect(card(page, AIHUBMIX)).toContainText('Key saved');
    await expect(card(page, NVIDIA)).toContainText('No key yet');

    // ---- Choosing NVIDIA: it is in use from now on, and it has no key of its own yet ----
    await card(page, NVIDIA)
      .getByRole('button', { name: `Use ${NVIDIA}` })
      .click();
    await expect(page.getByRole('status').filter({ hasText: `Now using ${NVIDIA}` })).toContainText(
      'Add its key below',
    );
    await expect(card(page, NVIDIA)).toContainText('In use');
    await expect(card(page, AIHUBMIX)).not.toContainText('In use');
    await expect(card(page, NVIDIA).getByRole('button')).toHaveAttribute('aria-pressed', 'true');
    // The other provider's key did not come along: this one starts empty.
    await expect(page.getByText(`${NVIDIA} key`, { exact: true })).toBeVisible();
    await expect(page.getByText('Not set', { exact: true })).toBeVisible();
    await expect(page.getByLabel('API key', { exact: true })).toHaveValue('');
    expect((await providerStatus(page)).provider_id).toBe('nvidia');

    await page.getByLabel('API key', { exact: true }).fill(NVIDIA_KEY);
    await page.getByRole('button', { name: 'Save key' }).click();
    await expect(page.getByText('Saved · ends in Lp2k')).toBeVisible();
    expect(await keyStates(page)).toEqual({
      aihubmix: { stored: true, hint: '4Wd1' },
      nvidia: { stored: true, hint: 'Lp2k' },
    });

    // The limits shown are said to be Adle's own: this provider publishes none.
    await expect(page.getByText('0 of 200', { exact: true })).toBeVisible();
    await expect(page.getByText(/does not publish a daily limit for these models/)).toBeVisible();
    await expectNoAccessibilityViolations(page);
    await screenshot(page, 'settings-providers');

    // ---- Ask for suggestions. The first model is away; the second is slow to answer ----
    await page.getByRole('button', { name: 'Library', exact: true }).click();
    await createCourse(page, 'Calculus refresher', { topic: 'Limits and derivatives.' });
    servers.nvidia.queue({ status: 404 }, HANG);
    await page.getByRole('button', { name: 'Suggest concepts with AI' }).click();
    const ask = page.getByRole('dialog', { name: 'Ask the AI for concepts?' });
    // Where it will go is said before anything is sent.
    await expect(ask).toContainText(NVIDIA);
    await ask.getByRole('button', { name: 'Send and suggest' }).click();

    // Said while it happens, not only afterwards.
    await expect(
      page.getByText(
        'Kimi K3.1 Pro is not available at the moment. Asking Mistral Large 4 instead',
      ),
    ).toBeVisible({ timeout: 30_000 });

    // ---- The provider cannot be changed under work that is under way ----
    await page.getByRole('button', { name: 'Settings' }).click();
    await card(page, AIHUBMIX)
      .getByRole('button', { name: `Use ${AIHUBMIX}` })
      .click();
    const refused = page.getByRole('alert').filter({ hasText: 'The provider was not changed' });
    await expect(refused).toContainText(`${NVIDIA} is writing something for you at the moment.`);
    await expect(card(page, NVIDIA)).toContainText('In use');
    expect((await providerStatus(page)).provider_id).toBe('nvidia');

    // ---- The answer arrives; who wrote it, and for whom, is said ----
    servers.nvidia.release();
    await page.getByRole('button', { name: 'Library', exact: true }).click();
    await courseCard(page, /Calculus refresher/).click();
    await openCourseTab(page, 'Curriculum');
    const waiting = page.getByText(/suggested 3 concepts for this course/);
    await expect(waiting).toBeVisible({ timeout: 30_000 });
    await expect(waiting).toContainText(`Mistral Large 4 on ${NVIDIA} suggested 3 concepts`);
    await page.getByRole('button', { name: 'Review suggestions' }).click();
    const review = page.getByRole('dialog', { name: 'Suggested concepts' });
    await expect(review).toContainText(`Suggested by Mistral Large 4 on ${NVIDIA}`);
    await expect(review).toContainText(
      'Kimi K3.1 Pro was not available, so Mistral Large 4 wrote this in its place.',
    );
    await expectNoAccessibilityViolations(page);
    await screenshot(page, 'providers-stand-in');

    // ---- What actually went where ----
    // Nothing at all went to the provider that was not chosen, with any key.
    expect(servers.aihubmix.requests).toHaveLength(0);
    // NVIDIA was asked twice: the model that was away, then the next. Each time with
    // NVIDIA's key, and never with the other one.
    expect(servers.nvidia.requests.map((request) => request.body.model)).toEqual([KIMI, MISTRAL]);
    expect(servers.nvidia.requests.map((request) => request.authorization)).toEqual([
      `Bearer ${NVIDIA_KEY}`,
      `Bearer ${NVIDIA_KEY}`,
    ]);
    // Each model was sent only the fields its own reference lists.
    const [toKimi, toMistral] = servers.nvidia.requests.map((request) => request.body);
    expect(Object.keys(toKimi!).sort()).toEqual([
      'max_tokens',
      'messages',
      'model',
      'reasoning_effort',
      'stream',
      'stream_options',
    ]);
    expect(toKimi!.reasoning_effort).toBe('low');
    expect(Object.keys(toMistral!).sort()).toEqual([
      'max_tokens',
      'messages',
      'model',
      'reasoning_effort',
      'stream',
    ]);

    await review.getByRole('button', { name: 'Add 3 concepts' }).click();
    await expect(review).toBeHidden();

    // Neither key is anywhere on disk in the clear.
    expect(filesContaining(profileDir, NVIDIA_KEY)).toEqual([]);
    expect(filesContaining(profileDir, AIHUBMIX_KEY)).toEqual([]);
    expect(adle.problems).toEqual([]);
    await adle.close();

    // ---- The choice and both keys are still there after a restart ----
    const again = await launch(profileDir, servers, false);
    await expect
      .poll(async () => providerStatus(again.page))
      .toMatchObject({
        provider_id: 'nvidia',
        providers: [
          { provider_id: 'aihubmix', key_configured: true },
          { provider_id: 'nvidia', key_configured: true },
        ],
      });
    await again.page.getByRole('button', { name: 'Settings' }).click();
    await expect(card(again.page, NVIDIA)).toContainText('In use');
    await expect(again.page.getByText('Saved · ends in Lp2k')).toBeVisible();
    // Both requests were counted, for this provider, and survived the restart.
    await expect(again.page.getByText('2 of 200', { exact: true })).toBeVisible();
    // Starting again sent nothing to anyone.
    expect(servers.aihubmix.requests).toHaveLength(0);
    expect(servers.nvidia.requests).toHaveLength(2);
    expect(again.problems).toEqual([]);
    await again.close();
    expect(filesContaining(profileDir, NVIDIA_KEY)).toEqual([]);

    await servers.aihubmix.close();
    await servers.nvidia.close();
  });

  test('a key is handed over only for the address it was saved for', async ({ profileDir }) => {
    test.setTimeout(120_000);
    const servers: Servers = {
      aihubmix: await startFakeProvider(),
      nvidia: await startFakeProvider(),
    };
    const first = await launch(profileDir, servers);
    await first.page.getByRole('button', { name: 'Settings' }).click();
    await card(first.page, NVIDIA)
      .getByRole('button', { name: `Use ${NVIDIA}` })
      .click();
    await expect(card(first.page, NVIDIA)).toContainText('In use');
    await first.page.getByLabel('API key', { exact: true }).fill(NVIDIA_KEY);
    await first.page.getByRole('button', { name: 'Save key' }).click();
    await expect(first.page.getByText('Saved · ends in Lp2k')).toBeVisible();
    await first.close();

    // The same profile, but "NVIDIA" is now somewhere else.
    const elsewhere = await startFakeProvider();
    const moved = await launch(
      profileDir,
      { aihubmix: servers.aihubmix, nvidia: elsewhere },
      false,
    );
    // The key that was typed for the first address is not given to the second: not to
    // the core, and so never to that server.
    await expect
      .poll(async () => providerStatus(moved.page))
      .toMatchObject({
        provider_id: 'nvidia',
        providers: [{ provider_id: 'aihubmix' }, { provider_id: 'nvidia', key_configured: false }],
      });
    expect(await keyStates(moved.page)).toMatchObject({ nvidia: { stored: false, hint: null } });
    await moved.page.getByRole('button', { name: 'Settings' }).click();
    await expect(moved.page.getByText('Not set', { exact: true })).toBeVisible();
    await moved.close();

    // Back where it was saved for, it is there again: it was kept, not thrown away.
    const back = await launch(profileDir, servers, false);
    await expect
      .poll(async () => providerStatus(back.page))
      .toMatchObject({
        providers: [{ provider_id: 'aihubmix' }, { provider_id: 'nvidia', key_configured: true }],
      });
    expect(await keyStates(back.page)).toMatchObject({ nvidia: { stored: true, hint: 'Lp2k' } });
    await back.close();

    for (const server of [servers.aihubmix, servers.nvidia, elsewhere]) {
      expect(server.requests).toHaveLength(0);
      await server.close();
    }
  });

  test('the page can name a provider, and can never say where a key goes', async ({ adle }) => {
    const { page } = adle;
    await waitForCore(page);
    const outcomes = await page.evaluate(async (key) => {
      const provider = window.adle!.provider as unknown as Record<
        string,
        (...args: unknown[]) => Promise<{ ok: boolean; error?: { code: string } }>
      >;
      const code = async (run: () => Promise<{ ok: boolean; error?: { code: string } }>) => {
        const result = await run();
        return result.ok ? 'accepted' : (result.error?.code ?? 'failed');
      };
      return {
        unknownName: await code(() => provider.select!('openai')),
        anAddress: await code(() => provider.select!('https://attacker.example/v1')),
        notText: await code(() => provider.select!({ provider_id: 'nvidia' })),
        // A provider Adle keeps keys for, which this installation does not offer.
        notOffered: await code(() => provider.select!('custom')),
        keyForUnknown: await code(() => provider.setApiKey!('openai', key)),
        keyWithAnAddress: await code(() =>
          provider.setApiKey!('nvidia', key, 'https://attacker.example/v1'),
        ),
        clearUnknown: await code(() => provider.clearApiKey!('https://attacker.example/v1')),
      };
    }, NVIDIA_KEY);
    expect(outcomes).toEqual({
      unknownName: 'invalid_request',
      anAddress: 'invalid_request',
      notText: 'invalid_request',
      notOffered: 'provider_unknown',
      keyForUnknown: 'invalid_request',
      // The extra argument is not part of the bridge: it is dropped, and the key is kept
      // for the provider's own address, which is the only place it can be sent.
      keyWithAnAddress: 'accepted',
      clearUnknown: 'invalid_request',
    });
    // Nothing above changed the provider in use.
    expect((await providerStatus(page)).provider_id).toBe('aihubmix');
    expect(await keyStates(page)).toEqual({
      aihubmix: { stored: false, hint: null },
      nvidia: { stored: true, hint: 'Lp2k' },
    });
    await page.evaluate(() => window.adle!.provider.clearApiKey('nvidia'));
    expect(await keyStates(page)).toMatchObject({ nvidia: { stored: false, hint: null } });
  });
});
