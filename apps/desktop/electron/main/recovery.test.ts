import { mkdtempSync, readFileSync, rmSync, statSync, writeFileSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { type AppLog, createAppLog, formatLine, type LogDetail } from './app-log';
import {
  CORE_RESTART_WINDOW_MS,
  MAIN_FAILED,
  MAIN_FAILED_AT_START,
  MAX_CORE_RESTARTS,
  mayRestartCore,
  MIN_UPTIME_TO_RESTART_SECONDS,
  noteRejection,
  oneAtATime,
  PAGE_GONE,
  PAGE_HUNG,
  type Question,
  whenMainFailed,
  whenPageGone,
  whenPageHung,
} from './recovery';

function recorder(): AppLog & { lines: { event: string; detail: LogDetail | undefined }[] } {
  const lines: { event: string; detail: LogDetail | undefined }[] = [];
  return { lines, record: (event, detail) => lines.push({ event, detail }) };
}

function page(answer: number) {
  const log = recorder();
  const asked: Question[] = [];
  return {
    asked,
    log,
    reload: vi.fn(),
    quit: vi.fn(),
    ask: (question: Question) => {
      asked.push(question);
      return Promise.resolve(answer);
    },
  };
}

describe('a page whose process is gone', () => {
  it('is reloaded when the learner says so, and the reason is noted', async () => {
    const actions = page(0);
    expect(await whenPageGone({ reason: 'crashed', exitCode: 133 }, actions)).toBe('reloaded');
    expect(actions.reload).toHaveBeenCalledTimes(1);
    expect(actions.quit).not.toHaveBeenCalled();
    expect(actions.asked).toEqual([PAGE_GONE]);
    expect(actions.log.lines).toEqual([
      { event: 'page-gone', detail: { reason: 'crashed', exitCode: 133 } },
    ]);
  });

  it('quits when the learner would rather', async () => {
    const actions = page(1);
    expect(await whenPageGone({ reason: 'oom', exitCode: -1 }, actions)).toBe('quit');
    expect(actions.quit).toHaveBeenCalledTimes(1);
    expect(actions.reload).not.toHaveBeenCalled();
  });

  it('says nothing when the process simply ended', async () => {
    const actions = page(0);
    expect(await whenPageGone({ reason: 'clean-exit', exitCode: 0 }, actions)).toBe('ignored');
    expect(actions.asked).toEqual([]);
    expect(actions.log.lines).toEqual([]);
  });

  it.each(['crashed', 'killed', 'oom', 'launch-failed', 'integrity-failure', 'abnormal-exit'])(
    'treats "%s" as a failure the learner must hear about',
    async (reason) => {
      const actions = page(0);
      await whenPageGone({ reason, exitCode: 1 }, actions);
      expect(actions.asked).toHaveLength(1);
    },
  );
});

describe('a page that has stopped answering', () => {
  it('is left alone by default: it may only be busy', async () => {
    const actions = page(0);
    expect(await whenPageHung(actions)).toBe('waited');
    expect(actions.reload).not.toHaveBeenCalled();
    expect(actions.asked).toEqual([PAGE_HUNG]);
    expect(actions.log.lines).toEqual([{ event: 'page-unresponsive', detail: undefined }]);
  });

  it('is reloaded when the learner asks', async () => {
    const actions = page(1);
    expect(await whenPageHung(actions)).toBe('reloaded');
    expect(actions.reload).toHaveBeenCalledTimes(1);
  });
});

describe('what the learner is told', () => {
  it.each([PAGE_GONE, PAGE_HUNG, MAIN_FAILED, MAIN_FAILED_AT_START])(
    'says the work is safe, in plain words, with no code or trace: $title',
    (question) => {
      const text = `${question.title} ${question.message} ${question.detail}`;
      expect(text).toContain('saved as you went');
      expect(text).not.toMatch(/exception|stack|renderer|process|0x|null|undefined/i);
      expect(question.buttons).toHaveLength(2);
    },
  );

  it('says that nothing is sent anywhere when something has failed', () => {
    for (const question of [PAGE_GONE, MAIN_FAILED]) {
      expect(question.detail).toMatch(/[Nn]othing( about this)? is sent anywhere/);
    }
  });
});

describe('one question at a time', () => {
  it('ignores a second failure while the first is still being answered', async () => {
    let answer: () => void = () => undefined;
    const handler = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          answer = resolve;
        }),
    );
    const guarded = oneAtATime(handler);

    guarded();
    guarded();
    guarded();
    expect(handler).toHaveBeenCalledTimes(1);

    answer();
    await Promise.resolve();
    await Promise.resolve();
    guarded();
    expect(handler).toHaveBeenCalledTimes(2);
  });

  it('is free again after a handler that failed', async () => {
    const handler = vi
      .fn<() => Promise<void>>()
      .mockRejectedValueOnce(new Error('the dialog could not open'))
      .mockResolvedValue(undefined);
    const guarded = oneAtATime(handler);
    // The rejection is the handler's own; nothing here may leave it unhandled.
    const unhandled = vi.fn();
    process.on('unhandledRejection', unhandled);
    guarded();
    await new Promise((resolve) => setTimeout(resolve, 10));
    process.off('unhandledRejection', unhandled);
    expect(unhandled).not.toHaveBeenCalled();
    guarded();
    expect(handler).toHaveBeenCalledTimes(2);
  });
});

describe('an error nobody caught in the main process', () => {
  function main(answer: number, uptimeSeconds: number) {
    const log = recorder();
    const asked: Question[] = [];
    return {
      asked,
      log,
      restart: vi.fn(),
      quit: vi.fn(),
      uptimeSeconds: () => uptimeSeconds,
      ask: (question: Question) => {
        asked.push(question);
        return Promise.resolve(answer);
      },
    };
  }

  it('offers a restart, and restarts', async () => {
    const actions = main(0, 600);
    expect(await whenMainFailed(new TypeError('x is not a function'), actions)).toBe('restarted');
    expect(actions.asked).toEqual([MAIN_FAILED]);
    expect(actions.restart).toHaveBeenCalledTimes(1);
    expect(actions.log.lines[0]).toMatchObject({
      event: 'uncaught-exception',
      detail: { name: 'TypeError', message: 'x is not a function' },
    });
  });

  it('quits when the learner chooses to', async () => {
    const actions = main(1, 600);
    expect(await whenMainFailed(new Error('boom'), actions)).toBe('quit');
    expect(actions.quit).toHaveBeenCalledTimes(1);
    expect(actions.restart).not.toHaveBeenCalled();
  });

  it('never restarts into a failure that happens at start-up', async () => {
    const actions = main(0, MIN_UPTIME_TO_RESTART_SECONDS - 1);
    expect(await whenMainFailed(new Error('boom at start'), actions)).toBe('quit');
    expect(actions.asked).toEqual([MAIN_FAILED_AT_START]);
    expect(actions.restart).not.toHaveBeenCalled();
    expect(actions.quit).toHaveBeenCalledTimes(1);
  });

  it('copes with something thrown that is not an error', async () => {
    const actions = main(1, 600);
    await whenMainFailed('just a string', actions);
    expect(actions.log.lines[0]?.detail).toEqual({
      name: 'NonError',
      message: 'just a string',
      stack: null,
    });
  });

  it('only notes a promise that was rejected with nobody waiting', () => {
    const log = recorder();
    noteRejection(new RangeError('out of range'), log);
    expect(log.lines).toEqual([
      {
        event: 'unhandled-rejection',
        detail: expect.objectContaining({
          name: 'RangeError',
          message: 'out of range',
        }) as LogDetail,
      },
    ]);
  });
});

describe('a core that stopped by itself', () => {
  const now = 1_000_000_000;

  it('is started again the first and the second time', () => {
    expect(mayRestartCore([], now)).toBe(true);
    expect(mayRestartCore([now - 60_000], now)).toBe(true);
  });

  it('is left stopped once it keeps dying', () => {
    expect(mayRestartCore([now - 120_000, now - 60_000], now)).toBe(false);
    expect(MAX_CORE_RESTARTS).toBe(2);
  });

  it('is given another chance after a quiet while', () => {
    const longAgo = now - CORE_RESTART_WINDOW_MS - 1;
    expect(mayRestartCore([longAgo, longAgo], now)).toBe(true);
    expect(mayRestartCore([longAgo, now - 1000], now)).toBe(true);
    expect(mayRestartCore([longAgo, now - 2000, now - 1000], now)).toBe(false);
  });
});

describe('the local log', () => {
  let directory: string;
  beforeEach(() => {
    directory = mkdtempSync(path.join(os.tmpdir(), 'adle-log-test-'));
  });
  afterEach(() => {
    rmSync(directory, { recursive: true, force: true, maxRetries: 5, retryDelay: 50 });
  });

  const at = new Date('2026-11-19T12:00:00.000Z');

  it('writes one line of JSON for each thing that happened', () => {
    const log = createAppLog(path.join(directory, 'logs'), () => at);
    log.record('page-gone', { reason: 'crashed', exitCode: 133 });
    log.record('page-unresponsive');
    const lines = readFileSync(path.join(directory, 'logs', 'app.log'), 'utf8')
      .trim()
      .split('\n');
    expect(lines.map((line) => JSON.parse(line) as unknown)).toEqual([
      { at: '2026-11-19T12:00:00.000Z', event: 'page-gone', reason: 'crashed', exitCode: 133 },
      { at: '2026-11-19T12:00:00.000Z', event: 'page-unresponsive' },
    ]);
  });

  it('cuts a long value short and turns nothing into null', () => {
    const line = JSON.parse(formatLine(at, 'x', { long: 'a'.repeat(5000), none: undefined })) as {
      long: string;
      none: null;
    };
    expect(line.long.length).toBeLessThan(2100);
    expect(line.long.endsWith('…')).toBe(true);
    expect(line.none).toBeNull();
  });

  it('starts afresh rather than grow without limit', () => {
    const logs = path.join(directory, 'logs');
    const log = createAppLog(logs, () => at);
    log.record('first');
    writeFileSync(path.join(logs, 'app.log'), 'x'.repeat(600 * 1024));
    log.record('after-the-limit');
    const file = path.join(logs, 'app.log');
    expect(statSync(file).size).toBeLessThan(1024);
    expect(readFileSync(file, 'utf8')).toContain('after-the-limit');
  });

  it('never throws, even when it cannot write', () => {
    const blocked = path.join(directory, 'a-file');
    writeFileSync(blocked, 'not a folder');
    const log = createAppLog(path.join(blocked, 'logs'), () => at);
    expect(() => log.record('page-gone', { reason: 'crashed' })).not.toThrow();
  });
});
