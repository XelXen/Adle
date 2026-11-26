import { randomBytes } from 'node:crypto';
import { existsSync, statSync } from 'node:fs';
import { readFile, rename, rm, writeFile } from 'node:fs/promises';
import path from 'node:path';

import { app, BrowserWindow, dialog, nativeTheme } from 'electron';

import { OPERATIONS } from '@adle/contracts';

import {
  type CoreResult,
  IPC,
  PROVIDER_AUTOMATIC,
  type SavedSettingsFile,
  type SettingsBroughtIn,
  type SettingsFileFound,
  type SettingsVoicePlan,
} from '../shared/ipc';
import { callCore } from './core/client';
import type { CoreProcess } from './core/process';
import { parseFileToken } from './course-file-rules';
import { type KnownProvider, readProviders } from './providers';
import type { ProviderKeyStore } from './secrets';
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
  SETTINGS_FILE_EXTENSION,
  type SettingsFile,
  unlockKeys,
  writeSettingsFile,
  WrongPasswordError,
} from './settings-file';
import { colorSchemeOf, type UiStateStore } from './ui-state';

/**
 * Settings saved as a file, and brought in from one (ADR-064).
 *
 * The page says which parts, and a password for the keys. It never says where a file goes
 * or which file is read: both are asked in a window of the operating system.
 *
 * A key leaves this process two ways only: to the core, for its own provider, as always;
 * and into a settings file, locked with the password the learner chose. It never reaches
 * the page. A file names a key's provider and never an address: a key brought in is kept
 * for the address this installation sends that provider's requests to, so a file cannot
 * send a key anywhere else.
 */

export interface SettingsFileDependencies {
  core: CoreProcess;
  keyStore: ProviderKeyStore;
  uiState: UiStateStore;
  /** Everything the core persists: a settings file is never written inside it. */
  dataDir: string;
}

type Handle = <Args extends unknown[], Result>(
  channel: string,
  handler: (...args: Args) => Promise<Result> | Result,
) => void;

/** A file the learner chose is remembered this long, for them to say what to bring in. */
const CHOSEN_FOR_MS = 30 * 60_000;

function failure(code: string, message: string): CoreResult<never> {
  return { ok: false, error: { code, message, status: 0 } };
}

function owner(): BrowserWindow | undefined {
  return BrowserWindow.getFocusedWindow() ?? BrowserWindow.getAllWindows()[0];
}

interface CoreSettings {
  learning: Record<string, unknown>;
  voice: Record<string, unknown>;
}

export function registerSettingsFileHandlers(deps: SettingsFileDependencies, handle: Handle): void {
  const { core, keyStore, uiState, dataDir } = deps;

  /** The file the learner chose last, read and checked, and the token the page knows it by. */
  let chosen: { token: string; file: SettingsFile; at: number } | null = null;

  const providers = async (): Promise<KnownProvider[] | null> =>
    (await readProviders(core))?.providers ?? null;

  handle(
    IPC.settingsSaveFile,
    async (parts: unknown, candidate: unknown): Promise<CoreResult<SavedSettingsFile | null>> => {
      const wanted = parseSettingsParts(parts);
      if (!wanted) return failure('invalid_request', 'Couldn’t save those settings.');
      const password = wanted.keys ? parsePassword(candidate) : null;
      if (wanted.keys && !password) {
        return failure(
          'password_needed',
          'Choose a password of 8 characters or more to lock the keys with.',
        );
      }

      const file: SettingsFile = {};
      if (wanted.appearance) {
        const { theme, notifications, pastelHue } = uiState.get();
        file.appearance = { theme, notifications, pastelHue };
      }
      if (wanted.learning || wanted.voice) {
        const kept = await callCore(core.getConnection(), OPERATIONS['settings.save_file']);
        if (!kept.ok) return kept;
        const data = kept.data as CoreSettings;
        if (wanted.learning) file.learning = data.learning;
        if (wanted.voice) file.voice = data.voice;
      }
      if (wanted.provider) {
        file.provider = { selection: keyStore.selected() ?? PROVIDER_AUTOMATIC };
      }
      let keysSaved = 0;
      if (wanted.keys && password) {
        const known = await providers();
        if (!known) {
          return failure('core_unavailable', 'Adle is still starting. Try again in a moment.');
        }
        const keys: KeyForProvider[] = [];
        for (const provider of known) {
          const key = keyStore.load(provider.id, provider.address);
          if (key) keys.push({ provider: provider.id, key });
        }
        keysSaved = keys.length;
        // A file that says it has keys has some.
        if (keys.length > 0) {
          file.keys = {
            providers: keys.map((entry) => entry.provider),
            locked: lockKeys(keys, password),
          };
        }
      }

      const options: Electron.SaveDialogOptions = {
        title: 'Save your Adle settings',
        buttonLabel: 'Save',
        defaultPath: defaultSettingsName(new Date()),
        filters: [{ name: 'Adle settings', extensions: [SETTINGS_FILE_EXTENSION] }],
        properties: ['createDirectory', 'showOverwriteConfirmation'],
      };
      const window = owner();
      const answer = window
        ? await dialog.showSaveDialog(window, options)
        : await dialog.showSaveDialog(options);
      if (answer.canceled || !answer.filePath) return { ok: true, data: null };
      const parsed = parseSettingsSavePath(answer.filePath, dataDir);
      if (!parsed.ok) return failure('invalid_request', parsed.message);
      const fileName = path.basename(parsed.path);
      if (parsed.amended && existsSync(parsed.path)) {
        return failure(
          'invalid_request',
          `There is already a file called ${fileName} there. Choose another name.`,
        );
      }
      const text = writeSettingsFile(file, `Adle ${app.getVersion()}`, new Date());
      const partial = `${parsed.path}.part`;
      try {
        // Whole or not at all, and readable by this account only where the system has that.
        await writeFile(partial, text, { mode: 0o600 });
        await rename(partial, parsed.path);
      } catch {
        await rm(partial, { force: true }).catch(() => undefined);
        return failure('not_saved', 'Couldn’t save the file there. Choose another place.');
      }
      return { ok: true, data: { fileName, parts: partsOf(file), keys: keysSaved } };
    },
  );

  handle(IPC.settingsChooseFile, async (): Promise<CoreResult<SettingsFileFound | null>> => {
    const options: Electron.OpenDialogOptions = {
      title: 'Import Adle settings',
      buttonLabel: 'Open',
      properties: ['openFile'],
      filters: [{ name: 'Adle settings', extensions: [SETTINGS_FILE_EXTENSION] }],
    };
    const window = owner();
    const picked = window
      ? await dialog.showOpenDialog(window, options)
      : await dialog.showOpenDialog(options);
    const [chosenPath] = picked.filePaths;
    if (picked.canceled || !chosenPath) return { ok: true, data: null };
    const parsedPath = parseSettingsOpenPath(chosenPath);
    if (!parsedPath.ok) return failure('invalid_request', parsedPath.message);
    let text: string;
    try {
      // Asked before any of it is read: a settings file is small.
      if (statSync(parsedPath.path).size > MAX_SETTINGS_FILE_BYTES) {
        return failure(
          'settings_file_invalid',
          'This file isn’t settings saved by Adle, or it is damaged. Nothing was changed.',
        );
      }
      text = await readFile(parsedPath.path, 'utf8');
    } catch {
      return failure('not_opened', 'The file could not be opened. It may have been moved.');
    }
    const parsed = parseSettingsFile(text);
    if (!parsed.ok) {
      return failure(
        parsed.code === 'newer' ? 'settings_file_newer' : 'settings_file_invalid',
        parsed.message,
      );
    }
    const { file } = parsed;

    // What the voice it names would be on this computer: said before anything is changed,
    // because setting a voice up downloads it.
    let voice: SettingsVoicePlan | null = null;
    if (file.voice) {
      const planned = await callCore(core.getConnection(), OPERATIONS['settings.look_at_file'], {
        body: { voice: file.voice },
      });
      if (!planned.ok) return planned;
      const plan = (planned.data as { voice: Record<string, unknown> | null }).voice;
      if (plan) {
        voice = {
          name: typeof plan.name === 'string' ? plan.name : null,
          setUp: plan.set_up === true,
          downloadBytes: typeof plan.download_bytes === 'number' ? plan.download_bytes : 0,
          sources: Array.isArray(plan.sources)
            ? plan.sources.filter((source): source is string => typeof source === 'string')
            : [],
          note: typeof plan.note === 'string' ? plan.note : '',
        };
      }
    }
    // Keys for providers this installation offers: the others have nowhere to go.
    const offered = new Set(((await providers()) ?? []).map((provider) => provider.id));
    const token = randomBytes(16).toString('hex');
    chosen = { token, file, at: Date.now() };
    return {
      ok: true,
      data: {
        token,
        fileName: path.basename(parsedPath.path),
        parts: partsOf(file),
        keysFor: (file.keys?.providers ?? []).filter((id) => offered.has(id)),
        voice,
      },
    };
  });

  handle(
    IPC.settingsBringIn,
    async (
      candidate: unknown,
      parts: unknown,
      options: unknown,
    ): Promise<CoreResult<SettingsBroughtIn>> => {
      const token = parseFileToken(candidate);
      const wanted = parseSettingsParts(parts);
      const asked = parseBringInOptions(options);
      if (!token || !wanted || !asked) {
        return failure('invalid_request', 'Couldn’t import those settings.');
      }
      if (!chosen || chosen.token !== token || Date.now() - chosen.at > CHOSEN_FOR_MS) {
        return failure('file_not_chosen', 'Choose the file again.');
      }
      const { file } = chosen;
      const notes: string[] = [];

      // The keys first: a wrong password changes nothing at all, and can be tried again.
      let keys: KeyForProvider[] = [];
      if (wanted.keys && file.keys) {
        if (!asked.password) return failure('password_needed', 'Type the password for the keys.');
        if (!keyStore.isAvailable()) {
          return failure(
            'secure_storage_unavailable',
            'This computer has no secure storage, so Adle can’t keep the keys. ' +
              'Import the settings without them.',
          );
        }
        try {
          keys = unlockKeys(file.keys.locked, asked.password);
        } catch (error) {
          if (error instanceof WrongPasswordError) return failure('wrong_password', error.message);
          return failure('settings_file_invalid', 'The keys in this file couldn’t be read.');
        }
      }
      // From here the file is being used: it is not kept for another go.
      chosen = null;

      const known =
        (wanted.keys && file.keys) || (wanted.provider && file.provider) ? await providers() : null;
      let keysKept = 0;
      for (const entry of keys) {
        const provider = known?.find((offeredHere) => offeredHere.id === entry.provider);
        // A provider this installation does not offer: its key has nowhere to go.
        if (!provider) continue;
        try {
          // Kept for the address this installation sends that provider's requests to: a
          // file names a provider, never a place.
          keyStore.save(provider.id, provider.address, entry.key);
        } catch {
          notes.push('One of the keys couldn’t be saved on this computer.');
          continue;
        }
        keysKept += 1;
        const pushed = await callCore(core.getConnection(), OPERATIONS['provider.set_credential'], {
          body: { api_key: entry.key, provider_id: provider.id },
        });
        if (!pushed.ok) notes.push('A key was saved, and is used the next time Adle starts.');
      }

      if (wanted.provider && file.provider) {
        const { selection } = file.provider;
        const offered =
          selection === PROVIDER_AUTOMATIC || known?.some((provider) => provider.id === selection);
        if (!offered) {
          // Never another in its place: where requests go changes only as the learner said.
          notes.push(
            'The AI provider chosen in the file isn’t offered here, so yours is unchanged.',
          );
        } else {
          const selected = await callCore(core.getConnection(), OPERATIONS['provider.select'], {
            body: { selection },
          });
          if (selected.ok) keyStore.select(selection);
          else notes.push(`The AI provider wasn’t changed. ${selected.error.message}`);
        }
      }

      let settingUpVoice = false;
      if ((wanted.learning && file.learning) || (wanted.voice && file.voice)) {
        const applied = await callCore(core.getConnection(), OPERATIONS['settings.bring_in_file'], {
          body: {
            learning: wanted.learning ? (file.learning ?? null) : null,
            voice: wanted.voice ? (file.voice ?? null) : null,
            set_up_voice: asked.setUpVoice,
          },
        });
        if (applied.ok) {
          const data = applied.data as { notes?: unknown; setting_up?: unknown };
          if (Array.isArray(data.notes)) {
            notes.push(...data.notes.filter((note): note is string => typeof note === 'string'));
          }
          settingUpVoice = data.setting_up !== null && data.setting_up !== undefined;
        } else {
          notes.push(`Your learning and voice settings weren’t changed. ${applied.error.message}`);
        }
      }

      if (wanted.appearance && file.appearance) {
        const next = uiState.update(file.appearance);
        // Chromium follows this for `prefers-color-scheme`, in the app and in player frames.
        nativeTheme.themeSource = colorSchemeOf(next.theme);
      }

      return {
        ok: true,
        data: {
          parts: {
            appearance: wanted.appearance && file.appearance !== undefined,
            learning: wanted.learning && file.learning !== undefined,
            voice: wanted.voice && file.voice !== undefined,
            provider: wanted.provider && file.provider !== undefined,
            keys: keysKept > 0,
          },
          keys: keysKept,
          notes,
          settingUpVoice,
        },
      };
    },
  );
}
