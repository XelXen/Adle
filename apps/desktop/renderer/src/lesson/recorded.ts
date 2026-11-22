import { CueKeeper, type NarrationHandlers, type Narrator, type Utterance } from './narration';

/**
 * Narration in a natural voice, recorded on this computer (ADR-042).
 *
 * Each line of a lesson that has been recorded is played from its clip, and each word is
 * marked when the clip reaches the time the voice said it, as recorded with the clip: the
 * voice's own durations, or what the aligner found. A line without a clip is read by the
 * narrator that read lessons before (the computer's own voice, or the words at reading pace),
 * so a lesson never waits for a recording.
 *
 * The clip is the clock: a line ends when its clip has ended, and pausing pauses the clip.
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

/** A word is marked this much before its time, so that the mark is not seen to lag. */
const LEAD_SECONDS = 0.03;

export class RecordedNarrator implements Narrator {
  readonly kind = 'speech';
  private readonly lines = new Map<string, RecordedLine>();

  constructor(
    /** Reads a line that has no clip. */
    private readonly fallback: Narrator,
    private readonly options: RecordedOptions,
    private readonly makeClip: () => Clip = () => new Audio(),
    private readonly frame: (callback: () => void) => number = (callback) =>
      window.requestAnimationFrame(callback),
    private readonly cancelFrame: (handle: number) => void = (handle) =>
      window.cancelAnimationFrame(handle),
  ) {}

  /** A line's clip has arrived. Lines already being read are not changed. */
  add(text: string, line: RecordedLine): void {
    this.lines.set(text, line);
  }

  has(text: string): boolean {
    return this.lines.has(text);
  }

  speak(text: string, handlers: NarrationHandlers): Utterance {
    const line = this.lines.get(text);
    if (!line) return this.fallback.speak(text, handlers);

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
    clip.play().catch(onError);

    return {
      pause: () => {
        if (standIn) standIn.pause();
        else clip.pause();
      },
      resume: () => {
        if (standIn) standIn.resume();
        else if (!over) clip.play().catch(onError);
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
}
