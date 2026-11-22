import type { SceneTrial, SceneTrialReport } from '@adle/contracts';
import type { ControlDescriptor, ControlValue } from '@adle/event-protocol';

import type { LoadSceneOptions, PlayerEvents } from '../../../player/host/WanimPlayerAdapter';

/**
 * Trying a picture before a learner is shown it (ADR-038).
 *
 * A scene a model wrote is run in a player frame of its own that nobody sees, as fast as it
 * can be drawn: every page of it, every control moved to its ends and back. Whatever goes
 * wrong is what the player reports when it goes wrong in front of a learner, said as it was
 * said, so that the model asked to write the file again can be told. A picture that is not
 * seen to fail passes: the player still falls back to words if it fails later.
 *
 * A slide (ADR-049) is paced by cues: it is loaded so, and told to go on as each of its
 * steps ends, until its last; a live page at its end is operated like any other.
 */

/** What a trial needs of the player: the adapter's own methods. */
export interface TrialPlayer {
  on<K extends keyof PlayerEvents>(
    event: K,
    listener: (payload: PlayerEvents[K]) => void,
  ): () => void;
  load(options: LoadSceneOptions): void;
  next(): void;
  setControl(name: string, value: ControlValue): void;
}

export interface TrialTiming {
  /** The longest a whole trial may take. A scene runs through at speed in a second or two. */
  budgetMs: number;
  /** How long an interactive page has to say what controls it has. */
  controlsMs: number;
  /** After the controls have been moved, how long to watch for a failure. */
  settleMs: number;
}

export const TRIAL_TIMING: TrialTiming = { budgetMs: 30_000, controlsMs: 2_000, settleMs: 500 };

/** The values a control is moved through: to each end, and back to where it was. */
export function valuesToTry(control: ControlDescriptor): ControlValue[] {
  if (control.kind === 'switch' || typeof control.value === 'boolean') {
    const value = control.value === true;
    return [!value, value];
  }
  const ends = [control.min, control.max].filter(
    (end): end is number => typeof end === 'number' && Number.isFinite(end),
  );
  return [...ends, control.value];
}

const later = (ms: number): Promise<void> =>
  new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });

/** Run one trial to its verdict. The caller disposes of the player afterwards. */
export function runTrial(
  player: TrialPlayer,
  trial: Pick<SceneTrial, 'source' | 'scene_class'> & Partial<Pick<SceneTrial, 'steps'>>,
  timing: TrialTiming = TRIAL_TIMING,
  wait: (ms: number) => Promise<void> = later,
): Promise<SceneTrialReport> {
  const steps = trial.steps ?? 0;
  return new Promise((resolve) => {
    let settled = false;
    let controls: ControlDescriptor[] = [];
    /** The interactive page being operated, if one is. */
    let operating: number | null = null;
    const operated = new Set<number>();
    const unsubscribe: (() => void)[] = [];

    const finish = (report: SceneTrialReport): void => {
      if (settled) return;
      settled = true;
      for (const stop of unsubscribe) stop();
      resolve(report);
    };

    const controlsArrived = async (): Promise<void> => {
      const until = Date.now() + timing.controlsMs;
      while (controls.length === 0 && Date.now() < until && !settled) await wait(50);
    };

    const operate = async (page: number, canNext: boolean): Promise<void> => {
      operating = page;
      operated.add(page);
      await controlsArrived();
      for (const control of controls) {
        for (const value of valuesToTry(control)) {
          if (settled) return;
          player.setControl(control.name, value);
          await wait(30);
        }
      }
      await wait(timing.settleMs);
      if (settled) return;
      operating = null;
      // Another page follows: go on to it. On the last, the picture is the learner's to
      // operate from here on, and nothing went wrong. A slide's live page is its last.
      if (canNext && steps === 0) player.next();
      else finish({ passed: true });
    };

    unsubscribe.push(
      player.on('failure', (failure) => {
        finish({
          passed: false,
          // What broke while a control was being moved broke because of it.
          stage: operating !== null && failure.stage === 'runtime' ? 'controls' : failure.stage,
          message: failure.message,
        });
      }),
      player.on('controls', (next) => {
        controls = next;
      }),
      player.on('state', (state) => {
        if (!state.interactive || operating !== null || operated.has(state.phaseIndex)) return;
        void operate(state.phaseIndex, state.canNext);
      }),
      player.on('finished', () => {
        if (operating === null) finish({ passed: true });
      }),
      player.on('scene-event', (event) => {
        if (steps === 0 || event.name !== 'step' || typeof event.value !== 'number') return;
        // Each step ends held: go on to the next. A slide is held at its last step, and
        // says nothing more; one with a live page there is operated when it comes.
        if (event.value < steps - 1) player.next();
        else if (operating === null && !operated.size) {
          void wait(timing.settleMs).then(() => {
            if (operating === null && operated.size === 0) finish({ passed: true });
          });
        }
      }),
    );

    // Not seen to fail in all that time: it passes, and the player keeps its fallback.
    void wait(timing.budgetMs).then(() => finish({ passed: true }));

    player.load({
      source: trial.source,
      sceneName: trial.scene_class,
      // As a lesson shows it (ADR-035).
      theme: 'dark',
      autoplay: true,
      rehearsal: true,
      pacing: steps > 0 ? 'cued' : 'normal',
    });
  });
}
