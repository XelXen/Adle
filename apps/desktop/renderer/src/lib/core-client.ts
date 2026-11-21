import type { OperationId, OperationTypes } from '@adle/contracts';

import { type CoreError, type CoreResult, getBridge } from './bridge';

/** A failed call to the local core. `code` is stable and safe to branch on. */
export class CoreRequestError extends Error {
  readonly code: string;
  readonly status: number;
  readonly retryAfterSeconds: number | undefined;
  readonly detail: unknown;

  constructor(error: CoreError) {
    super(error.message);
    this.name = 'CoreRequestError';
    this.code = error.code;
    this.status = error.status;
    this.retryAfterSeconds = error.retryAfterSeconds;
    this.detail = error.detail;
  }
}

/** Keys whose type admits `undefined` become optional. */
type OptionalWhenUndefined<T> = {
  [K in keyof T as undefined extends T[K] ? never : K]: T[K];
} & {
  [K in keyof T as undefined extends T[K] ? K : never]?: T[K];
};

export type OperationParams<K extends OperationId> = OptionalWhenUndefined<
  Omit<OperationTypes[K], 'result'>
>;
export type OperationResult<K extends OperationId> = OperationTypes[K]['result'];

type ParamsArgument<K extends OperationId> =
  Record<string, never> extends OperationParams<K>
    ? [params?: OperationParams<K>]
    : [params: OperationParams<K>];

/** Turn a bridge result into a value or a thrown `CoreRequestError`. */
export function unwrap<T>(result: CoreResult<T>): T {
  if (result.ok) return result.data;
  throw new CoreRequestError(result.error);
}

/**
 * Call an operation of the local core, typed from the generated contract.
 * The main process validates the operation against its allowlist before
 * forwarding it; the renderer never talks to the core directly.
 */
export async function callCore<K extends OperationId>(
  operation: K,
  ...[params]: ParamsArgument<K>
): Promise<OperationResult<K>> {
  const result = await getBridge().core.invoke(operation, params ?? {});
  return unwrap(result) as OperationResult<K>;
}

/** A learner-readable sentence for any thrown value. */
export function describeError(error: unknown): string {
  if (error instanceof CoreRequestError) return error.message;
  if (error instanceof Error && error.message) return error.message;
  return 'Something went wrong. Please try again.';
}
