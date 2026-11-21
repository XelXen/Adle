/** Tests for the core supervisor and its HTTP client, using a fake child process and fake fetch. */
import { mkdtempSync, rmSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { CoreStatus } from '../../shared/ipc';
import { buildPath, buildQuery, callCore } from './client';
import { CoreProcess } from './process';

const FAKE_CORE = path.join(import.meta.dirname, '__fixtures__', 'fake-core.mjs');

let directory: string;
const running: CoreProcess[] = [];

function createCore(
  mode: string,
  overrides: {
    readyTimeoutMs?: number;
    restoreTimeoutMs?: number;
    stopTimeoutMs?: number;
    afterReady?: (connection: { baseUrl: string; token: string }) => Promise<void>;
  } = {},
) {
  const core = new CoreProcess({
    resolveSpec: () => ({ command: process.execPath, args: [FAKE_CORE, mode], cwd: directory }),
    dataDir: path.join(directory, 'data'),
    logsDir: path.join(directory, 'logs'),
    ...overrides,
  });
  running.push(core);
  return core;
}

beforeEach(() => {
  directory = mkdtempSync(path.join(os.tmpdir(), 'adle-core-test-'));
});

afterEach(async () => {
  await Promise.all(running.splice(0).map((core) => core.stop()));
  rmSync(directory, { recursive: true, force: true, maxRetries: 5, retryDelay: 50 });
});

describe('CoreProcess', () => {
  it('starts, reports readiness, and exposes a loopback connection with a fresh token', async () => {
    const core = createCore('ready');
    const statuses: CoreStatus[] = [];
    core.on('status', (status) => statuses.push(status));

    expect(await core.start()).toEqual({ state: 'ready', version: 'fake' });
    expect(statuses.map((status) => status.state)).toEqual(['starting', 'ready']);

    const connection = core.getConnection();
    expect(connection?.baseUrl).toBe('http://127.0.0.1:4321');
    expect(connection?.token).toMatch(/^[0-9a-f]{64}$/);
  });

  it('is not ready for anyone until it has been given what it needs', async () => {
    let handedOver: (() => void) | undefined;
    const given: { baseUrl: string; token: string }[] = [];
    const core = createCore('ready', {
      afterReady: (connection) => {
        given.push(connection);
        return new Promise<void>((resolve) => {
          handedOver = resolve;
        });
      },
    });
    const statuses: CoreStatus[] = [];
    core.on('status', (status) => statuses.push(status));

    const starting = core.start();
    await vi.waitFor(() => expect(given).toHaveLength(1));
    // The core process is up, and what prepares it has its address. Nobody else does.
    expect(given[0]?.baseUrl).toBe('http://127.0.0.1:4321');
    expect(core.status.state).toBe('starting');
    expect(core.getConnection()).toBeNull();
    expect(statuses.map((status) => status.state)).toEqual(['starting']);

    handedOver?.();
    expect(await starting).toEqual({ state: 'ready', version: 'fake' });
    expect(core.getConnection()).toEqual(given[0]);
    expect(statuses.map((status) => status.state)).toEqual(['starting', 'ready']);
  });

  it('does not start at all if it could not be given what it needs', async () => {
    const core = createCore('ready', {
      afterReady: () => Promise.reject(new Error('the choice of provider was refused')),
    });
    const status = await core.start();
    expect(status.state).toBe('failed');
    // Said for the learner, with nothing of the error in it.
    expect(status).toMatchObject({ message: expect.stringContaining('AI provider settings') });
    expect(JSON.stringify(status)).not.toContain('refused');
    expect(core.getConnection()).toBeNull();
  });

  it('prepares the core again every time it starts', async () => {
    const afterReady = vi.fn(() => Promise.resolve());
    const core = createCore('ready', { afterReady });
    await core.start();
    await core.restart();
    expect(afterReady).toHaveBeenCalledTimes(2);
  });

  it('delivers the token over stdin only, never argv or the environment', async () => {
    const core = createCore('echo-argv');
    expect(await core.start()).toEqual({ state: 'ready', version: 'fake' });
  });

  it('shares one launch between concurrent start calls', async () => {
    const core = createCore('ready');
    const [first, second] = await Promise.all([core.start(), core.start()]);
    expect(first).toEqual(second);
  });

  it('surfaces a fatal startup message from the core', async () => {
    const core = createCore('fatal');
    expect(await core.start()).toEqual({
      state: 'failed',
      message: 'No data directory configured.',
    });
    expect(core.getConnection()).toBeNull();
  });

  it('fails cleanly when the core never becomes ready', async () => {
    const core = createCore('silent', { readyTimeoutMs: 300 });
    const status = await core.start();
    expect(status).toEqual({
      state: 'failed',
      message: 'Adle took too long to start.',
    });
  });

  it('reports a missing installation as a failed status instead of throwing', async () => {
    const core = new CoreProcess({
      resolveSpec: () => {
        throw new Error('The core service environment is not set up.');
      },
      dataDir: path.join(directory, 'data'),
      logsDir: path.join(directory, 'logs'),
    });
    expect(await core.start()).toEqual({
      state: 'failed',
      message: 'The core service environment is not set up.',
    });
  });

  it('notices an unexpected exit after startup', async () => {
    const core = createCore('crash');
    await core.start();
    const failed = await new Promise<CoreStatus>((resolve) => {
      core.on('status', (status) => {
        if (status.state === 'failed') resolve(status);
      });
    });
    expect(failed.state).toBe('failed');
    expect(core.getConnection()).toBeNull();
  });

  it('says so when it stopped without being asked, and only then', async () => {
    const crashing = createCore('crash');
    const stopped = new Promise<void>((resolve) => {
      crashing.once('stopped-unexpectedly', () => resolve());
    });
    await crashing.start();
    await stopped;
    expect(crashing.status.state).toBe('failed');

    const polite = createCore('ready');
    let surprised = false;
    polite.on('stopped-unexpectedly', () => {
      surprised = true;
    });
    await polite.start();
    await polite.stop();
    await polite.whileStopped(() => undefined);
    expect(surprised).toBe(false);
  });

  it('stops gracefully by closing stdin, and kills a core that ignores it', async () => {
    const polite = createCore('ready');
    await polite.start();
    await polite.stop();
    expect(polite.status).toEqual({ state: 'stopped' });
    expect(polite.getConnection()).toBeNull();

    const stubborn = createCore('stubborn', { stopTimeoutMs: 200 });
    await stubborn.start();
    await stubborn.stop();
    expect(stubborn.status).toEqual({ state: 'stopped' });
  });

  it('can restart after a stop', async () => {
    const core = createCore('ready');
    await core.start();
    const firstToken = core.getConnection()?.token;
    expect(await core.restart()).toEqual({ state: 'ready', version: 'fake' });
    // Every launch gets its own token.
    expect(core.getConnection()?.token).not.toBe(firstToken);
  });

  describe('a start that first restores a copy', () => {
    const copy = (name: string): string => path.join(directory, 'copies', name);

    it('passes the file over stdin and reports what the core said about it', async () => {
      const core = createCore('ready');
      await core.start();
      // Nothing was asked for, so there is nothing to report.
      expect(core.lastRestore).toBeNull();

      expect(await core.restart({ restoreFrom: copy('mine.adle') })).toEqual({
        state: 'ready',
        version: 'fake',
      });
      // The fake answers "leaked" if the path reached it through argv or the environment.
      expect(core.lastRestore).toEqual({ ok: true });
    });

    it('reports a refusal with its reason while the core runs on', async () => {
      const core = createCore('ready');
      expect((await core.start({ restoreFrom: copy('refused.adle') })).state).toBe('ready');
      expect(core.lastRestore).toEqual({
        ok: false,
        message: 'That file is not a copy of your data.',
      });
      expect(core.getConnection()).not.toBeNull();
    });

    it('does not mistake a report it cannot read for a success', async () => {
      const core = createCore('ready');
      expect((await core.start({ restoreFrom: copy('garbled.adle') })).state).toBe('ready');
      expect(core.lastRestore).toBeNull();
    });

    it('forgets the report at the next ordinary start', async () => {
      const core = createCore('ready');
      await core.start({ restoreFrom: copy('mine.adle') });
      expect(core.lastRestore).toEqual({ ok: true });
      await core.restart();
      expect(core.lastRestore).toBeNull();
    });

    it('is given longer than an ordinary start, but not for ever', async () => {
      const patient = createCore('ready', { readyTimeoutMs: 100, restoreTimeoutMs: 5000 });
      expect((await patient.start({ restoreFrom: copy('slow.adle') })).state).toBe('ready');
      expect(patient.lastRestore).toEqual({ ok: true });

      const impatient = createCore('ready', { readyTimeoutMs: 5000, restoreTimeoutMs: 100 });
      expect(await impatient.start({ restoreFrom: copy('slow.adle') })).toEqual({
        state: 'failed',
        message: 'Adle took too long to start.',
      });
      expect(impatient.lastRestore).toBeNull();
    });
  });

  describe('work that needs the core stopped', () => {
    it('runs with the core stopped, and nothing can start it meanwhile', async () => {
      const core = createCore('ready');
      await core.start();
      const seen: CoreStatus[] = [];

      const result = await core.whileStopped(async () => {
        seen.push(core.status);
        // Someone presses "Restart" in another part of the app while the files are going.
        seen.push(await core.start());
        seen.push(await core.restart());
        return 'done';
      });

      expect(result).toBe('done');
      expect(seen).toEqual([{ state: 'stopped' }, { state: 'stopped' }, { state: 'stopped' }]);
      expect(core.getConnection()).toBeNull();
      // Afterwards it starts as usual.
      expect(await core.start()).toEqual({ state: 'ready', version: 'fake' });
    });

    it('lets the core start again even if the work fails', async () => {
      const core = createCore('ready');
      await core.start();
      await expect(
        core.whileStopped(() => {
          throw new Error('the disk said no');
        }),
      ).rejects.toThrow('the disk said no');
      expect(await core.start()).toEqual({ state: 'ready', version: 'fake' });
    });

    it('ends a start that was already under way', async () => {
      const core = createCore('silent', { readyTimeoutMs: 10_000 });
      const starting = core.start();
      await core.whileStopped(() => undefined);
      expect((await starting).state).toBe('failed');
      expect(core.status).toEqual({ state: 'stopped' });
    });
  });
});

describe('core client', () => {
  const connection = { baseUrl: 'http://127.0.0.1:9', token: 't'.repeat(64) };
  const json = (status: number, body: unknown, headers: Record<string, string> = {}) =>
    new Response(body === null ? null : JSON.stringify(body), { status, headers });

  it('builds paths and queries safely', () => {
    expect(buildPath('/v1/courses/{course_id}', { course_id: 'crs_0123abc' })).toBe(
      '/v1/courses/crs_0123abc',
    );
    expect(buildPath('/v1/x/{a}/y/{b}', { a: 'seg_part-1', b: 7 })).toBe('/v1/x/seg_part-1/y/7');
    expect(() => buildPath('/v1/courses/{course_id}', {})).toThrow(/course_id/);
    // Nothing that could turn one address into another once the core has decoded it.
    for (const value of [
      '..',
      '.',
      'a/b',
      'a%2Fb',
      'a b',
      'a\\b',
      'a?b',
      'a#b',
      '',
      'x'.repeat(65),
    ]) {
      expect(() => buildPath('/v1/lessons/{lesson_id}', { lesson_id: value })).toThrow(
        /Malformed path parameter "lesson_id"/,
      );
    }
    expect(buildQuery({ q: 'a b', page: 2, flag: false, skip: undefined, none: null })).toBe(
      '?q=a+b&page=2&flag=false',
    );
    expect(buildQuery({})).toBe('');
  });

  it('authenticates every call and returns parsed data', async () => {
    const fetchImpl = vi.fn(async () => json(200, { status: 'ok' }));
    const result = await callCore(
      connection,
      { method: 'GET', path: '/v1/health' },
      {},
      { fetchImpl },
    );
    expect(result).toEqual({ ok: true, data: { status: 'ok' } });
    const [url, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe('http://127.0.0.1:9/v1/health');
    expect((init.headers as Record<string, string>).Authorization).toBe(
      `Bearer ${connection.token}`,
    );
    expect(init.redirect).toBe('error');
  });

  it('sends JSON bodies for writes and treats 204 as success', async () => {
    const fetchImpl = vi.fn(async () => new Response(null, { status: 204 }));
    const result = await callCore(
      connection,
      { method: 'PUT', path: '/v1/provider/credential' },
      { body: { api_key: 'sk-secret-123456' } },
      { fetchImpl },
    );
    expect(result).toEqual({ ok: true, data: null });
    const [, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    expect(init.body).toBe('{"api_key":"sk-secret-123456"}');
  });

  it('maps core errors, including retry hints, without inventing details', async () => {
    const fetchImpl = vi.fn(async () =>
      json(429, {
        error: { code: 'rate_limited', message: 'Please wait a moment.', retry_after_seconds: 12 },
      }),
    );
    const result = await callCore(connection, { method: 'GET', path: '/v1/x' }, {}, { fetchImpl });
    expect(result).toEqual({
      ok: false,
      error: {
        code: 'rate_limited',
        message: 'Please wait a moment.',
        status: 429,
        detail: undefined,
        retryAfterSeconds: 12,
      },
    });
  });

  it('handles an unreachable core, a timeout, and non-JSON responses', async () => {
    expect(await callCore(null, { method: 'GET', path: '/v1/health' })).toMatchObject({
      ok: false,
      error: { code: 'core_unavailable', status: 0 },
    });

    const refused = vi.fn(async () => {
      throw new TypeError('fetch failed');
    });
    expect(
      await callCore(connection, { method: 'GET', path: '/v1/health' }, {}, { fetchImpl: refused }),
    ).toMatchObject({ ok: false, error: { code: 'core_unavailable' } });

    const slow = vi.fn(async () => {
      const error = new Error('timed out');
      error.name = 'TimeoutError';
      throw error;
    });
    expect(
      await callCore(connection, { method: 'GET', path: '/v1/health' }, {}, { fetchImpl: slow }),
    ).toMatchObject({ ok: false, error: { code: 'core_timeout' } });

    const html = vi.fn(async () => new Response('<html>oops</html>', { status: 502 }));
    expect(
      await callCore(connection, { method: 'GET', path: '/v1/health' }, {}, { fetchImpl: html }),
    ).toMatchObject({ ok: false, error: { code: 'core_error', status: 502 } });
  });

  it('never puts the token in an error result', async () => {
    const fetchImpl = vi.fn(async () =>
      json(500, { error: { code: 'internal_error', message: 'x' } }),
    );
    const result = await callCore(connection, { method: 'GET', path: '/v1/x' }, {}, { fetchImpl });
    expect(JSON.stringify(result)).not.toContain(connection.token);
  });
});
