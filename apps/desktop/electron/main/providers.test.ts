/**
 * What a freshly started core is given: the key stored for each of its providers at its
 * address, and the learner's choice of provider. The journey through the real app is in
 * `e2e/providers.spec.ts`; these are the cases it would take several launches to reach.
 */
import { mkdtempSync, rmSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { OPERATIONS } from '@adle/contracts';

import type { CoreResult } from '../shared/ipc';
import { type Encryptor, ProviderKeyStore } from './secrets';

const client = vi.hoisted(() => ({ callCore: vi.fn() }));
vi.mock('./core/client', () => ({ callCore: client.callCore }));

const { ProviderChoiceNotAppliedError, syncProviders } = await import('./providers');

const AIHUBMIX = 'https://aihubmix.com/v1';
const NVIDIA = 'https://integrate.api.nvidia.com/v1';
const CONNECTION = { baseUrl: 'http://127.0.0.1:1', token: 't'.repeat(64) };
const core = { getConnection: () => CONNECTION };

/** A reversible stand-in for the OS credential facility. */
const encryptor: Encryptor = {
  isEncryptionAvailable: () => true,
  encryptString: (text) => Buffer.from(text, 'utf8').reverse(),
  decryptString: (buffer) => Buffer.from(buffer).reverse().toString('utf8'),
};

let directory: string;
let keyStore: ProviderKeyStore;

/** What the core was sent after being asked which providers there are. */
const sent = (): [unknown, unknown][] =>
  client.callCore.mock.calls
    .filter(([, operation]) => operation !== OPERATIONS['provider.status'])
    .map(([, operation, params]) => [operation, (params as { body?: unknown }).body]);

/** What the core offers, and what it is going by: "auto" until it is told otherwise. */
function coreOffers(
  providers: { provider_id: string; base_url: string }[] | null,
  selection = 'auto',
  refusing: unknown = null,
): void {
  client.callCore.mockImplementation((_connection: unknown, operation: unknown) => {
    const refused: CoreResult = {
      ok: false,
      error: { code: 'conflict', message: 'Something is being written right now.', status: 409 },
    };
    const result: CoreResult =
      operation === refusing
        ? refused
        : operation !== OPERATIONS['provider.status']
          ? { ok: true, data: null }
          : providers
            ? { ok: true, data: { providers, selection } }
            : { ok: false, error: { code: 'core_unavailable', message: 'starting', status: 0 } };
    return Promise.resolve(result);
  });
}

beforeEach(() => {
  directory = mkdtempSync(path.join(os.tmpdir(), 'adle-providers-test-'));
  keyStore = new ProviderKeyStore(encryptor, path.join(directory, 'credentials.bin'));
  client.callCore.mockReset();
});

afterEach(() => {
  rmSync(directory, { recursive: true, force: true });
});

describe('syncProviders', () => {
  const both = [
    { provider_id: 'aihubmix', base_url: AIHUBMIX },
    { provider_id: 'nvidia', base_url: NVIDIA },
  ];

  it('hands over the choice of provider first, and then each provider its own key, named', async () => {
    keyStore.save('aihubmix', AIHUBMIX, 'sk-aihubmix-key-1111');
    keyStore.save('nvidia', NVIDIA, 'nvapi-nvidia-key-2222');
    keyStore.select('nvidia');
    coreOffers(both);

    await syncProviders({ core, keyStore });

    // A core starts on "automatic". With the keys first it would be free, for a moment,
    // to use a provider the learner chose not to.
    expect(sent()).toEqual([
      [OPERATIONS['provider.select'], { selection: 'nvidia' }],
      [
        OPERATIONS['provider.set_credential'],
        { api_key: 'sk-aihubmix-key-1111', provider_id: 'aihubmix' },
      ],
      [
        OPERATIONS['provider.set_credential'],
        { api_key: 'nvapi-nvidia-key-2222', provider_id: 'nvidia' },
      ],
    ]);
  });

  it('hands over no key at all when the choice could not be applied, and says so', async () => {
    keyStore.save('aihubmix', AIHUBMIX, 'sk-aihubmix-key-1111');
    keyStore.save('nvidia', NVIDIA, 'nvapi-nvidia-key-2222');
    keyStore.select('nvidia');
    coreOffers(both, 'auto', OPERATIONS['provider.select']);

    await expect(syncProviders({ core, keyStore })).rejects.toBeInstanceOf(
      ProviderChoiceNotAppliedError,
    );

    // The core is still on "automatic", so it is left with nothing to send anywhere.
    expect(sent()).toEqual([[OPERATIONS['provider.select'], { selection: 'nvidia' }]]);
  });

  it('puts a core back on "automatic" when the learner never chose and it is on something else', async () => {
    keyStore.save('aihubmix', AIHUBMIX, 'sk-aihubmix-key-1111');
    coreOffers(both, 'nvidia');

    await syncProviders({ core, keyStore });

    expect(sent()).toEqual([
      [OPERATIONS['provider.select'], { selection: 'auto' }],
      [
        OPERATIONS['provider.set_credential'],
        { api_key: 'sk-aihubmix-key-1111', provider_id: 'aihubmix' },
      ],
    ]);
  });

  it('hands over a choice to let Adle use every provider, when the core is on one', async () => {
    keyStore.select('auto');
    coreOffers(both, 'nvidia');

    await syncProviders({ core, keyStore });

    expect(sent()).toEqual([[OPERATIONS['provider.select'], { selection: 'auto' }]]);
  });

  it('does not hand a key over for an address it was not stored for', async () => {
    keyStore.save('nvidia', NVIDIA, 'nvapi-real-key-4444');
    coreOffers([
      { provider_id: 'aihubmix', base_url: AIHUBMIX },
      // The same name, somewhere else: a developer's endpoint, or anything at all.
      { provider_id: 'nvidia', base_url: 'http://127.0.0.1:9100/v1' },
    ]);

    await syncProviders({ core, keyStore });

    expect(sent()).toEqual([]);
    // It is kept for the address it belongs to.
    expect(keyStore.load('nvidia', NVIDIA)).toBe('nvapi-real-key-4444');
  });

  it('says nothing about the choice when the learner has not made one, or the core has it', async () => {
    // Never chosen: the core starts on "automatic", and that is left as it is.
    coreOffers(both);
    await syncProviders({ core, keyStore });
    expect(sent()).toEqual([]);

    keyStore.select('aihubmix');
    coreOffers(both, 'aihubmix');
    await syncProviders({ core, keyStore });
    expect(sent()).toEqual([]);

    keyStore.select('auto');
    coreOffers(both, 'auto');
    await syncProviders({ core, keyStore });
    expect(sent()).toEqual([]);
  });

  it('keeps a choice the core does not offer, and gives the core no key to use in its place', async () => {
    keyStore.save('aihubmix', AIHUBMIX, 'sk-aihubmix-key-1111');
    keyStore.select('nvidia');
    // The learner chose NVIDIA alone; this core offers only AIHubMix.
    coreOffers([{ provider_id: 'aihubmix', base_url: AIHUBMIX }]);

    await syncProviders({ core, keyStore });

    // Not the choice (the core does not know it), and not the key of a provider they
    // did not choose: on "automatic" the core would use it.
    expect(sent()).toEqual([]);
    expect(keyStore.selected()).toBe('nvidia');
  });

  it('sends nothing when the core cannot say which providers there are', async () => {
    keyStore.save('aihubmix', AIHUBMIX, 'sk-aihubmix-key-1111');
    keyStore.select('nvidia');
    coreOffers(null);

    await syncProviders({ core, keyStore });

    expect(sent()).toEqual([]);
  });

  it('never sends a key to a provider whose name it does not know', async () => {
    keyStore.save('aihubmix', AIHUBMIX, 'sk-aihubmix-key-1111');
    coreOffers([
      { provider_id: 'openai', base_url: AIHUBMIX },
      { provider_id: 'aihubmix', base_url: 'https://aihubmix.com.attacker.example/v1' },
    ]);

    await syncProviders({ core, keyStore });

    expect(sent()).toEqual([]);
  });
});
