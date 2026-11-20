import { describe, expect, it } from 'vitest';

import type { CoreResult } from './bridge';
import { type DataAction, describeOutcome, readOutcome } from './data-actions';

const refused = (message: string): CoreResult<never> => ({
  ok: false,
  error: { code: 'restore_refused', message, status: 0 },
});

describe('readOutcome', () => {
  it('says nothing when the learner backed out of the dialog', () => {
    for (const action of ['save', 'restore', 'erase'] as const) {
      expect(readOutcome(action, { ok: true, data: null })).toBeNull();
    }
  });

  it('reports a saved copy by the name of its file', () => {
    const result = { ok: true, data: { fileName: 'Adle data 2026-11-19.adle' } } as const;
    expect(readOutcome('save', result)).toEqual({
      kind: 'saved',
      fileName: 'Adle data 2026-11-19.adle',
    });
  });

  it('does not show a name that is not a name', () => {
    expect(readOutcome('save', { ok: true, data: { fileName: 42 } })).toEqual({
      kind: 'saved',
      fileName: '',
    });
  });

  it('reports a restore and a deletion', () => {
    expect(readOutcome('restore', { ok: true, data: { restored: true } })).toEqual({
      kind: 'restored',
    });
    expect(readOutcome('erase', { ok: true, data: { erased: true } })).toEqual({ kind: 'erased' });
  });

  it('keeps the reason a failure came with, and which action it was', () => {
    const message = 'That file is not a copy of your data. Your current data was not changed.';
    expect(readOutcome('restore', refused(message))).toEqual({
      kind: 'failed',
      action: 'restore',
      message,
    });
  });
});

describe('describeOutcome', () => {
  it('names the file that was saved and says how to use it', () => {
    const said = describeOutcome({ kind: 'saved', fileName: 'Adle data 2026-11-19.adle' });
    expect(said.tone).toBe('success');
    expect(said.title).toBe('Saved as Adle data 2026-11-19.adle');
    expect(said.body).toContain('Restore from a copy');
    expect(said.offersLibrary).toBe(false);
  });

  it('still says a copy was saved when it has no name to show', () => {
    expect(describeOutcome({ kind: 'saved', fileName: '' }).title).toBe('A copy was saved');
  });

  it('after a restore, says what happened to the data that was replaced', () => {
    const said = describeOutcome({ kind: 'restored' });
    expect(said.body).toContain('safety copy');
    expect(said.offersLibrary).toBe(true);
    expect(said.offersSafetyCopies).toBe(true);
  });

  it('after deleting everything, says what was left alone', () => {
    const said = describeOutcome({ kind: 'erased' });
    expect(said.body).toContain('AI provider key');
    expect(said.offersLibrary).toBe(true);
    expect(said.offersSafetyCopies).toBe(false);
  });

  it.each<[DataAction, string]>([
    ['save', 'The copy was not saved'],
    ['restore', 'Nothing was restored'],
    ['erase', 'Not everything could be deleted'],
  ])('a failed %s is titled for what did not happen and carries the reason', (action, title) => {
    const said = describeOutcome({ kind: 'failed', action, message: 'The reason, in words.' });
    expect(said).toMatchObject({ tone: 'danger', title, body: 'The reason, in words.' });
    expect(said.offersLibrary).toBe(false);
  });
});
