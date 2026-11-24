import { useEffect, useState } from 'react';

import type { Job, Source } from '@adle/contracts';
import { Button, ProgressBar, useToast } from '@adle/design-system';

import { WhatIsSent } from '../../components/WhatIsSent';
import { callCore, describeError } from '../../lib/core-client';
import { destination, usualWait } from '../../lib/provider';
import { isJobActive, useJob } from '../../lib/use-job';
import { useResource } from '../../lib/use-resource';
import styles from './CourseScreen.module.css';
import { noReader } from './read-pictures-model';

const KIND = 'read_pictures';

/**
 * The pages of a file that are pictures (a scan, a photograph, handwriting), read by the
 * AI at the learner's word (ADR-060). What is sent, and where, is one press away; where
 * it goes is what the core plans, and nobody is asked who cannot read a picture.
 */
export function ReadPictures({ source, onRead }: { source: Source; onRead: () => void }) {
  const toast = useToast();
  const provider = useResource('provider-status', () => callCore('provider.status'));
  const status = provider.resource.status === 'ready' ? provider.resource.data : undefined;
  const [started, setStarted] = useState<Job | null>(null);
  const [starting, setStarting] = useState(false);
  const job = useJob(started, (finished) => {
    onRead();
    if (finished.status === 'failed') {
      toast.show({
        tone: 'danger',
        title: 'Couldn’t read every page',
        description: finished.error_message ?? 'Try again in a moment.',
      });
    }
  });

  // A reading begun before this was shown (the tab opened again) is followed as well.
  useEffect(() => {
    let cancelled = false;
    callCore('jobs.list_active', { path: { course_id: source.course_id } }).then(
      (list) => {
        if (cancelled) return;
        const running = list.jobs.find(
          (each) => each.kind === KIND && each.subject_id === source.id,
        );
        if (running) setStarted((current) => current ?? running);
      },
      () => {
        // Nothing to follow; reading can still be asked for.
      },
    );
    return () => {
      cancelled = true;
    };
  }, [source.course_id, source.id]);

  const count = source.picture_pages.length;
  if (job && isJobActive(job)) {
    return (
      <div className={styles.pictureReading}>
        <ProgressBar
          label={job.progress_message || 'Reading the pictures…'}
          showLabel
          value={job.progress_total > 0 ? job.progress_done / job.progress_total : undefined}
          valueText={
            job.progress_total > 0
              ? `${Math.min(job.progress_done + 1, job.progress_total)} of ${job.progress_total}`
              : undefined
          }
        />
        <Button
          size="small"
          onClick={() => void callCore('jobs.cancel', { path: { job_id: job.id } })}
        >
          Stop
        </Button>
      </div>
    );
  }
  if (count === 0) return null;

  const route = status?.routes.read;
  // Who would read them, with a key to do it: nobody, and the button could only refuse.
  const keyed = status?.providers.some(
    (each) => route?.provider_ids.includes(each.provider_id) && each.key_configured,
  );
  if (status && route && !keyed) {
    return <p className={styles.sourceFacts}>{noReader(status.providers, count)}</p>;
  }

  const start = async (): Promise<void> => {
    setStarting(true);
    try {
      setStarted(await callCore('sources.read_pictures', { path: { source_id: source.id } }));
    } catch (error) {
      toast.show({
        tone: 'danger',
        title: 'Couldn’t read the pictures',
        description: describeError(error),
      });
    } finally {
      setStarting(false);
    }
  };

  return (
    <div className={styles.pictureReading}>
      <Button size="small" loading={starting} onClick={() => void start()}>
        {count === 1 ? 'Read it' : 'Read them'}
      </Button>
      <WhatIsSent
        what={count === 1 ? 'a picture of that page' : `pictures of those ${count} pages`}
        to={destination(status, 'read')}
        wait={usualWait(status, 'read')}
        after="What it reads becomes the text of those pages here."
      />
    </div>
  );
}
