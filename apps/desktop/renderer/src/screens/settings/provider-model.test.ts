import { describe, expect, it } from 'vitest';

import { EXTERNAL_LINKS } from '../../../../electron/shared/ipc';
import { keyBadge, keyPage, limitsNote, modelOrder } from './provider-model';

describe('modelOrder', () => {
  it('says where every request goes when there is one model', () => {
    expect(modelOrder([{ name: 'Coding Kimi K3 (free)' }])).toBe(
      'Every request goes to Coding Kimi K3 (free).',
    );
  });

  it('names the stand-ins in order, and promises to say when one was used', () => {
    const said = modelOrder([
      { name: 'Kimi K3.1 Pro' },
      { name: 'Mistral Large 4' },
      { name: 'GLM 5.3 Flash' },
    ]);
    expect(said).toBe(
      'Requests go to Kimi K3.1 Pro. While it is not available, Mistral Large 4 and GLM 5.3 ' +
        'Flash stand in, in that order, and Adle tells you when that happened.',
    );
    // The first is never listed among its own stand-ins.
    expect(said.indexOf('Kimi K3.1 Pro')).toBe(said.lastIndexOf('Kimi K3.1 Pro'));
  });

  it('agrees in number with a single stand-in', () => {
    expect(modelOrder([{ name: 'A' }, { name: 'B' }])).toContain('B stands in');
    expect(modelOrder([{ name: 'A' }, { name: 'B' }, { name: 'C' }, { name: 'D' }])).toContain(
      'B, C, and D stand in',
    );
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
  it('says that a key is saved, and nothing of the key itself', () => {
    expect(keyBadge({ stored: true, hint: '9876' })).toEqual({
      text: 'Key saved',
      tone: 'success',
    });
  });

  it('says so when there is no key, or nothing is known yet', () => {
    expect(keyBadge({ stored: false, hint: null })).toEqual({
      text: 'No key yet',
      tone: undefined,
    });
    expect(keyBadge(undefined)).toEqual({ text: 'No key yet', tone: undefined });
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
    expect(published).toContain("a little short of the provider's daily limit");
    expect(published).toContain('never more than 4 a minute');
    expect(published).toContain('The count starts again at 7:00 PM.');
  });

  it("says the limits are Adle's own where the provider publishes none", () => {
    const own = limitsNote(nvidia, { limits_published: false, requests_per_minute: 4 }, '7:00 PM');
    expect(own).toContain('NVIDIA NIM does not publish a daily limit');
    expect(own).toContain("Adle's own");
    expect(own).not.toContain("the provider's daily limit");
    expect(own).toContain('never more than 4 a minute');
  });

  it('leaves out the time when it is not known', () => {
    expect(
      limitsNote(nvidia, { limits_published: false, requests_per_minute: 4 }, ''),
    ).not.toContain('starts again');
  });
});
