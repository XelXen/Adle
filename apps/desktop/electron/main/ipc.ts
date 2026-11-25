import { mkdirSync } from 'node:fs';

import {
  app,
  BrowserWindow,
  dialog,
  ipcMain,
  type IpcMainInvokeEvent,
  nativeTheme,
  Notification,
  shell,
  type WebContents,
} from 'electron';

import { OPERATIONS, type OperationId } from '@adle/contracts';
import { adleOriginOf, APP_ORIGIN } from '@adle/event-protocol';

import {
  type AppInfo,
  type CoreInvokeParams,
  type CoreResult,
  EXTERNAL_LINKS,
  type ExternalLinkId,
  type ImportJob,
  IPC,
  PROVIDER_AUTOMATIC,
  type ProviderKeyStates,
  type ProviderSelection,
  type UiState,
} from '../shared/ipc';
import { callCore } from './core/client';
import type { CoreProcess } from './core/process';
import { registerCourseFileHandlers } from './course-files';
import { registerFilmFileHandlers } from './film-files';
import { registerDataHandlers } from './data';
import {
  MAX_IMPORT_FILES,
  parseCourseId,
  parseImportPaths,
  SOURCE_FILE_EXTENSIONS,
} from './imports';
import { noticeFor, NoticePace, parseNoticeKind, shouldNotify } from './notices';
import { paths } from './paths';
import { type KnownProvider, readProviders } from './providers';
import {
  parseProviderId,
  type ProviderKeyStore,
  SecureStorageUnavailableError,
  validateApiKey,
} from './secrets';
import { openExternalLink } from './security';
import { registerSettingsFileHandlers } from './settings-files';
import { parseUiStatePatch, type UiStateStore } from './ui-state';

/** Upper bound on a serialised request body coming from the renderer. */
const MAX_BODY_BYTES = 1024 * 1024;

export interface IpcDependencies {
  core: CoreProcess;
  keyStore: ProviderKeyStore;
  uiState: UiStateStore;
  /** The app's window, if it has one at the moment. */
  getWindow: () => BrowserWindow | null;
  /** Everything the core persists. Deleted as a whole when the learner deletes everything. */
  dataDir: string;
  /** Where the app's own log files are. */
  logsDir: string;
}

function failure(code: string, message: string): CoreResult<never> {
  return { ok: false, error: { code, message, status: 0 } };
}

/**
 * Only the top-level document of the app origin may use the bridge. This
 * rejects the scene player frame and anything else that might ever be loaded.
 */
export function isTrustedSender(event: IpcMainInvokeEvent): boolean {
  const frame = event.senderFrame;
  if (!frame || frame.parent !== null) return false;
  return adleOriginOf(frame.url) === APP_ORIGIN;
}

function isPlainRecord(value: unknown): value is Record<string, unknown> {
  return (
    typeof value === 'object' &&
    value !== null &&
    !Array.isArray(value) &&
    Object.getPrototypeOf(value) === Object.prototype
  );
}

/** Validate untrusted renderer input for a core call. Exported for unit tests. */
export function parseInvokeRequest(
  operation: unknown,
  params: unknown,
): { ok: true; operation: OperationId; params: CoreInvokeParams } | { ok: false; reason: string } {
  if (typeof operation !== 'string' || !Object.hasOwn(OPERATIONS, operation)) {
    return { ok: false, reason: 'Unknown operation.' };
  }
  const id = operation as OperationId;
  if (OPERATIONS[id].internal) {
    return { ok: false, reason: 'This operation is not available to the interface.' };
  }
  if (params === undefined || params === null) return { ok: true, operation: id, params: {} };
  if (!isPlainRecord(params)) return { ok: false, reason: 'Malformed parameters.' };

  const { path, query, body, ...rest } = params;
  if (Object.keys(rest).length > 0) return { ok: false, reason: 'Unexpected parameters.' };

  for (const group of [path, query]) {
    if (group === undefined) continue;
    if (!isPlainRecord(group)) return { ok: false, reason: 'Malformed parameters.' };
    for (const value of Object.values(group)) {
      const allowed =
        value === undefined ||
        value === null ||
        typeof value === 'string' ||
        typeof value === 'boolean' ||
        (typeof value === 'number' && Number.isFinite(value));
      if (!allowed) return { ok: false, reason: 'Malformed parameters.' };
    }
  }

  if (body !== undefined) {
    let size: number;
    try {
      size = Buffer.byteLength(JSON.stringify(body) ?? '', 'utf8');
    } catch {
      return { ok: false, reason: 'The request could not be serialised.' };
    }
    if (size > MAX_BODY_BYTES) return { ok: false, reason: 'The request is too large.' };
  }

  return {
    ok: true,
    operation: id,
    params: {
      path: path as CoreInvokeParams['path'],
      query: query as CoreInvokeParams['query'],
      body,
    },
  };
}

export function registerIpcHandlers(deps: IpcDependencies): void {
  const { core, keyStore, uiState } = deps;

  const handle = <Args extends unknown[], Result>(
    channel: string,
    handler: (...args: Args) => Promise<Result> | Result,
  ): void => {
    ipcMain.handle(channel, (event, ...args) => {
      if (!isTrustedSender(event)) throw new Error('Forbidden.');
      return handler(...(args as Args));
    });
  };

  handle(IPC.appInfo, (): AppInfo => ({
    name: app.getName(),
    version: app.getVersion(),
    platform: process.platform,
    isPackaged: app.isPackaged,
    versions: {
      electron: process.versions.electron,
      chrome: process.versions.chrome,
      node: process.versions.node,
    },
    secureStorageAvailable: keyStore.isAvailable(),
    ui: uiState.get(),
  }));

  handle(IPC.uiStateUpdate, (candidate: unknown): UiState => {
    const patch = parseUiStatePatch(candidate);
    if (!patch) throw new Error('Invalid interface settings.');
    const next = uiState.update(patch);
    // Chromium follows this for `prefers-color-scheme`, in the app and in player frames.
    nativeTheme.themeSource = next.theme;
    return next;
  });

  handle(IPC.openExternal, async (link: unknown): Promise<void> => {
    if (typeof link !== 'string' || !Object.hasOwn(EXTERNAL_LINKS, link)) {
      throw new Error('Unknown external link.');
    }
    await openExternalLink(link as ExternalLinkId);
  });

  handle(IPC.showLogs, async (): Promise<CoreResult<null>> => {
    // A fixed folder of the app's own: the page chooses nothing here.
    try {
      mkdirSync(deps.logsDir, { recursive: true });
    } catch {
      return failure('not_opened', 'Couldn’t open the folder.');
    }
    const problem = await shell.openPath(deps.logsDir);
    return problem ? failure('not_opened', 'Couldn’t open the folder.') : { ok: true, data: null };
  });

  const noticePace = new NoticePace();
  const openNotices = new Set<Notification>();
  handle(IPC.appNotify, (candidate: unknown): boolean => {
    // The page says what kind of thing happened. The words are chosen here.
    const kind = parseNoticeKind(candidate);
    if (!kind) throw new Error('Unknown notice.');
    const window = deps.getWindow();
    const open = window !== null && !window.isDestroyed();
    const show = shouldNotify({
      enabled: uiState.get().notifications,
      supported: Notification.isSupported(),
      focused: open && window.isFocused(),
      justShown: noticePace.justShown(kind),
    });
    if (!show) return false;
    const notice = new Notification({ ...noticeFor(kind), icon: paths.windowIcon });
    // Held until it is gone: a notification nothing refers to can be cleared away
    // together with what happens when it is clicked.
    openNotices.add(notice);
    notice.on('close', () => openNotices.delete(notice));
    notice.on('click', () => {
      openNotices.delete(notice);
      // Bring back the window the learner already has; never open a second one.
      const current = deps.getWindow();
      if (!current || current.isDestroyed()) return;
      if (current.isMinimized()) current.restore();
      current.focus();
    });
    notice.show();
    noticePace.shown(kind);
    return true;
  });

  handle(IPC.coreStatus, () => core.status);
  handle(IPC.coreRestart, () => core.restart());

  handle(IPC.coreInvoke, async (operation: unknown, params: unknown): Promise<CoreResult> => {
    const request = parseInvokeRequest(operation, params);
    if (!request.ok) return failure('invalid_request', request.reason);
    return callCore(core.getConnection(), OPERATIONS[request.operation], request.params);
  });

  /** What is stored for each provider the core offers. The keys themselves stay here. */
  const keyStates = (providers: KnownProvider[] | undefined): ProviderKeyStates =>
    Object.fromEntries(
      (providers ?? []).map((provider) => [
        provider.id,
        keyStore.state(provider.id, provider.address),
      ]),
    );

  /**
   * One of the core's providers, by a name the page sent. The page only names it: where
   * its key goes is what the core says, never anything from the page.
   */
  const findProvider = async (
    candidate: unknown,
  ): Promise<
    | { ok: true; provider: KnownProvider; all: KnownProvider[] }
    | { ok: false; error: CoreResult<never> }
  > => {
    const id = parseProviderId(candidate);
    if (!id) {
      return {
        ok: false,
        error: failure('invalid_request', 'Unknown AI provider.'),
      };
    }
    const all = (await readProviders(core))?.providers;
    const provider = all?.find((known) => known.id === id);
    if (!all || !provider) {
      return {
        ok: false,
        error: failure(
          'provider_unknown',
          'Couldn’t check that AI provider, so nothing changed. Try again in a moment.',
        ),
      };
    }
    return { ok: true, provider, all };
  };

  handle(IPC.providerKeyState, async (): Promise<ProviderKeyStates> =>
    keyStates((await readProviders(core))?.providers),
  );

  handle(
    IPC.providerSetApiKey,
    async (providerId: unknown, candidate: unknown): Promise<CoreResult<ProviderKeyStates>> => {
      let apiKey: string;
      try {
        apiKey = validateApiKey(candidate);
      } catch (error) {
        return failure('invalid_api_key', error instanceof Error ? error.message : 'Invalid key.');
      }
      const found = await findProvider(providerId);
      if (!found.ok) return found.error;
      const { provider } = found;
      try {
        // Kept with the address it is for: it is never handed over for another.
        keyStore.save(provider.id, provider.address, apiKey);
      } catch (error) {
        if (error instanceof SecureStorageUnavailableError) {
          return failure('secure_storage_unavailable', error.message);
        }
        return failure('key_not_saved', 'Couldn’t save the key on this computer.');
      }
      const pushed = await callCore(core.getConnection(), OPERATIONS['provider.set_credential'], {
        body: { api_key: apiKey, provider_id: provider.id },
      });
      if (!pushed.ok) return pushed;
      return { ok: true, data: keyStates(found.all) };
    },
  );

  registerImportHandlers(core, handle);
  registerDataHandlers({ core, dataDir: deps.dataDir }, handle);
  registerCourseFileHandlers({ core, dataDir: deps.dataDir }, handle);
  registerSettingsFileHandlers({ core, keyStore, uiState, dataDir: deps.dataDir }, handle);
  registerFilmFileHandlers({ core, dataDir: deps.dataDir }, handle);

  handle(
    IPC.providerClearApiKey,
    async (providerId: unknown): Promise<CoreResult<ProviderKeyStates>> => {
      const found = await findProvider(providerId);
      if (!found.ok) return found.error;
      const { provider } = found;
      keyStore.clear(provider.id, provider.address);
      const cleared = await callCore(
        core.getConnection(),
        OPERATIONS['provider.clear_credential'],
        { query: { provider_id: provider.id } },
      );
      // The key is gone from disk regardless; a stopped core holds nothing in memory.
      if (!cleared.ok && cleared.error.code !== 'core_unavailable') return cleared;
      return { ok: true, data: keyStates(found.all) };
    },
  );

  handle(IPC.providerSelect, async (candidate: unknown): Promise<CoreResult<null>> => {
    // "Automatic" names no provider: there is nothing to look up. Any other choice must
    // be a provider the core offers.
    let selection: ProviderSelection;
    if (candidate === PROVIDER_AUTOMATIC) {
      selection = PROVIDER_AUTOMATIC;
    } else {
      const found = await findProvider(candidate);
      if (!found.ok) return found.error;
      selection = found.provider.id;
    }
    // The core decides whether this is a moment to change (not while it is writing).
    const chosen = await callCore(core.getConnection(), OPERATIONS['provider.select'], {
      body: { selection },
    });
    if (!chosen.ok) return chosen;
    // Remembered for the next launch only once it is true now.
    keyStore.select(selection);
    return { ok: true, data: null };
  });
}

/** Hand a validated list of paths to the core's internal import route. */
async function startImport(
  core: CoreProcess,
  courseId: unknown,
  candidatePaths: unknown,
): Promise<CoreResult<ImportJob>> {
  const id = parseCourseId(courseId);
  if (!id) return failure('invalid_request', 'Couldn’t find that course.');
  const parsed = parseImportPaths(candidatePaths);
  if (!parsed.ok) return failure(parsed.code, parsed.message);
  const result = await callCore(core.getConnection(), OPERATIONS['sources.import_paths'], {
    path: { course_id: id },
    body: { paths: parsed.paths },
  });
  return result as CoreResult<ImportJob>;
}

function registerImportHandlers(
  core: CoreProcess,
  handle: <Args extends unknown[], Result>(
    channel: string,
    handler: (...args: Args) => Promise<Result> | Result,
  ) => void,
): void {
  handle(
    IPC.sourcesImportWithPicker,
    async (courseId: unknown): Promise<CoreResult<ImportJob | null>> => {
      if (!parseCourseId(courseId)) return failure('invalid_request', 'Couldn’t find that course.');
      const owner = BrowserWindow.getFocusedWindow() ?? BrowserWindow.getAllWindows()[0];
      const options: Electron.OpenDialogOptions = {
        title: 'Add course materials',
        buttonLabel: 'Import',
        properties: ['openFile', 'multiSelections'],
        filters: [{ name: 'Documents', extensions: [...SOURCE_FILE_EXTENSIONS] }],
      };
      const picked = owner
        ? await dialog.showOpenDialog(owner, options)
        : await dialog.showOpenDialog(options);
      if (picked.canceled || picked.filePaths.length === 0) return { ok: true, data: null };
      if (picked.filePaths.length > MAX_IMPORT_FILES) {
        return failure('too_many_files', `Import at most ${MAX_IMPORT_FILES} files at a time.`);
      }
      return startImport(core, courseId, picked.filePaths);
    },
  );

  handle(IPC.sourcesImportPaths, (courseId: unknown, paths: unknown) =>
    startImport(core, courseId, paths),
  );
}

/** Forward core status changes to the app window. */
export function forwardCoreStatus(core: CoreProcess, getContents: () => WebContents | null): void {
  core.on('status', (status) => {
    const contents = getContents();
    if (contents && !contents.isDestroyed()) contents.send(IPC.coreStatusChanged, status);
  });
}
