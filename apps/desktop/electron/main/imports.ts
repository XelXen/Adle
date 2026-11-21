import path from 'node:path';

/**
 * Validation for importing course materials.
 *
 * File paths reach the core only from here: from the operating system's file
 * dialog, or from files the learner dropped (resolved to paths by the preload
 * script from real `File` objects). Renderer script can never name a path.
 */

/** Extensions offered in the file dialog. The core re-checks type by content. */
export const SOURCE_FILE_EXTENSIONS = ['pdf', 'docx', 'md', 'markdown', 'txt'] as const;
export const MAX_IMPORT_FILES = 50;
const MAX_PATH_LENGTH = 4096;
const COURSE_ID = /^crs_[0-9a-f]{20}$/;

export function parseCourseId(value: unknown): string | null {
  return typeof value === 'string' && COURSE_ID.test(value) ? value : null;
}

export type ImportPathsResult =
  { ok: true; paths: string[] } | { ok: false; code: string; message: string };

/** Accept only a bounded list of absolute, well-formed paths. */
export function parseImportPaths(value: unknown): ImportPathsResult {
  if (!Array.isArray(value) || value.length === 0) {
    return { ok: false, code: 'no_files', message: 'No files were chosen.' };
  }
  if (value.length > MAX_IMPORT_FILES) {
    return {
      ok: false,
      code: 'too_many_files',
      message: `Import at most ${MAX_IMPORT_FILES} files at a time.`,
    };
  }
  const paths: string[] = [];
  for (const entry of value) {
    if (
      typeof entry !== 'string' ||
      entry.length === 0 ||
      entry.length > MAX_PATH_LENGTH ||
      entry.includes('\0') ||
      !path.isAbsolute(entry)
    ) {
      return { ok: false, code: 'invalid_request', message: 'One of the files can’t be used.' };
    }
    paths.push(entry);
  }
  return { ok: true, paths: [...new Set(paths)] };
}
