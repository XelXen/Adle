import { useCallback } from 'react';

import type { Job } from '@adle/contracts';
import { useToast } from '@adle/design-system';

import { useWriting } from '../app/WritingContext';
import { lessonNotice } from './generation';

/**
 * Says that a lesson is ready, on the screen that shows it: once when it can be started,
 * and once more only if its pictures did not all arrive (`lessonNotice`).
 *
 * Give the returned function every lesson job this screen hears about, when it becomes
 * usable and when it ends. Elsewhere in the app the same is said by `WritingProvider`,
 * which also keeps the one record of what the learner has been told: a lesson announced
 * on one tab, or while they were in Settings, is not announced again on another.
 */
export function useLessonNotices(): (job: Job) => void {
  const toast = useToast();
  const { wasTold, markTold } = useWriting();
  return useCallback(
    (job: Job) => {
      const notice = lessonNotice(job, wasTold(job.id));
      if (!notice) return;
      markTold(job.id);
      toast.show(notice);
    },
    [toast, wasTold, markTold],
  );
}
