import { randomBytes } from 'node:crypto';
import { existsSync } from 'node:fs';
import { copyFile, rename, rm } from 'node:fs/promises';
import path from 'node:path';

import { BrowserWindow, dialog } from 'electron';

import { OPERATIONS } from '@adle/contracts';

import {
  type BroughtInCourse,
  type CoreResult,
  type CourseFileFound,
  IPC,
  type SavedCourseFile,
} from '../shared/ipc';
import { callCore } from './core/client';
import type { CoreProcess } from './core/process';
import {
  COURSE_FILE_EXTENSION,
  handedOverPath,
  parseCourseFileRequest,
  parseCourseOpenPath,
  parseCourseSavePath,
  parseFileToken,
  parseHolds,
} from './course-file-rules';
import { parseCourseId } from './imports';

/**
 * A course saved as a file, and brought in from one (ADR-063).
 *
 * The page says which course and what the file should hold, or which of the things a
 * chosen file holds to bring in. It never says where: the place a file is saved, and the
 * file a course is brought in from, are chosen in a window of the operating system that
 * only the learner can answer. A file the learner chose is known to the page by a token and
 * by its name, never by its path.
 */

export interface CourseFileDependencies {
  core: CoreProcess;
  /** Everything the core persists: it writes a file to be handed over inside it. */
  dataDir: string;
}

type Handle = <Args extends unknown[], Result>(
  channel: string,
  handler: (...args: Args) => Promise<Result> | Result,
) => void;

/** A course with its documents can take a while to write, and to read back. */
const FILE_TIMEOUT_MS = 600_000;
/** A file the learner chose is remembered this long, for them to say what to bring in. */
const CHOSEN_FOR_MS = 30 * 60_000;

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
  name: string;
  suggested_name: string;
  counts: SavedCourseFile['counts'];
  lessons_left_out: number;
}

export function registerCourseFileHandlers(deps: CourseFileDependencies, handle: Handle): void {
  const { core, dataDir } = deps;

  /** The file the learner chose last, and the token the page knows it by. */
  let chosen: { token: string; path: string; at: number } | null = null;

  handle(
    IPC.coursesSaveFile,
    async (courseId: unknown, candidate: unknown): Promise<CoreResult<SavedCourseFile | null>> => {
      const id = parseCourseId(courseId);
      const request = parseCourseFileRequest(candidate);
      if (!id || !request) return failure('invalid_request', 'Couldn’t save that course.');

      // Written first, in the core's own folder, so that the dialog can suggest the
      // course's name and the learner chooses only where a finished file goes.
      const written = await callCore(
        core.getConnection(),
        OPERATIONS['courses.save_file'],
        { path: { course_id: id }, body: request },
        { timeoutMs: FILE_TIMEOUT_MS },
      );
      if (!written.ok) return written;
      const saved = written.data as Saved;
      const source = handedOverPath(dataDir, saved.name);
      if (!source) return failure('core_error', 'Adle got an unexpected response. Try again.');
      const discard = async (): Promise<void> => {
        await rm(source, { force: true }).catch(() => undefined);
      };

      const options: Electron.SaveDialogOptions = {
        title: 'Save this course as a file',
        buttonLabel: 'Save',
        defaultPath: path.basename(String(saved.suggested_name)),
        filters: [{ name: 'Adle course', extensions: [COURSE_FILE_EXTENSION] }],
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
      const parsed = parseCourseSavePath(answer.filePath, dataDir);
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
        await move(source, parsed.path);
      } catch {
        await discard();
        return failure('not_saved', 'Couldn’t save the file there. Choose another place.');
      }
      return {
        ok: true,
        data: { fileName, counts: saved.counts, lessonsLeftOut: saved.lessons_left_out },
      };
    },
  );

  handle(IPC.coursesChooseFile, async (): Promise<CoreResult<CourseFileFound | null>> => {
    const options: Electron.OpenDialogOptions = {
      title: 'Import a course',
      buttonLabel: 'Open',
      properties: ['openFile'],
      filters: [{ name: 'Adle course', extensions: [COURSE_FILE_EXTENSION] }],
    };
    const window = owner();
    const picked = window
      ? await dialog.showOpenDialog(window, options)
      : await dialog.showOpenDialog(options);
    const [file] = picked.filePaths;
    if (picked.canceled || !file) return { ok: true, data: null };
    const parsed = parseCourseOpenPath(file);
    if (!parsed.ok) return failure('invalid_request', parsed.message);
    const looked = await callCore(core.getConnection(), OPERATIONS['courses.look_at_file'], {
      body: { path: parsed.path },
    });
    if (!looked.ok) return looked;
    const found = looked.data as Omit<CourseFileFound, 'token' | 'fileName'>;
    const token = randomBytes(16).toString('hex');
    chosen = { token, path: parsed.path, at: Date.now() };
    return {
      ok: true,
      data: {
        token,
        fileName: path.basename(parsed.path),
        title: found.title,
        kind: found.kind,
        counts: found.counts,
      },
    };
  });

  handle(
    IPC.coursesBringIn,
    async (candidate: unknown, holds: unknown): Promise<CoreResult<BroughtInCourse>> => {
      const token = parseFileToken(candidate);
      const wanted = parseHolds(holds);
      if (!token || !wanted) return failure('invalid_request', 'Couldn’t import that course.');
      // Only the file the learner chose, and only for a while after they chose it.
      if (!chosen || chosen.token !== token || Date.now() - chosen.at > CHOSEN_FOR_MS) {
        return failure('file_not_chosen', 'Choose the file again.');
      }
      const file = chosen.path;
      chosen = null;
      const brought = await callCore(
        core.getConnection(),
        OPERATIONS['courses.bring_in_file'],
        { body: { path: file, holds: wanted } },
        { timeoutMs: FILE_TIMEOUT_MS },
      );
      if (!brought.ok) return brought;
      const data = brought.data as {
        course_id: string;
        title: string;
        concepts: number;
        lessons: number;
        lessons_left_out: number;
        materials: number;
        progress: boolean;
        notes: number;
      };
      return {
        ok: true,
        data: {
          courseId: data.course_id,
          title: data.title,
          concepts: data.concepts,
          lessons: data.lessons,
          lessonsLeftOut: data.lessons_left_out,
          materials: data.materials,
          progress: data.progress,
          notes: data.notes,
        },
      };
    },
  );
}
