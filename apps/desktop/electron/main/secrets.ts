import { mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import path from 'node:path';

import {
  PROVIDER_AUTOMATIC,
  PROVIDER_IDS,
  type ProviderId,
  type ProviderKeyState,
  type ProviderSelection,
} from '../shared/ipc';

/** The subset of Electron's `safeStorage` this module needs; injectable for tests. */
export interface Encryptor {
  isEncryptionAvailable(): boolean;
  encryptString(plainText: string): Buffer;
  decryptString(encrypted: Buffer): string;
}

/** The parts of Electron's `safeStorage` needed to decide whether it is really secure. */
export interface SafeStorageLike extends Encryptor {
  /** Linux only: which secret store backs the encryption. */
  getSelectedStorageBackend?: () => string;
}

/**
 * Wrap `safeStorage` so that "available" means "actually protected".
 *
 * On Linux without a keyring, Electron falls back to the `basic_text` backend,
 * which encrypts with a hard-coded password. That is plaintext in effect, so it
 * is treated as unavailable and Adle refuses to store the key.
 */
export function createSecureEncryptor(storage: SafeStorageLike, platform: string): Encryptor {
  return {
    isEncryptionAvailable: () => {
      if (!storage.isEncryptionAvailable()) return false;
      if (platform !== 'linux') return true;
      const backend = storage.getSelectedStorageBackend?.() ?? 'unknown';
      return backend !== 'basic_text' && backend !== 'unknown';
    },
    encryptString: (plainText) => storage.encryptString(plainText),
    decryptString: (encrypted) => storage.decryptString(encrypted),
  };
}

export class SecureStorageUnavailableError extends Error {
  constructor() {
    super(
      'This computer has no secure storage, so Adle can’t save the key. ' +
        'Everything except AI generation still works.',
    );
  }
}

export const MAX_API_KEY_LENGTH = 512;

/** Reject obviously malformed keys before they are stored or sent anywhere. */
export function validateApiKey(value: unknown): string {
  if (typeof value !== 'string') throw new TypeError('The API key must be text.');
  const key = value.trim();
  if (key.length < 8) throw new TypeError('That API key looks too short.');
  if (key.length > MAX_API_KEY_LENGTH) throw new TypeError('That API key is too long.');
  if (!/^[\x21-\x7e]+$/.test(key)) {
    throw new TypeError('The API key contains spaces or unsupported characters.');
  }
  return key;
}

/** A provider's name, if it is one Adle keeps keys for. Anything else is refused. */
export function parseProviderId(value: unknown): ProviderId | null {
  return typeof value === 'string' && (PROVIDER_IDS as readonly string[]).includes(value)
    ? (value as ProviderId)
    : null;
}

/** What the learner may choose: one provider Adle keeps keys for, or "automatic". */
export function parseSelection(value: unknown): ProviderSelection | null {
  return value === PROVIDER_AUTOMATIC ? PROVIDER_AUTOMATIC : parseProviderId(value);
}

/** Where the one key that earlier versions kept was sent. */
export const LEGACY_PROVIDER: { id: ProviderId; address: string } = {
  id: 'aihubmix',
  address: 'https://aihubmix.com/v1',
};

const MAX_ADDRESS_LENGTH = 300;
/** More than there could honestly be: a few providers, each at a few addresses. */
const MAX_STORED_KEYS = 24;

/** One key, whose it is, and the address it was given for. */
interface StoredKey {
  provider: ProviderId;
  address: string;
  key: string;
}

interface Stored {
  /** What the learner chose (a provider, or "automatic"), or null while they have not. */
  selected: ProviderSelection | null;
  keys: StoredKey[];
}

const NOTHING: Stored = { selected: null, keys: [] };

/** The same address however it was written: without the slash some people end one with. */
function sameAddress(address: string): string {
  return address.trim().replace(/\/+$/, '');
}

/** Read what was kept. Anything that is not exactly what this module writes is left out. */
function parseStored(plain: string): Stored | null {
  let document: unknown;
  try {
    document = JSON.parse(plain);
  } catch {
    return null;
  }
  if (typeof document !== 'object' || document === null || Array.isArray(document)) return null;
  const { version, selected, keys } = document as Record<string, unknown>;
  if (version !== 2 || !Array.isArray(keys)) return null;
  const kept: StoredKey[] = [];
  for (const entry of keys.slice(0, MAX_STORED_KEYS)) {
    if (typeof entry !== 'object' || entry === null) continue;
    const { provider, address, key } = entry as Record<string, unknown>;
    const id = parseProviderId(provider);
    if (!id || typeof address !== 'string' || !address || address.length > MAX_ADDRESS_LENGTH) {
      continue;
    }
    try {
      kept.push({ provider: id, address: sameAddress(address), key: validateApiKey(key) });
    } catch {
      // A key that could not be sent anyway is not kept.
    }
  }
  return { selected: parseSelection(selected), keys: kept };
}

/**
 * Keeps the model providers' keys, and what the learner chose (one provider, or every
 * provider they have a key for), encrypted with the operating system's credential
 * facility (DPAPI, Keychain, or libsecret via Electron safeStorage).
 *
 * A key is kept with two things: the provider it is for, and the address it was given
 * for. It is only ever handed back for that provider at that address, so a key typed
 * while the screen said one place can never be sent to another (ADR-021).
 *
 * The plaintext keys exist only in main-process memory and in the core process's
 * memory. They are never written to disk in the clear, never logged, and never sent to
 * the renderer.
 */
export class ProviderKeyStore {
  constructor(
    private readonly encryptor: Encryptor,
    private readonly file: string,
  ) {}

  isAvailable(): boolean {
    return this.encryptor.isEncryptionAvailable();
  }

  /** Everything kept, or nothing if there is none or it can no longer be decrypted. */
  private read(): Stored {
    if (!this.isAvailable()) return NOTHING;
    let plain: string;
    try {
      plain = this.encryptor.decryptString(readFileSync(this.file));
    } catch {
      // No file, or the OS key changed (new user profile, restored backup): "no key".
      return NOTHING;
    }
    if (!plain) return NOTHING;
    const stored = parseStored(plain);
    if (stored) return stored;
    // What earlier versions kept: one key and nothing else. There was one provider then.
    try {
      return {
        selected: null,
        keys: [
          {
            provider: LEGACY_PROVIDER.id,
            address: LEGACY_PROVIDER.address,
            key: validateApiKey(plain),
          },
        ],
      };
    } catch {
      return NOTHING;
    }
  }

  private write(stored: Stored): void {
    if (stored.keys.length === 0 && stored.selected === null) {
      rmSync(this.file, { force: true });
      return;
    }
    if (!this.isAvailable()) throw new SecureStorageUnavailableError();
    mkdirSync(path.dirname(this.file), { recursive: true });
    const document = JSON.stringify({ version: 2, selected: stored.selected, keys: stored.keys });
    writeFileSync(this.file, this.encryptor.encryptString(document), { mode: 0o600 });
  }

  private static without(stored: Stored, provider: ProviderId, address: string): StoredKey[] {
    const where = sameAddress(address);
    return stored.keys.filter((entry) => entry.provider !== provider || entry.address !== where);
  }

  /** Keep a key for one provider at one address, in place of the one it had there. */
  save(provider: ProviderId, address: string, apiKey: string): void {
    if (!this.isAvailable()) throw new SecureStorageUnavailableError();
    const stored = this.read();
    const keys = ProviderKeyStore.without(stored, provider, address);
    keys.push({ provider, address: sameAddress(address), key: apiKey });
    this.write({ selected: stored.selected, keys: keys.slice(-MAX_STORED_KEYS) });
  }

  /** The key kept for this provider at this address, or `null`. Never another one's. */
  load(provider: ProviderId, address: string): string | null {
    const where = sameAddress(address);
    const entry = this.read().keys.find(
      (candidate) => candidate.provider === provider && candidate.address === where,
    );
    return entry ? entry.key : null;
  }

  /** Forget the key kept for this provider at this address. The others stay. */
  clear(provider: ProviderId, address: string): void {
    const stored = this.read();
    const keys = ProviderKeyStore.without(stored, provider, address);
    if (keys.length === stored.keys.length) return;
    try {
      this.write({ selected: stored.selected, keys });
    } catch {
      // Without encryption nothing could be read in the first place, so nothing is kept.
    }
  }

  state(provider: ProviderId, address: string): ProviderKeyState {
    const key = this.load(provider, address);
    return { stored: key !== null, hint: key ? key.slice(-4) : null };
  }

  /** What the learner chose, or null while they have not chosen anything. */
  selected(): ProviderSelection | null {
    return this.read().selected;
  }

  /**
   * Remember the learner's choice for the next launch. Returns false where it could not
   * be kept (no secure storage): the choice then lasts until the app closes.
   */
  select(selection: ProviderSelection): boolean {
    try {
      this.write({ ...this.read(), selected: selection });
      return true;
    } catch {
      return false;
    }
  }
}
