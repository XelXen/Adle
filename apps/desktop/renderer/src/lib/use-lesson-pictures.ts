import { useEffect, useState } from 'react';

import type { LessonForPlayer } from '@adle/contracts';

import { callCore } from './core-client';

type Scene = LessonForPlayer['scenes'][number];

/** How often to look while a picture is still being drawn. */
export const LOOK_EVERY_MS = 3000;

export interface LessonPictures {
  /** The pictures the lesson has by now. */
  scenes: readonly Scene[];
  /** The pictures that parts refer to and that are still being drawn, by id. */
  pending: ReadonlySet<string>;
}

/**
 * The pictures of a lesson that was opened before all of them were drawn (ADR-031).
 *
 * Starts from what the lesson had when it was opened, and looks again every few seconds
 * for as long as a picture is still to come. Only the pictures change: the lesson's own
 * words stay as they were when the learner opened it, so nothing moves under them.
 *
 * This is not a lesson's clock. It decides nothing about what is said or when; it only
 * finds out whether a picture has arrived.
 */
export function useLessonPictures(
  lessonId: string,
  opened: Pick<LessonForPlayer, 'scenes' | 'pending_scene_ids'>,
): LessonPictures {
  const [scenes, setScenes] = useState<readonly Scene[]>(opened.scenes);
  const [pending, setPending] = useState<ReadonlySet<string>>(
    () => new Set(opened.pending_scene_ids ?? []),
  );
  const waiting = pending.size > 0;

  useEffect(() => {
    if (!waiting) return;
    let cancelled = false;
    const timer = window.setInterval(() => {
      callCore('lessons.get', { path: { lesson_id: lessonId } }).then(
        (latest) => {
          if (cancelled) return;
          setScenes(latest.scenes);
          setPending(new Set(latest.pending_scene_ids ?? []));
        },
        () => {
          // Looked at again on the next turn. The lesson in front of the learner is whole
          // without its pictures.
        },
      );
    }, LOOK_EVERY_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [lessonId, waiting]);

  return { scenes, pending };
}
