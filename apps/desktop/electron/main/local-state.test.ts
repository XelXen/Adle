/** Unit tests for what the main process keeps on disk: the encrypted key and UI preferences. */
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';

import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { resolveLaunchSpec, CoreNotInstalledError } from './core/launch-spec';
import {
  createSecureEncryptor,
  type Encryptor,
  ProviderKeyStore,
  SecureStorageUnavailableError,
  validateApiKey,
} from './secrets';
import { parseUiStatePatch, UiStateStore } from './ui-state';

let directory: string;

beforeEach(() => {
  directory = mkdtempSync(path.join(os.tmpdir(), 'adle-main-test-'));
});

afterEach(() => {
  rmSync(directory, { recursive: true, force: true });
});

/** A reversible stand-in for the OS credential facility. */
const xorEncryptor = (available = true): Encryptor => ({
  isEncryptionAvailable: () => available,
  encryptString: (text) => Buffer.from([...Buffer.from(text, 'utf8')].map((byte) => byte ^ 0x5a)),
  decryptString: (buffer) => Buffer.from([...buffer].map((byte) => byte ^ 0x5a)).toString('utf8'),
});

describe('validateApiKey', () => {
  it('trims and accepts a plausible key', () => {
    expect(validateApiKey('  sk-abcdef1234567890  ')).toBe('sk-abcdef1234567890');
  });

  it.each([
    ['a non-string', 12345678],
    ['an empty value', '   '],
    ['a short value', 'sk-1'],
    ['inner whitespace', 'sk-abc def12345'],
    ['a newline (header injection)', 'sk-abcdefgh\r\nX-Evil: 1'],
    ['non-ASCII text', 'sk-abcdéfgh1234'],
    ['an oversized value', 'k'.repeat(513)],
  ])('rejects %s', (_label, value) => {
    expect(() => validateApiKey(value)).toThrow(TypeError);
  });
});

describe('ProviderKeyStore', () => {
  it('round-trips a key without ever writing it in the clear', () => {
    const file = path.join(directory, 'nested', 'credentials.bin');
    const store = new ProviderKeyStore(xorEncryptor(), file);
    expect(store.state()).toEqual({ stored: false, hint: null });

    store.save('sk-test-secret-value-9876');
    expect(readFileSync(file).includes('sk-test-secret-value-9876')).toBe(false);
    expect(store.load()).toBe('sk-test-secret-value-9876');
    // The renderer only ever learns that a key exists and its last four characters.
    expect(store.state()).toEqual({ stored: true, hint: '9876' });

    store.clear();
    expect(store.load()).toBeNull();
    expect(store.state()).toEqual({ stored: false, hint: null });
  });

  it('refuses to save when the OS offers no encryption', () => {
    const store = new ProviderKeyStore(xorEncryptor(false), path.join(directory, 'c.bin'));
    expect(() => store.save('sk-test-secret-value')).toThrow(SecureStorageUnavailableError);
    expect(store.load()).toBeNull();
  });

  it('treats an undecryptable file as "no key" rather than crashing', () => {
    const file = path.join(directory, 'c.bin');
    writeFileSync(file, 'garbage');
    const store = new ProviderKeyStore(
      {
        ...xorEncryptor(),
        decryptString: () => {
          throw new Error('key changed');
        },
      },
      file,
    );
    expect(store.state()).toEqual({ stored: false, hint: null });
  });
});

describe('createSecureEncryptor', () => {
  it('trusts the OS store on Windows and macOS', () => {
    expect(createSecureEncryptor(xorEncryptor(), 'win32').isEncryptionAvailable()).toBe(true);
    expect(createSecureEncryptor(xorEncryptor(), 'darwin').isEncryptionAvailable()).toBe(true);
    expect(createSecureEncryptor(xorEncryptor(false), 'win32').isEncryptionAvailable()).toBe(false);
  });

  it('refuses the Linux plaintext fallback', () => {
    const withBackend = (backend: string) =>
      createSecureEncryptor(
        { ...xorEncryptor(), getSelectedStorageBackend: () => backend },
        'linux',
      );
    expect(withBackend('gnome_libsecret').isEncryptionAvailable()).toBe(true);
    expect(withBackend('kwallet6').isEncryptionAvailable()).toBe(true);
    expect(withBackend('basic_text').isEncryptionAvailable()).toBe(false);
    expect(withBackend('unknown').isEncryptionAvailable()).toBe(false);
    expect(createSecureEncryptor(xorEncryptor(), 'linux').isEncryptionAvailable()).toBe(false);
  });
});

describe('UiStateStore', () => {
  it('starts with defaults and persists updates', () => {
    const file = path.join(directory, 'ui-state.json');
    const store = new UiStateStore(file);
    expect(store.get()).toEqual({ theme: 'system', onboardingCompleted: false });

    store.update({ theme: 'dark' });
    store.update({ onboardingCompleted: true });
    expect(new UiStateStore(file).get()).toEqual({ theme: 'dark', onboardingCompleted: true });
  });

  it('falls back to defaults when the file is corrupt or tampered with', () => {
    const file = path.join(directory, 'ui-state.json');
    writeFileSync(file, '{ not json');
    expect(new UiStateStore(file).get()).toEqual({ theme: 'system', onboardingCompleted: false });
    writeFileSync(file, JSON.stringify({ theme: 'neon', onboardingCompleted: true }));
    expect(new UiStateStore(file).get()).toEqual({ theme: 'system', onboardingCompleted: false });
  });

  it('rejects patches with unknown or mistyped fields', () => {
    expect(parseUiStatePatch({ theme: 'light' })).toEqual({ theme: 'light' });
    expect(parseUiStatePatch({ theme: 'light', admin: true })).toBeNull();
    expect(parseUiStatePatch({ onboardingCompleted: 'yes' })).toBeNull();
    expect(parseUiStatePatch(['theme'])).toBeNull();
    expect(parseUiStatePatch(null)).toBeNull();
  });
});

describe('resolveLaunchSpec', () => {
  const base = { resourcesPath: '/opt/adle/resources', repoRoot: '/repo', exists: () => true };

  it('uses the private Python in a packaged app, cut off from the computer it is on', () => {
    const spec = resolveLaunchSpec({ ...base, isPackaged: true, platform: 'win32' });
    expect(spec.command).toBe(path.join('/opt/adle/resources', 'core', 'adle-core.exe'));
    // Isolated first: nothing after it may be read from the environment or the folder.
    expect(spec.args).toEqual(['-I', '-u', '-X', 'utf8', '-m', 'adle_core']);
    expect(spec.cwd).toBe(path.join('/opt/adle/resources', 'core'));

    const elsewhere = resolveLaunchSpec({ ...base, isPackaged: true, platform: 'darwin' });
    expect(elsewhere.command).toBe(path.join('/opt/adle/resources', 'core', 'bin', 'python3.12'));
    expect(elsewhere.args).toEqual(spec.args);
  });

  it('never looks at the repository or a development environment when packaged', () => {
    const seen: string[] = [];
    resolveLaunchSpec({
      ...base,
      isPackaged: true,
      platform: 'win32',
      exists: (file) => {
        seen.push(file);
        return true;
      },
    });
    expect(seen).toHaveLength(1);
    expect(seen[0]).not.toContain('.venv');
    expect(seen[0]!.startsWith(path.join('/opt/adle/resources'))).toBe(true);
  });

  it('uses the uv environment in development', () => {
    const spec = resolveLaunchSpec({ ...base, isPackaged: false, platform: 'linux' });
    expect(spec.command).toBe(path.join('/repo', 'services', 'core', '.venv', 'bin', 'python'));
    expect(spec.args).toEqual(['-m', 'adle_core']);
  });

  it('explains what is missing instead of failing obscurely', () => {
    const missing = { ...base, exists: () => false };
    expect(() => resolveLaunchSpec({ ...missing, isPackaged: true, platform: 'darwin' })).toThrow(
      CoreNotInstalledError,
    );
    expect(() => resolveLaunchSpec({ ...missing, isPackaged: false, platform: 'win32' })).toThrow(
      /npm run core:sync/,
    );
  });
});
