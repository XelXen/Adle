import { useEffect, useState } from 'react';

import type { LessonForPlayer } from '@adle/contracts';

import { callCore } from './core-client';

type Scene = LessonForPlayer['scenes'][number];
type Segment = LessonForPlayer['lesson']['segments'][number];

/** How often to look while a picture is still being drawn, or a part still being written. */
export const LOOK_EVERY_MS = 2000;

export interface LessonUpdates {
  /** The pictures the lesson has by now. */
  scenes: readonly Scene[];
  /** The pictures that parts refer to and that are still being drawn, by id. */
  pending: ReadonlySet<string>;
  /**
   * The lesson's parts as it has them now. A lesson opened while it was still being
   * written has more of them as they are written (ADR-048); a part never changes.
   */
  segments: readonly Segment[];
  /** More parts are being written. */
  writing: boolean;
}

/**
 * What arrives for a lesson after it was opened: its pictures, when it was opened before
 * all of them were drawn (ADR-031), and its later parts, when it was opened at its first
 * part while the rest was being written (ADR-048).
 *
 * Starts from what the lesson had when it was opened, and looks again every few seconds
 * for as long as a picture or a part is still to come. The words of a part already there
 * stay as they were when the learner opened it, so nothing moves under them: new parts
 * only ever come after the last one.
 *
 * This is not a lesson's clock. It decides nothing about what is said or when; it only
 * finds out whether something has arrived.
 */
export function useLessonUpdates(
  lessonId: string,
  opened: Pick<LessonForPlayer, 'scenes' | 'pending_scene_ids' | 'writing'> & {
    lesson: Pick<LessonForPlayer['lesson'], 'segments'>;
  },
): LessonUpdates {
  const [scenes, setScenes] = useState<readonly Scene[]>(opened.scenes);
  const [pending, setPending] = useState<ReadonlySet<string>>(
    () => new Set(opened.pending_scene_ids ?? []),
  );
  const [segments, setSegments] = useState<readonly Segment[]>(opened.lesson.segments);
  const [writing, setWriting] = useState(opened.writing ?? false);
  const waiting = pending.size > 0 || writing;

  useEffect(() => {
    if (!waiting) return;
    let cancelled = false;
    const timer = window.setInterval(() => {
      callCore('lessons.get', { path: { lesson_id: lessonId } }).then(
        (latest) => {
          if (cancelled) return;
          setScenes(latest.scenes);
          setPending(new Set(latest.pending_scene_ids ?? []));
          setSegments((had) =>
            latest.lesson.segments.length > had.length ? latest.lesson.segments : had,
          );
          setWriting(latest.writing ?? false);
        },
        () => {
          // Looked at again on the next turn. The lesson in front of the learner is whole
          // without what has not come yet.
        },
      );
    }, LOOK_EVERY_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [lessonId, waiting]);

  return { scenes, pending, segments, writing };
}
