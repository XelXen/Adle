import { mkdirSync } from 'node:fs';

import {
  app,
  BrowserWindow,
  dialog,
  ipcMain,
  type IpcMainInvokeEvent,
  nativeTheme,
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
  type ProviderKeyState,
  type UiState,
} from '../shared/ipc';
import { callCore } from './core/client';
import type { CoreProcess } from './core/process';
import { registerDataHandlers } from './data';
import {
  MAX_IMPORT_FILES,
  parseCourseId,
  parseImportPaths,
  SOURCE_FILE_EXTENSIONS,
} from './imports';
import { type ProviderKeyStore, SecureStorageUnavailableError, validateApiKey } from './secrets';
import { openExternalLink } from './security';
import { parseUiStatePatch, type UiStateStore } from './ui-state';

/** Upper bound on a serialised request body coming from the renderer. */
const MAX_BODY_BYTES = 1024 * 1024;

export interface IpcDependencies {
  core: CoreProcess;
  keyStore: ProviderKeyStore;
  uiState: UiStateStore;
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

/** Push the stored provider key to a freshly started core. */
export async function syncProviderKey(deps: IpcDependencies): Promise<void> {
  const key = deps.keyStore.load();
  if (!key) return;
  await callCore(deps.core.getConnection(), OPERATIONS['provider.set_credential'], {
    body: { api_key: key },
  });
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
      return failure('not_opened', 'The folder could not be opened.');
    }
    const problem = await shell.openPath(deps.logsDir);
    return problem
      ? failure('not_opened', 'The folder could not be opened.')
      : { ok: true, data: null };
  });

  handle(IPC.coreStatus, () => core.status);
  handle(IPC.coreRestart, async () => {
    const status = await core.restart();
    if (status.state === 'ready') await syncProviderKey(deps);
    return status;
  });

  handle(IPC.coreInvoke, async (operation: unknown, params: unknown): Promise<CoreResult> => {
    const request = parseInvokeRequest(operation, params);
    if (!request.ok) return failure('invalid_request', request.reason);
    return callCore(core.getConnection(), OPERATIONS[request.operation], request.params);
  });

  handle(IPC.providerKeyState, (): ProviderKeyState => keyStore.state());

  handle(
    IPC.providerSetApiKey,
    async (candidate: unknown): Promise<CoreResult<ProviderKeyState>> => {
      let apiKey: string;
      try {
        apiKey = validateApiKey(candidate);
      } catch (error) {
        return failure('invalid_api_key', error instanceof Error ? error.message : 'Invalid key.');
      }
      try {
        keyStore.save(apiKey);
      } catch (error) {
        if (error instanceof SecureStorageUnavailableError) {
          return failure('secure_storage_unavailable', error.message);
        }
        return failure('key_not_saved', 'The key could not be saved on this computer.');
      }
      const pushed = await callCore(core.getConnection(), OPERATIONS['provider.set_credential'], {
        body: { api_key: apiKey },
      });
      if (!pushed.ok) return pushed;
      return { ok: true, data: keyStore.state() };
    },
  );

  registerImportHandlers(core, handle);
  registerDataHandlers(
    { core, dataDir: deps.dataDir, afterStart: () => syncProviderKey(deps) },
    handle,
  );

  handle(IPC.providerClearApiKey, async (): Promise<CoreResult<ProviderKeyState>> => {
    keyStore.clear();
    const cleared = await callCore(core.getConnection(), OPERATIONS['provider.clear_credential']);
    // The key is gone from disk regardless; a stopped core holds nothing in memory.
    if (!cleared.ok && cleared.error.code !== 'core_unavailable') return cleared;
    return { ok: true, data: keyStore.state() };
  });
}

/** Hand a validated list of paths to the core's internal import route. */
async function startImport(
  core: CoreProcess,
  courseId: unknown,
  candidatePaths: unknown,
): Promise<CoreResult<ImportJob>> {
  const id = parseCourseId(courseId);
  if (!id) return failure('invalid_request', 'That course could not be found.');
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
      if (!parseCourseId(courseId))
        return failure('invalid_request', 'That course could not be found.');
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
