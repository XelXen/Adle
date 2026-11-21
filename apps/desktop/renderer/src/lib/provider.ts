import type { Job, ProviderStatus } from '@adle/contracts';

/**
 * What the core says about the learner's providers, put into the words the interface
 * shows. Nothing here decides where a request goes: the core does (`provider.status`),
 * and this only reads it.
 */

/** The kinds of work a request can be for, as the core names its routes. */
export type Work = 'ask' | 'curriculum' | 'lesson';

/** The choice that lets Adle use every provider the learner has a key for (ADR-023). */
export const AUTOMATIC = 'auto';

/**
 * Where a request of this kind would go, to put after "Sends to".
 *
 * With one provider that is its name. Where a second may be asked if the first cannot
 * answer, both are named: a request never goes anywhere that was not said first.
 */
export function destination(status: ProviderStatus | undefined, work: Work): string {
  return status?.routes[work].sentence || 'your AI provider';
}

/** A length of time as a person would say it. Never more exact than it is known. */
export function aboutHowLong(seconds: number): string {
  if (seconds < 20) return 'a few seconds';
  if (seconds < 50) return 'under a minute';
  if (seconds < 100) return 'about a minute';
  return `about ${Math.round(seconds / 60)} minutes`;
}

/** How long this kind of work usually takes where it would go now, in words. */
export function usualWait(status: ProviderStatus | undefined, work: Work): string | null {
  const route = status?.routes[work];
  return route && route.wait_seconds > 0 ? aboutHowLong(route.wait_seconds) : null;
}

export const KIND_CHECK = 'provider_check';

/** What a finished check of a key found. */
export interface CheckOutcome {
  provider: string;
  model: string;
  /** How long the answer took, in words. */
  took: string;
  /** A sentence when another model stood in for the provider's first; otherwise empty. */
  note: string;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

/** How long an answer took, said plainly: "in under a second", "in 2.4 seconds". */
export function tookHowLong(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 1) return 'in under a second';
  if (seconds < 10) return `in ${seconds.toFixed(1)} seconds`;
  if (seconds < 90) return `in ${Math.round(seconds)} seconds`;
  return `in ${aboutHowLong(seconds).replace('about ', '')}`;
}

/** The outcome a finished check carries, or null if the job is not (or not yet) one. */
export function readCheck(job: Job | null): CheckOutcome | null {
  if (!job || job.kind !== KIND_CHECK || job.status !== 'succeeded') return null;
  const result = job.result;
  if (!isRecord(result) || typeof result.provider !== 'string') return null;
  return {
    provider: result.provider,
    model: typeof result.model === 'string' ? result.model : '',
    took: tookHowLong(typeof result.seconds === 'number' ? result.seconds : Number.NaN),
    note: typeof result.note === 'string' ? result.note : '',
  };
}
