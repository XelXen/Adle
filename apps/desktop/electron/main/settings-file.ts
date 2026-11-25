import { createCipheriv, createDecipheriv, randomBytes, scryptSync } from 'node:crypto';
import path from 'node:path';

import {
  PROVIDER_IDS,
  type ProviderId,
  type ProviderSelection,
  type SettingsFileParts,
  THEME_PREFERENCES,
  type ThemePreference,
} from '../shared/ipc';
import { isInside } from './data-copy';
import { parseSelection, validateApiKey } from './secrets';

/**
 * A settings file (ADR-064): what one holds, reading one that may come from anywhere, and
 * locking the provider keys in it with a password. Pure, so it can be tested without
 * Electron; the handlers that use it are in `settings-files.ts`.
 *
 * A settings file is one JSON document. Its keys, if it has any, are never in it in the
 * clear: they are encrypted with a key made from a password the learner chose (scrypt,
 * then AES-256-GCM), and a key is named by its provider and never by an address, so that a
 * file cannot send a key anywhere but where this installation sends that provider's.
 */

export const SETTINGS_FILE_EXTENSION = 'json';
export const SETTINGS_FORMAT = 'adle-settings';
export const SETTINGS_VERSION = 1;
/** A settings file is small. One that is not is not one. */
export const MAX_SETTINGS_FILE_BYTES = 256 * 1024;
export const MIN_PASSWORD_LENGTH = 8;
export const MAX_PASSWORD_LENGTH = 200;
const MAX_PATH_LENGTH = 4096;

/** The parts of a settings file, in the order they are shown. */
export const SETTINGS_PARTS = ['appearance', 'learning', 'voice', 'provider', 'keys'] as const;
export type SettingsPart = (typeof SETTINGS_PARTS)[number];

/** How a password becomes a key. Written into the file, so that it can change later. */
const SCRYPT = { N: 32768, r: 8, p: 1 } as const;
const KEY_BYTES = 32;
/** Said with the keys as they are locked, so that they cannot be read as anything else. */
const BOUND_TO = Buffer.from('adle-settings-keys-v1', 'utf8');

export interface LockedKeys {
  kdf: 'scrypt';
  n: number;
  r: number;
  p: number;
  salt: string;
  iv: string;
  tag: string;
  data: string;
}

export interface KeyForProvider {
  provider: ProviderId;
  key: string;
}

/** What a settings file holds. Every part is optional: a file holds what was chosen. */
export interface SettingsFile {
  appearance?: { theme: ThemePreference; notifications: boolean };
  /** How the learner likes to learn, as the core keeps it: checked by the core. */
  learning?: Record<string, unknown>;
  /** The voice chosen, as the core keeps it: checked by the core. */
  voice?: Record<string, unknown>;
  provider?: { selection: ProviderSelection };
  /** The providers the file has keys for, and the keys, locked. */
  keys?: { providers: ProviderId[]; locked: LockedKeys };
}

function isPlainRecord(value: unknown): value is Record<string, unknown> {
  return (
    typeof value === 'object' &&
    value !== null &&
    !Array.isArray(value) &&
    Object.getPrototypeOf(value) === Object.prototype
  );
}

/** Exactly the five choices, each true or false: nothing else, and none left out. */
export function parseSettingsParts(candidate: unknown): SettingsFileParts | null {
  if (!isPlainRecord(candidate)) return null;
  const names = Object.keys(candidate);
  if (names.length !== SETTINGS_PARTS.length) return null;
  if (!SETTINGS_PARTS.every((name) => typeof candidate[name] === 'boolean')) return null;
  return {
    appearance: candidate.appearance === true,
    learning: candidate.learning === true,
    voice: candidate.voice === true,
    provider: candidate.provider === true,
    keys: candidate.keys === true,
  };
}

/** A password for the keys in a file: text of a sensible length, or nothing. */
export function parsePassword(candidate: unknown): string | null {
  if (typeof candidate !== 'string') return null;
  if (candidate.length < MIN_PASSWORD_LENGTH || candidate.length > MAX_PASSWORD_LENGTH) return null;
  return candidate;
}

/** What the page says with the parts to bring in: a password, and whether to set up a
 * voice that is not on this computer. Nothing else, and both of them. */
export function parseBringInOptions(
  candidate: unknown,
): { password: string | null; setUpVoice: boolean } | null {
  if (!isPlainRecord(candidate) || Object.keys(candidate).length !== 2) return null;
  const { password, setUpVoice } = candidate;
  if (typeof setUpVoice !== 'boolean') return null;
  if (password === null) return { password: null, setUpVoice };
  const usable = parsePassword(password);
  return usable ? { password: usable, setUpVoice } : null;
}

// -- the keys, locked ------------------------------------------------------------------------

export class WrongPasswordError extends Error {
  constructor() {
    super('That password doesn’t open the keys in this file.');
  }
}

function derive(password: string, salt: Buffer, cost: { N: number; r: number; p: number }): Buffer {
  return scryptSync(password.normalize('NFKC'), salt, KEY_BYTES, {
    ...cost,
    maxmem: 256 * 1024 * 1024,
  });
}

/** Lock keys with a password. Nothing of them can be read from the result without it. */
export function lockKeys(
  keys: readonly KeyForProvider[],
  password: string,
  random: (size: number) => Buffer = randomBytes,
): LockedKeys {
  const salt = random(16);
  const iv = random(12);
  const cipher = createCipheriv('aes-256-gcm', derive(password, salt, SCRYPT), iv);
  cipher.setAAD(BOUND_TO);
  const plain = Buffer.from(JSON.stringify(keys), 'utf8');
  const data = Buffer.concat([cipher.update(plain), cipher.final()]);
  plain.fill(0);
  return {
    kdf: 'scrypt',
    n: SCRYPT.N,
    r: SCRYPT.r,
    p: SCRYPT.p,
    salt: salt.toString('base64'),
    iv: iv.toString('base64'),
    tag: cipher.getAuthTag().toString('base64'),
    data: data.toString('base64'),
  };
}

/**
 * The keys a file holds, opened with the password they were locked with. Throws
 * `WrongPasswordError` for any other, and for keys that were changed on the way.
 */
export function unlockKeys(locked: LockedKeys, password: string): KeyForProvider[] {
  let plain: string;
  try {
    const key = derive(password, Buffer.from(locked.salt, 'base64'), {
      N: locked.n,
      r: locked.r,
      p: locked.p,
    });
    const decipher = createDecipheriv('aes-256-gcm', key, Buffer.from(locked.iv, 'base64'));
    decipher.setAAD(BOUND_TO);
    decipher.setAuthTag(Buffer.from(locked.tag, 'base64'));
    plain = Buffer.concat([
      decipher.update(Buffer.from(locked.data, 'base64')),
      decipher.final(),
    ]).toString('utf8');
  } catch {
    throw new WrongPasswordError();
  }
  let listed: unknown;
  try {
    listed = JSON.parse(plain);
  } catch {
    throw new WrongPasswordError();
  }
  const keys: KeyForProvider[] = [];
  if (!Array.isArray(listed)) return keys;
  for (const entry of listed.slice(0, PROVIDER_IDS.length)) {
    if (!isPlainRecord(entry)) continue;
    const provider = parseProvider(entry.provider);
    if (!provider || keys.some((kept) => kept.provider === provider)) continue;
    try {
      keys.push({ provider, key: validateApiKey(entry.key) });
    } catch {
      // A key that could not be sent anyway is not kept.
    }
  }
  return keys;
}

function parseProvider(value: unknown): ProviderId | null {
  return typeof value === 'string' && (PROVIDER_IDS as readonly string[]).includes(value)
    ? (value as ProviderId)
    : null;
}

const BASE64 = /^[A-Za-z0-9+/]+={0,2}$/;

function isBase64(value: unknown, most: number): value is string {
  return (
    typeof value === 'string' && value.length > 0 && value.length <= most && BASE64.test(value)
  );
}

/** Keys as a file holds them, if they are of the one kind this Adle can open. */
function parseLocked(candidate: unknown): LockedKeys | null {
  if (!isPlainRecord(candidate)) return null;
  const { kdf, n, r, p, salt, iv, tag, data } = candidate;
  if (kdf !== 'scrypt') return null;
  // Bounds on the work a file can ask for: a cost a file names is a cost this computer pays.
  if (typeof n !== 'number' || !Number.isInteger(n) || n < 16384 || n > 1048576) return null;
  if ((n & (n - 1)) !== 0) return null;
  if (typeof r !== 'number' || !Number.isInteger(r) || r < 8 || r > 16) return null;
  if (typeof p !== 'number' || !Number.isInteger(p) || p < 1 || p > 4) return null;
  if (!isBase64(salt, 64) || !isBase64(iv, 32) || !isBase64(tag, 32) || !isBase64(data, 16384)) {
    return null;
  }
  return { kdf, n, r, p, salt, iv, tag, data };
}

// -- reading and writing a file -----------------------------------------------------------------

export type ParsedSettingsFile =
  { ok: true; file: SettingsFile } | { ok: false; code: 'not_settings' | 'newer'; message: string };

const NOT_SETTINGS =
  'This file isn’t settings saved by Adle, or it is damaged. Nothing was changed.';

/**
 * Read a settings file's text. What is in a part is checked where the part is applied; a
 * part that is not what it should be is left out, so that one bad setting does not cost
 * the rest. A file that is not a settings file at all is refused whole.
 */
export function parseSettingsFile(text: string): ParsedSettingsFile {
  if (text.length > MAX_SETTINGS_FILE_BYTES) {
    return { ok: false, code: 'not_settings', message: NOT_SETTINGS };
  }
  let document: unknown;
  try {
    document = JSON.parse(text);
  } catch {
    return { ok: false, code: 'not_settings', message: NOT_SETTINGS };
  }
  if (!isPlainRecord(document) || document.format !== SETTINGS_FORMAT) {
    return { ok: false, code: 'not_settings', message: NOT_SETTINGS };
  }
  const { version } = document;
  if (typeof version !== 'number' || !Number.isInteger(version) || version < 1) {
    return { ok: false, code: 'not_settings', message: NOT_SETTINGS };
  }
  if (version > SETTINGS_VERSION) {
    return {
      ok: false,
      code: 'newer',
      message: 'These settings were saved by a newer version of Adle. Update Adle to import them.',
    };
  }
  const file: SettingsFile = {};
  const { appearance, learning, voice, provider, keys } = document;
  if (isPlainRecord(appearance)) {
    const theme = (THEME_PREFERENCES as readonly unknown[]).includes(appearance.theme)
      ? (appearance.theme as ThemePreference)
      : null;
    if (theme && typeof appearance.notifications === 'boolean') {
      file.appearance = { theme, notifications: appearance.notifications };
    }
  }
  if (isPlainRecord(learning)) file.learning = learning;
  if (isPlainRecord(voice)) file.voice = voice;
  if (isPlainRecord(provider)) {
    const selection = parseSelection(provider.selection);
    if (selection) file.provider = { selection };
  }
  if (isPlainRecord(keys) && Array.isArray(keys.providers)) {
    const locked = parseLocked(keys.locked);
    const providers = [
      ...new Set(keys.providers.map(parseProvider).filter((id): id is ProviderId => id !== null)),
    ];
    if (locked && providers.length > 0) file.keys = { providers, locked };
  }
  return { ok: true, file };
}

/** A settings file as text, ready to be written. */
export function writeSettingsFile(file: SettingsFile, madeBy: string, now: Date): string {
  return `${JSON.stringify(
    {
      format: SETTINGS_FORMAT,
      version: SETTINGS_VERSION,
      made_by: madeBy,
      made_at: now.toISOString(),
      ...file,
    },
    null,
    2,
  )}\n`;
}

/** Which parts a file has: there is nothing else in it to bring in. */
export function partsOf(file: SettingsFile): SettingsFileParts {
  return {
    appearance: file.appearance !== undefined,
    learning: file.learning !== undefined,
    voice: file.voice !== undefined,
    provider: file.provider !== undefined,
    keys: file.keys !== undefined,
  };
}

/** "Adle settings 2026-11-24.json": sorts by date and says what it is. */
export function defaultSettingsName(now: Date): string {
  const day = [
    now.getFullYear(),
    String(now.getMonth() + 1).padStart(2, '0'),
    String(now.getDate()).padStart(2, '0'),
  ].join('-');
  return `Adle settings ${day}.${SETTINGS_FILE_EXTENSION}`;
}

function usablePath(candidate: unknown): string | null {
  if (typeof candidate !== 'string' || candidate.length === 0) return null;
  if (candidate.length > MAX_PATH_LENGTH || candidate.includes('\0')) return null;
  if (!path.isAbsolute(candidate)) return null;
  return path.resolve(candidate);
}

export type ParsedSettingsPath =
  { ok: true; path: string; amended: boolean } | { ok: false; message: string };

/** Check where settings are to be saved, as the save dialog returned it. */
export function parseSettingsSavePath(candidate: unknown, dataDir: string): ParsedSettingsPath {
  const chosen = usablePath(candidate);
  if (!chosen) return { ok: false, message: 'That file name can’t be used.' };
  const amended = path.extname(chosen).toLowerCase() !== `.${SETTINGS_FILE_EXTENSION}`;
  const target = amended ? `${chosen}.${SETTINGS_FILE_EXTENSION}` : chosen;
  if (isInside(dataDir, target)) {
    return { ok: false, message: 'Choose a place outside Adle’s own data folder.' };
  }
  return { ok: true, path: target, amended };
}

/** Check the file settings are brought in from, as the open dialog returned it. */
export function parseSettingsOpenPath(
  candidate: unknown,
): { ok: true; path: string } | { ok: false; message: string } {
  const chosen = usablePath(candidate);
  if (!chosen) return { ok: false, message: 'That file can’t be used.' };
  if (path.extname(chosen).toLowerCase() !== `.${SETTINGS_FILE_EXTENSION}`) {
    return { ok: false, message: 'Choose settings saved by Adle: a file that ends in .json.' };
  }
  return { ok: true, path: chosen };
}
