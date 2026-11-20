import { OPERATIONS } from '@adle/contracts';

import { PROVIDER_AUTOMATIC, type ProviderId, type ProviderSelection } from '../shared/ipc';
import { callCore } from './core/client';
import type { CoreProcess } from './core/process';
import { parseProviderId, parseSelection, type ProviderKeyStore } from './secrets';

/** One provider as the core describes it: its name, and where its key would be sent. */
export interface KnownProvider {
  id: ProviderId;
  /** The provider's base address. A key is stored and handed over for exactly this. */
  address: string;
}

/** What the core says about its providers. */
export interface KnownProviders {
  providers: KnownProvider[];
  /** What the core is going by at the moment: one provider, or "automatic". */
  selection: ProviderSelection | null;
}

/**
 * Read the list of providers out of the core's `provider.status`.
 *
 * The core is the one that knows where each provider is: the page is never asked, and
 * neither is anything a document or a model wrote. A provider whose name is not one
 * Adle keeps keys for is left out, so no key can be stored or sent for it.
 */
export function parseProviders(status: unknown): KnownProviders | null {
  if (typeof status !== 'object' || status === null) return null;
  const { providers, selection } = status as { providers?: unknown; selection?: unknown };
  if (!Array.isArray(providers)) return null;
  const known: KnownProvider[] = [];
  for (const entry of providers) {
    if (typeof entry !== 'object' || entry === null) continue;
    const { provider_id: name, base_url: address } = entry as Record<string, unknown>;
    const id = parseProviderId(name);
    if (!id || typeof address !== 'string' || !/^https?:\/\//.test(address)) continue;
    if (known.some((provider) => provider.id === id)) continue;
    known.push({ id, address });
  }
  return { providers: known, selection: parseSelection(selection) };
}

/** Ask the core which providers it offers, and where each one's key would be sent. */
export async function readProviders(
  core: Pick<CoreProcess, 'getConnection'>,
): Promise<KnownProviders | null> {
  const status = await callCore(core.getConnection(), OPERATIONS['provider.status']);
  return status.ok ? parseProviders(status.data) : null;
}

/**
 * Give a freshly started core what it does not keep itself: the key stored for each of
 * its providers, and what the learner chose.
 *
 * A key is handed over only for the provider and the address it was stored for, so the
 * core is never given a key for somewhere else. A choice of one provider is handed over
 * only if the core offers that provider; it is never replaced by another because of
 * that. A learner who has never chosen is left with what the core starts with:
 * "automatic", which with one key is simply that provider.
 */
export async function syncProviders(deps: {
  core: Pick<CoreProcess, 'getConnection'>;
  keyStore: Pick<ProviderKeyStore, 'load' | 'selected'>;
}): Promise<void> {
  const known = await readProviders(deps.core);
  if (!known) return;
  const { providers } = known;
  for (const provider of providers) {
    const key = deps.keyStore.load(provider.id, provider.address);
    if (!key) continue;
    await callCore(deps.core.getConnection(), OPERATIONS['provider.set_credential'], {
      body: { api_key: key, provider_id: provider.id },
    });
  }
  const chosen = deps.keyStore.selected();
  if (!chosen || chosen === known.selection) return;
  // A choice the core does not offer (a developer's other endpoint) is kept, and not used.
  const offered =
    chosen === PROVIDER_AUTOMATIC || providers.some((provider) => provider.id === chosen);
  if (offered) {
    await callCore(deps.core.getConnection(), OPERATIONS['provider.select'], {
      body: { selection: chosen },
    });
  }
}
