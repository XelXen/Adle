import path from 'node:path';

import { describe, expect, it } from 'vitest';

import {
  defaultSettingsName,
  type KeyForProvider,
  lockKeys,
  MAX_SETTINGS_FILE_BYTES,
  parseBringInOptions,
  parsePassword,
  parseSettingsFile,
  parseSettingsOpenPath,
  parseSettingsParts,
  parseSettingsSavePath,
  partsOf,
  type SettingsFile,
  unlockKeys,
  writeSettingsFile,
  WrongPasswordError,
} from './settings-file';

const root = path.resolve(path.sep, 'adle-test');
const dataDir = path.join(root, 'data');
const PASSWORD = 'correct horse battery';
const KEYS: KeyForProvider[] = [
  { provider: 'aihubmix', key: 'sk-test-not-a-real-key-4Hq7' },
  { provider: 'nvidia', key: 'nvapi-test-not-a-real-key-9Zx2' },
];
const ALL = { appearance: true, learning: true, voice: true, provider: true, keys: true };
const NOW = new Date(2026, 10, 24, 12, 0, 0);

function aFile(): SettingsFile {
  return {
    appearance: { theme: 'dark', notifications: false },
    learning: { pace: 'brisk', volume: 40 },
    voice: { enabled: true, tier: 'kokoro' },
    provider: { selection: 'nvidia' },
    keys: { providers: ['aihubmix', 'nvidia'], locked: lockKeys(KEYS, PASSWORD) },
  };
}

describe('the keys in a settings file', () => {
  it('open with the password they were locked with, and with no other', () => {
    const locked = lockKeys(KEYS, PASSWORD);
    expect(unlockKeys(locked, PASSWORD)).toEqual(KEYS);
    expect(() => unlockKeys(locked, 'correct horse batterx')).toThrow(WrongPasswordError);
    expect(() => unlockKeys(locked, '')).toThrow(WrongPasswordError);
  });

  it('cannot be read in the file: not a key, and not a part of one', () => {
    const text = writeSettingsFile(aFile(), 'Adle 0.1.0', NOW);
    for (const { key } of KEYS) {
      expect(text).not.toContain(key);
      expect(text).not.toContain(key.slice(-8));
      expect(text).not.toContain(Buffer.from(key).toString('base64').slice(0, 12));
    }
    expect(text).not.toContain(PASSWORD);
    // Whose keys are there is said: the page shows it before asking for the password.
    expect(JSON.parse(text).keys.providers).toEqual(['aihubmix', 'nvidia']);
  });

  it('are locked differently each time, so two files of the same keys do not match', () => {
    const one = lockKeys(KEYS, PASSWORD);
    const other = lockKeys(KEYS, PASSWORD);
    expect(one.salt).not.toBe(other.salt);
    expect(one.data).not.toBe(other.data);
    expect(unlockKeys(other, PASSWORD)).toEqual(KEYS);
  });

  it('do not open once anything about them has been changed', () => {
    const locked = lockKeys(KEYS, PASSWORD);
    const flipped = Buffer.from(locked.data, 'base64');
    flipped[3] = flipped[3]! ^ 1;
    for (const changed of [
      { ...locked, data: flipped.toString('base64') },
      { ...locked, tag: Buffer.alloc(16, 7).toString('base64') },
      { ...locked, iv: Buffer.alloc(12, 7).toString('base64') },
      { ...locked, salt: Buffer.alloc(16, 7).toString('base64') },
      { ...locked, n: 16384 },
    ]) {
      expect(() => unlockKeys(changed, PASSWORD)).toThrow(WrongPasswordError);
    }
  });

  it('are only keys this Adle could send: one for each provider it knows, well formed', () => {
    const odd = lockKeys(
      [
        { provider: 'nvidia', key: 'nvapi-test-not-a-real-key-9Zx2' },
        { provider: 'nvidia', key: 'nvapi-a-second-key-for-the-same-1' },
        { provider: 'somewhere-else' as never, key: 'sk-test-not-a-real-key-4Hq7' },
        { provider: 'aihubmix', key: 'short' },
        { provider: 'aihubmix', key: 'has a space in it 12345' },
      ],
      PASSWORD,
    );
    expect(unlockKeys(odd, PASSWORD)).toEqual([
      { provider: 'nvidia', key: 'nvapi-test-not-a-real-key-9Zx2' },
    ]);
  });

  it('treat a password the same however its letters were typed', () => {
    // The same word, with its accent as one character and as two.
    const locked = lockKeys(KEYS, 'caf\u00e9 au lait');
    expect(unlockKeys(locked, 'cafe\u0301 au lait')).toEqual(KEYS);
  });
});

describe('a settings file', () => {
  it('is read back as it was written', () => {
    const file = aFile();
    const parsed = parseSettingsFile(writeSettingsFile(file, 'Adle 0.1.0', NOW));
    expect(parsed).toEqual({ ok: true, file });
    expect(partsOf(file)).toEqual(ALL);
  });

  it('holds only the parts that were chosen', () => {
    const file: SettingsFile = { appearance: { theme: 'light', notifications: true } };
    const parsed = parseSettingsFile(writeSettingsFile(file, 'Adle 0.1.0', NOW));
    expect(parsed).toEqual({ ok: true, file });
    expect(partsOf(file)).toEqual({
      appearance: true,
      learning: false,
      voice: false,
      provider: false,
      keys: false,
    });
  });

  it('is refused whole when it is not one', () => {
    for (const text of [
      '',
      'not json',
      '[]',
      '"adle-settings"',
      '{}',
      JSON.stringify({ format: 'something-else', version: 1 }),
      JSON.stringify({ format: 'adle-settings' }),
      JSON.stringify({ format: 'adle-settings', version: 0 }),
      JSON.stringify({ format: 'adle-settings', version: '1' }),
      `${' '.repeat(MAX_SETTINGS_FILE_BYTES)}{}`,
    ]) {
      const parsed = parseSettingsFile(text);
      expect(parsed.ok, text.slice(0, 40)).toBe(false);
      if (!parsed.ok) expect(parsed.code).toBe('not_settings');
    }
  });

  it('says so when it is from a newer Adle', () => {
    const parsed = parseSettingsFile(JSON.stringify({ format: 'adle-settings', version: 2 }));
    expect(parsed).toMatchObject({ ok: false, code: 'newer' });
    if (!parsed.ok) expect(parsed.message).toContain('newer version');
  });

  it('loses a part that is not what it should be, and keeps the rest', () => {
    const text = JSON.stringify({
      format: 'adle-settings',
      version: 1,
      appearance: { theme: 'neon', notifications: true },
      learning: { pace: 'brisk' },
      voice: 'expressive',
      provider: { selection: 'https://elsewhere.example/v1' },
      keys: { providers: ['nvidia'], locked: { kdf: 'none', data: 'plain-key-here' } },
      something_else: { path: 'C:\\Users' },
    });
    expect(parseSettingsFile(text)).toEqual({ ok: true, file: { learning: { pace: 'brisk' } } });
  });

  it('never takes an address for a provider or for a key', () => {
    const locked = lockKeys(KEYS, PASSWORD);
    const text = JSON.stringify({
      format: 'adle-settings',
      version: 1,
      provider: { selection: 'nvidia', address: 'https://elsewhere.example/v1' },
      keys: {
        providers: ['nvidia', 'https://elsewhere.example/v1', 'custom', 'nvidia'],
        locked,
        address: 'https://elsewhere.example/v1',
      },
    });
    const parsed = parseSettingsFile(text);
    expect(parsed).toEqual({
      ok: true,
      file: {
        provider: { selection: 'nvidia' },
        keys: { providers: ['nvidia', 'custom'], locked },
      },
    });
  });

  it('cannot ask this computer for more work than a password needs', () => {
    const locked = lockKeys(KEYS, PASSWORD);
    const withCost = (cost: Record<string, unknown>): SettingsFile =>
      (
        parseSettingsFile(
          JSON.stringify({
            format: 'adle-settings',
            version: 1,
            keys: { providers: ['nvidia'], locked: { ...locked, ...cost } },
          }),
        ) as { file: SettingsFile }
      ).file;
    for (const cost of [
      { n: 2 ** 30 },
      { n: 32769 },
      { n: 1024 },
      { r: 1024 },
      { p: 64 },
      { n: '32768' },
      { kdf: 'pbkdf2' },
      { salt: '' },
      { data: 'x'.repeat(20_000) },
      { iv: 'not base64!' },
    ]) {
      expect(withCost(cost).keys, JSON.stringify(cost).slice(0, 30)).toBeUndefined();
    }
    expect(withCost({}).keys).toBeDefined();
  });
});

describe('what the page may say', () => {
  it('is exactly the five parts, each true or false', () => {
    expect(parseSettingsParts(ALL)).toEqual(ALL);
    expect(parseSettingsParts({ ...ALL, keys: false })?.keys).toBe(false);
    expect(parseSettingsParts({ ...ALL, path: 'C:\\x.json' })).toBeNull();
    expect(parseSettingsParts({ appearance: true })).toBeNull();
    expect(parseSettingsParts({ ...ALL, keys: 'yes' })).toBeNull();
    expect(parseSettingsParts(null)).toBeNull();
    expect(parseSettingsParts([true, true, true, true, true])).toBeNull();
  });

  it('is a password of a sensible length, or none', () => {
    expect(parsePassword(PASSWORD)).toBe(PASSWORD);
    expect(parsePassword('1234567')).toBeNull();
    expect(parsePassword('x'.repeat(201))).toBeNull();
    expect(parsePassword(12345678)).toBeNull();
    expect(parsePassword(undefined)).toBeNull();
  });

  it('with the parts to bring in: a password or none, and whether to set a voice up', () => {
    expect(parseBringInOptions({ password: PASSWORD, setUpVoice: true })).toEqual({
      password: PASSWORD,
      setUpVoice: true,
    });
    expect(parseBringInOptions({ password: null, setUpVoice: false })).toEqual({
      password: null,
      setUpVoice: false,
    });
    expect(parseBringInOptions({ password: 'short', setUpVoice: true })).toBeNull();
    expect(parseBringInOptions({ password: null })).toBeNull();
    expect(parseBringInOptions({ password: null, setUpVoice: 'yes' })).toBeNull();
    expect(parseBringInOptions({ password: null, setUpVoice: true, path: 'x' })).toBeNull();
    expect(parseBringInOptions(null)).toBeNull();
  });
});

describe('where settings are saved and read from', () => {
  it('is a place the learner chose, with the ending added if a dialog left it off', () => {
    expect(defaultSettingsName(NOW)).toBe('Adle settings 2026-11-24.json');
    const chosen = path.join(root, 'Documents', 'Adle settings.json');
    expect(parseSettingsSavePath(chosen, dataDir)).toEqual({
      ok: true,
      path: chosen,
      amended: false,
    });
    const bare = path.join(root, 'Documents', 'settings');
    expect(parseSettingsSavePath(bare, dataDir)).toEqual({
      ok: true,
      path: `${bare}.json`,
      amended: true,
    });
  });

  it('is never inside Adle’s own data, and never a path that is not whole', () => {
    expect(parseSettingsSavePath(path.join(dataDir, 'settings.json'), dataDir).ok).toBe(false);
    expect(parseSettingsSavePath('settings.json', dataDir).ok).toBe(false);
    expect(parseSettingsSavePath(undefined, dataDir).ok).toBe(false);
    expect(parseSettingsOpenPath(path.join(root, 'Downloads', 'Adle settings.json')).ok).toBe(true);
    expect(parseSettingsOpenPath(path.join(root, 'Downloads', 'settings.zip')).ok).toBe(false);
    expect(parseSettingsOpenPath('settings.json').ok).toBe(false);
    expect(parseSettingsOpenPath(null).ok).toBe(false);
  });
});
