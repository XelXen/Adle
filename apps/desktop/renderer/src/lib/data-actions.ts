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
  save: 'The copy was not saved',
  restore: 'Nothing was restored',
  erase: 'Not everything could be deleted',
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
        title: outcome.fileName ? `Saved as ${outcome.fileName}` : 'A copy was saved',
        body: 'It holds everything in Adle as it is now. Keep it somewhere safe; to use it, choose "Restore from a copy" here or on another computer.',
        offersLibrary: false,
        offersSafetyCopies: false,
      };
    case 'restored':
      return {
        tone: 'success',
        title: 'Your data was restored from the copy',
        body: 'What was here before was not thrown away: it was kept as a safety copy first, and can be restored in the same way.',
        offersLibrary: true,
        offersSafetyCopies: true,
      };
    case 'erased':
      return {
        tone: 'success',
        title: 'Everything was deleted',
        body: 'Adle holds no courses, materials, answers, or safety copies now. Your AI provider key and your appearance settings were left as they were.',
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
