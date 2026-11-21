import { type ChildProcessWithoutNullStreams, spawn } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import { EventEmitter } from 'node:events';
import { createWriteStream, mkdirSync, type WriteStream } from 'node:fs';
import path from 'node:path';

import type { CoreStatus } from '../../shared/ipc';
import type { LaunchSpec } from './launch-spec';

export interface CoreConnection {
  baseUrl: string;
  token: string;
}

export interface CoreProcessOptions {
  /** Resolved lazily so a missing installation becomes a `failed` status, not a crash. */
  resolveSpec: () => LaunchSpec;
  dataDir: string;
  logsDir: string;
  readyTimeoutMs?: number;
  /** How long a start may take when it has a copy to restore first. */
  restoreTimeoutMs?: number;
  stopTimeoutMs?: number;
  /**
   * What a core that has just come up must be given before anything else may use it (the
   * learner's choice of provider and their keys). It runs on every start, before "ready"
   * is said to anyone, so no request can reach a core that does not have them yet. If it
   * fails, so does the start.
   */
  afterReady?: (connection: CoreConnection) => Promise<void>;
}

const NOT_PREPARED =
  'Adle couldn’t give its background service your AI provider settings, so it was not started. ' +
  'Restart it from Settings, under About.';

const DEFAULT_READY_TIMEOUT_MS = 30_000;
/** A start that first restores a copy checks, copies, and upgrades a whole database. */
const DEFAULT_RESTORE_TIMEOUT_MS = 180_000;
const DEFAULT_STOP_TIMEOUT_MS = 6_000;
/** Stop buffering protocol output from a misbehaving child. */
const MAX_STDOUT_BUFFER = 64 * 1024;

/** What the core says about a restore it was asked to do while starting. */
export type RestoreReport = { ok: true } | { ok: false; message: string };

/** Something to do once, while starting, before any data is opened. */
export interface LaunchInstruction {
  /** Replace the data with this copy first. An absolute path chosen by the learner. */
  restoreFrom?: string;
}

interface ReadyEvent {
  event: 'ready';
  port: number;
  version: string;
  restore: RestoreReport | null;
}

function parseRestoreReport(value: unknown): RestoreReport | null {
  if (typeof value !== 'object' || value === null) return null;
  const record = value as Record<string, unknown>;
  if (record.ok === true) return { ok: true };
  if (record.ok === false && typeof record.message === 'string') {
    return { ok: false, message: record.message.slice(0, 500) };
  }
  return null;
}

function parseProtocolLine(line: string): ReadyEvent | { event: 'fatal'; message: string } | null {
  let value: unknown;
  try {
    value = JSON.parse(line);
  } catch {
    return null;
  }
  if (typeof value !== 'object' || value === null) return null;
  const record = value as Record<string, unknown>;
  if (
    record.event === 'ready' &&
    typeof record.port === 'number' &&
    Number.isInteger(record.port) &&
    record.port > 0 &&
    record.port < 65536 &&
    typeof record.version === 'string'
  ) {
    return {
      event: 'ready',
      port: record.port,
      version: record.version,
      restore: parseRestoreReport(record.restore),
    };
  }
  if (record.event === 'fatal' && typeof record.message === 'string') {
    return { event: 'fatal', message: record.message.slice(0, 500) };
  }
  return null;
}

/**
 * Supervises the Python core as a child process.
 *
 * Security properties (see SECURITY.md):
 * - The per-launch token is generated here and delivered over stdin, never via
 *   argv or the environment.
 * - The child binds loopback on an OS-assigned port and reports it on stdout.
 * - Closing the child's stdin asks it to exit; it also exits if this process dies.
 */
export class CoreProcess extends EventEmitter<{
  status: [CoreStatus];
  /** The core exited after starting, and nobody had asked it to. */
  'stopped-unexpectedly': [];
}> {
  private child: ChildProcessWithoutNullStreams | null = null;
  private connection: CoreConnection | null = null;
  private currentStatus: CoreStatus = { state: 'stopped' };
  private logStream: WriteStream | null = null;
  private starting: Promise<CoreStatus> | null = null;
  private stopping = false;
  /** True while something that needs the core stopped is running; see `whileStopped`. */
  private held = false;
  private restoreReport: RestoreReport | null = null;

  constructor(private readonly options: CoreProcessOptions) {
    super();
  }

  get status(): CoreStatus {
    return this.currentStatus;
  }

  /** Connection details for the main-process client. Never sent to the renderer. */
  getConnection(): CoreConnection | null {
    return this.connection;
  }

  /**
   * What the core reported about the restore asked for at its latest start, or null if none
   * was asked for (or the core did not get far enough to try).
   */
  get lastRestore(): RestoreReport | null {
    return this.restoreReport;
  }

  start(instruction: LaunchInstruction = {}): Promise<CoreStatus> {
    if (this.currentStatus.state === 'ready') return Promise.resolve(this.currentStatus);
    if (this.held) return Promise.resolve(this.currentStatus);
    this.starting ??= this.launch(instruction).finally(() => {
      this.starting = null;
    });
    return this.starting;
  }

  async restart(instruction: LaunchInstruction = {}): Promise<CoreStatus> {
    await this.stop();
    return this.start(instruction);
  }

  /**
   * Stop the core and run `work` while it stays stopped. Until `work` has finished,
   * nothing can start the core again (a start asked for meanwhile is not carried out),
   * so `work` may delete or replace the core's files. Start it again afterwards.
   */
  async whileStopped<T>(work: () => Promise<T> | T): Promise<T> {
    this.held = true;
    try {
      // A start already under way has a child by now; stopping ends that too.
      await this.stop();
      return await work();
    } finally {
      this.held = false;
    }
  }

  async stop(): Promise<void> {
    const child = this.child;
    if (!child) {
      this.setStatus({ state: 'stopped' });
      return;
    }
    this.stopping = true;
    const exited = new Promise<void>((resolve) => child.once('exit', () => resolve()));
    child.stdin.end(); // EOF on stdin is the graceful-shutdown signal.
    const timeout = this.options.stopTimeoutMs ?? DEFAULT_STOP_TIMEOUT_MS;
    const timer = setTimeout(() => child.kill(), timeout);
    await exited;
    clearTimeout(timer);
    this.stopping = false;
    this.setStatus({ state: 'stopped' });
  }

  private setStatus(status: CoreStatus): void {
    this.currentStatus = status;
    this.emit('status', status);
  }

  private openLog(): WriteStream {
    mkdirSync(this.options.logsDir, { recursive: true });
    // Truncate on each launch: the log is for diagnosing the current session only.
    return createWriteStream(path.join(this.options.logsDir, 'core.log'), { flags: 'w' });
  }

  private launch(instruction: LaunchInstruction): Promise<CoreStatus> {
    this.restoreReport = null;
    this.setStatus({ state: 'starting' });

    let spec: LaunchSpec;
    try {
      spec = this.options.resolveSpec();
      mkdirSync(this.options.dataDir, { recursive: true });
      this.logStream = this.openLog();
    } catch (error) {
      const message =
        error instanceof Error ? error.message : 'Adle’s background service couldn’t start.';
      this.setStatus({ state: 'failed', message });
      return Promise.resolve(this.currentStatus);
    }

    const token = randomBytes(32).toString('hex');
    const child = spawn(spec.command, spec.args, {
      cwd: spec.cwd,
      env: {
        ...process.env,
        ADLE_DATA_DIR: this.options.dataDir,
        PYTHONUNBUFFERED: '1',
        PYTHONUTF8: '1',
      },
      stdio: ['pipe', 'pipe', 'pipe'],
      windowsHide: true,
    });
    this.child = child;
    child.stderr.pipe(this.logStream, { end: false });

    return new Promise<CoreStatus>((resolve) => {
      let settled = false;
      let buffer = '';

      const settle = (status: CoreStatus): void => {
        if (settled) return;
        settled = true;
        clearTimeout(readyTimer);
        this.setStatus(status);
        resolve(status);
      };

      const patience = instruction.restoreFrom
        ? (this.options.restoreTimeoutMs ?? DEFAULT_RESTORE_TIMEOUT_MS)
        : (this.options.readyTimeoutMs ?? DEFAULT_READY_TIMEOUT_MS);
      const readyTimer = setTimeout(() => {
        settle({ state: 'failed', message: 'Adle took too long to start.' });
        child.kill();
      }, patience);

      child.stdout.setEncoding('utf8');
      child.stdout.on('data', (chunk: string) => {
        if (settled) return;
        buffer += chunk;
        if (buffer.length > MAX_STDOUT_BUFFER) buffer = buffer.slice(-MAX_STDOUT_BUFFER);
        let newline: number;
        while ((newline = buffer.indexOf('\n')) >= 0) {
          const line = buffer.slice(0, newline).trim();
          buffer = buffer.slice(newline + 1);
          const event = parseProtocolLine(line);
          if (event?.event === 'ready') {
            this.restoreReport = event.restore;
            const connection = { baseUrl: `http://127.0.0.1:${event.port}`, token };
            const version = event.version;
            void (async () => {
              try {
                await this.options.afterReady?.(connection);
              } catch {
                if (settled) return;
                settle({ state: 'failed', message: NOT_PREPARED });
                child.kill();
                return;
              }
              // It may have given up or gone meanwhile; then it is not ready after all.
              if (settled) return;
              this.connection = connection;
              settle({ state: 'ready', version });
            })();
          } else if (event?.event === 'fatal') {
            settle({ state: 'failed', message: event.message });
          }
        }
      });

      child.once('error', (error) => {
        settle({
          state: 'failed',
          message: `Adle’s background service couldn’t start (${error.name}).`,
        });
      });

      child.once('exit', (code) => {
        this.child = null;
        this.connection = null;
        this.logStream?.end();
        this.logStream = null;
        if (!settled) {
          settle({
            state: 'failed',
            message: `Adle’s background service stopped while starting (exit code ${code ?? 'unknown'}).`,
          });
        } else if (!this.stopping && this.currentStatus.state === 'ready') {
          this.setStatus({
            state: 'failed',
            message: 'Adle’s background service stopped unexpectedly. Your saved progress is safe.',
          });
          // Nobody asked it to stop. Whoever supervises may want to start it again.
          this.emit('stopped-unexpectedly');
        }
      });

      // The handshake. Writing to a pipe keeps the token out of argv and the environment.
      child.stdin.on('error', () => {
        /* The exit handler reports the failure; a broken pipe here is not actionable. */
      });
      // A one-time instruction travels the same way: it names a file, and argv is visible
      // to other processes.
      const handshake = instruction.restoreFrom
        ? { token, restore_from: instruction.restoreFrom }
        : { token };
      child.stdin.write(`${JSON.stringify(handshake)}\n`);
    });
  }
}
