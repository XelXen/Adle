import { useEffect, useRef } from 'react';

import { WanimPlayerAdapter } from '../../../player/host/WanimPlayerAdapter';
import { callCore } from '../lib/core-client';
import { KIND_LESSON } from '../lib/generation';
import { runTrial } from '../lib/scene-trial';
import styles from './SceneTrials.module.css';
import { useWriting } from './WritingContext';

/** How often the core is asked for pictures to try while a lesson is being written. */
const LOOK_EVERY_MS = 1_000;

/**
 * Where pictures are tried before a learner is shown them (ADR-038).
 *
 * While a lesson is being written the core is asked, every second, whether a picture is
 * waiting to be tried; asking is also how the core knows the app is there to try one. Each
 * is run in a player frame of its own that nobody sees, one at a time, and what happened is
 * said back. The frames are ordinary player frames: sandboxed, on an origin of their own,
 * removed when the trial is over.
 */
export function SceneTrials() {
  const { jobs } = useWriting();
  const writingALesson = jobs.some((job) => job.kind === KIND_LESSON);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!writingALesson) return;
    let stopped = false;
    let busy = false;
    const look = async (): Promise<void> => {
      const container = box.current;
      if (busy || stopped || !container) return;
      busy = true;
      try {
        const { trials } = await callCore('scenes.trials');
        for (const trial of trials) {
          if (stopped) break;
          const player = new WanimPlayerAdapter(container, {
            title: 'A picture being tried',
            className: styles.frame,
            hidden: true,
          });
          try {
            const report = await runTrial(player, trial);
            await callCore('scenes.report_trial', { path: { trial_id: trial.id }, body: report });
          } finally {
            player.dispose();
          }
        }
      } catch {
        // Asked again at the next look; a trial that is never answered is kept untried.
      } finally {
        busy = false;
      }
    };
    void look();
    const timer = window.setInterval(() => void look(), LOOK_EVERY_MS);
    return () => {
      stopped = true;
      window.clearInterval(timer);
    };
  }, [writingALesson]);

  return <div ref={box} className={styles.trials} aria-hidden="true" />;
}
