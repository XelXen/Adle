import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  loadLocalVoices,
  pickVoice,
  SPEAKING_RATE,
  type SpeechEngine,
  SpeechNarrator,
  type SpokenLine,
  type Voice,
} from './speech';

const voice = (name: string, lang: string, extra: Partial<Voice> = {}): Voice => ({
  name,
  lang,
  localService: true,
  default: false,
  ...extra,
});

const ZIRA = voice('Microsoft Zira', 'en-US');
const DAVID = voice('Microsoft David', 'en-US', { default: true });
const HAZEL = voice('Microsoft Hazel', 'en-GB');
const HARUKA = voice('Microsoft Haruka', 'ja-JP');
const CLOUD = voice('Cloud English', 'en-US', { localService: false });

/** A speech engine a test drives by hand. */
class FakeEngine implements SpeechEngine {
  voices: Voice[] = [];
  spoken: SpokenLine[] = [];
  log: string[] = [];
  speaking = false;
  pending = false;
  private listeners = new Set<() => void>();

  getVoices = (): Voice[] => this.voices;
  speak = (line: SpokenLine): void => {
    this.spoken.push(line);
    this.speaking = true;
  };
  cancel = (): void => {
    this.log.push('cancel');
    this.speaking = false;
  };
  pause = (): void => {
    this.log.push('pause');
  };
  resume = (): void => {
    this.log.push('resume');
  };
  addEventListener = (_type: 'voiceschanged', listener: () => void): void => {
    this.listeners.add(listener);
  };
  removeEventListener = (_type: 'voiceschanged', listener: () => void): void => {
    this.listeners.delete(listener);
  };

  /** The engine finishes loading its voices. */
  announce(voices: Voice[]): void {
    this.voices = voices;
    for (const listener of [...this.listeners]) listener();
  }

  get listening(): number {
    return this.listeners.size;
  }

  get current(): SpokenLine {
    const line = this.spoken.at(-1);
    if (!line) throw new Error('Nothing has been spoken.');
    return line;
  }
}

const line = (): SpokenLine => ({
  voice: null,
  lang: '',
  rate: 1,
  volume: 1,
  onend: null,
  onerror: null,
  onboundary: null,
});

function narrator(engine: FakeEngine, options: { volume?: number; pace?: 'brisk' } = {}) {
  return new SpeechNarrator(engine, line, {
    voice: ZIRA,
    pace: options.pace ?? 'standard',
    volume: options.volume ?? 0.8,
  });
}

beforeEach(() => {
  vi.useFakeTimers();
});
afterEach(() => {
  vi.useRealTimers();
});

describe('loadLocalVoices', () => {
  it('has no voices when the computer has no speech at all', async () => {
    await expect(loadLocalVoices(null)).resolves.toEqual([]);
  });

  it('uses only voices that speak on this computer', async () => {
    const engine = new FakeEngine();
    engine.voices = [CLOUD, ZIRA, HARUKA];
    await expect(loadLocalVoices(engine)).resolves.toEqual([ZIRA, HARUKA]);
  });

  it('waits for the engine to finish listing its voices', async () => {
    const engine = new FakeEngine();
    const loading = loadLocalVoices(engine, 1500);
    vi.advanceTimersByTime(400);
    engine.announce([CLOUD, DAVID]);
    await expect(loading).resolves.toEqual([DAVID]);
    expect(engine.listening).toBe(0);
  });

  it('gives up after a short while rather than holding the lesson', async () => {
    const engine = new FakeEngine();
    const loading = loadLocalVoices(engine, 1500);
    vi.advanceTimersByTime(1500);
    await expect(loading).resolves.toEqual([]);
    expect(engine.listening).toBe(0);
  });
});

describe('pickVoice', () => {
  it('keeps the voice the learner chose while it is installed', () => {
    expect(pickVoice([DAVID, ZIRA, HAZEL], 'Microsoft Hazel')).toBe(HAZEL);
  });

  it('prefers a voice for the lesson language over the system default', () => {
    const japaneseDefault = { ...HARUKA, default: true };
    expect(pickVoice([japaneseDefault, HAZEL, ZIRA], '')).toBe(HAZEL);
    expect(pickVoice([japaneseDefault, HAZEL, DAVID], '')).toBe(DAVID);
    // A chosen voice that has been uninstalled falls back the same way.
    expect(pickVoice([japaneseDefault, ZIRA], 'Microsoft Hazel')).toBe(ZIRA);
  });

  it('reads with whatever there is when nothing fits, and with nothing when there is nothing', () => {
    expect(pickVoice([HARUKA], '')).toBe(HARUKA);
    expect(pickVoice([], 'Microsoft Zira')).toBeNull();
  });

  it('recognises a language however the engine writes it', () => {
    expect(pickVoice([HARUKA, voice('Legacy', 'en_GB')], '')?.name).toBe('Legacy');
    expect(pickVoice([HARUKA, voice('Plain', 'EN')], '')?.name).toBe('Plain');
    // "en" does not match a language that merely starts with the same letters.
    expect(pickVoice([voice('Other', 'enx-ZZ'), HARUKA], '')?.name).toBe('Other');
    expect(pickVoice([voice('Other', 'enx-ZZ'), HAZEL], '')).toBe(HAZEL);
  });
});

describe('SpeechNarrator', () => {
  it('speaks with the chosen voice, at the pace and volume asked for', () => {
    const engine = new FakeEngine();
    narrator(engine, { pace: 'brisk', volume: 0.35 }).speak('Hello there.', { onEnd: vi.fn() });
    expect(engine.current).toMatchObject({
      voice: ZIRA,
      lang: 'en-US',
      rate: SPEAKING_RATE.brisk,
      volume: 0.35,
    });
  });

  it('keeps the volume within what an engine accepts', () => {
    const engine = new FakeEngine();
    narrator(engine, { volume: 7 }).speak('Loud.', { onEnd: vi.fn() });
    expect(engine.current.volume).toBe(1);
    narrator(engine, { volume: -1 }).speak('Quiet.', { onEnd: vi.fn() });
    expect(engine.current.volume).toBe(0);
  });

  it('ends when the voice has finished, and only once', () => {
    const engine = new FakeEngine();
    const onEnd = vi.fn();
    narrator(engine).speak('One sentence.', { onEnd });
    expect(onEnd).not.toHaveBeenCalled();
    engine.current.onend?.();
    engine.current.onend?.();
    expect(onEnd).toHaveBeenCalledOnce();
  });

  it('reports the word being spoken only when the engine says where it is', () => {
    const engine = new FakeEngine();
    const onWord = vi.fn();
    narrator(engine).speak('Weights matter most.', { onEnd: vi.fn(), onWord });
    engine.current.onboundary?.({ name: 'sentence', charIndex: 0 });
    expect(onWord).not.toHaveBeenCalled();
    engine.current.onboundary?.({ name: 'word', charIndex: 0, charLength: 7 });
    // Some engines say where a word starts but not how long it is.
    engine.current.onboundary?.({ name: 'word', charIndex: 8 });
    engine.current.onboundary?.({ name: 'word', charIndex: 15, charLength: 0 });
    expect(onWord.mock.calls).toEqual([
      [0, 7],
      [8, 6],
      [15, 5],
    ]);
  });

  it('pauses and resumes the voice itself', () => {
    const engine = new FakeEngine();
    const utterance = narrator(engine).speak('A sentence.', { onEnd: vi.fn() });
    utterance.pause();
    utterance.resume();
    expect(engine.log).toEqual(['pause', 'resume']);
  });

  it('says nothing more once cancelled, and treats being stopped as no failure', () => {
    const engine = new FakeEngine();
    const onEnd = vi.fn();
    const onWord = vi.fn();
    const utterance = narrator(engine).speak('A sentence.', { onEnd, onWord });
    utterance.cancel();
    expect(engine.log).toEqual(['cancel']);
    engine.current.onerror?.({ error: 'canceled' });
    engine.current.onboundary?.({ name: 'word', charIndex: 0, charLength: 1 });
    engine.current.onend?.();
    vi.advanceTimersByTime(60_000);
    expect(onEnd).not.toHaveBeenCalled();
    expect(onWord).not.toHaveBeenCalled();
    utterance.cancel(); // already cancelled: the engine is left alone
    expect(engine.log).toEqual(['cancel']);
  });

  it('does not let an earlier line talk over a new one', () => {
    const engine = new FakeEngine();
    const reader = narrator(engine);
    reader.speak('First.', { onEnd: vi.fn() });
    reader.speak('Second.', { onEnd: vi.fn() });
    expect(engine.log).toEqual(['cancel']);
    expect(engine.spoken).toHaveLength(2);
  });

  it('shows the line for its reading time if the voice fails, so the lesson never stalls', () => {
    const engine = new FakeEngine();
    const onEnd = vi.fn();
    const onWord = vi.fn();
    // Sixteen words take six seconds to read at the standard pace.
    const utterance = narrator(engine).speak('word '.repeat(16), { onEnd, onWord });
    engine.current.onerror?.({ error: 'synthesis-failed' });

    vi.advanceTimersByTime(2000);
    utterance.pause();
    vi.advanceTimersByTime(60_000);
    expect(onEnd).not.toHaveBeenCalled();
    // Pausing held the stand-in's own clock; the broken voice was left alone.
    expect(engine.log).toEqual([]);
    utterance.resume();
    vi.advanceTimersByTime(4000);
    expect(onEnd).toHaveBeenCalledOnce();
    // A late word from the failed voice is not shown against the stand-in.
    engine.current.onboundary?.({ name: 'word', charIndex: 0, charLength: 4 });
    expect(onWord).not.toHaveBeenCalled();
  });

  it('can be cancelled while the stand-in is showing', () => {
    const engine = new FakeEngine();
    const onEnd = vi.fn();
    const utterance = narrator(engine).speak('word '.repeat(16), { onEnd });
    engine.current.onerror?.({ error: 'audio-busy' });
    utterance.cancel();
    vi.advanceTimersByTime(60_000);
    expect(onEnd).not.toHaveBeenCalled();
    expect(engine.log).toEqual([]);
  });
});
