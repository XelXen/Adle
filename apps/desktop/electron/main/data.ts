import { existsSync } from 'node:fs';
import { rm } from 'node:fs/promises';
import path from 'node:path';

import { BrowserWindow, dialog, shell } from 'electron';

import { OPERATIONS } from '@adle/contracts';

import { type CoreResult, IPC, type SavedCopy } from '../shared/ipc';
import { callCore } from './core/client';
import type { CoreProcess } from './core/process';
import {
  canErase,
  COPY_EXTENSION,
  defaultCopyName,
  parseRestorePath,
  parseSavePath,
  SAFETY_COPY_EXTENSION,
  safetyCopiesDir,
} from './data-copy';

/**
 * The learner's data as a whole: save a copy, restore from one, delete everything.
 *
 * Each of these begins in a window of the operating system that only the learner can
 * answer: where to save, which file to restore, whether to delete. The page asks for the
 * action and never supplies a path or a confirmation, so nothing running in the page can
 * copy the data somewhere, swap it, or destroy it on its own (ADR-016).
 */

export interface DataDependencies {
  core: CoreProcess;
  /** Everything the core persists. Deleted as a whole when the learner deletes everything. */
  dataDir: string;
  /** What must happen whenever the core has started again (it is handed the provider key). */
  afterStart: () => Promise<void>;
}

type Handle = <Args extends unknown[], Result>(
  channel: string,
  handler: (...args: Args) => Promise<Result> | Result,
) => void;

/** Writing a copy of a large database takes longer than an ordinary call. */
const SAVE_TIMEOUT_MS = 180_000;

function failure(code: string, message: string): CoreResult<never> {
  return { ok: false, error: { code, message, status: 0 } };
}

function owner(): BrowserWindow | undefined {
  return BrowserWindow.getFocusedWindow() ?? BrowserWindow.getAllWindows()[0];
}

export function registerDataHandlers(deps: DataDependencies, handle: Handle): void {
  const { core, dataDir, afterStart } = deps;

  /** One of these at a time: each reads, replaces, or deletes the whole of the data. */
  let busy = false;
  const exclusively = async <T>(work: () => Promise<CoreResult<T>>): Promise<CoreResult<T>> => {
    if (busy) return failure('busy', 'Adle is still working on your data. Try again in a moment.');
    busy = true;
    try {
      return await work();
    } finally {
      busy = false;
    }
  };

  handle(IPC.dataSaveCopy, () =>
    exclusively<SavedCopy | null>(async () => {
      const options: Electron.SaveDialogOptions = {
        title: 'Save a copy of your Adle data',
        buttonLabel: 'Save copy',
        defaultPath: defaultCopyName(new Date()),
        filters: [{ name: 'Adle data', extensions: [COPY_EXTENSION] }],
        properties: ['createDirectory', 'showOverwriteConfirmation'],
      };
      const window = owner();
      const chosen = window
        ? await dialog.showSaveDialog(window, options)
        : await dialog.showSaveDialog(options);
      if (chosen.canceled || !chosen.filePath) return { ok: true, data: null };

      const parsed = parseSavePath(chosen.filePath, dataDir);
      if (!parsed.ok) return failure('invalid_request', parsed.message);
      const fileName = path.basename(parsed.path);
      if (parsed.amended && existsSync(parsed.path)) {
        return failure(
          'invalid_request',
          `There is already a file called ${fileName} there. Choose another name.`,
        );
      }
      const saved = await callCore(
        core.getConnection(),
        OPERATIONS['data.save_copy'],
        { body: { path: parsed.path } },
        { timeoutMs: SAVE_TIMEOUT_MS },
      );
      if (!saved.ok) return saved;
      return { ok: true, data: { fileName } };
    }),
  );

  handle(IPC.dataRestoreCopy, () =>
    exclusively<{ restored: true } | null>(async () => {
      const options: Electron.OpenDialogOptions = {
        title: 'Restore your Adle data from a copy',
        buttonLabel: 'Restore',
        properties: ['openFile'],
        filters: [{ name: 'Adle data', extensions: [COPY_EXTENSION, SAFETY_COPY_EXTENSION] }],
      };
      const window = owner();
      const picked = window
        ? await dialog.showOpenDialog(window, options)
        : await dialog.showOpenDialog(options);
      const [file] = picked.filePaths;
      if (picked.canceled || !file) return { ok: true, data: null };
      const parsed = parseRestorePath(file);
      if (!parsed.ok) return failure('invalid_request', parsed.message);

      // The data cannot be swapped under a running core. It is stopped, and replaces its
      // data as the first thing it does when it starts again: after checking the copy,
      // after bringing it up to date, and after keeping what it replaces.
      const status = await core.restart({ restoreFrom: parsed.path });
      if (status.state === 'ready') await afterStart();
      const report = core.lastRestore;
      if (status.state !== 'ready') {
        return failure(
          'core_unavailable',
          status.state === 'failed'
            ? status.message
            : 'Adle could not start again after the restore.',
        );
      }
      if (!report) {
        return failure('restore_failed', 'The copy was not restored. Your data is as it was.');
      }
      if (!report.ok) return failure('restore_refused', report.message);
      return { ok: true, data: { restored: true } };
    }),
  );

  handle(IPC.dataEraseAll, () =>
    exclusively<{ erased: true } | null>(async () => {
      const options: Electron.MessageBoxOptions = {
        type: 'warning',
        title: 'Delete everything',
        message: 'Delete everything Adle has stored on this computer?',
        detail:
          'Every course, imported material, lesson, answer, and safety copy will be ' +
          'permanently deleted. This cannot be undone. Copies you saved elsewhere, and your ' +
          'AI provider key, are not touched.',
        buttons: ['Cancel', 'Delete everything'],
        defaultId: 0,
        cancelId: 0,
        noLink: true,
      };
      const window = owner();
      const answer = window
        ? await dialog.showMessageBox(window, options)
        : await dialog.showMessageBox(options);
      if (answer.response !== 1) return { ok: true, data: null };
      if (!canErase(dataDir)) {
        return failure('erase_failed', 'Adle could not tell which folder holds its data.');
      }

      // Nothing can start the core between stopping it and the folder being gone.
      const erased = await core.whileStopped(async () => {
        try {
          await rm(dataDir, { recursive: true, force: true, maxRetries: 8, retryDelay: 250 });
          return true;
        } catch {
          return false;
        }
      });
      // Whatever happened, the core is started again so the app is usable.
      const status = await core.start();
      if (status.state === 'ready') await afterStart();
      if (!erased) {
        return failure(
          'erase_failed',
          'Some of the data could not be deleted. Close anything that may have a file of ' +
            'Adle open, then try again.',
        );
      }
      if (status.state !== 'ready') {
        return failure(
          'core_unavailable',
          status.state === 'failed'
            ? status.message
            : 'Everything was deleted, but Adle could not start again. Restart the app.',
        );
      }
      return { ok: true, data: { erased: true } };
    }),
  );

  handle(IPC.dataShowSafetyCopies, async (): Promise<CoreResult<null>> => {
    // A fixed folder of the app's own: the page chooses nothing here.
    const folder = safetyCopiesDir(dataDir);
    if (!existsSync(folder)) return failure('not_found', 'There are no safety copies yet.');
    const problem = await shell.openPath(folder);
    if (problem) return failure('not_opened', 'The folder could not be opened.');
    return { ok: true, data: null };
  });
}
