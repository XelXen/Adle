import { mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import path from 'node:path';

import type { ProviderKeyState } from '../shared/ipc';

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
      'This computer does not offer secure credential storage, so Adle will not save the key. ' +
        'You can still use the bundled sample course.',
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

/**
 * Stores the model provider key encrypted with the operating system's
 * credential facility (DPAPI, Keychain, or libsecret via Electron safeStorage).
 *
 * The plaintext key exists only in main-process memory and in the core
 * process's memory. It is never written to disk in the clear, never logged,
 * and never sent to the renderer.
 */
export class ProviderKeyStore {
  constructor(
    private readonly encryptor: Encryptor,
    private readonly file: string,
  ) {}

  isAvailable(): boolean {
    return this.encryptor.isEncryptionAvailable();
  }

  save(apiKey: string): void {
    if (!this.isAvailable()) throw new SecureStorageUnavailableError();
    mkdirSync(path.dirname(this.file), { recursive: true });
    writeFileSync(this.file, this.encryptor.encryptString(apiKey), { mode: 0o600 });
  }

  /** Returns the stored key, or `null` if none is stored or it can no longer be decrypted. */
  load(): string | null {
    if (!this.isAvailable()) return null;
    let encrypted: Buffer;
    try {
      encrypted = readFileSync(this.file);
    } catch {
      return null;
    }
    try {
      return this.encryptor.decryptString(encrypted) || null;
    } catch {
      // The OS key changed (new user profile, restored backup). Treat as "no key".
      return null;
    }
  }

  clear(): void {
    rmSync(this.file, { force: true });
  }

  state(): ProviderKeyState {
    const key = this.load();
    return { stored: key !== null, hint: key ? key.slice(-4) : null };
  }
}
