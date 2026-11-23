import { CueKeeper, type NarrationHandlers, type Narrator, type Utterance } from './narration';

/**
 * Narration in a natural voice, recorded on this computer (ADR-042, ADR-051).
 *
 * Each line of a lesson that has been recorded is played from its clip, and each word is
 * marked when the clip reaches the time the voice said it, as recorded with the clip: the
 * voice's own durations, or what the aligner found.
 *
 * A line not recorded yet is waited for (ADR-051): the voice does not change in the middle
 * of a lesson by itself. The lesson holds at that line, which says so (`state.waiting`),
 * until its clip arrives, and goes on in the natural voice. A line is read by the narrator
 * that read lessons before (the computer's own voice, or the words at reading pace) only
 * when no recording will come for it (`expect(false)`), or from the moment the learner
 * chooses that voice for the rest of the lesson (`useFallback`).
 *
 * The clip is the clock: a line ends when its clip has ended, and pausing pauses the clip.
 * A line waited for has not begun, so nothing measures the wait.
 */

export interface RecordedWord {
  /** Where the word is in the line, in characters. */
  index: number;
  length: number;
  /** When it is said, in seconds from the start of the clip. */
  start: number;
  end: number;
}

export interface RecordedLine {
  /** Where the clip can be played from: an object URL of the page's own. */
  url: string;
  words: readonly RecordedWord[];
}

/** What of an audio element this needs: enough to stand in for one in a test. */
export interface Clip {
  src: string;
  currentTime: number;
  playbackRate: number;
  volume: number;
  preservesPitch: boolean;
  readonly paused: boolean;
  play(): Promise<void>;
  pause(): void;
  addEventListener(type: 'playing' | 'ended' | 'error', listener: () => void): void;
  removeEventListener(type: 'playing' | 'ended' | 'error', listener: () => void): void;
  removeAttribute(name: 'src'): void;
  load(): void;
}

export interface RecordedOptions {
  /** How fast to play: the learner's pace, with the voice's pitch kept. */
  rate: number;
  /** 0 to 1. */
  volume: number;
}

/** What the screen shows of the narrator, beyond what it says. */
export interface RecordedState {
  /** A line is waiting for its recording: the lesson holds there until it comes. */
  waiting: boolean;
  /** The learner chose the other voice for the rest of this lesson. */
  usingFallback: boolean;
}

/** A word is marked this much before its time, so that the mark is not seen to lag. */
const LEAD_SECONDS = 0.03;

/** A line held until its clip comes: told what to read it with when there is one. */
interface Held {
  text: string;
  go: (line: RecordedLine | null) => void;
}

export class RecordedNarrator implements Narrator {
  readonly kind = 'speech';
  private readonly lines = new Map<string, RecordedLine>();
  /** More clips may come: a line without one is waited for. */
  private expecting = true;
  private held: Held | null = null;
  private state: RecordedState = { waiting: false, usingFallback: false };
  private readonly listeners = new Set<() => void>();

  constructor(
    /** Reads a line that has no clip and will have none. */
    private readonly fallback: Narrator,
    private readonly options: RecordedOptions,
    private readonly makeClip: () => Clip = () => new Audio(),
    private readonly frame: (callback: () => void) => number = (callback) =>
      window.requestAnimationFrame(callback),
    private readonly cancelFrame: (handle: number) => void = (handle) =>
      window.cancelAnimationFrame(handle),
  ) {}

  getState = (): RecordedState => this.state;

  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  /** A line's clip has arrived. Lines already being read are not changed; one waited for
   * begins. */
  add(text: string, line: RecordedLine): void {
    this.lines.set(text, line);
    if (this.held?.text === text) this.held.go(line);
  }

  has(text: string): boolean {
    return this.lines.has(text);
  }

  /**
   * Whether more clips may come. When none will (the recording ended without some lines,
   * or cannot be made), a line without one is read by the other narrator, now and from
   * here on.
   */
  expect(more: boolean): void {
    this.expecting = more;
    if (!more) this.held?.go(null);
  }

  /** The learner chose the other voice for the rest of this lesson. */
  useFallback(): void {
    if (this.state.usingFallback) return;
    this.update({ usingFallback: true });
    this.held?.go(null);
  }

  speak(text: string, handlers: NarrationHandlers): Utterance {
    if (this.state.usingFallback) return this.fallback.speak(text, handlers);
    const line = this.lines.get(text);
    if (line) return this.play(text, line, handlers);
    if (!this.expecting) return this.fallback.speak(text, handlers);
    return this.hold(text, handlers);
  }

  /** A line whose clip is still being recorded: held until it comes, or until the other
   * voice is to read it. Paused meanwhile, it begins when the lesson is resumed. */
  private hold(text: string, handlers: NarrationHandlers): Utterance {
    let inner: Utterance | null = null;
    let later: (() => Utterance) | null = null;
    let paused = false;
    let cancelled = false;
    const held: Held = {
      text,
      go: (line) => {
        if (this.held !== held) return;
        this.held = null;
        this.update({ waiting: false });
        if (cancelled) return;
        const begin = (): Utterance =>
          line ? this.play(text, line, handlers) : this.fallback.speak(text, handlers);
        if (paused) later = begin;
        else inner = begin();
      },
    };
    this.held = held;
    this.update({ waiting: true });
    return {
      pause: () => {
        paused = true;
        inner?.pause();
      },
      resume: () => {
        paused = false;
        if (later) {
          inner = later();
          later = null;
        } else {
          inner?.resume();
        }
      },
      cancel: () => {
        cancelled = true;
        if (this.held === held) {
          this.held = null;
          this.update({ waiting: false });
        }
        inner?.cancel();
      },
    };
  }

  private play(text: string, line: RecordedLine, handlers: NarrationHandlers): Utterance {
    const words = [...line.words].sort((a, b) => a.start - b.start);
    const clip = this.makeClip();
    // A picture's cues (ADR-049) are reached with the words the core measured.
    const cues = new CueKeeper(handlers.cues ?? [], handlers.onCue);
    let next = 0;
    let handle: number | null = null;
    let over = false;
    let standIn: Utterance | null = null;

    const watch = (): void => {
      handle = null;
      if (over || standIn) return;
      const now = clip.currentTime + LEAD_SECONDS;
      while (next < words.length && words[next]!.start <= now) {
        const word = words[next]!;
        handlers.onWord?.(word.index, word.length);
        cues.reached(word.index);
        next += 1;
      }
      if (!clip.paused) handle = this.frame(watch);
    };
    const stopWatching = (): void => {
      if (handle !== null) this.cancelFrame(handle);
      handle = null;
    };
    const onPlaying = (): void => {
      handle ??= this.frame(watch);
    };
    const detach = (): void => {
      clip.removeEventListener('playing', onPlaying);
      clip.removeEventListener('ended', onEnded);
      clip.removeEventListener('error', onError);
    };
    function onEnded(): void {
      if (over || standIn) return;
      over = true;
      stopWatching();
      detach();
      cues.flush();
      handlers.onEnd();
    }
    const onError = (): void => {
      // The clip cannot be played: the line is read as it would have been without one.
      if (over || standIn) return;
      stopWatching();
      detach();
      standIn = this.fallback.speak(text, { ...handlers, cues: cues.remaining() });
    };

    clip.addEventListener('playing', onPlaying);
    clip.addEventListener('ended', onEnded);
    clip.addEventListener('error', onError);
    clip.preservesPitch = true;
    clip.playbackRate = this.options.rate;
    clip.volume = Math.min(1, Math.max(0, this.options.volume));
    clip.src = line.url;
    // A play the learner paused before it began is not a clip that cannot be played.
    const failed = (error: unknown): void => {
      if (error instanceof DOMException && error.name === 'AbortError') return;
      onError();
    };
    clip.play().catch(failed);

    return {
      pause: () => {
        if (standIn) standIn.pause();
        else clip.pause();
      },
      resume: () => {
        if (standIn) standIn.resume();
        else if (!over) clip.play().catch(failed);
      },
      cancel: () => {
        if (standIn) {
          standIn.cancel();
          return;
        }
        if (over) return;
        over = true;
        stopWatching();
        detach();
        clip.pause();
        clip.removeAttribute('src');
        clip.load();
      },
    };
  }

  private update(changes: Partial<RecordedState>): void {
    this.state = { ...this.state, ...changes };
    for (const listener of [...this.listeners]) listener();
  }
}
