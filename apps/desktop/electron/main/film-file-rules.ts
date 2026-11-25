import path from 'node:path';

import { isInside } from './data-copy';

/**
 * Rules for saving a film of a course where the learner chooses (ADR-065). Pure, so they
 * can be tested without Electron; the handler that uses them is in `film-files.ts`.
 *
 * The page says only which film. Every path checked here came from a dialog of the
 * operating system or from the core's own folder, never from the page.
 */

/** A film is an MP4 video, and its subtitles an SRT file beside it. */
export const FILM_EXTENSION = 'mp4';
export const CAPTIONS_EXTENSION = 'srt';
/** The folder inside the data directory where the core writes a file to be handed over. */
const HANDOVER_FOLDER = 'handover';
/** The only kinds of name the core gives a film handed over, and its subtitles. */
const HANDED_OVER: Record<string, RegExp> = {
  [FILM_EXTENSION]: /^film-[0-9a-f]{20}\.mp4$/,
  [CAPTIONS_EXTENSION]: /^film-[0-9a-f]{20}\.srt$/,
};
const FILM_ID = /^flm_[0-9a-f]{20}$/;
const MAX_PATH_LENGTH = 4096;

/** A film's id, as the core gives them out; anything else is refused. */
export function parseFilmId(candidate: unknown): string | null {
  return typeof candidate === 'string' && FILM_ID.test(candidate) ? candidate : null;
}

/**
 * Where the core left a film, or its subtitles, from the name it gave: only a name of the
 * kind the core makes for that, and only inside its folder.
 */
export function filmHandedOverPath(
  dataDir: string,
  name: unknown,
  extension: typeof FILM_EXTENSION | typeof CAPTIONS_EXTENSION,
): string | null {
  const pattern = HANDED_OVER[extension];
  if (typeof name !== 'string' || !pattern?.test(name)) return null;
  return path.join(dataDir, HANDOVER_FOLDER, name);
}

export type ParsedFilmSavePath =
  | {
      ok: true;
      path: string;
      /** Where its subtitles go: beside it, under its name. */
      captions: string;
      /** True if the extension was added here: a file already there must not be replaced. */
      amended: boolean;
    }
  | { ok: false; message: string };

/** Check where a film is to be saved, as the save dialog returned it. */
export function parseFilmSavePath(candidate: unknown, dataDir: string): ParsedFilmSavePath {
  if (typeof candidate !== 'string' || candidate.length === 0) {
    return { ok: false, message: 'That file name can’t be used.' };
  }
  if (
    candidate.length > MAX_PATH_LENGTH ||
    candidate.includes('\0') ||
    !path.isAbsolute(candidate)
  ) {
    return { ok: false, message: 'That file name can’t be used.' };
  }
  const chosen = path.resolve(candidate);
  const amended = path.extname(chosen).toLowerCase() !== `.${FILM_EXTENSION}`;
  const target = amended ? `${chosen}.${FILM_EXTENSION}` : chosen;
  if (isInside(dataDir, target)) {
    return { ok: false, message: 'Choose a place outside Adle’s own data folder.' };
  }
  const captions = path.join(
    path.dirname(target),
    `${path.basename(target, path.extname(target))}.${CAPTIONS_EXTENSION}`,
  );
  return { ok: true, path: target, captions, amended };
}
