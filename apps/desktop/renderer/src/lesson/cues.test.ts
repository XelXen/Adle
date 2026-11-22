import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { PlayerLesson } from '@adle/contracts';

import { LessonController, type PlaybackHost } from './controller';
import {
  CueKeeper,
  type NarrationHandlers,
  type Narrator,
  readingTimeMs,
  READING_PACE,
  TimedNarrator,
  type Utterance,
} from './narration';
import { type Clip, RecordedNarrator } from './recorded';
import { SceneCues } from './scene-cues';
import { type SpeechEngine, SpeechNarrator, type SpokenLine, type Voice } from './speech';

/**
 * A slide's cues (ADR-049): words of the narration where the part's picture takes its next
 * step. Every narrator delivers each once, in order, and all of them before the line ends;
 * the lesson passes each to the scene on screen, one step at a time.
 */

beforeEach(() => {
  vi.useFakeTimers();
});
afterEach(() => {
  vi.useRealTimers();
});

describe('CueKeeper', () => {
  it('delivers each cue once, in order, as the words reach it, and the rest at the end', () => {
    const onCue = vi.fn();
    const keeper = new CueKeeper([5, 12, 30], onCue);
    keeper.reached(4);
    expect(onCue).not.toHaveBeenCalled();
    keeper.reached(12);
    expect(onCue).toHaveBeenCalledTimes(2);
    keeper.reached(12);
    expect(onCue).toHaveBeenCalledTimes(2);
    expect(keeper.remaining()).toEqual([30]);
    keeper.flush();
    keeper.flush();
    expect(onCue).toHaveBeenCalledTimes(3);
  });
});

describe('TimedNarrator', () => {
  const TEXT = 'Flip a coin. There are two outcomes, heads and tails, and nothing else.';

  it('delivers a cue when as much of the line has been read as comes before it', () => {
    const events: string[] = [];
    const total = readingTimeMs(TEXT, READING_PACE.standard);
    const cue = TEXT.indexOf('two');
    new TimedNarrator('standard').speak(TEXT, {
      onEnd: () => events.push('end'),
      cues: [cue],
      onCue: () => events.push('cue'),
    });
    vi.advanceTimersByTime((total * cue) / TEXT.length - 50);
    expect(events).toEqual([]);
    vi.advanceTimersByTime(100);
    expect(events).toEqual(['cue']);
    vi.advanceTimersByTime(total);
    expect(events).toEqual(['cue', 'end']);
  });

  it('keeps its place in time while paused', () => {
    const onCue = vi.fn();
    const total = readingTimeMs(TEXT, READING_PACE.standard);
    const reading = new TimedNarrator('standard').speak(TEXT, {
      onEnd: vi.fn(),
      cues: [Math.floor(TEXT.length / 2)],
      onCue,
    });
    vi.advanceTimersByTime(total * 0.4);
    reading.pause();
    vi.advanceTimersByTime(total * 5);
    expect(onCue).not.toHaveBeenCalled();
    reading.resume();
    vi.advanceTimersByTime(total * 0.15);
    expect(onCue).toHaveBeenCalledOnce();
  });

  it('delivers nothing once cancelled', () => {
    const onCue = vi.fn();
    const onEnd = vi.fn();
    const reading = new TimedNarrator('standard').speak(TEXT, { onEnd, cues: [3, 40], onCue });
    reading.cancel();
    vi.advanceTimersByTime(60_000);
    expect(onCue).not.toHaveBeenCalled();
    expect(onEnd).not.toHaveBeenCalled();
  });
});

class Engine implements SpeechEngine {
  spoken: SpokenLine[] = [];
  speaking = false;
  pending = false;
  getVoices = (): Voice[] => [];
  speak = (line: SpokenLine): void => {
    this.spoken.push(line);
  };
  cancel = vi.fn();
  pause = vi.fn();
  resume = vi.fn();
  addEventListener = vi.fn();
  removeEventListener = vi.fn();
  get current(): SpokenLine {
    return this.spoken.at(-1)!;
  }
}

const VOICE = { name: 'Zira', lang: 'en-US', localService: true, default: true } as Voice;

function speech(engine: Engine): SpeechNarrator {
  return new SpeechNarrator(
    engine,
    () => ({
      voice: null,
      lang: '',
      rate: 1,
      volume: 1,
      onend: null,
      onerror: null,
      onboundary: null,
    }),
    { voice: VOICE, pace: 'standard', volume: 1 },
  );
}

describe('SpeechNarrator', () => {
  const TEXT = 'There are two outcomes, heads and tails.';

  it('delivers a cue at the word when the voice says where it is, and never by the clock', () => {
    const engine = new Engine();
    const onCue = vi.fn();
    speech(engine).speak(TEXT, { onEnd: vi.fn(), cues: [TEXT.indexOf('heads')], onCue });
    engine.current.onboundary?.({ name: 'word', charIndex: 0, charLength: 5 });
    vi.advanceTimersByTime(60_000);
    expect(onCue).not.toHaveBeenCalled();
    engine.current.onboundary?.({ name: 'word', charIndex: TEXT.indexOf('heads') });
    expect(onCue).toHaveBeenCalledOnce();
  });

  it('delivers a cue by its pace when the voice says nothing of where it is', () => {
    const engine = new Engine();
    const onCue = vi.fn();
    speech(engine).speak(TEXT, { onEnd: vi.fn(), cues: [TEXT.indexOf('heads')], onCue });
    vi.advanceTimersByTime(20_000);
    expect(onCue).toHaveBeenCalledOnce();
  });

  it('delivers every cue left before the line ends', () => {
    const engine = new Engine();
    const events: string[] = [];
    speech(engine).speak(TEXT, {
      onEnd: () => events.push('end'),
      cues: [4, 20],
      onCue: () => events.push('cue'),
    });
    engine.current.onboundary?.({ name: 'word', charIndex: 0 });
    engine.current.onend?.();
    expect(events).toEqual(['cue', 'cue', 'end']);
  });
});

class Clip_ implements Clip {
  src = '';
  currentTime = 0;
  playbackRate = 1;
  volume = 1;
  preservesPitch = false;
  paused = true;
  private readonly listeners = new Map<string, Set<() => void>>();
  play(): Promise<void> {
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
  removeAttribute = vi.fn();
  load = vi.fn();
  emit(type: string): void {
    for (const listener of [...(this.listeners.get(type) ?? [])]) listener();
  }
}

describe('RecordedNarrator', () => {
  it('delivers a cue with the word the core measured, and the rest as the clip ends', () => {
    const clip = new Clip_();
    const waiting: (() => void)[] = [];
    const silent: Narrator = {
      kind: 'silent',
      speak: (): Utterance => ({ pause: vi.fn(), resume: vi.fn(), cancel: vi.fn() }),
    };
    const narrator = new RecordedNarrator(
      silent,
      { rate: 1, volume: 1 },
      () => clip,
      (callback) => waiting.push(callback),
      vi.fn(),
    );
    const LINE = 'Each input has a weight.';
    narrator.add(LINE, {
      url: 'blob:adle://app/one',
      words: [
        { index: 0, length: 4, start: 0.2, end: 0.4 },
        { index: 5, length: 5, start: 0.45, end: 0.8 },
        { index: 17, length: 6, start: 1.25, end: 1.7 },
      ],
    });
    const events: string[] = [];
    narrator.speak(LINE, {
      onEnd: () => events.push('end'),
      cues: [5, 17],
      onCue: () => events.push('cue'),
    });
    clip.currentTime = 0.5;
    for (const callback of waiting.splice(0)) callback();
    expect(events).toEqual(['cue']);
    clip.emit('ended');
    expect(events).toEqual(['cue', 'cue', 'end']);
  });
});

describe('SceneCues and a slide', () => {
  it('gives a slide one cue each time it holds after a step', () => {
    const cues = new SceneCues();
    const controls = { next: vi.fn(), reset: vi.fn() };
    cues.attach('seg_a', controls);
    // Three cues are said while the slide is still drawing its first step.
    cues.advance('seg_a');
    cues.advance('seg_a');
    cues.advance('seg_a');
    expect(controls.next).not.toHaveBeenCalled();
    // Held after its first step: one cue. The same step said again takes none.
    for (let times = 0; times < 5; times += 1) cues.setHolding('seg_a', true, 0);
    expect(controls.next).toHaveBeenCalledOnce();
    cues.setHolding('seg_a', true, 1);
    cues.setHolding('seg_a', true, 1);
    expect(controls.next).toHaveBeenCalledTimes(2);
    cues.setHolding('seg_a', true, 2);
    expect(controls.next).toHaveBeenCalledTimes(3);
    // No cue is left for the last step: it stays.
    cues.setHolding('seg_a', true, 3);
    expect(controls.next).toHaveBeenCalledTimes(3);
  });

  it('forgets the cues of a part played again from its start', () => {
    const cues = new SceneCues();
    const controls = { next: vi.fn(), reset: vi.fn() };
    cues.attach('seg_a', controls);
    cues.advance('seg_a');
    cues.advance('seg_a');
    cues.restart();
    cues.setHolding('seg_a', true, 0);
    expect(controls.next).not.toHaveBeenCalled();
    expect(controls.reset).toHaveBeenCalledOnce();
  });
});

describe('LessonController', () => {
  it('passes each cue of a line on to the scene, and none once the line is left', () => {
    let handlers: NarrationHandlers | null = null;
    const narrator: Narrator = {
      kind: 'silent',
      speak: (_text, given) => {
        handlers = given;
        return { pause: vi.fn(), resume: vi.fn(), cancel: vi.fn() };
      },
    };
    const host: PlaybackHost = { narrator, advanceScene: vi.fn(), saveProgress: vi.fn() };
    const lesson = {
      schema_version: '1.0',
      lesson_id: 'les_00000000000000000001',
      course_id: 'crs_00000000000000000001',
      title: 'Coins',
      concept_ids: ['con_00000000000000000001'],
      objectives: [{ statement: 'Name the outcomes of a flip.' }],
      source_refs: [],
      grounding: 'sample',
      strategy: 'visual',
      estimated_minutes: 1,
      segments: [
        {
          id: 'seg_flip',
          type: 'explanation',
          title: 'One flip',
          estimated_seconds: 20,
          narration: [{ text: 'There are two outcomes, heads and tails.', cues: [10, 24] }],
          scene: { scene_id: 'scn_1', fallback_text: 'A coin.' },
        },
        {
          id: 'seg_end',
          type: 'summary',
          title: 'Summary',
          estimated_seconds: 10,
          narration: [{ text: 'Done.' }],
        },
      ],
      practice: [],
    } as unknown as PlayerLesson;
    const controller = new LessonController(lesson, host);
    controller.play();
    const given = handlers as unknown as NarrationHandlers;
    expect(given.cues).toEqual([10, 24]);
    given.onCue?.();
    given.onCue?.();
    expect(host.advanceScene).toHaveBeenCalledTimes(2);
    controller.next();
    given.onCue?.();
    expect(host.advanceScene).toHaveBeenCalledTimes(2);
  });
});
