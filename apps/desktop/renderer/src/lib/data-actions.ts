import type { CoreResult } from './bridge';

/**
 * What to tell the learner after they saved a copy of their data, restored from one,
 * or deleted everything (Settings → Privacy & data).
 *
 * Each of these is carried out by the main process, which asks the learner where, which,
 * or whether in a window of the operating system. The page only starts it and reports
 * how it went: it never sees a path.
 */

export type DataAction = 'save' | 'restore' | 'erase';

export type DataOutcome =
  | { kind: 'saved'; fileName: string }
  | { kind: 'restored' }
  | { kind: 'erased' }
  | { kind: 'failed'; action: DataAction; message: string };

const FAILED: Record<DataAction, string> = {
  save: 'Couldn’t save the copy',
  restore: 'Nothing was restored',
  erase: 'Couldn’t delete everything',
};

/**
 * Read the answer to one of the three actions. `null` means the learner backed out in the
 * dialog, which is not an outcome: nothing happened and nothing needs saying.
 */
export function readOutcome(action: DataAction, result: CoreResult<unknown>): DataOutcome | null {
  if (!result.ok) return { kind: 'failed', action, message: result.error.message };
  if (result.data === null || result.data === undefined) return null;
  if (action === 'save') {
    const fileName = (result.data as { fileName?: unknown }).fileName;
    return { kind: 'saved', fileName: typeof fileName === 'string' ? fileName : '' };
  }
  return action === 'restore' ? { kind: 'restored' } : { kind: 'erased' };
}

export interface OutcomeMessage {
  tone: 'success' | 'danger';
  title: string;
  body: string;
  /** Offer the way to the library: what is there has changed. */
  offersLibrary: boolean;
  /** Offer to show the safety copies: one was just made. */
  offersSafetyCopies: boolean;
}

export function describeOutcome(outcome: DataOutcome): OutcomeMessage {
  switch (outcome.kind) {
    case 'saved':
      return {
        tone: 'success',
        title: outcome.fileName ? `Saved as ${outcome.fileName}` : 'Copy saved',
        body: 'It contains everything in Adle as of now. To use it, choose “Restore from a copy” here or on another computer.',
        offersLibrary: false,
        offersSafetyCopies: false,
      };
    case 'restored':
      return {
        tone: 'success',
        title: 'Data restored',
        body: 'Your previous data was kept as a safety copy. You can restore it the same way.',
        offersLibrary: true,
        offersSafetyCopies: true,
      };
    case 'erased':
      return {
        tone: 'success',
        title: 'Everything deleted',
        body: 'All courses, materials, answers, and safety copies are gone. Your provider keys and appearance settings were kept.',
        offersLibrary: true,
        offersSafetyCopies: false,
      };
    case 'failed':
      return {
        tone: 'danger',
        title: FAILED[outcome.action],
        body: outcome.message,
        offersLibrary: false,
        offersSafetyCopies: false,
      };
  }
}
