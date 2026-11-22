/**
 * Narration engines. The lesson timeline talks to this interface only, so the
 * way a lesson is read (aloud by the system voice, or silently at reading
 * pace) can change without touching how a lesson is played.
 */

export interface NarrationHandlers {
  /** The whole text has been delivered. Never called after `cancel()`. */
  onEnd: () => void;
  /**
   * The engine has reached a word. Only engines that really know where they
   * are call this; a timer does not pretend to.
   */
  onWord?: (charIndex: number, charLength: number) => void;
  /**
   * Places in the text (the index of a character, in order) where the part's
   * picture takes its next step (ADR-049), and what to call as each is reached:
   * once each, in order, and every one before `onEnd`. An engine that knows
   * where it is calls it at the word; one that does not, at the time it would
   * reach it at its pace. Not a highlighted word: nothing claims a position.
   */
  cues?: readonly number[];
  onCue?: () => void;
}

/**
 * Delivers a line's cues once each, in order: those reached by a position in the
 * text, and the rest when the line ends.
 */
export class CueKeeper {
  private next = 0;

  constructor(
    private readonly cues: readonly number[],
    private readonly onCue: (() => void) | undefined,
  ) {}

  /** The narration has reached this character: every cue up to it is delivered. */
  reached(charIndex: number): void {
    while (this.next < this.cues.length && (this.cues[this.next] ?? Infinity) <= charIndex) {
      this.next += 1;
      this.onCue?.();
    }
  }

  /** The line is over: any cue not reached yet is delivered now, before the end. */
  flush(): void {
    this.reached(Infinity);
  }

  /** The cues not delivered yet, for whoever reads the rest of the line. */
  remaining(): number[] {
    return this.cues.slice(this.next);
  }
}

/**
 * For an engine that may or may not say where it is: each cue is delivered at the time
 * the line would reach it at an estimated pace, unless the engine has said where it is
 * by then, in which case its words deliver the cues. Pausing stops the clock exactly.
 */
export class CueClock {
  private elapsed = 0;
  private startedAt = 0;
  private timer: number | null = null;
  private placed = false;
  private stopped = false;

  constructor(
    private readonly keeper: CueKeeper,
    private readonly cues: readonly number[],
    private readonly text: string,
    private readonly estimateMs: number,
  ) {}

  /** The engine has said where it is: from now on its words deliver the cues. */
  located(charIndex: number): void {
    this.placed = true;
    this.halt();
    this.keeper.reached(charIndex);
  }

  start(): void {
    if (this.stopped || this.placed || this.timer !== null) return;
    this.startedAt = performance.now();
    const due = this.cues
      .map((cue) => (this.estimateMs * cue) / Math.max(1, this.text.length))
      .find((time) => time > this.elapsed);
    if (due === undefined) return;
    this.timer = window.setTimeout(
      () => {
        this.timer = null;
        this.elapsed = due;
        this.keeper.reached(Math.floor((due / this.estimateMs) * this.text.length));
        this.start();
      },
      Math.max(0, due - this.elapsed),
    );
  }

  pause(): void {
    if (this.timer === null) return;
    this.halt();
    this.elapsed += performance.now() - this.startedAt;
  }

  stop(): void {
    this.stopped = true;
    this.halt();
  }

  private halt(): void {
    if (this.timer !== null) window.clearTimeout(this.timer);
    this.timer = null;
  }
}

export interface Utterance {
  pause: () => void;
  resume: () => void;
  /** Stop for good. No handler is called afterwards. */
  cancel: () => void;
}

export interface Narrator {
  readonly kind: 'silent' | 'speech';
  speak: (text: string, handlers: NarrationHandlers) => Utterance;
}

export type Pace = 'relaxed' | 'standard' | 'brisk';

/** Words per minute for reading along, by the learner's chosen pace. */
export const READING_PACE: Record<Pace, number> = { relaxed: 130, standard: 160, brisk: 195 };

const MINIMUM_MS = 1_400;

/** How long a caption stays up when nothing is spoken. */
export function readingTimeMs(text: string, wordsPerMinute: number): number {
  const words = text.trim().split(/\s+/).filter(Boolean).length;
  return Math.max(MINIMUM_MS, Math.round((words / wordsPerMinute) * 60_000));
}

/**
 * Captions without sound: each piece of narration stays up for as long as it
 * takes to read at the chosen pace. Pausing stops the clock exactly.
 */
export class TimedNarrator implements Narrator {
  readonly kind = 'silent';
  private readonly wordsPerMinute: number;

  constructor(pace: Pace = 'standard') {
    this.wordsPerMinute = READING_PACE[pace];
  }

  speak(text: string, handlers: NarrationHandlers): Utterance {
    const total = readingTimeMs(text, this.wordsPerMinute);
    let elapsed = 0;
    let startedAt = performance.now();
    let timer: number | null = null;
    let finished = false;
    // A cue is reached when as much of the line has been read as comes before it.
    const cues = new CueKeeper(handlers.cues ?? [], handlers.onCue);
    const due = (handlers.cues ?? []).map((cue) => (total * cue) / Math.max(1, text.length));

    const start = (): void => {
      startedAt = performance.now();
      const upcoming = due.find((time) => time > elapsed);
      const until = upcoming === undefined ? total : Math.min(upcoming, total);
      timer = window.setTimeout(
        () => {
          timer = null;
          elapsed = until;
          cues.reached(Math.floor((elapsed / total) * text.length));
          if (elapsed >= total) {
            finished = true;
            cues.flush();
            handlers.onEnd();
          } else {
            start();
          }
        },
        Math.max(0, until - elapsed),
      );
    };
    const stop = (): void => {
      if (timer === null) return;
      window.clearTimeout(timer);
      timer = null;
      elapsed = Math.min(total, elapsed + (performance.now() - startedAt));
    };

    start();
    return {
      pause: stop,
      resume: () => {
        if (!finished && timer === null) start();
      },
      cancel: () => {
        stop();
        finished = true;
      },
    };
  }
}
