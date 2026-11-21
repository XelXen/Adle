import { describe, expect, it } from 'vitest';

import { EXTERNAL_LINKS } from '../../../../electron/shared/ipc';
import {
  couldUseBoth,
  keyBadge,
  keyPage,
  limitsNote,
  modelOrder,
  providerCharacter,
  routeLines,
  selectionOptions,
} from './provider-model';

describe('modelOrder', () => {
  it('has nothing to add when there is one model: its name is already beside it', () => {
    expect(modelOrder([{ name: 'Coding Kimi K3 (free)' }])).toBe('');
  });

  it('names every model, says each has its kind of request, and promises to say a stand-in', () => {
    const said = modelOrder([
      { name: 'Nemotron 3 Ultra' },
      { name: 'Nemotron 3.5 Super' },
      { name: 'Kimi K3.1 Pro' },
    ]);
    expect(said).toBe(
      'Uses Nemotron 3 Ultra, Nemotron 3.5 Super, and Kimi K3.1 Pro, each for the kind of ' +
        'request it was measured to do best. When one is unavailable another stands in, and ' +
        'Adle says so.',
    );
    expect(modelOrder([{ name: 'A' }, { name: 'B' }])).toContain('Uses A and B,');
  });

  it('says nothing about a provider with no model', () => {
    expect(modelOrder([])).toBe('');
  });
});

describe('keyPage', () => {
  it('knows a page for each provider Adle ships with, and each is one it may open', () => {
    for (const id of ['aihubmix', 'nvidia']) {
      const page = keyPage(id);
      expect(page).not.toBeNull();
      expect(Object.hasOwn(EXTERNAL_LINKS, page!.link)).toBe(true);
    }
    expect(keyPage('nvidia')?.label).toBe('Get a key from NVIDIA');
    expect(EXTERNAL_LINKS[keyPage('nvidia')!.link]).toMatch(/^https:\/\/build\.nvidia\.com\//);
  });

  it("offers nothing for a developer's own endpoint", () => {
    expect(keyPage('custom')).toBeNull();
    expect(keyPage('openai')).toBeNull();
  });
});

describe('keyBadge', () => {
  it('says that a key is saved, and only the end of it, to tell keys apart', () => {
    expect(keyBadge({ stored: true, hint: '9876' })).toEqual({
      text: 'Key saved · ends in 9876',
      tone: 'success',
    });
  });

  it('says so when there is no key, or nothing is known yet', () => {
    expect(keyBadge({ stored: false, hint: null })).toEqual({
      text: 'No key',
      tone: undefined,
    });
    expect(keyBadge(undefined)).toEqual({ text: 'No key', tone: undefined });
  });
});

describe('providerCharacter', () => {
  it('says what a provider is asked first for with “Automatic”', () => {
    const coder = providerCharacter({ first_for: ['scene'], limits_published: true });
    expect(coder).toBe(
      'With “Automatic”, draws the pictures: its model is made for code. A small daily allowance.',
    );
    const writer = providerCharacter({
      first_for: ['ask', 'check', 'curriculum', 'lesson'],
      limits_published: false,
    });
    expect(writer).toBe('With “Automatic”, writes lessons, suggested concepts and answers.');
    // A provider asked first for everything has nothing to tell it apart.
    expect(
      providerCharacter({
        first_for: ['ask', 'check', 'curriculum', 'lesson', 'scene'],
        limits_published: false,
      }),
    ).toBe('');
    // It never promises a speed.
    for (const text of [coder, writer]) expect(text).not.toMatch(/\d/);
  });
});

describe('limitsNote', () => {
  const nvidia = { display_name: 'NVIDIA NIM' };

  it("speaks of the provider's limit only where the provider publishes one", () => {
    const published = limitsNote(
      { display_name: 'AIHubMix' },
      { limits_published: true, requests_per_minute: 4 },
      '7:00 PM',
    );
    expect(published).toContain('just under the provider’s daily limit');
    expect(published).toContain('At most 4 requests a minute');
    expect(published).toContain('Resets at 7:00 PM.');
  });

  it("says the limits are Adle's own where the provider publishes none", () => {
    const own = limitsNote(nvidia, { limits_published: false, requests_per_minute: 4 }, '7:00 PM');
    expect(own).toContain('NVIDIA NIM publishes no daily limit');
    expect(own).toContain('Adle’s own');
    expect(own).not.toContain('the provider’s daily limit');
    expect(own).toContain('At most 4 requests a minute');
  });

  it('leaves out the time when it is not known', () => {
    expect(
      limitsNote(nvidia, { limits_published: false, requests_per_minute: 4 }, ''),
    ).not.toContain('starts again');
  });
});

describe('selectionOptions', () => {
  const providers = [
    { provider_id: 'aihubmix', display_name: 'AIHubMix' },
    { provider_id: 'nvidia', display_name: 'NVIDIA NIM' },
  ];

  it('offers automatic first, then each provider alone', () => {
    const options = selectionOptions(providers);
    expect(options.map((option) => [option.value, option.label, option.recommended])).toEqual([
      ['auto', 'Automatic', true],
      ['aihubmix', 'AIHubMix only', false],
      ['nvidia', 'NVIDIA NIM only', false],
    ]);
  });

  it('says of automatic that it only uses providers with a key, and that a stand-in is told', () => {
    const [automatic, alone] = selectionOptions(providers);
    expect(automatic?.description).toContain('each provider you have a key for');
    expect(automatic?.description).toContain('Adle says so');
    expect(alone?.description).toBe('Only AIHubMix is used. Nothing ever goes elsewhere.');
  });
});

describe('routeLines', () => {
  const route = (sentence: string, reason = '', model_name = 'A model') => ({
    sentence,
    reason,
    model_name,
    names: [],
    provider_ids: [],
    wait_seconds: 60,
    wait_measured: false,
  });

  it('gives the destination of each kind of request in the words the core used', () => {
    const lines = routeLines({
      routes: {
        ask: route('AIHubMix, or NVIDIA NIM if AIHubMix cannot answer', 'It answers quickly.'),
        curriculum: route('AIHubMix'),
        lesson: route('NVIDIA NIM', 'This is long work.', 'Nemotron 3 Ultra'),
        scene: route('AIHubMix', 'Its model is made for code.', 'Coding Kimi K3 (free)'),
      },
    });
    expect(lines.map((line) => line.work)).toEqual(['ask', 'curriculum', 'lesson', 'scene']);
    expect(lines[3]).toMatchObject({ label: 'Pictures', model: 'Coding Kimi K3 (free)' });
    expect(lines[0]).toMatchObject({
      label: 'Questions',
      destination: 'AIHubMix, or NVIDIA NIM if AIHubMix cannot answer',
      reason: 'It answers quickly.',
    });
    expect(lines[2]).toMatchObject({
      label: 'Lessons',
      reason: 'This is long work.',
    });
  });
});

describe('couldUseBoth', () => {
  const keyed = (...configured: boolean[]) =>
    configured.map((key_configured) => ({ key_configured }));

  it('suggests it only to a learner who chose one provider and has keys for two', () => {
    expect(couldUseBoth({ selection: 'nvidia', providers: keyed(true, true) })).toBe(true);
    expect(couldUseBoth({ selection: 'nvidia', providers: keyed(false, true) })).toBe(false);
    expect(couldUseBoth({ selection: 'auto', providers: keyed(true, true) })).toBe(false);
  });
});
