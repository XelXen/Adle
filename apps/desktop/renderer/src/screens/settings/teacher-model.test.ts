import { describe, expect, it } from 'vitest';

import { ADLE_OWN, presetOf, sameParts, teacherRequest, withPart } from './teacher-model';

const presets = [
  { name: ADLE_OWN, parts: {} },
  { name: 'Calm guide', parts: { manner: 'calm', style: 'guide' } },
];

describe('a teacher made of parts (ADR-071)', () => {
  it('changes one part at a time, and leaves a part to Adle when its choice is empty', () => {
    expect(withPart({ manner: 'calm' }, 'style', 'guide')).toEqual({
      manner: 'calm',
      style: 'guide',
    });
    expect(withPart({ manner: 'calm', style: 'guide' }, 'style', '')).toEqual({ manner: 'calm' });
    expect(sameParts({ a: '1', b: '2' }, { b: '2', a: '1' })).toBe(true);
    expect(sameParts({ a: '1' }, { a: '1', b: '2' })).toBe(false);
  });

  it('knows which teacher to start from the parts are, and none for words of your own', () => {
    expect(presetOf(presets, {}, false)).toBe(ADLE_OWN);
    expect(presetOf(presets, { style: 'guide', manner: 'calm' }, false)).toBe('Calm guide');
    expect(presetOf(presets, { manner: 'calm' }, false)).toBe('');
    expect(presetOf(presets, {}, true)).toBe('');
  });

  it('saves the parts while the words are what they make, and else the words', () => {
    const composed = 'A calm guide who walks beside the learner, speaking plainly.';
    expect(teacherRequest({ manner: 'calm' }, composed, composed)).toEqual({
      character_parts: { manner: 'calm' },
    });
    expect(teacherRequest({}, '  A retired sea captain ', composed)).toEqual({
      character: 'A retired sea captain',
    });
    // Nothing at all is Adle's own teacher.
    expect(teacherRequest({}, '', composed)).toEqual({ character_parts: {} });
  });
});
