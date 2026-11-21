/**
 * The handlers behind "Save a copy", "Restore from a copy", "Delete everything", and
 * "Show safety copies", with Electron's dialogs, the core, and the core client replaced.
 * The journeys through the real app are in `e2e/data.spec.ts`; these are the branches a
 * journey cannot reach: a core that will not come back, a folder that will not go away,
 * two actions at once.
 */
import { existsSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import type * as FsPromises from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { OPERATIONS } from '@adle/contracts';

import { type CoreResult, type CoreStatus, IPC } from '../shared/ipc';
import type { CoreProcess, LaunchInstruction, RestoreReport } from './core/process';

const electron = vi.hoisted(() => ({
  save: vi.fn(),
  open: vi.fn(),
  confirm: vi.fn(),
  openPath: vi.fn(),
}));
const client = vi.hoisted(() => ({ callCore: vi.fn() }));
const disk = vi.hoisted(() => ({ refuseToDelete: false }));

vi.mock('electron', () => ({
  BrowserWindow: { getFocusedWindow: () => null, getAllWindows: () => [] },
  dialog: {
    showSaveDialog: electron.save,
    showOpenDialog: electron.open,
    showMessageBox: electron.confirm,
  },
  shell: { openPath: electron.openPath },
}));
vi.mock('./core/client', () => ({ callCore: client.callCore }));
vi.mock('node:fs/promises', async (importOriginal) => {
  const actual = await importOriginal<typeof FsPromises>();
  return {
    ...actual,
    rm: (...args: Parameters<typeof actual.rm>) =>
      disk.refuseToDelete ? Promise.reject(new Error('EBUSY')) : actual.rm(...args),
  };
});

const { registerDataHandlers } = await import('./data');

const READY: CoreStatus = { state: 'ready', version: 'test' };
const CONNECTION = { baseUrl: 'http://127.0.0.1:1', token: 't'.repeat(64) };

let root: string;
let dataDir: string;

interface FakeCore {
  lastRestore: RestoreReport | null;
  getConnection: () => typeof CONNECTION;
  restart: ReturnType<typeof vi.fn<(instruction?: LaunchInstruction) => Promise<CoreStatus>>>;
  start: ReturnType<typeof vi.fn<() => Promise<CoreStatus>>>;
  whileStopped: <T>(work: () => Promise<T> | T) => Promise<T>;
  /** What happened, in order, so a test can check nothing was deleted under a running core. */
  log: string[];
}

function setUp(changes: Partial<FakeCore> = {}) {
  const log: string[] = [];
  const core: FakeCore = {
    lastRestore: null,
    getConnection: () => CONNECTION,
    restart: vi.fn((_instruction?: LaunchInstruction) => {
      log.push('restart');
      return Promise.resolve(READY);
    }),
    start: vi.fn(() => {
      log.push('start');
      return Promise.resolve(READY);
    }),
    whileStopped: async (work) => {
      log.push('stopped');
      try {
        return await work();
      } finally {
        log.push(existsSync(dataDir) ? 'released with the folder there' : 'released, folder gone');
      }
    },
    log,
    ...changes,
  };
  const handlers = new Map<string, () => Promise<CoreResult<unknown>>>();
  registerDataHandlers({ core: core as unknown as CoreProcess, dataDir }, (channel, handler) => {
    handlers.set(channel, handler as () => Promise<CoreResult<unknown>>);
  });
  const call = (channel: string): Promise<CoreResult<unknown>> => {
    const handler = handlers.get(channel);
    if (!handler) throw new Error(`No handler for ${channel}.`);
    return handler();
  };
  return { core, call, log };
}

beforeEach(() => {
  root = mkdtempSync(path.join(os.tmpdir(), 'adle-data-test-'));
  dataDir = path.join(root, 'profile', 'data');
  mkdirSync(path.join(dataDir, 'backups'), { recursive: true });
  writeFileSync(path.join(dataDir, 'adle.db'), 'the database');
  writeFileSync(path.join(dataDir, 'backups', 'adle-replaced-1.db'), 'a safety copy');
  disk.refuseToDelete = false;
  for (const mock of [electron.save, electron.open, electron.confirm, electron.openPath]) {
    mock.mockReset();
  }
  client.callCore.mockReset();
});

afterEach(() => {
  rmSync(root, { recursive: true, force: true, maxRetries: 5, retryDelay: 50 });
});

describe('saving a copy', () => {
  it('does nothing when the learner closes the dialog', async () => {
    electron.save.mockResolvedValue({ canceled: true, filePath: '' });
    const { call } = setUp();
    expect(await call(IPC.dataSaveCopy)).toEqual({ ok: true, data: null });
    expect(client.callCore).not.toHaveBeenCalled();
  });

  it('hands the chosen path to the internal operation and reports only the name', async () => {
    const chosen = path.join(root, 'Documents', 'Adle data 2026-11-19.adle');
    electron.save.mockResolvedValue({ canceled: false, filePath: chosen });
    client.callCore.mockResolvedValue({ ok: true, data: null });
    const { call } = setUp();

    const result = await call(IPC.dataSaveCopy);

    expect(result).toEqual({ ok: true, data: { fileName: 'Adle data 2026-11-19.adle' } });
    // The page is told what was saved, not where: it has no use for a path.
    expect(JSON.stringify(result)).not.toContain('Documents');
    expect(client.callCore).toHaveBeenCalledTimes(1);
    const [connection, operation, params, options] = client.callCore.mock.calls[0]!;
    expect(connection).toBe(CONNECTION);
    expect(operation).toBe(OPERATIONS['data.save_copy']);
    expect(params).toEqual({ body: { path: chosen } });
    // A large database takes longer to copy than an ordinary call is allowed.
    expect((options as { timeoutMs: number }).timeoutMs).toBeGreaterThan(60_000);
  });

  it('offers a name with today’s date and asks about replacing a file', async () => {
    electron.save.mockResolvedValue({ canceled: true, filePath: '' });
    const { call } = setUp();
    await call(IPC.dataSaveCopy);
    const options = electron.save.mock.calls[0]!.at(-1) as Electron.SaveDialogOptions;
    expect(options.defaultPath).toMatch(/^Adle data \d{4}-\d{2}-\d{2}\.adle$/);
    expect(options.filters).toEqual([{ name: 'Adle data', extensions: ['adle'] }]);
    expect(options.properties).toContain('showOverwriteConfirmation');
  });

  it('passes on the reason when the core could not write the copy', async () => {
    electron.save.mockResolvedValue({ canceled: false, filePath: path.join(root, 'copy.adle') });
    const refusal = {
      ok: false,
      error: {
        code: 'copy_not_saved',
        message: 'Adle could not save the copy there.',
        status: 400,
      },
    };
    client.callCore.mockResolvedValue(refusal);
    const { call } = setUp();
    expect(await call(IPC.dataSaveCopy)).toEqual(refusal);
  });

  it('never replaces a file the dialog did not ask about', async () => {
    // The learner typed "copy"; the ending is added here; "copy.adle" is already there.
    writeFileSync(path.join(root, 'copy.adle'), 'an older copy');
    electron.save.mockResolvedValue({ canceled: false, filePath: path.join(root, 'copy') });
    const { call } = setUp();
    expect(await call(IPC.dataSaveCopy)).toMatchObject({
      ok: false,
      error: { message: 'There is already a file called copy.adle there. Choose another name.' },
    });
    expect(client.callCore).not.toHaveBeenCalled();
  });
});

describe('restoring from a copy', () => {
  const copy = (): string => path.join(root, 'Documents', 'mine.adle');

  it('does nothing when the learner closes the dialog', async () => {
    electron.open.mockResolvedValue({ canceled: true, filePaths: [] });
    const { call, core } = setUp();
    expect(await call(IPC.dataRestoreCopy)).toEqual({ ok: true, data: null });
    expect(core.restart).not.toHaveBeenCalled();
  });

  it('does not stop the core for a file that cannot be a copy', async () => {
    electron.open.mockResolvedValue({ canceled: false, filePaths: [path.join(root, 'notes.pdf')] });
    const { call, core } = setUp();
    expect(await call(IPC.dataRestoreCopy)).toMatchObject({
      ok: false,
      error: { code: 'invalid_request' },
    });
    expect(core.restart).not.toHaveBeenCalled();
  });

  it('restarts the core with the copy (which is handed its keys as part of starting)', async () => {
    electron.open.mockResolvedValue({ canceled: false, filePaths: [copy()] });
    const { call, core, log } = setUp({ lastRestore: { ok: true } });
    expect(await call(IPC.dataRestoreCopy)).toEqual({ ok: true, data: { restored: true } });
    expect(core.restart).toHaveBeenCalledWith({ restoreFrom: copy() });
    expect(log).toEqual(['restart']);
  });

  it('reports the core’s reason when it refuses the copy, and the core runs on', async () => {
    electron.open.mockResolvedValue({ canceled: false, filePaths: [copy()] });
    const message = 'That file is not a copy of your data. Your current data was not changed.';
    const { call } = setUp({ lastRestore: { ok: false, message } });
    expect(await call(IPC.dataRestoreCopy)).toEqual({
      ok: false,
      error: { code: 'restore_refused', message, status: 0 },
    });
  });

  it('does not claim a restore the core said nothing about', async () => {
    electron.open.mockResolvedValue({ canceled: false, filePaths: [copy()] });
    const { call } = setUp({ lastRestore: null });
    expect(await call(IPC.dataRestoreCopy)).toMatchObject({
      ok: false,
      error: { code: 'restore_failed', message: expect.stringContaining('unchanged') as string },
    });
  });

  it('says so when the core does not come back', async () => {
    electron.open.mockResolvedValue({ canceled: false, filePaths: [copy()] });
    const failed: CoreStatus = { state: 'failed', message: 'The core service took too long.' };
    const { call } = setUp({ restart: vi.fn(() => Promise.resolve(failed)) });
    expect(await call(IPC.dataRestoreCopy)).toEqual({
      ok: false,
      error: { code: 'core_unavailable', message: 'The core service took too long.', status: 0 },
    });
  });
});

describe('deleting everything', () => {
  it('asks first, with "Cancel" as the answer a stray key press gives', async () => {
    electron.confirm.mockResolvedValue({ response: 0 });
    const { call, log } = setUp();
    expect(await call(IPC.dataEraseAll)).toEqual({ ok: true, data: null });
    const options = electron.confirm.mock.calls[0]!.at(-1) as Electron.MessageBoxOptions;
    expect(options.buttons).toEqual(['Cancel', 'Delete everything']);
    expect(options.defaultId).toBe(0);
    expect(options.cancelId).toBe(0);
    expect(log).toEqual([]);
    expect(existsSync(path.join(dataDir, 'adle.db'))).toBe(true);
  });

  it('deletes the folder while the core is held stopped, then starts it afresh', async () => {
    electron.confirm.mockResolvedValue({ response: 1 });
    const { call, log } = setUp();
    expect(await call(IPC.dataEraseAll)).toEqual({ ok: true, data: { erased: true } });
    expect(existsSync(dataDir)).toBe(false);
    // In this order: stopped, gone before anything may start it, started.
    expect(log).toEqual(['stopped', 'released, folder gone', 'start']);
  });

  it('leaves everything outside the data folder alone', async () => {
    electron.confirm.mockResolvedValue({ response: 1 });
    const beside = path.join(root, 'profile', 'credentials.bin');
    writeFileSync(beside, 'the encrypted key');
    const { call } = setUp();
    await call(IPC.dataEraseAll);
    expect(existsSync(beside)).toBe(true);
  });

  it('starts the core again and says so when the folder cannot be deleted', async () => {
    electron.confirm.mockResolvedValue({ response: 1 });
    disk.refuseToDelete = true;
    const { call, log } = setUp();
    expect(await call(IPC.dataEraseAll)).toMatchObject({
      ok: false,
      error: { code: 'erase_failed' },
    });
    expect(log).toEqual(['stopped', 'released with the folder there', 'start']);
  });

  it('says what happened when everything is gone but the core does not start', async () => {
    electron.confirm.mockResolvedValue({ response: 1 });
    const failed: CoreStatus = { state: 'failed', message: 'No Python was found.' };
    const { call } = setUp({ start: vi.fn(() => Promise.resolve(failed)) });
    expect(await call(IPC.dataEraseAll)).toEqual({
      ok: false,
      error: { code: 'core_unavailable', message: 'No Python was found.', status: 0 },
    });
    expect(existsSync(dataDir)).toBe(false);
  });

  it('refuses a folder that is plainly not its own, before stopping anything', async () => {
    electron.confirm.mockResolvedValue({ response: 1 });
    dataDir = path.parse(root).root;
    const { call, log } = setUp();
    expect(await call(IPC.dataEraseAll)).toMatchObject({
      ok: false,
      error: { code: 'erase_failed' },
    });
    expect(log).toEqual([]);
  });
});

describe('one thing at a time', () => {
  it('refuses a second action while the first is waiting on the learner', async () => {
    let answer: (value: { canceled: boolean; filePath: string }) => void = () => undefined;
    electron.save.mockReturnValue(
      new Promise((resolve) => {
        answer = resolve;
      }),
    );
    electron.confirm.mockResolvedValue({ response: 1 });
    const { call, log } = setUp();

    const saving = call(IPC.dataSaveCopy);
    // The save dialog is still open, and something asks to delete everything.
    expect(await call(IPC.dataEraseAll)).toMatchObject({ ok: false, error: { code: 'busy' } });
    expect(await call(IPC.dataRestoreCopy)).toMatchObject({ ok: false, error: { code: 'busy' } });
    expect(electron.confirm).not.toHaveBeenCalled();
    expect(log).toEqual([]);

    answer({ canceled: true, filePath: '' });
    expect(await saving).toEqual({ ok: true, data: null });
    // Once it has finished, the next one goes ahead.
    expect(await call(IPC.dataEraseAll)).toEqual({ ok: true, data: { erased: true } });
  });

  it('is free again after an action that threw', async () => {
    electron.save.mockRejectedValueOnce(new Error('the dialog could not open'));
    const { call } = setUp();
    await expect(call(IPC.dataSaveCopy)).rejects.toThrow('could not open');
    electron.save.mockResolvedValue({ canceled: true, filePath: '' });
    expect(await call(IPC.dataSaveCopy)).toEqual({ ok: true, data: null });
  });
});

describe('showing the safety copies', () => {
  it('opens the one folder it is for, whatever it is called with', async () => {
    electron.openPath.mockResolvedValue('');
    const { call } = setUp();
    expect(await call(IPC.dataShowSafetyCopies)).toEqual({ ok: true, data: null });
    expect(electron.openPath).toHaveBeenCalledExactlyOnceWith(path.join(dataDir, 'backups'));
  });

  it('says there are none when the folder is not there', async () => {
    rmSync(path.join(dataDir, 'backups'), { recursive: true });
    const { call } = setUp();
    expect(await call(IPC.dataShowSafetyCopies)).toMatchObject({
      ok: false,
      error: { code: 'not_found', message: 'There are no safety copies yet.' },
    });
    expect(electron.openPath).not.toHaveBeenCalled();
  });

  it('reports a file manager that would not open it', async () => {
    electron.openPath.mockResolvedValue('Failed to open path');
    const { call } = setUp();
    expect(await call(IPC.dataShowSafetyCopies)).toMatchObject({
      ok: false,
      error: { code: 'not_opened' },
    });
  });
});
