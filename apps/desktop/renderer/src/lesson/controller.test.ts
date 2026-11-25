import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { PlayerLesson } from '@adle/contracts';

import { canContinue, LessonController, type LessonSegment, type PlaybackHost } from './controller';
import {
  type NarrationHandlers,
  type Narrator,
  readingTimeMs,
  TimedNarrator,
  type Utterance,
} from './narration';

/** A narrator the test finishes by hand, recording everything it was asked to do. */
class FakeNarrator implements Narrator {
  readonly kind = 'silent';
  spoken: string[] = [];
  log: string[] = [];
  private current: NarrationHandlers | null = null;

  speak(text: string, handlers: NarrationHandlers): Utterance {
    this.spoken.push(text);
    this.current = handlers;
    return {
      pause: () => this.log.push('pause'),
      resume: () => this.log.push('resume'),
      cancel: () => {
        this.log.push('cancel');
        if (this.current === handlers) this.current = null;
      },
    };
  }

  /** The narrator reaches the end of what it was saying. */
  finish(): void {
    const handlers = this.current;
    this.current = null;
    handlers?.onEnd();
  }

  word(start: number, length: number): void {
    this.current?.onWord?.(start, length);
  }

  get speaking(): boolean {
    return this.current !== null;
  }
}

const LESSON: PlayerLesson = {
  schema_version: '1.0',
  lesson_id: 'les_00000000000000000001',
  course_id: 'crs_00000000000000000001',
  title: 'A single neuron',
  concept_ids: ['con_00000000000000000001'],
  objectives: [{ statement: 'Compute a weighted sum.' }],
  source_refs: [],
  grounding: 'sample',
  strategy: 'visual',
  estimated_minutes: 5,
  segments: [
    {
      id: 'seg_idea',
      type: 'explanation',
      title: 'The idea',
      estimated_seconds: 20,
      narration: [{ text: 'First.', show: 'Point one' }, { text: 'Second.' }],
    },
    {
      id: 'seg_try',
      type: 'interaction',
      title: 'Try it',
      estimated_seconds: 30,
      prompt: 'Drag the weight.',
      narration: [{ text: 'Your turn.' }, { text: 'Now watch.', advance_scene: true }],
      scene: { scene_id: 'scn_neuron', fallback_text: 'A bar grows with the weight.' },
    },
    {
      id: 'seg_check',
      type: 'checkpoint',
      title: 'Check',
      estimated_seconds: 20,
      narration: [],
      question: {
        id: 'q_one',
        form: 'true_false',
        concept_id: 'con_00000000000000000001',
        stem: 'A larger weight matters more.',
        difficulty: 1,
        is_transfer: false,
      },
    },
    {
      id: 'seg_think',
      type: 'reflection',
      title: 'Think',
      estimated_seconds: 10,
      prompt: 'What would a weight of zero mean?',
      narration: [],
    },
    {
      id: 'seg_recap',
      type: 'summary',
      title: 'In short',
      estimated_seconds: 10,
      narration: [{ text: 'That is a neuron.', show: 'Weighted sum plus bias' }],
    },
  ],
};

function setup(position = 0, furthest?: number) {
  const narrator = new FakeNarrator();
  const host: PlaybackHost & { saved: [number, boolean][]; advanced: number } = {
    narrator,
    saved: [],
    advanced: 0,
    advanceScene: () => {
      host.advanced += 1;
    },
    saveProgress: (at, completed) => {
      host.saved.push([at, completed]);
    },
  };
  const controller = new LessonController(LESSON, host, { position, furthest });
  const changes = vi.fn();
  controller.subscribe(changes);
  return { controller, narrator, host, changes };
}

describe('starting a lesson', () => {
  it('opens ready and silent: nothing plays until the learner asks', () => {
    const { controller, narrator } = setup();
    expect(controller.getState()).toMatchObject({
      segmentIndex: 0,
      status: 'ready',
      beatIndex: -1,
      beatsStarted: 0,
      finished: false,
    });
    expect(narrator.spoken).toEqual([]);
  });

  it('resumes at the saved position, clamped to the lesson', () => {
    expect(setup(3).controller.getState().segmentIndex).toBe(3);
    expect(setup(99).controller.getState().segmentIndex).toBe(4);
    expect(setup(-2).controller.getState().segmentIndex).toBe(0);
    // Segments before the saved position can be revisited.
    expect(setup(3).controller.getState().furthest).toBe(3);
  });

  it('opens a lesson that was completed before from end to end', () => {
    const { controller } = setup(0, 99);
    expect(controller.getState()).toMatchObject({ segmentIndex: 0, furthest: 4, status: 'ready' });
    controller.goTo(4);
    expect(controller.getState().segmentIndex).toBe(4);
  });
});

describe('narration', () => {
  it('speaks each beat in turn and reveals what each one shows', () => {
    const { controller, narrator, changes } = setup();
    controller.play();
    expect(narrator.spoken).toEqual(['First.']);
    expect(controller.getState()).toMatchObject({
      status: 'playing',
      beatIndex: 0,
      beatsStarted: 1,
    });
    expect(changes).toHaveBeenCalled();

    narrator.finish();
    expect(narrator.spoken).toEqual(['First.', 'Second.']);
    expect(controller.getState()).toMatchObject({
      status: 'playing',
      beatIndex: 1,
      beatsStarted: 2,
    });

    narrator.finish();
    expect(controller.getState()).toMatchObject({ status: 'done', beatIndex: 1, beatsStarted: 2 });
    expect(narrator.speaking).toBe(false);
  });

  it('pauses and resumes the narrator itself, so the clock is never guessed', () => {
    const { controller, narrator } = setup();
    controller.play();
    controller.pause();
    expect(controller.getState().status).toBe('paused');
    controller.pause(); // already paused: nothing more to do
    controller.play();
    expect(controller.getState().status).toBe('playing');
    expect(narrator.log).toEqual(['pause', 'resume']);
    // Resuming did not start the beat again.
    expect(narrator.spoken).toEqual(['First.']);
  });

  it('passes word positions through while a beat is spoken and clears them between beats', () => {
    const { controller, narrator } = setup();
    controller.play();
    narrator.word(0, 5);
    expect(controller.getState().word).toEqual({ start: 0, length: 5 });
    narrator.finish();
    expect(controller.getState().word).toBeNull();
  });

  it('replays a segment from its first beat', () => {
    const { controller, narrator } = setup();
    controller.play();
    narrator.finish();
    controller.replay();
    expect(narrator.log).toContain('cancel');
    expect(controller.getState()).toMatchObject({
      status: 'playing',
      beatIndex: 0,
      beatsStarted: 1,
    });
    expect(narrator.spoken).toEqual(['First.', 'Second.', 'First.']);
  });

  it('ignores a narrator callback that arrives after the lesson has moved on', () => {
    const { controller, narrator } = setup();
    const handlers: NarrationHandlers[] = [];
    const original = narrator.speak.bind(narrator);
    narrator.speak = (text, callbacks) => {
      handlers.push(callbacks);
      return original(text, callbacks);
    };
    controller.play();
    controller.next();
    const before = controller.getState();
    handlers[0]?.onEnd();
    handlers[0]?.onWord?.(3, 2);
    expect(controller.getState()).toEqual(before);
  });

  it('hands the reading to another narrator, starting the current beat again', () => {
    const { controller, narrator } = setup();
    const other = new FakeNarrator();
    controller.setNarrator(other); // nothing is being read yet: nothing to restart
    expect(other.spoken).toEqual([]);

    controller.setNarrator(narrator);
    controller.play();
    narrator.finish();
    expect(narrator.spoken).toEqual(['First.', 'Second.']);

    controller.setNarrator(other);
    // The old narrator was stopped; the new one reads the same beat from its start.
    expect(narrator.log).toEqual(['cancel']);
    expect(other.spoken).toEqual(['Second.']);
    expect(controller.getState()).toMatchObject({ status: 'playing', beatIndex: 1 });
    controller.setNarrator(other); // the same one again changes nothing
    expect(other.spoken).toEqual(['Second.']);

    // A late callback from the old narrator does not move the lesson on.
    narrator.finish();
    expect(controller.getState()).toMatchObject({ status: 'playing', beatIndex: 1 });
    other.finish();
    expect(controller.getState().status).toBe('done');
  });

  it('stays paused when the narrator is changed while paused', () => {
    const { controller, narrator } = setup();
    const other = new FakeNarrator();
    controller.play();
    controller.pause();
    controller.setNarrator(other);
    expect(controller.getState()).toMatchObject({ status: 'paused', beatIndex: 0 });
    expect(other.spoken).toEqual(['First.']);
    expect(other.log).toEqual(['pause']);
    controller.play();
    expect(other.log).toEqual(['pause', 'resume']);
    expect(narrator.spoken).toEqual(['First.']);
  });

  it('copes with a narrator that finishes at once', () => {
    const narrator: Narrator = {
      kind: 'silent',
      speak: (_text, handlers) => {
        handlers.onEnd();
        return { pause: () => undefined, resume: () => undefined, cancel: () => undefined };
      },
    };
    const controller = new LessonController(LESSON, {
      narrator,
      advanceScene: () => undefined,
      saveProgress: () => undefined,
    });
    controller.play();
    expect(controller.getState()).toMatchObject({ status: 'done', beatIndex: 1, beatsStarted: 2 });
  });
});

describe('moving through the lesson', () => {
  it('continues into the next segment, which then starts by itself, and saves the position', () => {
    const { controller, narrator, host } = setup();
    controller.play();
    narrator.finish();
    narrator.finish();
    expect(controller.next()).toBe(true);
    expect(controller.getState()).toMatchObject({
      segmentIndex: 1,
      status: 'playing',
      beatIndex: 0,
    });
    expect(narrator.spoken.at(-1)).toBe('Your turn.');
    expect(host.saved).toEqual([[1, false]]);
  });

  it('does not start talking after a jump if the learner never pressed play', () => {
    const { controller, narrator } = setup();
    controller.next();
    expect(controller.getState()).toMatchObject({ segmentIndex: 1, status: 'ready' });
    expect(narrator.spoken).toEqual([]);
  });

  it('lets the learner skip ahead while narration is still running', () => {
    const { controller, narrator } = setup();
    controller.play();
    expect(controller.next()).toBe(true);
    expect(narrator.log).toEqual(['cancel']);
    expect(controller.getState().segmentIndex).toBe(1);
  });

  it('cues the scene when a beat asks for it, then waits on the learner', () => {
    const { controller, narrator, host } = setup(1);
    controller.play();
    expect(host.advanced).toBe(0);
    narrator.finish();
    expect(host.advanced).toBe(1);
    narrator.finish();
    // An interaction is never forced: the learner may explore or simply move on.
    expect(controller.getState().status).toBe('waiting');
    expect(canContinue(controller.getState(), controller.segment)).toBe(true);
    controller.markExplored();
    expect(controller.getState().explored).toBe(true);
    expect(controller.next()).toBe(true);
  });

  it('waits at a question until it is answered or skipped', () => {
    const { controller, host } = setup(2);
    // No lead-in narration: the question is simply there.
    expect(controller.getState().status).toBe('waiting');
    expect(canContinue(controller.getState(), controller.segment)).toBe(false);
    expect(controller.next()).toBe(false);
    expect(controller.getState().segmentIndex).toBe(2);
    expect(host.saved).toEqual([]);

    controller.markAnswered();
    expect(controller.getState()).toMatchObject({ answered: true, status: 'done' });
    expect(controller.next()).toBe(true);
    expect(controller.getState().segmentIndex).toBe(3);
  });

  it('treats a segment with nothing to narrate as ready to leave', () => {
    const { controller } = setup(3);
    expect(controller.getState().status).toBe('done');
  });

  it('goes back without replaying, and only jumps to segments already reached', () => {
    const { controller, narrator } = setup();
    controller.play();
    controller.next();
    controller.next(); // now at the question, which blocks
    expect(controller.getState()).toMatchObject({ segmentIndex: 2, furthest: 2 });

    controller.previous();
    expect(controller.getState()).toMatchObject({ segmentIndex: 1, status: 'ready', furthest: 2 });
    const spoken = narrator.spoken.length;
    controller.goTo(4); // not reached yet
    expect(controller.getState().segmentIndex).toBe(1);
    controller.goTo(0);
    expect(controller.getState()).toMatchObject({ segmentIndex: 0, status: 'ready' });
    controller.goTo(2);
    expect(controller.getState().segmentIndex).toBe(2);
    expect(narrator.spoken).toHaveLength(spoken);
    controller.previous();
    controller.previous();
    controller.previous(); // already at the start
    expect(controller.getState().segmentIndex).toBe(0);
  });

  it('finishes on the last segment and records the lesson as completed', () => {
    const { controller, narrator, host } = setup(4);
    controller.play();
    narrator.finish();
    expect(controller.getState().finished).toBe(false);
    expect(controller.next()).toBe(true);
    expect(controller.getState()).toMatchObject({
      segmentIndex: 4,
      finished: true,
      status: 'done',
    });
    expect(host.saved).toEqual([[4, true]]);
  });

  it('only offers a question again on a later visit, instead of blocking on it', () => {
    const { controller } = setup(2);
    controller.markAnswered();
    controller.next();
    controller.previous();
    // Back at the question: it starts fresh, but the way forward is open.
    expect(controller.getState()).toMatchObject({ segmentIndex: 2, answered: false, furthest: 3 });
    expect(canContinue(controller.getState(), controller.segment)).toBe(true);
    expect(controller.next()).toBe(true);
    expect(controller.getState().segmentIndex).toBe(3);
  });

  it('starts again from the first segment after finishing, without talking unasked', () => {
    const { controller, narrator, host } = setup(4);
    controller.play();
    narrator.finish();
    controller.next();
    expect(controller.getState().finished).toBe(true);
    const spoken = narrator.spoken.length;

    controller.restart();
    expect(controller.getState()).toMatchObject({
      segmentIndex: 0,
      status: 'ready',
      finished: false,
      furthest: 4,
    });
    expect(narrator.spoken).toHaveLength(spoken);
    // Moving on does not start the narration either, until the learner presses play again.
    controller.next();
    expect(controller.getState()).toMatchObject({ segmentIndex: 1, status: 'ready' });
    // Completion was recorded once and is not undone by reviewing.
    expect(host.saved).toEqual([
      [4, true],
      [1, false],
    ]);
  });

  it('stops narration when it is disposed', () => {
    const { controller, narrator, changes } = setup();
    controller.play();
    changes.mockClear();
    controller.dispose();
    expect(narrator.log).toEqual(['cancel']);
    narrator.finish();
    expect(changes).not.toHaveBeenCalled();
  });
});

describe('TimedNarrator', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it('gives each caption time in proportion to its length', () => {
    expect(readingTimeMs('One two three four.', 160)).toBe(1500);
    expect(readingTimeMs('word '.repeat(80), 160)).toBe(30_000);
    expect(readingTimeMs('Hi.', 160)).toBe(1400);
  });

  it('ends after the reading time, and holds the clock exactly while paused', () => {
    const narrator = new TimedNarrator('standard');
    const onEnd = vi.fn();
    const utterance = narrator.speak('word '.repeat(16), { onEnd }); // six seconds
    vi.advanceTimersByTime(4000);
    utterance.pause();
    vi.advanceTimersByTime(60_000);
    expect(onEnd).not.toHaveBeenCalled();
    utterance.resume();
    vi.advanceTimersByTime(1999);
    expect(onEnd).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(onEnd).toHaveBeenCalledOnce();
    utterance.resume(); // finished: nothing restarts
    vi.advanceTimersByTime(60_000);
    expect(onEnd).toHaveBeenCalledOnce();
  });

  it('never ends once cancelled', () => {
    const narrator = new TimedNarrator('brisk');
    const onEnd = vi.fn();
    const utterance = narrator.speak('A short caption.', { onEnd });
    utterance.cancel();
    utterance.resume();
    vi.advanceTimersByTime(60_000);
    expect(onEnd).not.toHaveBeenCalled();
  });
});

describe('going straight to the next question', () => {
  it('leaves out what lies between, keeps it reachable, and saves the new place', () => {
    const { controller, narrator, host } = setup();
    controller.play();
    expect(controller.nextQuestionIndex()).toBe(2);

    expect(controller.skipToNextQuestion()).toBe(true);
    expect(controller.getState()).toMatchObject({ segmentIndex: 2, furthest: 2 });
    expect(controller.segment.type).toBe('checkpoint');
    // The explanation that was being read stops, and nothing else starts by itself.
    expect(narrator.log).toContain('cancel');
    expect(narrator.speaking).toBe(false);
    expect(host.saved).toEqual([[2, false]]);

    // What was skipped can still be opened.
    controller.goTo(1);
    expect(controller.getState().segmentIndex).toBe(1);
  });

  it('does not jump past a question that is still waiting for an answer', () => {
    const { controller } = setup(2);
    expect(controller.nextQuestionIndex()).toBeNull();
    expect(controller.skipToNextQuestion()).toBe(false);
    expect(controller.getState().segmentIndex).toBe(2);
  });

  it('says so when there is no question ahead', () => {
    const { controller, host } = setup(3);
    expect(controller.nextQuestionIndex()).toBeNull();
    expect(controller.skipToNextQuestion()).toBe(false);
    expect(host.saved).toEqual([]);
  });
});

describe('a lesson still being written (ADR-048)', () => {
  function growing() {
    const narrator = new FakeNarrator();
    const host: PlaybackHost & { saved: [number, boolean][] } = {
      narrator,
      saved: [],
      advanceScene: () => undefined,
      saveProgress: (at, completed) => {
        host.saved.push([at, completed]);
      },
    };
    const first = { ...LESSON, segments: LESSON.segments.slice(0, 2) };
    const controller = new LessonController(first, host, { position: 0 }, { more: true });
    return { controller, narrator, host };
  }

  it('opens with the parts written so far and says more are coming', () => {
    const { controller } = growing();
    expect(controller.getState()).toMatchObject({ parts: 2, more: true, held: false });
    expect(controller.segments.map((segment) => segment.id)).toEqual(
      LESSON.segments.slice(0, 2).map((segment) => segment.id),
    );
  });

  it('adds the parts written since, after the last, and changes none it has', () => {
    const { controller } = growing();
    const opened = controller.segments[0];
    const changed = { ...LESSON.segments[0], title: 'Written over' } as LessonSegment;
    controller.extend([changed, ...LESSON.segments.slice(1, 4)], true);
    expect(controller.segments).toHaveLength(4);
    expect(controller.segments[0]).toBe(opened);
    expect(controller.getState()).toMatchObject({ parts: 4, more: true });
  });

  it('waits at the end of what is written, and goes on by itself when the next part comes', () => {
    const { controller, narrator, host } = growing();
    controller.play();
    narrator.finish();
    controller.next();
    narrator.finish();
    expect(controller.getState().segmentIndex).toBe(1);
    // Past the last part written so far: held, not finished.
    expect(controller.next()).toBe(true);
    expect(controller.getState()).toMatchObject({ held: true, finished: false, segmentIndex: 1 });

    controller.extend(LESSON.segments.slice(0, 3), true);
    expect(controller.getState()).toMatchObject({ segmentIndex: 2, held: false, parts: 3 });
    // The learner had pressed play: the new part goes on as the others did.
    expect(host.saved.at(-1)).toEqual([2, false]);
  });

  it('finishes where it is when no more parts will come', () => {
    const { controller, narrator, host } = growing();
    controller.goTo(0);
    controller.play();
    narrator.finish();
    controller.next();
    narrator.finish();
    controller.next();
    expect(controller.getState().held).toBe(true);

    controller.extend(LESSON.segments.slice(0, 2), false);
    expect(controller.getState()).toMatchObject({ finished: true, held: false, more: false });
    expect(host.saved.at(-1)).toEqual([1, true]);
  });

  it('is never finished while more parts are coming, and finished once they have all come', () => {
    const { controller, narrator } = growing();
    controller.extend(LESSON.segments, false);
    controller.goTo(0);
    for (const _ of LESSON.segments) {
      controller.play();
      narrator.finish();
      controller.markAnswered();
      controller.next();
    }
    expect(controller.getState().finished).toBe(true);
  });
});

describe('a part whose picture the learner changed (ADR-067)', () => {
  it('takes the part with its new picture, and starts it again where the learner is', () => {
    const { controller, narrator, changes } = setup(1, 2);
    controller.play();
    expect(controller.getState().status).toBe('playing');
    const part = LESSON.segments[1]!;
    const redrawn: LessonSegment = { ...part, title: part.title };

    controller.replace(redrawn);

    expect(controller.segments[1]).toBe(redrawn);
    // Begun again from its start, waiting for the learner.
    expect(controller.getState()).toMatchObject({
      segmentIndex: 1,
      status: 'ready',
      beatIndex: -1,
    });
    expect(narrator.log).toContain('cancel');
    expect(changes).toHaveBeenCalled();
  });

  it('changes a part the learner is not in without moving them, and ignores a part it lacks', () => {
    const { controller } = setup(0, 2);
    const part = LESSON.segments[2]!;
    const redrawn: LessonSegment = { ...part };
    controller.replace(redrawn);
    expect(controller.segments[2]).toBe(redrawn);
    expect(controller.getState().segmentIndex).toBe(0);
    const before = controller.segments;
    controller.replace({ ...part, id: 'seg_unknown' });
    expect(controller.segments).toEqual(before);
  });
});
