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
  overrides: { readyTimeoutMs?: number; stopTimeoutMs?: number } = {},
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
      message: 'The core service took too long to start.',
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
});

describe('core client', () => {
  const connection = { baseUrl: 'http://127.0.0.1:9', token: 't'.repeat(64) };
  const json = (status: number, body: unknown, headers: Record<string, string> = {}) =>
    new Response(body === null ? null : JSON.stringify(body), { status, headers });

  it('builds paths and queries safely', () => {
    expect(buildPath('/v1/courses/{course_id}', { course_id: 'a/b ../c' })).toBe(
      '/v1/courses/a%2Fb%20..%2Fc',
    );
    expect(() => buildPath('/v1/courses/{course_id}', {})).toThrow(/course_id/);
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
