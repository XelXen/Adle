import path from 'node:path';

import { isInside } from './data-copy';

/**
 * Rules for a course saved as a file and brought in from one (ADR-063). Pure, so they can
 * be tested without Electron; the handlers that use them are in `course-files.ts`.
 *
 * What the page sends is checked here as untrusted: which kind of file, and what it holds.
 * Every path checked here came from a dialog of the operating system or from the core's own
 * folder, never from the page.
 */

/** A course file is a zip. */
export const COURSE_FILE_EXTENSION = 'zip';
/** The folder inside the data directory where the core writes a file to be handed over. */
const HANDOVER_FOLDER = 'handover';
/** The only kind of name the core gives such a file. */
const HANDED_OVER = /^course-[0-9a-f]{20}\.zip$/;
const MAX_PATH_LENGTH = 4096;

export const COURSE_FILE_KINDS = ['template', 'transfer'] as const;
export type CourseFileKind = (typeof COURSE_FILE_KINDS)[number];

/** What goes into a file, or is brought in from one. The course's plan always is. */
export interface CourseFileHolds {
  lessons: boolean;
  /** The documents the course was made from, and their text. */
  materials: boolean;
  /** The learner's own: answers, what they showed, where they stopped. */
  progress: boolean;
  /** The questions they asked during lessons, and the answers. */
  notes: boolean;
}

const HOLDS: readonly (keyof CourseFileHolds)[] = ['lessons', 'materials', 'progress', 'notes'];

function isPlainRecord(value: unknown): value is Record<string, unknown> {
  return (
    typeof value === 'object' &&
    value !== null &&
    !Array.isArray(value) &&
    Object.getPrototypeOf(value) === Object.prototype
  );
}

/** Exactly the four choices, each true or false: nothing else, and none left out. */
export function parseHolds(candidate: unknown): CourseFileHolds | null {
  if (!isPlainRecord(candidate)) return null;
  const names = Object.keys(candidate);
  if (names.length !== HOLDS.length || !HOLDS.every((name) => names.includes(name))) return null;
  if (!HOLDS.every((name) => typeof candidate[name] === 'boolean')) return null;
  return {
    lessons: candidate.lessons === true,
    materials: candidate.materials === true,
    progress: candidate.progress === true,
    notes: candidate.notes === true,
  };
}

export interface CourseFileRequest {
  kind: CourseFileKind;
  holds: CourseFileHolds;
}

/** What the page asks to be saved: a kind of file, and what it holds. */
export function parseCourseFileRequest(candidate: unknown): CourseFileRequest | null {
  if (!isPlainRecord(candidate) || Object.keys(candidate).length !== 2) return null;
  const { kind } = candidate;
  if (typeof kind !== 'string' || !(COURSE_FILE_KINDS as readonly string[]).includes(kind)) {
    return null;
  }
  const holds = parseHolds(candidate.holds);
  return holds ? { kind: kind as CourseFileKind, holds } : null;
}

/**
 * Where the core left a file to be handed over, from the name it gave: only a name of the
 * one kind the core makes, and only inside its folder.
 */
export function handedOverPath(dataDir: string, name: unknown): string | null {
  if (typeof name !== 'string' || !HANDED_OVER.test(name)) return null;
  return path.join(dataDir, HANDOVER_FOLDER, name);
}

function usablePath(candidate: unknown): string | null {
  if (typeof candidate !== 'string' || candidate.length === 0) return null;
  if (candidate.length > MAX_PATH_LENGTH || candidate.includes('\0')) return null;
  if (!path.isAbsolute(candidate)) return null;
  return path.resolve(candidate);
}

export type ParsedCourseSavePath =
  | {
      ok: true;
      path: string;
      /** True if the extension was added here: a file already there must not be replaced. */
      amended: boolean;
    }
  | { ok: false; message: string };

/** Check where a course file is to be saved, as the save dialog returned it. */
export function parseCourseSavePath(candidate: unknown, dataDir: string): ParsedCourseSavePath {
  const chosen = usablePath(candidate);
  if (!chosen) return { ok: false, message: 'That file name can’t be used.' };
  const amended = path.extname(chosen).toLowerCase() !== `.${COURSE_FILE_EXTENSION}`;
  const target = amended ? `${chosen}.${COURSE_FILE_EXTENSION}` : chosen;
  if (isInside(dataDir, target)) {
    return { ok: false, message: 'Choose a place outside Adle’s own data folder.' };
  }
  return { ok: true, path: target, amended };
}

export type ParsedCourseOpenPath = { ok: true; path: string } | { ok: false; message: string };

/**
 * Check the file to bring a course in from, as the open dialog returned it. Whether it
 * really is a course is for the core to decide, by reading it.
 */
export function parseCourseOpenPath(candidate: unknown): ParsedCourseOpenPath {
  const chosen = usablePath(candidate);
  if (!chosen) return { ok: false, message: 'That file can’t be used.' };
  if (path.extname(chosen).toLowerCase() !== `.${COURSE_FILE_EXTENSION}`) {
    return { ok: false, message: 'Choose a course saved by Adle: a file that ends in .zip.' };
  }
  return { ok: true, path: chosen };
}

/** A token the page is given for a file it chose, to say "that one" with. */
const TOKEN = /^[0-9a-f]{32}$/;

export function parseFileToken(candidate: unknown): string | null {
  return typeof candidate === 'string' && TOKEN.test(candidate) ? candidate : null;
}
