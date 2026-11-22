/**
 * Narration read aloud by the computer's own voices.
 *
 * Speech comes from the operating system through the browser's speech
 * synthesis. Only voices that speak **on this computer** are ever used: a voice
 * that would send the text to a service is ignored, because narration is lesson
 * content and nothing leaves the machine without the learner asking.
 *
 * The narrator reports where it is only when the engine says so (a word
 * boundary event). It never estimates where it is. A picture's cues are not a
 * claim to a place: a voice that says nothing of where it is has them at the
 * time the line would reach them at its pace (ADR-049).
 */
import {
  CueClock,
  CueKeeper,
  type NarrationHandlers,
  type Narrator,
  type Pace,
  readingTimeMs,
  TimedNarrator,
  type Utterance,
} from './narration';

/** The voice of one installed speech engine, as the browser lists it. */
export interface Voice {
  readonly name: string;
  readonly lang: string;
  readonly localService: boolean;
  readonly default: boolean;
}

/** What is asked of the browser's speech synthesis. A test can stand in for it. */
export interface SpeechEngine {
  readonly speaking: boolean;
  readonly pending: boolean;
  getVoices: () => Voice[];
  speak: (utterance: SpokenLine) => void;
  cancel: () => void;
  pause: () => void;
  resume: () => void;
  addEventListener: (type: 'voiceschanged', listener: () => void) => void;
  removeEventListener: (type: 'voiceschanged', listener: () => void) => void;
}

/** One thing to say: the part of `SpeechSynthesisUtterance` that is used. */
export interface SpokenLine {
  voice: Voice | null;
  lang: string;
  rate: number;
  volume: number;
  onend: (() => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onboundary: ((event: { name: string; charIndex: number; charLength?: number }) => void) | null;
}

/** How fast each pace speaks. 1 is the voice's own speed. */
export const SPEAKING_RATE: Record<Pace, number> = { relaxed: 0.9, standard: 1, brisk: 1.15 };

/** About how many words a minute a voice says at each pace, for a voice that does not
 * say where it is. */
const SPOKEN_WORDS_PER_MINUTE: Record<Pace, number> = { relaxed: 150, standard: 165, brisk: 190 };

/** The language lessons are written in. Voices for it are preferred over the system default. */
export const LESSON_LANGUAGE = 'en';

/** The browser's speech synthesis, if this computer has one. */
export function browserSpeech(): SpeechEngine | null {
  const candidate = (globalThis as { speechSynthesis?: unknown }).speechSynthesis;
  if (typeof candidate !== 'object' || candidate === null) return null;
  return candidate as SpeechEngine;
}

/**
 * The voices that speak on this computer, once the engine has listed them.
 *
 * Voices are loaded in the background, so an empty list may only mean "not
 * yet". This waits for the engine to say the list changed, for a short while.
 */
export function loadLocalVoices(engine: SpeechEngine | null, timeoutMs = 1500): Promise<Voice[]> {
  if (!engine) return Promise.resolve([]);
  const read = (): Voice[] => engine.getVoices().filter((voice) => voice.localService);
  const now = read();
  if (now.length > 0) return Promise.resolve(now);
  return new Promise((resolve) => {
    const finish = (): void => {
      window.clearTimeout(timer);
      engine.removeEventListener('voiceschanged', finish);
      resolve(read());
    };
    const timer = window.setTimeout(finish, timeoutMs);
    engine.addEventListener('voiceschanged', finish);
  });
}

function speaks(voice: Voice, language: string): boolean {
  const lang = voice.lang.toLowerCase().replace('_', '-');
  return lang === language || lang.startsWith(`${language}-`);
}

/**
 * The voice to read with: the learner's own choice if it is still installed,
 * otherwise a voice for the lesson's language, otherwise whatever there is.
 */
export function pickVoice(
  voices: readonly Voice[],
  preferredName: string,
  language: string = LESSON_LANGUAGE,
): Voice | null {
  if (voices.length === 0) return null;
  const chosen = voices.find((voice) => voice.name === preferredName);
  if (chosen) return chosen;
  const fitting = voices.filter((voice) => speaks(voice, language));
  return (
    fitting.find((voice) => voice.default) ??
    fitting[0] ??
    voices.find((voice) => voice.default) ??
    voices[0] ??
    null
  );
}

/** The length of the word that starts at `index`, for engines that report only where it starts. */
function wordLengthAt(text: string, index: number): number {
  const rest = text.slice(index);
  const match = /^\S+/.exec(rest);
  return match ? match[0].length : 0;
}

export interface SpeechOptions {
  voice: Voice;
  pace: Pace;
  /** 0 to 1. */
  volume: number;
}

/**
 * Reads narration aloud. The engine is the clock: a line ends when the voice
 * has finished it, and pausing pauses the voice.
 *
 * If the voice fails part-way through a line, that line is shown for as long as
 * it takes to read instead, so a lesson never stalls on a broken voice.
 */
export class SpeechNarrator implements Narrator {
  readonly kind = 'speech';
  private readonly silent: TimedNarrator;

  constructor(
    private readonly engine: SpeechEngine,
    private readonly createLine: (text: string) => SpokenLine,
    private readonly options: SpeechOptions,
  ) {
    this.silent = new TimedNarrator(options.pace);
  }

  speak(text: string, handlers: NarrationHandlers): Utterance {
    let over = false;
    let standIn: Utterance | null = null;
    // A picture's cues (ADR-049): at the words, when the voice says where it is; at the
    // time the line would reach them when it does not; and any left, as the line ends.
    const cues = new CueKeeper(handlers.cues ?? [], handlers.onCue);
    const clock = new CueClock(
      cues,
      handlers.cues ?? [],
      text,
      readingTimeMs(text, SPOKEN_WORDS_PER_MINUTE[this.options.pace]),
    );
    const finish = (): void => {
      if (over) return;
      over = true;
      clock.stop();
      cues.flush();
      handlers.onEnd();
    };

    const line = this.createLine(text);
    line.voice = this.options.voice;
    line.lang = this.options.voice.lang;
    line.rate = SPEAKING_RATE[this.options.pace];
    line.volume = Math.min(1, Math.max(0, this.options.volume));
    line.onboundary = (event) => {
      if (over || standIn || event.name !== 'word') return;
      const length = event.charLength && event.charLength > 0 ? event.charLength : 0;
      handlers.onWord?.(event.charIndex, length || wordLengthAt(text, event.charIndex));
      clock.located(event.charIndex);
    };
    line.onend = finish;
    line.onerror = (event) => {
      // Being stopped on purpose is not a failure.
      if (over || standIn || event.error === 'canceled' || event.error === 'interrupted') return;
      clock.stop();
      standIn = this.silent.speak(text, {
        onEnd: finish,
        cues: cues.remaining(),
        onCue: handlers.onCue,
      });
    };

    // Nothing left over from an earlier line may talk over this one.
    if (this.engine.speaking || this.engine.pending) this.engine.cancel();
    this.engine.speak(line);
    clock.start();

    return {
      pause: () => {
        clock.pause();
        if (standIn) standIn.pause();
        else this.engine.pause();
      },
      resume: () => {
        if (standIn) standIn.resume();
        else {
          this.engine.resume();
          clock.start();
        }
      },
      cancel: () => {
        if (over) return;
        over = true;
        clock.stop();
        if (standIn) standIn.cancel();
        else this.engine.cancel();
      },
    };
  }
}

/** A line for the real engine. */
export function browserLine(text: string): SpokenLine {
  return new SpeechSynthesisUtterance(text) as unknown as SpokenLine;
}
