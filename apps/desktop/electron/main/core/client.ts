import type { CoreError, CoreInvokeParams, CoreResult } from '../../shared/ipc';
import type { CoreConnection } from './process';

export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';

export interface OperationSpec {
  method: HttpMethod;
  /** Path template relative to the core base URL, e.g. `/v1/courses/{course_id}`. */
  path: string;
}

export interface CallOptions {
  timeoutMs?: number;
  fetchImpl?: typeof fetch;
}

const DEFAULT_TIMEOUT_MS = 30_000;

const UNAVAILABLE: CoreError = {
  code: 'core_unavailable',
  message: 'Adle is still starting. Try again in a moment.',
  status: 0,
};

const PATH_VALUE = /^[A-Za-z0-9_-]{1,64}$/;

/** Substitute `{name}` placeholders. Throws on a missing or unsafe value. */
export function buildPath(template: string, values: CoreInvokeParams['path'] = {}): string {
  return template.replace(/\{([a-zA-Z_][a-zA-Z0-9_]*)\}/g, (_match, name: string) => {
    const value = values[name];
    if (typeof value !== 'string' && typeof value !== 'number') {
      throw new TypeError(`Missing path parameter "${name}".`);
    }
    // Every identifier the core gives out is made of these. Anything else ("..", a slash,
    // a percent sign) could turn one address into another once it is decoded.
    const text = String(value);
    if (!PATH_VALUE.test(text)) throw new TypeError(`Malformed path parameter "${name}".`);
    return encodeURIComponent(text);
  });
}

export function buildQuery(query: CoreInvokeParams['query'] = {}): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null) continue;
    search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : '';
}

function toCoreError(status: number, payload: unknown): CoreError {
  const error =
    typeof payload === 'object' && payload !== null
      ? (payload as { error?: Record<string, unknown> }).error
      : undefined;
  if (error && typeof error.code === 'string' && typeof error.message === 'string') {
    return {
      code: error.code,
      message: error.message,
      status,
      detail: error.detail,
      retryAfterSeconds:
        typeof error.retry_after_seconds === 'number' ? error.retry_after_seconds : undefined,
    };
  }
  return {
    code: 'core_error',
    message: 'Adle got an unexpected response. Please try again.',
    status,
  };
}

/** Perform one authenticated call to the core and normalise the outcome. */
export async function callCore(
  connection: CoreConnection | null,
  spec: OperationSpec,
  params: CoreInvokeParams = {},
  options: CallOptions = {},
): Promise<CoreResult> {
  if (!connection) return { ok: false, error: UNAVAILABLE };

  let url: string;
  try {
    url = connection.baseUrl + buildPath(spec.path, params.path) + buildQuery(params.query);
  } catch (error) {
    return {
      ok: false,
      error: {
        code: 'invalid_request',
        message: error instanceof Error ? error.message : 'Invalid request.',
        status: 0,
      },
    };
  }

  const hasBody = params.body !== undefined && spec.method !== 'GET';
  const fetchImpl = options.fetchImpl ?? fetch;
  try {
    const response = await fetchImpl(url, {
      method: spec.method,
      headers: {
        Authorization: `Bearer ${connection.token}`,
        Accept: 'application/json',
        ...(hasBody ? { 'Content-Type': 'application/json' } : {}),
      },
      body: hasBody ? JSON.stringify(params.body) : undefined,
      signal: AbortSignal.timeout(options.timeoutMs ?? DEFAULT_TIMEOUT_MS),
      redirect: 'error',
    });

    if (response.status === 204) return { ok: true, data: null };
    const text = await response.text();
    let payload: unknown = null;
    if (text) {
      try {
        payload = JSON.parse(text);
      } catch {
        return { ok: false, error: toCoreError(response.status, null) };
      }
    }
    if (response.ok) return { ok: true, data: payload };
    return { ok: false, error: toCoreError(response.status, payload) };
  } catch (error) {
    const timedOut = error instanceof Error && error.name === 'TimeoutError';
    return {
      ok: false,
      error: timedOut
        ? { code: 'core_timeout', message: 'That took too long. Please try again.', status: 0 }
        : UNAVAILABLE,
    };
  }
}
