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
    let remaining = readingTimeMs(text, this.wordsPerMinute);
    let startedAt = performance.now();
    let timer: number | null = null;
    let finished = false;

    const start = (): void => {
      startedAt = performance.now();
      timer = window.setTimeout(() => {
        timer = null;
        finished = true;
        handlers.onEnd();
      }, remaining);
    };
    const stop = (): void => {
      if (timer === null) return;
      window.clearTimeout(timer);
      timer = null;
      remaining = Math.max(0, remaining - (performance.now() - startedAt));
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
