import { describe, expect, it, vi } from 'vitest';

import type { NarrationHandlers, Narrator, Utterance } from './narration';
import { type Clip, RecordedNarrator } from './recorded';

/** An audio element that plays when told and reaches whatever time the test says. */
class FakeClip implements Clip {
  src = '';
  currentTime = 0;
  playbackRate = 1;
  volume = 1;
  preservesPitch = false;
  paused = true;
  plays = 0;
  failToPlay = false;
  private readonly listeners = new Map<string, Set<() => void>>();

  play(): Promise<void> {
    if (this.failToPlay) return Promise.reject(new Error('cannot play'));
    this.plays += 1;
    this.paused = false;
    this.emit('playing');
    return Promise.resolve();
  }

  pause(): void {
    this.paused = true;
  }

  addEventListener(type: string, listener: () => void): void {
    const set = this.listeners.get(type) ?? new Set();
    set.add(listener);
    this.listeners.set(type, set);
  }

  removeEventListener(type: string, listener: () => void): void {
    this.listeners.get(type)?.delete(listener);
  }

  removeAttribute(): void {
    this.src = '';
  }

  load(): void {
    this.currentTime = 0;
  }

  emit(type: string): void {
    for (const listener of [...(this.listeners.get(type) ?? [])]) listener();
  }

  listening(): number {
    return [...this.listeners.values()].reduce((sum, set) => sum + set.size, 0);
  }
}

/** Frames the test hands out itself. */
function frames() {
  const waiting = new Map<number, () => void>();
  let next = 1;
  return {
    frame: (callback: () => void) => {
      waiting.set(next, callback);
      return next++;
    },
    cancel: (handle: number) => {
      waiting.delete(handle);
    },
    run: () => {
      const due = [...waiting.values()];
      waiting.clear();
      for (const callback of due) callback();
    },
  };
}

function fallbackNarrator() {
  const spoken: string[] = [];
  const utterance: Utterance = { pause: vi.fn(), resume: vi.fn(), cancel: vi.fn() };
  const narrator: Narrator = {
    kind: 'speech',
    speak: (text: string, _handlers: NarrationHandlers) => {
      spoken.push(text);
      return utterance;
    },
  };
  return { narrator, spoken, utterance };
}

const LINE = 'Each input has a weight.';
const WORDS = [
  { index: 0, length: 4, start: 0.2, end: 0.4 },
  { index: 5, length: 5, start: 0.45, end: 0.8 },
  { index: 11, length: 3, start: 0.9, end: 1.1 },
  { index: 15, length: 1, start: 1.15, end: 1.2 },
  { index: 17, length: 6, start: 1.25, end: 1.7 },
];

function setUp(options = { rate: 1.15, volume: 0.6 }) {
  const clip = new FakeClip();
  const clock = frames();
  const fallback = fallbackNarrator();
  const narrator = new RecordedNarrator(
    fallback.narrator,
    options,
    () => clip,
    clock.frame,
    clock.cancel,
  );
  narrator.add(LINE, { url: 'blob:adle://app/one', words: WORDS });
  return { clip, clock, fallback, narrator };
}

describe('RecordedNarrator', () => {
  it('plays a recorded line at the learner’s pace and volume, keeping the voice’s pitch', () => {
    const { clip, narrator } = setUp();
    narrator.speak(LINE, { onEnd: vi.fn() });
    expect(clip.src).toBe('blob:adle://app/one');
    expect(clip.playbackRate).toBe(1.15);
    expect(clip.volume).toBe(0.6);
    expect(clip.preservesPitch).toBe(true);
    expect(clip.plays).toBe(1);
  });

  it('marks each word when the clip reaches the time it was said, and ends with the clip', () => {
    const { clip, clock, narrator } = setUp();
    const onWord = vi.fn();
    const onEnd = vi.fn();
    narrator.speak(LINE, { onWord, onEnd });
    clock.run();
    expect(onWord).not.toHaveBeenCalled();
    clip.currentTime = 0.5;
    clock.run();
    expect(onWord.mock.calls).toEqual([
      [0, 4],
      [5, 5],
    ]);
    clip.currentTime = 1.3;
    clock.run();
    expect(onWord.mock.calls.map((call) => call[0] as number)).toEqual([0, 5, 11, 15, 17]);
    expect(onEnd).not.toHaveBeenCalled();
    clip.emit('ended');
    expect(onEnd).toHaveBeenCalledOnce();
    // Nothing is left listening once the line is over.
    expect(clip.listening()).toBe(0);
  });

  it('pauses and resumes the clip, and nothing is marked while it is paused', () => {
    const { clip, clock, narrator } = setUp();
    const onWord = vi.fn();
    const utterance = narrator.speak(LINE, { onWord, onEnd: vi.fn() });
    utterance.pause();
    expect(clip.paused).toBe(true);
    clock.run();
    utterance.resume();
    expect(clip.plays).toBe(2);
    clip.currentTime = 0.3;
    clock.run();
    expect(onWord).toHaveBeenCalledWith(0, 4);
  });

  it('stops for good when cancelled: no word and no end afterwards', () => {
    const { clip, clock, narrator } = setUp();
    const onWord = vi.fn();
    const onEnd = vi.fn();
    narrator.speak(LINE, { onWord, onEnd }).cancel();
    clip.currentTime = 2;
    clock.run();
    clip.emit('ended');
    expect(onWord).not.toHaveBeenCalled();
    expect(onEnd).not.toHaveBeenCalled();
    expect(clip.src).toBe('');
  });

  it('reads a line it has no clip for as the lesson read it before', () => {
    const { clip, fallback, narrator } = setUp();
    narrator.speak('A line nobody recorded.', { onEnd: vi.fn() });
    expect(fallback.spoken).toEqual(['A line nobody recorded.']);
    expect(clip.plays).toBe(0);
    expect(narrator.has(LINE)).toBe(true);
    expect(narrator.has('A line nobody recorded.')).toBe(false);
  });

  it('reads the line another way when its clip cannot be played', async () => {
    const { clip, fallback, narrator } = setUp();
    clip.failToPlay = true;
    const onEnd = vi.fn();
    const utterance = narrator.speak(LINE, { onEnd });
    await Promise.resolve();
    await Promise.resolve();
    expect(fallback.spoken).toEqual([LINE]);
    // From then on the stand-in is what is paused, resumed and cancelled.
    utterance.pause();
    expect(fallback.utterance.pause).toHaveBeenCalled();
    utterance.cancel();
    expect(fallback.utterance.cancel).toHaveBeenCalled();
  });
});
