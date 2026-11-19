import { describe, expect, it } from 'vitest';

import type { PlayerQuestion } from '@adle/contracts';

import { buildAnswer, emptyDraft, moved, parseNumber } from './answers';

const MINUS = String.fromCharCode(0x2212);

function question(
  form: PlayerQuestion['form'],
  extra: Partial<PlayerQuestion> = {},
): PlayerQuestion {
  return {
    id: 'q_one',
    form,
    concept_id: 'con_00000000000000000001',
    stem: 'A question?',
    difficulty: 1,
    is_transfer: false,
    ...extra,
  };
}

describe('parseNumber', () => {
  it.each([
    ['3', 3],
    [' 3.0 ', 3],
    ['-0.5', -0.5],
    [`${MINUS}0.5`, -0.5],
    ['+2', 2],
    ['.25', 0.25],
    ['2.', 2],
    ['2,5', 2.5],
    ['1/2', 0.5],
    ['-3 / 4', -0.75],
    ['0', 0],
  ])('reads %j as %d', (text, expected) => {
    expect(parseNumber(text)).toBeCloseTo(expected);
  });

  it.each(['', 'three', '1.2.3', '1,2,3', '1/0', '2x', '1e400x', '--2', '1 2', '1,000.5'])(
    'does not guess at %j',
    (text) => {
      expect(parseNumber(text)).toBeNull();
    },
  );
});

describe('buildAnswer', () => {
  const options = [
    { id: 'b', text: 'Second' },
    { id: 'a', text: 'First' },
  ];

  it('asks for a choice before a choice question can be checked', () => {
    const item = question('multiple_choice', { options });
    expect(buildAnswer(item, emptyDraft(item))).toEqual({
      ok: false,
      message: 'Choose one of the options first.',
    });
    expect(buildAnswer(item, { ...emptyDraft(item), choice: 'a' })).toEqual({
      ok: true,
      body: { option_id: 'a' },
    });
    const prediction = question('prediction', { options });
    expect(buildAnswer(prediction, { ...emptyDraft(prediction), choice: 'b' })).toEqual({
      ok: true,
      body: { option_id: 'b' },
    });
  });

  it('sends true or false as a boolean', () => {
    const item = question('true_false');
    expect(buildAnswer(item, emptyDraft(item)).ok).toBe(false);
    expect(buildAnswer(item, { ...emptyDraft(item), choice: 'false' })).toEqual({
      ok: true,
      body: { truth: false },
    });
  });

  it('explains what a number should look like instead of sending text', () => {
    const item = question('numeric');
    expect(buildAnswer(item, { ...emptyDraft(item), text: 'about three' })).toEqual({
      ok: false,
      message: 'Enter a number, for example 2.5 or 1/2.',
    });
    expect(buildAnswer(item, { ...emptyDraft(item), text: ' 1/4 ' })).toEqual({
      ok: true,
      body: { number: 0.25 },
    });
  });

  it('trims a short answer and refuses an empty one', () => {
    const item = question('short_answer');
    expect(buildAnswer(item, { ...emptyDraft(item), text: '   ' }).ok).toBe(false);
    expect(buildAnswer(item, { ...emptyDraft(item), text: ' the bias ' })).toEqual({
      ok: true,
      body: { text: 'the bias' },
    });
  });

  it('starts an ordering question in the order it was given and sends the order as it stands', () => {
    const item = question('ordering', { options });
    const draft = emptyDraft(item);
    expect(draft.order).toEqual(['b', 'a']);
    expect(buildAnswer(item, { ...draft, order: ['a', 'b'] })).toEqual({
      ok: true,
      body: { order: ['a', 'b'] },
    });
  });

  it('sends the rubric points an explanation covered, even when there are none', () => {
    const item = question('explanation');
    expect(buildAnswer(item, emptyDraft(item))).toEqual({ ok: true, body: { covered: [] } });
    expect(buildAnswer(item, { ...emptyDraft(item), covered: ['sum'] })).toEqual({
      ok: true,
      body: { covered: ['sum'] },
    });
  });
});

describe('moved', () => {
  it('swaps an item with its neighbour and leaves the ends alone', () => {
    expect(moved(['a', 'b', 'c'], 1, -1)).toEqual(['b', 'a', 'c']);
    expect(moved(['a', 'b', 'c'], 1, 1)).toEqual(['a', 'c', 'b']);
    expect(moved(['a', 'b', 'c'], 0, -1)).toEqual(['a', 'b', 'c']);
    expect(moved(['a', 'b', 'c'], 2, 1)).toEqual(['a', 'b', 'c']);
  });
});
