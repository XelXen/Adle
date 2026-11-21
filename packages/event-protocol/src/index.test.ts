import { describe, expect, it } from 'vitest';

import {
  adleOriginOf,
  APP_ORIGIN,
  createPlayerInstanceId,
  createRunId,
  isPlayerHost,
  isPlayerOrigin,
  MAX_SCENE_SOURCE_CHARS,
  parseHostMessage,
  parsePlayerMessage,
  playerEntryUrl,
  playerOrigin,
  PROTOCOL_VERSION,
} from './index';

const load = {
  adle: PROTOCOL_VERSION,
  type: 'load',
  runId: 'run-1',
  source: 'from manim import *\n',
  sceneName: null,
  theme: 'light',
  quality: 'medium',
  autoplay: true,
  rehearsal: false,
};

describe('parseHostMessage', () => {
  it('accepts a well-formed load', () => {
    expect(parseHostMessage(load)).toEqual(load);
  });

  it.each([
    ['unknown field', { ...load, callback: 'x' }],
    ['missing field', (({ autoplay: _autoplay, ...rest }) => rest)(load)],
    ['no word on whether it is a rehearsal', (({ rehearsal: _rehearsal, ...rest }) => rest)(load)],
    ['a rehearsal that is not yes or no', { ...load, rehearsal: 'fast' }],
    ['wrong protocol version', { ...load, adle: 2 }],
    ['empty source', { ...load, source: '' }],
    ['oversized source', { ...load, source: 'x'.repeat(MAX_SCENE_SOURCE_CHARS + 1) }],
    ['non-identifier scene name', { ...load, sceneName: 'a b' }],
    ['unknown theme', { ...load, theme: 'neon' }],
    ['unknown quality', { ...load, quality: '4k' }],
    ['malformed run id', { ...load, runId: '../etc' }],
  ])('rejects a load with %s', (_label, message) => {
    expect(parseHostMessage(message)).toBeNull();
  });

  it('accepts run commands and rejects extras on them', () => {
    for (const type of ['play', 'pause', 'next'] as const) {
      expect(parseHostMessage({ adle: 1, type, runId: 'r' })).toEqual({
        adle: 1,
        type,
        runId: 'r',
      });
      expect(parseHostMessage({ adle: 1, type, runId: 'r', extra: 1 })).toBeNull();
    }
  });

  it('validates set-control values', () => {
    const base = { adle: 1, type: 'set-control', runId: 'r', name: 'weight' };
    expect(parseHostMessage({ ...base, value: 1.5 })).not.toBeNull();
    expect(parseHostMessage({ ...base, value: true })).not.toBeNull();
    expect(parseHostMessage({ ...base, value: Number.NaN })).toBeNull();
    expect(parseHostMessage({ ...base, value: 'eval(1)' })).toBeNull();
    expect(parseHostMessage({ ...base, name: 'constructor.prototype', value: 1 })).toBeNull();
  });

  it('accepts ping and dispose, and rejects unknown types and non-objects', () => {
    expect(parseHostMessage({ adle: 1, type: 'ping', nonce: 3 })).toEqual({
      adle: 1,
      type: 'ping',
      nonce: 3,
    });
    expect(parseHostMessage({ adle: 1, type: 'dispose' })).toEqual({ adle: 1, type: 'dispose' });
    expect(parseHostMessage({ adle: 1, type: 'restart', runId: 'r' })).toBeNull();
    expect(parseHostMessage({ adle: 1, type: 'run-script', code: 'x' })).toBeNull();
    for (const junk of [null, undefined, 'load', 42, [], [load]]) {
      expect(parseHostMessage(junk)).toBeNull();
    }
  });

  it('rejects objects with an unexpected prototype', () => {
    class Sneaky {
      adle = 1;
      type = 'dispose';
    }
    expect(parseHostMessage(new Sneaky())).toBeNull();
  });
});

describe('parsePlayerMessage', () => {
  const state = {
    sceneName: 'Demo',
    phaseKind: 'blueprint',
    phaseIndex: 0,
    phaseCount: 2,
    interactive: true,
    canNext: true,
    done: false,
  };

  it('accepts each known message shape', () => {
    const messages = [
      { adle: 1, type: 'ready', wanimVersion: '0.1.3' },
      { adle: 1, type: 'loaded', runId: 'r', sceneName: 'Demo', loadMs: 120.5 },
      { adle: 1, type: 'first-frame', runId: 'r', elapsedMs: 300 },
      { adle: 1, type: 'state', runId: 'r', state },
      { adle: 1, type: 'paused', runId: 'r', paused: true },
      { adle: 1, type: 'finished', runId: 'r' },
      { adle: 1, type: 'pong', nonce: 7 },
      { adle: 1, type: 'error', runId: null, stage: 'boot', message: 'no runtime' },
      { adle: 1, type: 'scene-event', runId: 'r', name: 'passed', value: true },
      {
        adle: 1,
        type: 'controls',
        runId: 'r',
        controls: [
          { name: 'weight', kind: 'slider', value: 0.5, min: -2, max: 2 },
          { name: 'bias_on', kind: 'switch', value: false },
        ],
      },
    ];
    for (const message of messages) expect(parsePlayerMessage(message)).toEqual(message);
  });

  it('drops scene events outside the closed vocabulary', () => {
    const event = { adle: 1, type: 'scene-event', runId: 'r', name: 'passed', value: true };
    expect(parsePlayerMessage({ ...event, name: 'navigate' })).toBeNull();
    expect(parsePlayerMessage({ ...event, value: { nested: true } })).toBeNull();
    expect(parsePlayerMessage({ ...event, value: ['a'] })).toBeNull();
    expect(parsePlayerMessage({ ...event, value: 'x'.repeat(201) })).toBeNull();
    expect(parsePlayerMessage({ ...event, value: Number.POSITIVE_INFINITY })).toBeNull();
  });

  it('rejects malformed control descriptors', () => {
    const wrap = (control: unknown) => ({
      adle: 1,
      type: 'controls',
      runId: 'r',
      controls: [control],
    });
    expect(parsePlayerMessage(wrap({ name: 'w', kind: 'slider', value: 1 }))).toBeNull(); // no range
    expect(
      parsePlayerMessage(wrap({ name: 'w', kind: 'slider', value: 1, min: 2, max: 1 })),
    ).toBeNull();
    expect(parsePlayerMessage(wrap({ name: 'w', kind: 'switch', value: 1 }))).toBeNull();
    expect(
      parsePlayerMessage(wrap({ name: 'w', kind: 'slider', value: true, min: 0, max: 1 })),
    ).toBeNull();
    expect(
      parsePlayerMessage(wrap({ name: 'w', kind: 'dial', value: 1, min: 0, max: 1 })),
    ).toBeNull();
    expect(
      parsePlayerMessage(wrap({ name: 'w', kind: 'switch', value: true, onclick: 'x' })),
    ).toBeNull();
    const duplicate = { name: 'w', kind: 'switch', value: true };
    expect(
      parsePlayerMessage({
        adle: 1,
        type: 'controls',
        runId: 'r',
        controls: [duplicate, duplicate],
      }),
    ).toBeNull();
  });

  it('truncates long error text instead of trusting its size', () => {
    const parsed = parsePlayerMessage({
      adle: 1,
      type: 'error',
      runId: 'r',
      stage: 'runtime',
      message: 'e'.repeat(3000),
    });
    expect(parsed?.type === 'error' && parsed.message.length).toBe(2000);
  });

  it('rejects oversized and unknown messages', () => {
    expect(
      parsePlayerMessage({
        adle: 1,
        type: 'error',
        runId: 'r',
        stage: 'runtime',
        message: 'e'.repeat(9000),
      }),
    ).toBeNull();
    expect(
      parsePlayerMessage({ adle: 1, type: 'state', runId: 'r', state: { ...state, extra: 1 } }),
    ).toBeNull();
    expect(
      parsePlayerMessage({ adle: 1, type: 'open-url', url: 'https://example.com' }),
    ).toBeNull();
    expect(parsePlayerMessage({ type: 'ready', wanimVersion: '0.1.3' })).toBeNull();
  });
});

describe('origins', () => {
  it('gives every player instance its own origin', () => {
    const first = createPlayerInstanceId();
    const second = createPlayerInstanceId();
    expect(first).not.toBe(second);
    expect(playerOrigin(first)).toBe(`adle://${first}.player`);
    expect(playerEntryUrl(first)).toBe(`adle://${first}.player/index.html`);
    expect(isPlayerOrigin(playerOrigin(first))).toBe(true);
  });

  it('refuses instance ids that could change the host', () => {
    for (const bad of ['', 'a.b', 'app', '../x', 'A', 'x'.repeat(25), 'a/b', 'a:1']) {
      expect(() => playerOrigin(bad === 'app' ? 'app!' : bad)).toThrow();
    }
  });

  it('recognises player hosts strictly', () => {
    expect(isPlayerHost('k3f9.player')).toBe(true);
    expect(isPlayerHost('player')).toBe(false);
    expect(isPlayerHost('app')).toBe(false);
    expect(isPlayerHost('evil.player.example')).toBe(false);
    expect(isPlayerHost('a.b.player')).toBe(false);
    expect(isPlayerOrigin('https://x.player')).toBe(false);
    expect(isPlayerOrigin(APP_ORIGIN)).toBe(false);
  });

  it('derives adle origins without relying on the URL parser', () => {
    expect(adleOriginOf('adle://app/index.html')).toBe(APP_ORIGIN);
    expect(adleOriginOf('adle://ab12.player/assets/x.js?y#z')).toBe('adle://ab12.player');
    expect(adleOriginOf('adle://app')).toBe(APP_ORIGIN);
    expect(adleOriginOf('https://app/index.html')).toBeNull();
    expect(adleOriginOf('adle://app@evil.example/')).toBeNull();
    expect(adleOriginOf('adle:/app/')).toBeNull();
  });

  it('creates run ids that satisfy the protocol', () => {
    expect(parseHostMessage({ adle: 1, type: 'play', runId: createRunId() })).not.toBeNull();
  });
});
