import { existsSync } from 'node:fs';
import { copyFile, rename, rm } from 'node:fs/promises';
import path from 'node:path';

import { BrowserWindow, dialog } from 'electron';

import { OPERATIONS } from '@adle/contracts';

import { type CoreResult, IPC, type SavedFilmFile } from '../shared/ipc';
import { callCore } from './core/client';
import type { CoreProcess } from './core/process';
import {
  CAPTIONS_EXTENSION,
  FILM_EXTENSION,
  filmHandedOverPath,
  parseFilmId,
  parseFilmSavePath,
} from './film-file-rules';

/**
 * A film of a course saved where the learner chooses (ADR-065), as a course file is
 * (ADR-063): the core writes it in a folder of its own and says its name; the place it
 * goes is asked here, in a window of the operating system, and the file is moved there.
 * The page says which film, and is told the name of what was saved: never a path.
 */

export interface FilmFileDependencies {
  core: CoreProcess;
  /** Everything the core persists: it writes a film to be handed over inside it. */
  dataDir: string;
}

type Handle = <Args extends unknown[], Result>(
  channel: string,
  handler: (...args: Args) => Promise<Result> | Result,
) => void;

/** A long film takes a while to copy. */
const FILE_TIMEOUT_MS = 600_000;

function failure(code: string, message: string): CoreResult<never> {
  return { ok: false, error: { code, message, status: 0 } };
}

function owner(): BrowserWindow | undefined {
  return BrowserWindow.getFocusedWindow() ?? BrowserWindow.getAllWindows()[0];
}

/** Move a file to where the learner chose: to another disk it is copied, then removed. */
async function move(from: string, to: string): Promise<void> {
  try {
    await rename(from, to);
  } catch {
    await copyFile(from, to);
    await rm(from, { force: true });
  }
}

interface Saved {
  file_name: string;
  captions_name: string | null;
  suggested_name: string;
}

export function registerFilmFileHandlers(deps: FilmFileDependencies, handle: Handle): void {
  const { core, dataDir } = deps;

  handle(IPC.filmsSaveFile, async (filmId: unknown): Promise<CoreResult<SavedFilmFile | null>> => {
    const id = parseFilmId(filmId);
    if (!id) return failure('invalid_request', 'Couldn’t save that film.');

    const written = await callCore(
      core.getConnection(),
      OPERATIONS['films.save_file'],
      { path: { film_id: id } },
      { timeoutMs: FILE_TIMEOUT_MS },
    );
    if (!written.ok) return written;
    const saved = written.data as Saved;
    const video = filmHandedOverPath(dataDir, saved.file_name, FILM_EXTENSION);
    const captions =
      saved.captions_name === null
        ? null
        : filmHandedOverPath(dataDir, saved.captions_name, CAPTIONS_EXTENSION);
    if (!video) return failure('core_error', 'Adle got an unexpected response. Try again.');
    const discard = async (): Promise<void> => {
      await rm(video, { force: true }).catch(() => undefined);
      if (captions) await rm(captions, { force: true }).catch(() => undefined);
    };

    const options: Electron.SaveDialogOptions = {
      title: 'Save this film',
      buttonLabel: 'Save',
      defaultPath: path.basename(String(saved.suggested_name)),
      filters: [{ name: 'Video', extensions: [FILM_EXTENSION] }],
      properties: ['createDirectory', 'showOverwriteConfirmation'],
    };
    const window = owner();
    const answer = window
      ? await dialog.showSaveDialog(window, options)
      : await dialog.showSaveDialog(options);
    if (answer.canceled || !answer.filePath) {
      await discard();
      return { ok: true, data: null };
    }
    const parsed = parseFilmSavePath(answer.filePath, dataDir);
    if (!parsed.ok) {
      await discard();
      return failure('invalid_request', parsed.message);
    }
    const fileName = path.basename(parsed.path);
    if (parsed.amended && existsSync(parsed.path)) {
      await discard();
      return failure(
        'invalid_request',
        `There is already a file called ${fileName} there. Choose another name.`,
      );
    }
    try {
      await move(video, parsed.path);
    } catch {
      await discard();
      return failure('not_saved', 'Couldn’t save the film there. Choose another place.');
    }
    // Its subtitles go beside it, but never over a file the learner has there already.
    let withCaptions = false;
    if (captions && !existsSync(parsed.captions)) {
      try {
        await move(captions, parsed.captions);
        withCaptions = true;
      } catch {
        withCaptions = false;
      }
    }
    if (captions && !withCaptions) await rm(captions, { force: true }).catch(() => undefined);
    return { ok: true, data: { fileName, withCaptions } };
  });
}
