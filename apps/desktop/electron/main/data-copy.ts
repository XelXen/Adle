import path from 'node:path';

/**
 * Rules for the files and folders involved in saving a copy of the learner's data,
 * restoring from one, and deleting everything. Pure, so they can be tested without
 * Electron; the handlers that use them are in `data.ts`.
 *
 * Every path checked here came from a dialog of the operating system or from the
 * app's own configuration, never from the page. The checks are for the day that
 * stops being true.
 */

/** A copy of Adle's data is a single file with this extension. */
export const COPY_EXTENSION = 'adle';
/** The core's own safety copies end in this. They are copies too and can be restored. */
export const SAFETY_COPY_EXTENSION = 'db';
/** The folder inside the data directory where the core keeps safety copies. */
const SAFETY_COPIES_FOLDER = 'backups';
const MAX_PATH_LENGTH = 4096;

/** "Adle data 2026-11-19.adle": sorts by date and says what it is. */
export function defaultCopyName(now: Date): string {
  const day = [
    now.getFullYear(),
    String(now.getMonth() + 1).padStart(2, '0'),
    String(now.getDate()).padStart(2, '0'),
  ].join('-');
  return `Adle data ${day}.${COPY_EXTENSION}`;
}

/** Whether `child` is `parent` itself or anything inside it. */
export function isInside(parent: string, child: string): boolean {
  const relative = path.relative(path.resolve(parent), path.resolve(child));
  return relative === '' || (!relative.startsWith('..') && !path.isAbsolute(relative));
}

/** Where the core keeps the copies it makes before it replaces or updates the data. */
export function safetyCopiesDir(dataDir: string): string {
  return path.join(dataDir, SAFETY_COPIES_FOLDER);
}

function usablePath(candidate: unknown): string | null {
  if (typeof candidate !== 'string' || candidate.length === 0) return null;
  if (candidate.length > MAX_PATH_LENGTH || candidate.includes('\0')) return null;
  if (!path.isAbsolute(candidate)) return null;
  return path.resolve(candidate);
}

export type ParsedSavePath =
  | {
      ok: true;
      path: string;
      /**
       * True if the extension was added here. The save dialog asked about replacing the
       * name the learner typed, not this one, so a file already there must not be replaced.
       */
      amended: boolean;
    }
  | { ok: false; message: string };

/** Check where a copy is to be saved, as the save dialog returned it. */
export function parseSavePath(candidate: unknown, dataDir: string): ParsedSavePath {
  const chosen = usablePath(candidate);
  if (!chosen) return { ok: false, message: 'That file name can’t be used.' };
  // Not every save dialog adds the extension of its filter (GTK's does not).
  const amended = path.extname(chosen).toLowerCase() !== `.${COPY_EXTENSION}`;
  const target = amended ? `${chosen}.${COPY_EXTENSION}` : chosen;
  // A copy kept inside the folder it is a copy of would be deleted or replaced with it.
  if (isInside(dataDir, target)) {
    return { ok: false, message: 'Choose a place outside Adle’s own data folder.' };
  }
  return { ok: true, path: target, amended };
}

export type ParsedRestorePath = { ok: true; path: string } | { ok: false; message: string };

/**
 * Check the file to restore from, as the open dialog returned it. Whether it really is
 * a copy of Adle's data is for the core to decide, by reading it; the extension only
 * catches a slip of the hand.
 */
export function parseRestorePath(candidate: unknown): ParsedRestorePath {
  const chosen = usablePath(candidate);
  if (!chosen) return { ok: false, message: 'That file can’t be used.' };
  const extension = path.extname(chosen).toLowerCase();
  if (extension !== `.${COPY_EXTENSION}` && extension !== `.${SAFETY_COPY_EXTENSION}`) {
    return {
      ok: false,
      message: `Choose a copy of your data: a file that ends in .${COPY_EXTENSION}.`,
    };
  }
  return { ok: true, path: chosen };
}

/**
 * Whether a folder may be deleted as "everything Adle has stored". It must be a folder
 * of its own: never a relative path, the root of a disk, or a folder directly under one.
 */
export function canErase(dataDir: string): boolean {
  if (typeof dataDir !== 'string' || !path.isAbsolute(dataDir)) return false;
  const resolved = path.resolve(dataDir);
  const parent = path.dirname(resolved);
  return parent !== resolved && path.dirname(parent) !== parent;
}
