/** Unit tests for what the main process keeps on disk: the encrypted key and UI preferences. */
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';

import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { resolveLaunchSpec, CoreNotInstalledError } from './core/launch-spec';
import { parseProviders } from './providers';
import {
  createSecureEncryptor,
  type Encryptor,
  LEGACY_PROVIDER,
  parseProviderId,
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

const AIHUBMIX = 'https://aihubmix.com/v1';
const NVIDIA = 'https://integrate.api.nvidia.com/v1';

describe('ProviderKeyStore', () => {
  it('round-trips a key without ever writing it in the clear', () => {
    const file = path.join(directory, 'nested', 'credentials.bin');
    const store = new ProviderKeyStore(xorEncryptor(), file);
    expect(store.state('aihubmix', AIHUBMIX)).toEqual({ stored: false, hint: null });

    store.save('aihubmix', AIHUBMIX, 'sk-test-secret-value-9876');
    const written = readFileSync(file);
    expect(written.includes('sk-test-secret-value-9876')).toBe(false);
    // Not which providers have a key, either: the whole record is encrypted.
    expect(written.includes('aihubmix')).toBe(false);
    expect(store.load('aihubmix', AIHUBMIX)).toBe('sk-test-secret-value-9876');
    // The renderer only ever learns that a key exists and its last four characters.
    expect(store.state('aihubmix', AIHUBMIX)).toEqual({ stored: true, hint: '9876' });

    store.clear('aihubmix', AIHUBMIX);
    expect(store.load('aihubmix', AIHUBMIX)).toBeNull();
    expect(store.state('aihubmix', AIHUBMIX)).toEqual({ stored: false, hint: null });
  });

  it('keeps a key for each provider and never hands one out for another', () => {
    const store = new ProviderKeyStore(xorEncryptor(), path.join(directory, 'c.bin'));
    store.save('aihubmix', AIHUBMIX, 'sk-aihubmix-key-1111');
    store.save('nvidia', NVIDIA, 'nvapi-nvidia-key-2222');

    expect(store.load('aihubmix', AIHUBMIX)).toBe('sk-aihubmix-key-1111');
    expect(store.load('nvidia', NVIDIA)).toBe('nvapi-nvidia-key-2222');
    // One provider's name with the other's address finds nothing.
    expect(store.load('nvidia', AIHUBMIX)).toBeNull();
    expect(store.load('aihubmix', NVIDIA)).toBeNull();

    // Replacing or removing one leaves the other exactly as it was.
    store.save('nvidia', NVIDIA, 'nvapi-nvidia-key-3333');
    expect(store.state('nvidia', NVIDIA)).toEqual({ stored: true, hint: '3333' });
    store.clear('nvidia', NVIDIA);
    expect(store.load('nvidia', NVIDIA)).toBeNull();
    expect(store.load('aihubmix', AIHUBMIX)).toBe('sk-aihubmix-key-1111');
  });

  it('hands a key back only for the address it was given for', () => {
    const store = new ProviderKeyStore(xorEncryptor(), path.join(directory, 'c.bin'));
    store.save('nvidia', NVIDIA, 'nvapi-real-key-4444');

    // The same provider moved somewhere else (a developer's endpoint) does not get it.
    expect(store.load('nvidia', 'http://127.0.0.1:9100/v1')).toBeNull();
    expect(store.load('nvidia', 'https://integrate.api.nvidia.com.attacker.example/v1')).toBeNull();
    // A key typed there is kept beside the real one, not over it.
    store.save('nvidia', 'http://127.0.0.1:9100/v1', 'nvapi-test-key-5555');
    expect(store.load('nvidia', NVIDIA)).toBe('nvapi-real-key-4444');
    expect(store.load('nvidia', 'http://127.0.0.1:9100/v1')).toBe('nvapi-test-key-5555');
    // The same address written with a slash at its end is the same address.
    expect(store.load('nvidia', `${NVIDIA}/`)).toBe('nvapi-real-key-4444');
  });

  it('remembers which provider was chosen, apart from the keys', () => {
    const file = path.join(directory, 'c.bin');
    const store = new ProviderKeyStore(xorEncryptor(), file);
    expect(store.selected()).toBeNull();

    expect(store.select('nvidia')).toBe(true);
    expect(new ProviderKeyStore(xorEncryptor(), file).selected()).toBe('nvidia');
    store.save('nvidia', NVIDIA, 'nvapi-nvidia-key-2222');
    store.clear('nvidia', NVIDIA);
    // Removing a key is not a change of provider.
    expect(store.selected()).toBe('nvidia');

    // Letting Adle use every provider with a key is a choice like any other, and is kept.
    expect(store.select('auto')).toBe(true);
    expect(new ProviderKeyStore(xorEncryptor(), file).selected()).toBe('auto');
  });

  it('reads the one key an earlier version kept as the key of the provider there was', () => {
    const file = path.join(directory, 'c.bin');
    const encryptor = xorEncryptor();
    writeFileSync(file, encryptor.encryptString('sk-kept-since-before-7777'));
    const store = new ProviderKeyStore(encryptor, file);

    expect(LEGACY_PROVIDER).toEqual({ id: 'aihubmix', address: AIHUBMIX });
    expect(store.load('aihubmix', AIHUBMIX)).toBe('sk-kept-since-before-7777');
    expect(store.load('nvidia', NVIDIA)).toBeNull();
    expect(store.selected()).toBeNull();

    // Adding another provider's key keeps it.
    store.save('nvidia', NVIDIA, 'nvapi-nvidia-key-2222');
    expect(store.load('aihubmix', AIHUBMIX)).toBe('sk-kept-since-before-7777');
  });

  it('refuses to save when the OS offers no encryption', () => {
    const store = new ProviderKeyStore(xorEncryptor(false), path.join(directory, 'c.bin'));
    expect(() => store.save('aihubmix', AIHUBMIX, 'sk-test-secret-value')).toThrow(
      SecureStorageUnavailableError,
    );
    expect(store.load('aihubmix', AIHUBMIX)).toBeNull();
    // The choice cannot be kept either, and says so instead of failing.
    expect(store.select('nvidia')).toBe(false);
    expect(store.selected()).toBeNull();
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
    expect(store.state('aihubmix', AIHUBMIX)).toEqual({ stored: false, hint: null });
    expect(store.selected()).toBeNull();
  });

  it('keeps nothing from a record it did not write itself', () => {
    const file = path.join(directory, 'c.bin');
    const encryptor = xorEncryptor();
    const tampered = {
      version: 2,
      selected: 'somewhere-else',
      keys: [
        { provider: 'openai', address: 'https://api.example/v1', key: 'sk-not-ours-0000' },
        { provider: 'nvidia', address: NVIDIA, key: 'has spaces in it' },
        { provider: 'nvidia', address: 42, key: 'nvapi-no-address-0000' },
        'not an entry',
        { provider: 'aihubmix', address: AIHUBMIX, key: 'sk-the-good-one-8888' },
      ],
    };
    writeFileSync(file, encryptor.encryptString(JSON.stringify(tampered)));
    const store = new ProviderKeyStore(encryptor, file);
    expect(store.selected()).toBeNull();
    expect(store.load('aihubmix', AIHUBMIX)).toBe('sk-the-good-one-8888');
    expect(store.load('nvidia', NVIDIA)).toBeNull();
  });
});

describe('parseProviderId', () => {
  it('accepts the providers Adle keeps keys for and nothing else', () => {
    expect(parseProviderId('aihubmix')).toBe('aihubmix');
    expect(parseProviderId('nvidia')).toBe('nvidia');
    expect(parseProviderId('custom')).toBe('custom');
    for (const value of ['NVIDIA', 'openai', '', 'https://example.com', '__proto__', 7, null]) {
      expect(parseProviderId(value)).toBeNull();
    }
  });
});

describe('parseProviders', () => {
  const status = {
    provider_id: 'nvidia',
    selection: 'nvidia',
    providers: [
      { provider_id: 'aihubmix', base_url: AIHUBMIX, selected: false, key_configured: true },
      { provider_id: 'nvidia', base_url: NVIDIA, selected: true, key_configured: false },
    ],
  };

  it('reads each provider, where its key would go, and what the core is going by', () => {
    expect(parseProviders(status)).toEqual({
      providers: [
        { id: 'aihubmix', address: AIHUBMIX },
        { id: 'nvidia', address: NVIDIA },
      ],
      selection: 'nvidia',
    });
    expect(parseProviders({ ...status, selection: 'auto' })?.selection).toBe('auto');
    // A choice that is neither a provider Adle keeps keys for nor "automatic" is not one.
    for (const selection of ['openai', 'AUTO', '', 7, null, undefined]) {
      expect(parseProviders({ ...status, selection })?.selection).toBeNull();
    }
  });

  it('leaves out anything a key must not be kept or sent for', () => {
    expect(
      parseProviders({
        providers: [
          { provider_id: 'openai', base_url: 'https://api.example/v1', selected: true },
          { provider_id: 'nvidia', base_url: 'file:///etc/passwd' },
          { provider_id: 'nvidia', base_url: 7 },
          { provider_id: 'aihubmix', base_url: AIHUBMIX, selected: 'yes' },
          // A name that appears twice is not given two addresses.
          { provider_id: 'aihubmix', base_url: 'https://elsewhere.example/v1', selected: true },
          null,
        ],
      }),
    ).toEqual({ providers: [{ id: 'aihubmix', address: AIHUBMIX }], selection: null });
  });

  it('says nothing is known when the answer is not a list of providers', () => {
    for (const value of [null, 'providers', {}, { providers: 'nvidia' }]) {
      expect(parseProviders(value)).toBeNull();
    }
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

const DEFAULTS = {
  theme: 'system',
  pastelHue: 295,
  onboardingCompleted: false,
  notifications: true,
};

describe('UiStateStore', () => {
  it('starts with defaults and persists updates', () => {
    const file = path.join(directory, 'ui-state.json');
    const store = new UiStateStore(file);
    expect(store.get()).toEqual(DEFAULTS);

    store.update({ theme: 'dark' });
    store.update({ onboardingCompleted: true });
    expect(new UiStateStore(file).get()).toEqual({
      theme: 'dark',
      pastelHue: 295,
      onboardingCompleted: true,
      notifications: true,
    });
    // Notifications are on until the learner turns them off, and that is remembered.
    store.update({ notifications: false });
    expect(new UiStateStore(file).get().notifications).toBe(false);
  });

  it('reads what an earlier version kept, which said nothing about notifications', () => {
    const file = path.join(directory, 'ui-state.json');
    writeFileSync(file, JSON.stringify({ theme: 'light', onboardingCompleted: true }));
    expect(new UiStateStore(file).get()).toEqual({
      theme: 'light',
      pastelHue: 295,
      onboardingCompleted: true,
      notifications: true,
    });
  });

  it('keeps a Pastel theme and its color, and says each change to who follows it', () => {
    const file = path.join(directory, 'ui-state.json');
    const store = new UiStateStore(file);
    const seen: string[] = [];
    const stop = store.onChange((state) => seen.push(`${state.theme} ${state.pastelHue}`));
    store.update({ theme: 'pastel', pastelHue: 160 });
    store.update({ theme: 'dark' });
    stop();
    store.update({ theme: 'pastel-dark' });
    expect(seen).toEqual(['pastel 160', 'dark 160']);
    // The color stays while another theme is chosen, so Pastel comes back in it.
    expect(new UiStateStore(file).get()).toMatchObject({ theme: 'pastel-dark', pastelHue: 160 });
  });

  it('falls back to defaults when the file is corrupt or tampered with', () => {
    const file = path.join(directory, 'ui-state.json');
    writeFileSync(file, '{ not json');
    expect(new UiStateStore(file).get()).toEqual(DEFAULTS);
    writeFileSync(file, JSON.stringify({ theme: 'neon', onboardingCompleted: true }));
    expect(new UiStateStore(file).get()).toEqual(DEFAULTS);
  });

  it('rejects patches with unknown or mistyped fields', () => {
    expect(parseUiStatePatch({ theme: 'light' })).toEqual({ theme: 'light' });
    expect(parseUiStatePatch({ theme: 'light', admin: true })).toBeNull();
    expect(parseUiStatePatch({ onboardingCompleted: 'yes' })).toBeNull();
    expect(parseUiStatePatch({ notifications: false })).toEqual({ notifications: false });
    expect(parseUiStatePatch({ notifications: 'off' })).toBeNull();
    expect(parseUiStatePatch(['theme'])).toBeNull();
    expect(parseUiStatePatch({ theme: 'pastel', pastelHue: 0 })).toEqual({
      theme: 'pastel',
      pastelHue: 0,
    });
    expect(parseUiStatePatch({ pastelHue: 359 })).toEqual({ pastelHue: 359 });
    for (const pastelHue of [360, -1, 1.5, '200', null]) {
      expect(parseUiStatePatch({ pastelHue }), String(pastelHue)).toBeNull();
    }
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
