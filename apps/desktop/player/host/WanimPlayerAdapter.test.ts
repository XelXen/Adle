import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { type HostMessage, isPlayerOrigin, type PlayerMessage } from '@adle/event-protocol';

import { type PlayerStatus, WanimPlayerAdapter } from './WanimPlayerAdapter';

/**
 * The real frame needs Electron's custom protocol, so these tests stand in for
 * it: they capture what the adapter posts and replay what a player would send.
 * End-to-end behaviour against the real runtime is covered in apps/desktop/e2e.
 */
function harness(timeouts = {}) {
  const container = document.createElement('div');
  document.body.appendChild(container);
  const adapter = new WanimPlayerAdapter(container, { timeouts });
  const statuses: PlayerStatus[] = [];
  adapter.on('status', (status) => statuses.push(status));

  const sent: HostMessage[] = [];
  const frame = (): HTMLIFrameElement => {
    const element = container.querySelector('iframe');
    if (!element) throw new Error('No frame mounted.');
    return element;
  };
  const hook = (): void => {
    const target = frame().contentWindow;
    if (!target) throw new Error('Frame has no window.');
    vi.spyOn(target, 'postMessage').mockImplementation((message: unknown) => {
      sent.push(message as HostMessage);
    });
  };
  const fromPlayer = (
    data: unknown,
    overrides: { origin?: string; source?: Window | null } = {},
  ): void => {
    const element = frame();
    window.dispatchEvent(
      new MessageEvent('message', {
        data,
        origin:
          overrides.origin ?? new URL(element.src).protocol + '//' + new URL(element.src).host,
        source: overrides.source === undefined ? element.contentWindow : overrides.source,
      }),
    );
  };
  const runId = (): string => {
    const load = sent.findLast((message) => message.type === 'load');
    if (load?.type !== 'load') throw new Error('No load was sent.');
    return load.runId;
  };
  const player = (message: Record<string, unknown>): void => fromPlayer({ adle: 1, ...message });
  const ready = (): void => player({ type: 'ready', wanimVersion: '0.1.3' });

  return { adapter, container, statuses, sent, frame, hook, fromPlayer, player, ready, runId };
}

const SCENE = { source: 'from manim import *\n', theme: 'light' } as const;

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
  document.body.replaceChildren();
});

describe('WanimPlayerAdapter', () => {
  it('mounts a sandboxed frame on a unique player origin', () => {
    const { adapter, frame } = harness();
    adapter.load(SCENE);
    const element = frame();
    expect(element.getAttribute('sandbox')).toBe('allow-scripts allow-same-origin');
    expect(element.title).toBe('Interactive visualization');
    const url = new URL(element.src);
    expect(isPlayerOrigin(`${url.protocol}//${url.host}`)).toBe(true);
  });

  it('queues the load until the frame is ready, then walks through its states', () => {
    const h = harness();
    h.adapter.load(SCENE);
    h.hook();
    expect(h.sent).toHaveLength(0);

    h.ready();
    const load = h.sent[0];
    expect(load).toMatchObject({ type: 'load', theme: 'light', quality: 'medium', autoplay: true });

    h.player({ type: 'loaded', runId: h.runId(), sceneName: 'Demo', loadMs: 120 });
    expect(h.adapter.status).toBe('playing');

    h.player({
      type: 'state',
      runId: h.runId(),
      state: {
        sceneName: 'Demo',
        phaseKind: 'blueprint',
        phaseIndex: 0,
        phaseCount: 2,
        interactive: true,
        canNext: true,
        done: false,
      },
    });
    expect(h.adapter.status).toBe('interactive');

    h.player({ type: 'finished', runId: h.runId() });
    expect(h.statuses).toEqual(['loading', 'playing', 'interactive', 'finished']);
  });

  it('forwards scene events, controls, and first-frame timing', () => {
    const h = harness();
    const events: unknown[] = [];
    h.adapter.on('scene-event', (event) => events.push(event));
    h.adapter.on('controls', (controls) => events.push(controls));
    h.adapter.on('first-frame', (timing) => events.push(timing));
    h.adapter.load(SCENE);
    h.hook();
    h.ready();
    const runId = h.runId();
    h.player({ type: 'loaded', runId, sceneName: 'Demo', loadMs: 100 });
    h.player({ type: 'first-frame', runId, elapsedMs: 150 });
    h.player({ type: 'scene-event', runId, name: 'passed', value: true });
    h.player({ type: 'controls', runId, controls: [{ name: 'on', kind: 'switch', value: true }] });
    expect(events).toEqual([
      { loadMs: 100, firstFrameMs: 150 },
      { name: 'passed', value: true },
      [{ name: 'on', kind: 'switch', value: true }],
    ]);
  });

  it('ignores messages from the wrong origin, the wrong window, or a stale run', () => {
    const h = harness();
    const events: unknown[] = [];
    h.adapter.on('scene-event', (event) => events.push(event));
    h.adapter.load(SCENE);
    h.hook();
    h.ready();
    const runId = h.runId();
    const event: PlayerMessage = {
      adle: 1,
      type: 'scene-event',
      runId,
      name: 'passed',
      value: true,
    };

    h.fromPlayer(event, { origin: 'adle://app' });
    h.fromPlayer(event, { origin: 'https://evil.example' });
    h.fromPlayer(event, { source: window });
    h.fromPlayer({ ...event, runId: 'another-run' });
    h.fromPlayer({ ...event, name: 'navigate' });
    expect(events).toEqual([]);

    h.fromPlayer(event);
    expect(events).toHaveLength(1);
  });

  it('reports a compile error once and discards the frame', () => {
    const h = harness();
    const failures: unknown[] = [];
    h.adapter.on('failure', (failure) => failures.push(failure));
    h.adapter.load(SCENE);
    h.hook();
    h.ready();
    h.player({
      type: 'error',
      runId: h.runId(),
      stage: 'compile',
      message: 'Inconsistent indentation',
    });
    expect(failures).toEqual([{ stage: 'compile', message: 'Inconsistent indentation' }]);
    expect(h.adapter.status).toBe('failed');
    expect(h.container.querySelector('iframe')).toBeNull();
  });

  it('fails when the runtime never starts', () => {
    const h = harness({ bootMs: 1000 });
    const failures: { stage: string }[] = [];
    h.adapter.on('failure', (failure) => failures.push(failure));
    h.adapter.load(SCENE);
    vi.advanceTimersByTime(1001);
    expect(failures.map((failure) => failure.stage)).toEqual(['boot']);
  });

  it('fails when a scene takes too long to prepare', () => {
    const h = harness({ loadMs: 2000, unresponsiveMs: 60_000 });
    const failures: { stage: string }[] = [];
    h.adapter.on('failure', (failure) => failures.push(failure));
    h.adapter.load(SCENE);
    h.hook();
    h.ready();
    vi.advanceTimersByTime(2001);
    expect(failures.map((failure) => failure.stage)).toEqual(['timeout']);
  });

  it('declares a silent frame unresponsive, and a pong keeps it alive', () => {
    const h = harness({ pingIntervalMs: 100, unresponsiveMs: 350, loadMs: 60_000 });
    const failures: { stage: string }[] = [];
    h.adapter.on('failure', (failure) => failures.push(failure));
    h.adapter.load(SCENE);
    h.hook();
    h.ready();
    h.player({ type: 'loaded', runId: h.runId(), sceneName: 'Demo', loadMs: 10 });

    vi.advanceTimersByTime(300);
    const ping = h.sent.findLast((message) => message.type === 'ping');
    expect(ping?.type).toBe('ping');
    h.player({ type: 'pong', nonce: ping?.type === 'ping' ? ping.nonce : -1 });
    vi.advanceTimersByTime(300);
    expect(failures).toEqual([]);

    vi.advanceTimersByTime(600);
    expect(failures.map((failure) => failure.stage)).toEqual(['unresponsive']);
  });

  it('uses a fresh origin after a failure so a stuck process is never reused', () => {
    const h = harness();
    h.adapter.load(SCENE);
    const firstSrc = h.frame().src;
    h.hook();
    h.ready();
    h.player({ type: 'error', runId: h.runId(), stage: 'runtime', message: 'boom' });

    h.adapter.reset();
    expect(h.adapter.status).toBe('loading');
    expect(h.frame().src).not.toBe(firstSrc);
  });

  it('sends run commands only while a scene is active', () => {
    const h = harness();
    h.adapter.pause();
    h.adapter.load(SCENE);
    h.hook();
    h.ready();
    const runId = h.runId();
    h.player({ type: 'loaded', runId, sceneName: 'Demo', loadMs: 10 });

    h.adapter.pause();
    h.player({ type: 'paused', runId, paused: true });
    expect(h.adapter.status).toBe('paused');
    h.adapter.play();
    h.adapter.next();
    h.adapter.setControl('weight', 1.5);
    expect(h.sent.slice(1).map((message) => message.type)).toEqual([
      'pause',
      'play',
      'next',
      'set-control',
    ]);

    h.player({ type: 'finished', runId });
    h.adapter.pause();
    expect(h.sent.filter((message) => message.type === 'pause')).toHaveLength(1);
  });

  it('reloads the scene when the theme changes', () => {
    const h = harness();
    h.adapter.load(SCENE);
    h.hook();
    h.ready();
    h.player({ type: 'loaded', runId: h.runId(), sceneName: 'Demo', loadMs: 10 });
    h.adapter.setTheme('light');
    expect(h.sent.filter((message) => message.type === 'load')).toHaveLength(1);
    h.adapter.setTheme('dark');
    const loads = h.sent.filter((message) => message.type === 'load');
    expect(loads).toHaveLength(2);
    expect(loads[1]).toMatchObject({ theme: 'dark' });
  });

  it('removes the frame and goes quiet on dispose', () => {
    const h = harness();
    const events: unknown[] = [];
    h.adapter.on('finished', () => events.push('finished'));
    h.adapter.load(SCENE);
    h.hook();
    h.ready();
    const runId = h.runId();
    const element = h.frame();
    h.adapter.dispose();
    expect(h.container.querySelector('iframe')).toBeNull();
    expect(h.sent.at(-1)).toEqual({ adle: 1, type: 'dispose' });
    window.dispatchEvent(
      new MessageEvent('message', {
        data: { adle: 1, type: 'finished', runId },
        origin: new URL(element.src).protocol + '//' + new URL(element.src).host,
        source: element.contentWindow,
      }),
    );
    expect(events).toEqual([]);
    h.adapter.load(SCENE);
    expect(h.adapter.status).toBe('disposed');
  });
});
