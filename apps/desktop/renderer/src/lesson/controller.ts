import type { PlayerLesson } from '@adle/contracts';

import type { Narrator, Utterance } from './narration';

export type LessonSegment = PlayerLesson['segments'][number];

/**
 * Where a segment is:
 *  - `ready`    shown, not started (the lesson opens like this, so nothing plays unasked)
 *  - `playing`  narration is running
 *  - `paused`   narration is held
 *  - `waiting`  the narration is over and the learner has something to do
 *  - `done`     nothing more happens here; the lesson can move on
 */
export type SegmentStatus = 'ready' | 'playing' | 'paused' | 'waiting' | 'done';

export interface PlaybackState {
  segmentIndex: number;
  status: SegmentStatus;
  /** The beat being narrated, or the last one that was; -1 before the segment starts. */
  beatIndex: number;
  /** How many beats have begun. What those beats show is on the board. */
  beatsStarted: number;
  /** The word being spoken in the current beat, when the narrator reports it. */
  word: { start: number; length: number } | null;
  /** The current checkpoint has been answered or explicitly skipped. */
  answered: boolean;
  /** The current interaction has been tried. */
  explored: boolean;
  /** The furthest segment reached so far. Earlier ones can be revisited. */
  furthest: number;
  /** The last segment has been completed. */
  finished: boolean;
}

export interface PlaybackHost {
  narrator: Narrator;
  /** Move the current segment's scene on to its animation. */
  advanceScene: () => void;
  /** Remember where the learner is. Called at segment boundaries, never on unload. */
  saveProgress: (position: number, completed: boolean) => void;
}

function narrationOf(segment: LessonSegment): { text: string; advance_scene?: boolean }[] {
  return segment.narration ?? [];
}

/**
 * Whether the lesson may move on from this segment. A question must be answered
 * or skipped the first time it is met; on a later visit it is only an offer, so
 * going back through a lesson never traps the learner behind a question again.
 */
export function canContinue(state: PlaybackState, segment: LessonSegment): boolean {
  return segment.type !== 'checkpoint' || state.answered || state.segmentIndex < state.furthest;
}

/**
 * Plays a lesson: which segment is showing, which beat is being narrated, and
 * what the learner still has to do before moving on.
 *
 * The narrator is the clock. A beat ends when the narrator says it has ended,
 * and pausing pauses the narrator; nothing here measures time itself.
 */
export class LessonController {
  private state: PlaybackState;
  private utterance: Utterance | null = null;
  /** Bumped whenever narration is cancelled, so a late callback can be recognised. */
  private generation = 0;
  /** Once the learner has pressed play, later segments start by themselves. */
  private started = false;
  private readonly listeners = new Set<() => void>();
  /** Who is reading. Starts as the host's narrator and can be changed while a lesson plays. */
  private narrator: Narrator;

  constructor(
    private readonly lesson: PlayerLesson,
    private readonly host: PlaybackHost,
    start: { position: number; furthest?: number } = { position: 0 },
  ) {
    this.narrator = host.narrator;
    const last = lesson.segments.length - 1;
    const clamp = (index: number): number => Math.min(Math.max(0, index), last);
    const position = clamp(start.position);
    // A lesson that was completed before is open from end to end.
    this.state = this.entered(position, clamp(start.furthest ?? position));
    this.settleIfSilent();
  }

  getState = (): PlaybackState => this.state;

  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  get segment(): LessonSegment {
    const segment = this.lesson.segments[this.state.segmentIndex];
    if (!segment) throw new Error('The lesson has no segment at this position.');
    return segment;
  }

  /** Start the segment's narration, or resume it. */
  play(): void {
    if (this.state.status === 'paused') {
      this.utterance?.resume();
      this.update({ status: 'playing' });
    } else if (this.state.status === 'ready') {
      this.started = true;
      this.startBeat(0);
    }
  }

  pause(): void {
    if (this.state.status !== 'playing') return;
    this.utterance?.pause();
    this.update({ status: 'paused' });
  }

  /** Hear the current segment again from its beginning. */
  replay(): void {
    this.started = true;
    this.enter(this.state.segmentIndex, true);
  }

  /** Move on. Returns false when the learner still has a question to answer or skip. */
  next(): boolean {
    if (!canContinue(this.state, this.segment)) return false;
    const last = this.lesson.segments.length - 1;
    if (this.state.segmentIndex >= last) {
      this.cancelNarration();
      this.update({ status: 'done', finished: true, word: null });
      this.host.saveProgress(last, true);
      return true;
    }
    const position = this.state.segmentIndex + 1;
    this.enter(position, this.started);
    this.host.saveProgress(position, false);
    return true;
  }

  previous(): void {
    if (this.state.segmentIndex > 0) this.enter(this.state.segmentIndex - 1, false);
  }

  /** Jump to a segment that has already been reached. */
  goTo(index: number): void {
    if (index < 0 || index > this.state.furthest || index === this.state.segmentIndex) return;
    this.enter(index, false);
  }

  /**
   * Go back to the first segment after finishing, to go through the lesson
   * again. Everything stays reachable and nothing plays until asked.
   */
  restart(): void {
    this.started = false;
    this.enter(0, false);
  }

  markAnswered(): void {
    this.update({
      answered: true,
      status: this.state.status === 'waiting' ? 'done' : this.state.status,
    });
  }

  markExplored(): void {
    if (!this.state.explored) this.update({ explored: true });
  }

  /**
   * Read with another narrator from here on (aloud instead of silently, or the
   * other way round). What was being read starts again with the new one, since
   * the two keep time differently and the old one cannot hand over mid-sentence.
   */
  setNarrator(narrator: Narrator): void {
    if (narrator === this.narrator) return;
    this.narrator = narrator;
    const { status, beatIndex } = this.state;
    if (status !== 'playing' && status !== 'paused') return;
    this.cancelNarration();
    this.startBeat(Math.max(0, beatIndex));
    if (status === 'paused') this.pause();
  }

  /** Stop everything. The controller must not be used afterwards. */
  dispose(): void {
    this.cancelNarration();
    this.listeners.clear();
  }

  // -- internals -----------------------------------------------------------

  private entered(index: number, furthest: number): PlaybackState {
    return {
      segmentIndex: index,
      status: 'ready',
      beatIndex: -1,
      beatsStarted: 0,
      word: null,
      answered: false,
      explored: false,
      furthest: Math.max(furthest, index),
      finished: false,
    };
  }

  private enter(index: number, autoplay: boolean): void {
    this.cancelNarration();
    this.state = this.entered(index, this.state.furthest);
    if (autoplay && narrationOf(this.segment).length > 0) this.startBeat(0);
    else this.settleIfSilent();
    this.notify();
  }

  /** A segment with nothing to narrate has nothing to wait for. */
  private settleIfSilent(): void {
    if (narrationOf(this.segment).length === 0) {
      this.state = { ...this.state, status: this.restingStatus() };
    }
  }

  private restingStatus(): SegmentStatus {
    const { type } = this.segment;
    if (type === 'checkpoint') return this.state.answered ? 'done' : 'waiting';
    return type === 'interaction' ? 'waiting' : 'done';
  }

  private startBeat(index: number): void {
    const beat = narrationOf(this.segment)[index];
    if (!beat) {
      this.update({ status: this.restingStatus(), word: null });
      return;
    }
    const generation = this.generation;
    this.update({ status: 'playing', beatIndex: index, beatsStarted: index + 1, word: null });
    if (beat.advance_scene) this.host.advanceScene();
    let ended = false;
    const utterance = this.narrator.speak(beat.text, {
      onEnd: () => {
        ended = true;
        if (generation !== this.generation) return;
        this.utterance = null;
        this.startBeat(index + 1);
      },
      onWord: (start, length) => {
        if (generation === this.generation) this.update({ word: { start, length } });
      },
    });
    // A narrator may finish before `speak` returns; then there is nothing to hold on to.
    if (!ended && generation === this.generation) this.utterance = utterance;
  }

  private cancelNarration(): void {
    this.generation += 1;
    this.utterance?.cancel();
    this.utterance = null;
  }

  private update(changes: Partial<PlaybackState>): void {
    this.state = { ...this.state, ...changes };
    this.notify();
  }

  private notify(): void {
    for (const listener of [...this.listeners]) listener();
  }
}
