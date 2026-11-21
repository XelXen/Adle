/**
 * The learner's AI providers, through the whole real path (interface, main process, key
 * store, core, jobs), with two servers on this computer standing in for AIHubMix and for
 * NVIDIA. No request leaves the machine, and no test here reaches a real provider.
 *
 * What these journeys are about. The learner chooses (ADR-021, ADR-023): one provider, or
 * "automatic", which uses every provider they have given a key to, each for what it is
 * good at. Nothing else changes that choice. A key is only ever sent to the provider and
 * the address it was given for. And when what answers is not what was asked first
 * (another model, or another provider), that is said.
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
  providerCard,
  providerKeyField,
  saveProviderKey,
  screenshot,
  showNarrationAsText,
  openWhatIsSent,
  closeWhatIsSent,
} from './support/courses';
import { type FakeProvider, HANG, startFakeProvider } from './support/fake-provider';

/** Recognisable fake keys. Each only ever reaches a server on this computer. */
const AIHUBMIX_KEY = 'sk-e2e-not-a-real-key-7Hq2mZx94Wd1';
const NVIDIA_KEY = 'nvapi-e2e-not-a-real-key-Qm81xTz5Lp2k';

const AIHUBMIX = 'AIHubMix (custom endpoint 127.0.0.1)';
const NVIDIA = 'NVIDIA NIM (custom endpoint 127.0.0.1)';
const BOTH = `${AIHUBMIX}, then ${NVIDIA} if needed`;
const ULTRA = 'nvidia/nemotron-3-ultra-550b-a55b';
const SUPER = 'nvidia/nemotron-3.5-super-vl-120b-a12b';
/** "Current routing" in Settings: each kind of request, where it goes and which model writes it. */
const KINDS = ['Questions', 'Suggested concepts', 'Lessons', 'Pictures'];

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

/** The choice between "automatic" and one provider alone. */
const choice = (page: Page, name: string) =>
  page.getByRole('group', { name: 'Provider' }).getByRole('button', { name });

/** Where each kind of request would go at this moment, as the settings say. */
const routes = (page: Page) => page.getByRole('region', { name: 'Current routing' });

const keyStates = (page: Page) => page.evaluate(() => window.adle!.provider.keyState());

const providerStatus = async (
  page: Page,
): Promise<{
  provider_id: string;
  selection: string;
  providers: { provider_id: string; key_configured: boolean }[];
}> => {
  const result = await page.evaluate(() => window.adle!.core.invoke('provider.status'));
  if (!result.ok) throw new Error(result.error.message);
  return result.data as never;
};

test.describe('the AI providers', () => {
  test('choose NVIDIA alone, give it its own key, and have it write: only NVIDIA is sent anything, and a stand-in is said', async ({
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
    // Until the learner says otherwise: every provider they give a key to. There are none.
    await expect(choice(page, 'Automatic')).toHaveAttribute('aria-pressed', 'true');
    await expect(routes(page)).toContainText('No key yet. Add one below.');
    await expect(providerCard(page, AIHUBMIX)).not.toContainText('In use');
    await expect(providerCard(page, NVIDIA)).not.toContainText('In use');
    await expect(providerCard(page, NVIDIA)).toContainText(servers.nvidia.baseUrl);
    // The models, and how they are used: each for what it was measured to do best.
    await expect(providerCard(page, NVIDIA).getByRole('list').getByRole('listitem')).toHaveText([
      /Nemotron 3 Ultra\s*nvidia\/nemotron-3-ultra-550b-a55b/,
      /Nemotron 3\.5 Super\s*nvidia\/nemotron-3\.5-super-vl-120b-a12b/,
      /Kimi K3\.1 Pro\s*moonshotai\/kimi-k3\.1-pro/,
      /Mistral Large 4\s*mistralai\/mistral-large-4-1t-a52b/,
    ]);
    await expect(providerCard(page, NVIDIA)).toContainText(
      'Uses Nemotron 3 Ultra, Nemotron 3.5 Super, Kimi K3.1 Pro, and Mistral Large 4, each for ' +
        'the kind of request it was measured to do best. When one is unavailable another stands ' +
        'in, and Adle says so.',
    );
    await expectNoAccessibilityViolations(page);
    await screenshot(page, 'settings-provider-choice');

    // ---- A key for one provider: automatic is then simply that provider ----
    await saveProviderKey(page, AIHUBMIX, AIHUBMIX_KEY);
    await expect(providerCard(page, AIHUBMIX)).toContainText('In use');
    await expect(providerCard(page, NVIDIA)).toContainText('No key');
    await expect(routes(page).getByRole('term')).toHaveText(KINDS);
    for (const line of await routes(page).getByRole('definition').all()) {
      await expect(line).toHaveText(`${AIHUBMIX}Coding Kimi K3 (free)`);
    }

    // ---- Choosing NVIDIA alone: everything goes there, and it has no key of its own yet ----
    await choice(page, `${NVIDIA} only`).click();
    await expect(
      page.getByRole('status').filter({ hasText: `Using ${NVIDIA} only` }),
    ).toContainText('Add its key below');
    await expect(choice(page, `${NVIDIA} only`)).toHaveAttribute('aria-pressed', 'true');
    await expect(choice(page, 'Automatic')).toHaveAttribute('aria-pressed', 'false');
    // The other provider's key did not come along, and is no longer in use.
    await expect(providerCard(page, AIHUBMIX)).not.toContainText('In use');
    await expect(providerCard(page, NVIDIA)).not.toContainText('In use');
    await expect(routes(page)).toContainText('No key for this provider yet. Add one below.');
    await expect(providerKeyField(page, NVIDIA)).toHaveValue('');
    expect(await providerStatus(page)).toMatchObject({
      selection: 'nvidia',
      provider_id: 'nvidia',
    });

    await saveProviderKey(page, NVIDIA, NVIDIA_KEY);
    await expect(providerCard(page, NVIDIA)).toContainText('In use');
    // One provider, and each kind of request at the model measured to do it best.
    await expect(routes(page).getByRole('definition')).toHaveText([
      `${NVIDIA}Nemotron 3.5 Super`,
      `${NVIDIA}Nemotron 3 Ultra`,
      `${NVIDIA}Nemotron 3 Ultra`,
      `${NVIDIA}Kimi K3.1 Pro`,
    ]);
    expect(await keyStates(page)).toEqual({
      aihubmix: { stored: true, hint: '4Wd1' },
      nvidia: { stored: true, hint: 'Lp2k' },
    });
    // Having keys for both and using one is a choice; the other way is offered, not taken.
    await expect(page.getByText('You have keys for both providers')).toBeVisible();

    // The limits shown are said to be Adle's own: this provider publishes none.
    await expect(providerCard(page, NVIDIA).getByText('0 of 200', { exact: true })).toBeVisible();
    await expect(providerCard(page, NVIDIA)).toContainText(
      'publishes no daily limit, so this is Adle’s own cap.',
    );
    await expectNoAccessibilityViolations(page);
    await screenshot(page, 'settings-providers');

    // ---- Ask for suggestions. The first model is away; the second is slow to answer ----
    await page.getByRole('button', { name: 'Library', exact: true }).click();
    await createCourse(page, 'Calculus refresher', { topic: 'Limits and derivatives.' });
    servers.nvidia.queue({ status: 404 }, HANG);
    // Where it will go can be read before anything is sent: one provider, and no "or".
    const sent = await openWhatIsSent(page);
    await expect(sent).toContainText(`to ${NVIDIA}.`);
    await expect(sent).not.toContainText(AIHUBMIX);
    await closeWhatIsSent(page);
    expect(servers.nvidia.requests).toHaveLength(0);
    await page.getByRole('button', { name: 'Suggest concepts with AI' }).click();

    // Said while it happens, not only afterwards.
    await expect(
      page.getByText(
        'Nemotron 3 Ultra isn’t available right now. Asking Nemotron 3.5 Super instead',
      ),
    ).toBeVisible({ timeout: 30_000 });

    // ---- The choice cannot be changed under work that is under way ----
    await page.getByRole('button', { name: 'Settings' }).click();
    await choice(page, `${AIHUBMIX} only`).click();
    const refused = page.getByRole('alert').filter({ hasText: 'Couldn’t change the provider' });
    await expect(refused).toContainText('Something is being written right now.');
    await expect(choice(page, `${NVIDIA} only`)).toHaveAttribute('aria-pressed', 'true');
    expect((await providerStatus(page)).selection).toBe('nvidia');

    // ---- The answer arrives; who wrote it, and for whom, is said ----
    servers.nvidia.release();
    await page.getByRole('button', { name: 'Library', exact: true }).click();
    await courseCard(page, /Calculus refresher/).click();
    await openCourseTab(page, 'Curriculum');
    const waiting = page.getByText(/suggested 3 concepts\. Nothing is added until you choose/);
    await expect(waiting).toBeVisible({ timeout: 30_000 });
    await expect(waiting).toContainText(`Nemotron 3.5 Super on ${NVIDIA} suggested 3 concepts`);
    await page.getByRole('button', { name: 'Review suggestions' }).click();
    const review = page.getByRole('dialog', { name: 'Suggested concepts' });
    await expect(review).toContainText(`Suggested by Nemotron 3.5 Super on ${NVIDIA}`);
    await expect(review).toContainText(
      'Nemotron 3 Ultra wasn’t available, so Nemotron 3.5 Super wrote this instead.',
    );
    await expectNoAccessibilityViolations(page);
    await screenshot(page, 'providers-stand-in');

    // ---- What actually went where ----
    // Nothing at all went to the provider that was not chosen, with any key.
    expect(servers.aihubmix.requests).toHaveLength(0);
    // NVIDIA was asked twice: the model that was away, then the next. Each time with
    // NVIDIA's key, and never with the other one.
    expect(servers.nvidia.requests.map((request) => request.body.model)).toEqual([ULTRA, SUPER]);
    expect(servers.nvidia.requests.map((request) => request.authorization)).toEqual([
      `Bearer ${NVIDIA_KEY}`,
      `Bearer ${NVIDIA_KEY}`,
    ]);
    // Each model was sent only the fields it was measured with: the ones every request has.
    for (const body of servers.nvidia.requests.map((request) => request.body)) {
      expect(Object.keys(body).sort()).toEqual(['max_tokens', 'messages', 'model', 'stream']);
    }

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
        selection: 'nvidia',
        provider_id: 'nvidia',
        providers: [
          { provider_id: 'aihubmix', key_configured: true },
          { provider_id: 'nvidia', key_configured: true },
        ],
      });
    await again.page.getByRole('button', { name: 'Settings' }).click();
    await expect(choice(again.page, `${NVIDIA} only`)).toHaveAttribute('aria-pressed', 'true');
    await expect(providerCard(again.page, NVIDIA)).toContainText('Key saved · ends in Lp2k');
    // Both requests were counted, for this provider, and survived the restart.
    await expect(
      providerCard(again.page, NVIDIA).getByText('2 of 200', { exact: true }),
    ).toBeVisible();
    // Starting again sent nothing to anyone.
    expect(servers.aihubmix.requests).toHaveLength(0);
    expect(servers.nvidia.requests).toHaveLength(2);
    expect(again.problems).toEqual([]);
    await again.close();
    expect(filesContaining(profileDir, NVIDIA_KEY)).toEqual([]);

    await servers.aihubmix.close();
    await servers.nvidia.close();
  });

  test('with keys for both, each is used for what it is best at, a key can be checked, and a provider that stands in is said', async ({
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
    await page.getByRole('button', { name: 'Settings' }).click();

    // ---- Two keys, and the choice left at "automatic": where each kind of request goes ----
    await saveProviderKey(page, AIHUBMIX, AIHUBMIX_KEY);
    await saveProviderKey(page, NVIDIA, NVIDIA_KEY);
    await expect(choice(page, 'Automatic')).toHaveAttribute('aria-pressed', 'true');
    await expect(providerCard(page, AIHUBMIX)).toContainText('In use');
    await expect(providerCard(page, NVIDIA)).toContainText('In use');
    // Said before anything is sent, with the reason: AIHubMix's model for code draws the
    // pictures; NVIDIA writes everything else, each kind with its own model.
    const writes = `${NVIDIA}, then ${AIHUBMIX} if needed`;
    await expect(routes(page).getByRole('term')).toHaveText(KINDS);
    const lines = routes(page).getByRole('definition');
    for (const [index, model] of [
      'Nemotron 3.5 Super',
      'Nemotron 3 Ultra',
      'Nemotron 3 Ultra',
    ].entries()) {
      await expect(lines.nth(index)).toContainText(writes);
      await expect(lines.nth(index)).toContainText(model);
      await expect(lines.nth(index)).toContainText(
        `${NVIDIA} writes this, and ${AIHUBMIX} is kept for the pictures.`,
      );
    }
    await expect(lines.nth(3)).toContainText(BOTH);
    await expect(lines.nth(3)).toContainText('Coding Kimi K3 (free)');
    await expect(lines.nth(3)).toContainText(
      `${AIHUBMIX} draws the pictures: its model is made for code.`,
    );
    await expect(providerCard(page, AIHUBMIX)).toContainText(
      'With “Automatic”, draws the pictures: its model is made for code. A small daily allowance.',
    );
    await expect(providerCard(page, NVIDIA)).toContainText(
      'With “Automatic”, writes lessons, suggested concepts and answers.',
    );
    // Already on automatic, so there is nothing to suggest.
    await expect(page.getByText('You have keys for both providers')).toHaveCount(0);
    await expectNoAccessibilityViolations(page);
    await screenshot(page, 'settings-providers-automatic');

    // ---- Checking a key: one word from that provider, and from no other ----
    await providerCard(page, NVIDIA).getByRole('button', { name: 'Test key' }).click();
    await expect(providerCard(page, NVIDIA).getByRole('status')).toContainText(
      /The key works\. Nemotron 3\.5 Super answered in /,
      { timeout: 30_000 },
    );
    expect(servers.nvidia.requests.map((request) => request.kind)).toEqual(['check']);
    expect(servers.nvidia.requests[0]?.authorization).toBe(`Bearer ${NVIDIA_KEY}`);
    // Nothing of the learner's is in a check.
    expect(servers.nvidia.requests[0]?.prompt).toBe(
      'You are checking that a connection works.\nReply with the single word "ready".',
    );
    expect(servers.aihubmix.requests).toHaveLength(0);
    // It counted as one of today's requests there.
    await expect(providerCard(page, NVIDIA).getByText('1 of 200', { exact: true })).toBeVisible();

    // A key the provider does not accept is said in words, and only that provider is asked.
    servers.aihubmix.queue({ status: 401 });
    await providerCard(page, AIHUBMIX).getByRole('button', { name: 'Test key' }).click();
    await expect(
      page.getByRole('alert').filter({ hasText: `The ${AIHUBMIX} key test failed` }),
    ).toBeVisible({ timeout: 30_000 });
    expect(servers.aihubmix.requests.map((request) => request.kind)).toEqual(['check']);
    expect(servers.nvidia.requests).toHaveLength(1);
    // What the check found is not found out again at the cost of another request: a
    // provider whose key was refused is asked second from now on, even for the pictures it
    // would draw, and the settings say why.
    const afterwards = `${NVIDIA}, then ${AIHUBMIX} if needed`;
    await expect(lines.nth(3)).toContainText(afterwards);
    await expect(lines.nth(3)).toContainText(
      `${AIHUBMIX} couldn’t answer earlier, so it’s paused for now.`,
    );

    // ---- Suggestions: the first provider fails; the other writes, and that is said ----
    await page.getByRole('button', { name: 'Library', exact: true }).click();
    await createCourse(page, 'Calculus refresher', { topic: 'Limits and derivatives.' });
    // Both are named before anything is sent: it never goes anywhere that was not said.
    const both = await openWhatIsSent(page);
    await expect(both).toContainText(`to ${afterwards}.`);
    await closeWhatIsSent(page);
    // None of the four NVIDIA models that write suggestions answers.
    servers.nvidia.queue({ status: 500 }, { status: 500 }, { status: 500 }, { status: 500 });
    await page.getByRole('button', { name: 'Suggest concepts with AI' }).click();

    // The learner stayed where they were, so the suggestions open by themselves when they
    // arrive, and say who wrote them and for whom.
    const review = page.getByRole('dialog', { name: 'Suggested concepts' });
    await expect(review).toBeVisible({ timeout: 60_000 });
    await expect(review).toContainText(`Suggested by Coding Kimi K3 (free) on ${AIHUBMIX}`);
    await expect(review).toContainText(`${NVIDIA} couldn’t answer, so ${AIHUBMIX} wrote this.`);
    await expectNoAccessibilityViolations(page);
    await screenshot(page, 'providers-other-provider-stood-in');
    await review.getByRole('button', { name: 'Add 3 concepts' }).click();
    await expect(review).toBeHidden();

    // ---- What actually went where, and with which key ----
    // NVIDIA: the check, then the suggestions, asked of each of its models in turn.
    expect(servers.nvidia.requests.map((request) => request.kind)).toEqual([
      'check',
      'curriculum',
      'curriculum',
      'curriculum',
      'curriculum',
    ]);
    // AIHubMix: the check that was refused, then the suggestions it wrote in the other's place.
    expect(servers.aihubmix.requests.map((request) => request.kind)).toEqual([
      'check',
      'curriculum',
    ]);
    for (const request of servers.nvidia.requests) {
      expect(request.authorization).toBe(`Bearer ${NVIDIA_KEY}`);
    }
    for (const request of servers.aihubmix.requests) {
      expect(request.authorization).toBe(`Bearer ${AIHUBMIX_KEY}`);
    }

    expect(filesContaining(profileDir, NVIDIA_KEY)).toEqual([]);
    expect(filesContaining(profileDir, AIHUBMIX_KEY)).toEqual([]);
    expect(adle.problems).toEqual([]);
    await adle.close();

    // ---- "Automatic" is what the learner left it at, and it is still that after a restart ----
    const again = await launch(profileDir, servers, false);
    await expect
      .poll(async () => providerStatus(again.page))
      .toMatchObject({
        selection: 'auto',
        providers: [
          { provider_id: 'aihubmix', key_configured: true },
          { provider_id: 'nvidia', key_configured: true },
        ],
      });
    expect(again.problems).toEqual([]);
    await again.close();

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
    await saveProviderKey(first.page, NVIDIA, NVIDIA_KEY);
    await expect(providerCard(first.page, NVIDIA)).toContainText('In use');
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
        providers: [{ provider_id: 'aihubmix' }, { provider_id: 'nvidia', key_configured: false }],
      });
    expect(await keyStates(moved.page)).toMatchObject({ nvidia: { stored: false, hint: null } });
    await moved.page.getByRole('button', { name: 'Settings' }).click();
    await expect(providerCard(moved.page, NVIDIA)).toContainText('No key');
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
        almostAutomatic: await code(() => provider.select!('AUTO')),
        // A provider Adle keeps keys for, which this installation does not offer.
        notOffered: await code(() => provider.select!('custom')),
        keyForUnknown: await code(() => provider.setApiKey!('openai', key)),
        keyForAutomatic: await code(() => provider.setApiKey!('auto', key)),
        keyWithAnAddress: await code(() =>
          provider.setApiKey!('nvidia', key, 'https://attacker.example/v1'),
        ),
        clearUnknown: await code(() => provider.clearApiKey!('https://attacker.example/v1')),
        // The one choice that is not a provider's name.
        automatic: await code(() => provider.select!('auto')),
      };
    }, NVIDIA_KEY);
    expect(outcomes).toEqual({
      unknownName: 'invalid_request',
      anAddress: 'invalid_request',
      notText: 'invalid_request',
      almostAutomatic: 'invalid_request',
      notOffered: 'provider_unknown',
      keyForUnknown: 'invalid_request',
      // "Automatic" is a choice, never somewhere a key can be kept for.
      keyForAutomatic: 'invalid_request',
      // The extra argument is not part of the bridge: it is dropped, and the key is kept
      // for the provider's own address, which is the only place it can be sent.
      keyWithAnAddress: 'accepted',
      clearUnknown: 'invalid_request',
      automatic: 'accepted',
    });
    // Nothing that was refused changed the choice.
    expect((await providerStatus(page)).selection).toBe('auto');
    expect(await keyStates(page)).toEqual({
      aihubmix: { stored: false, hint: null },
      nvidia: { stored: true, hint: 'Lp2k' },
    });
    await page.evaluate(() => window.adle!.provider.clearApiKey('nvidia'));
    expect(await keyStates(page)).toMatchObject({ nvidia: { stored: false, hint: null } });
  });
});
