import { describe, expect, it } from 'vitest';

import type { ControlDescriptor, ControlValue, ScenePlaybackState } from '@adle/event-protocol';

import type { LoadSceneOptions, PlayerEvents } from '../../../player/host/WanimPlayerAdapter';
import { runTrial, type TrialPlayer, valuesToTry } from './scene-trial';

/** A player that does what the test says, and remembers what it was asked. */
class FakePlayer implements TrialPlayer {
  loaded: LoadSceneOptions | null = null;
  moved: [string, ControlValue][] = [];
  nexts = 0;
  private readonly listeners = new Map<string, Set<(payload: unknown) => void>>();

  on<K extends keyof PlayerEvents>(event: K, listener: (payload: PlayerEvents[K]) => void) {
    const set = this.listeners.get(event) ?? new Set();
    set.add(listener as (payload: unknown) => void);
    this.listeners.set(event, set);
    return () => set.delete(listener as (payload: unknown) => void);
  }

  emit<K extends keyof PlayerEvents>(event: K, payload: PlayerEvents[K]): void {
    for (const listener of this.listeners.get(event) ?? []) listener(payload);
  }

  load(options: LoadSceneOptions): void {
    this.loaded = options;
  }

  next(): void {
    this.nexts += 1;
  }

  setControl(name: string, value: ControlValue): void {
    this.moved.push([name, value]);
  }
}

const TRIAL = { source: 'from manim import *', scene_class: 'Weights' };
const QUICK = { budgetMs: 2_000, controlsMs: 200, settleMs: 20 };
const tick = (): Promise<void> => new Promise((resolve) => setTimeout(resolve, 0));

function page(phaseIndex: number, canNext: boolean): ScenePlaybackState {
  return {
    sceneName: 'Weights',
    phaseKind: 'blueprint',
    phaseIndex,
    phaseCount: 2,
    interactive: true,
    canNext,
    done: false,
  };
}

const slider: ControlDescriptor = { name: 'weight', kind: 'slider', value: 1, min: -2, max: 3 };
const toggle: ControlDescriptor = { name: 'bias', kind: 'switch', value: false };

describe('valuesToTry', () => {
  it('moves a slider to each end and back, and a switch over and back', () => {
    expect(valuesToTry(slider)).toEqual([-2, 3, 1]);
    expect(valuesToTry(toggle)).toEqual([true, false]);
    expect(valuesToTry({ name: 'n', kind: 'number', value: 4 })).toEqual([4]);
  });
});

describe('runTrial', () => {
  it('runs the scene as a rehearsal, as a lesson shows it, and passes one that finishes', async () => {
    const player = new FakePlayer();
    const verdict = runTrial(player, TRIAL, QUICK);
    expect(player.loaded).toMatchObject({
      source: TRIAL.source,
      sceneName: 'Weights',
      theme: 'dark',
      rehearsal: true,
      autoplay: true,
    });
    player.emit('finished', undefined);
    await expect(verdict).resolves.toEqual({ passed: true });
  });

  it('says how it failed, in the player’s words', async () => {
    const player = new FakePlayer();
    const verdict = runTrial(player, TRIAL, QUICK);
    player.emit('failure', { stage: 'compile', message: "NameError: name 'Arow' is not defined" });
    await expect(verdict).resolves.toEqual({
      passed: false,
      stage: 'compile',
      message: "NameError: name 'Arow' is not defined",
    });
  });

  it('operates every control of every page, and goes on from all but the last', async () => {
    const player = new FakePlayer();
    const verdict = runTrial(player, TRIAL, QUICK);
    player.emit('state', page(0, true));
    player.emit('controls', [slider, toggle]);
    await expect.poll(() => player.nexts, { timeout: 1_000 }).toBe(1);
    expect(player.moved).toEqual([
      ['weight', -2],
      ['weight', 3],
      ['weight', 1],
      ['bias', true],
      ['bias', false],
    ]);
    // The same page said again is not operated again; the next one is, and it is the last.
    player.emit('state', page(0, true));
    player.emit('state', page(1, false));
    await expect(verdict).resolves.toEqual({ passed: true });
    expect(player.moved).toHaveLength(10);
    expect(player.nexts).toBe(1);
  });

  it('blames a failure while a control is moved on the control', async () => {
    const player = new FakePlayer();
    const verdict = runTrial(player, TRIAL, { ...QUICK, settleMs: 500 });
    player.emit('controls', [slider]);
    player.emit('state', page(0, false));
    await tick();
    player.emit('failure', { stage: 'runtime', message: 'TypeError: bad value' });
    await expect(verdict).resolves.toEqual({
      passed: false,
      stage: 'controls',
      message: 'TypeError: bad value',
    });
  });

  it('passes a scene that is not seen to fail in all the time it has', async () => {
    const player = new FakePlayer();
    await expect(runTrial(player, TRIAL, { ...QUICK, budgetMs: 30 })).resolves.toEqual({
      passed: true,
    });
  });

  it('says one verdict, whatever the player says afterwards', async () => {
    const player = new FakePlayer();
    const verdict = runTrial(player, TRIAL, QUICK);
    player.emit('failure', { stage: 'unresponsive', message: 'The scene stopped responding.' });
    player.emit('finished', undefined);
    await expect(verdict).resolves.toMatchObject({ passed: false, stage: 'unresponsive' });
  });

  it('steps a slide on as each step ends, and passes it held at its last (ADR-049)', async () => {
    const player = new FakePlayer();
    const verdict = runTrial(player, { ...TRIAL, steps: 3 }, QUICK);
    expect(player.loaded).toMatchObject({ pacing: 'cued', rehearsal: true });
    player.emit('scene-event', { name: 'step', value: 0 });
    player.emit('scene-event', { name: 'step', value: 1 });
    expect(player.nexts).toBe(2);
    player.emit('scene-event', { name: 'step', value: 2 });
    await expect(verdict).resolves.toEqual({ passed: true });
    expect(player.nexts).toBe(2);
  });

  it('operates the live page at the end of a slide and goes no further', async () => {
    const player = new FakePlayer();
    const verdict = runTrial(player, { ...TRIAL, steps: 2 }, QUICK);
    player.emit('scene-event', { name: 'step', value: 0 });
    player.emit('scene-event', { name: 'step', value: 1 });
    player.emit('state', page(1, true));
    player.emit('controls', [slider]);
    await expect(verdict).resolves.toEqual({ passed: true });
    expect(player.moved).toEqual([
      ['weight', -2],
      ['weight', 3],
      ['weight', 1],
    ]);
    expect(player.nexts).toBe(1);
  });

  it('loads a picture that is not a slide to play through', () => {
    const player = new FakePlayer();
    void runTrial(player, TRIAL, QUICK);
    expect(player.loaded).toMatchObject({ pacing: 'normal' });
  });
});
