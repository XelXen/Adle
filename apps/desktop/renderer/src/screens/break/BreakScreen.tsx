import { ArrowLeft, ArrowRight, Coffee, Minus, Plus } from 'lucide-react';
import { useState } from 'react';

import type { Job } from '@adle/contracts';
import { Button, Callout, Card, Page, ProgressBar, Stack } from '@adle/design-system';

import { useBreak } from '../../app/BreakContext';
import { useRouter } from '../../app/router';
import { useWriting } from '../../app/WritingContext';
import {
  clockText,
  LONGEST_BREAK_MINUTES,
  restIdea,
  SHORTEST_BREAK_MINUTES,
  spokenTime,
  USUAL_BREAK_MINUTES,
} from '../../lib/breaks';
import {
  jobFailure,
  jobProgress,
  KIND_LESSON,
  KIND_PROPOSAL,
  readLessonOutcome,
} from '../../lib/generation';
import styles from './Break.module.css';

const LENGTHS = [3, 5, 10, 15] as const;

/** The ring is drawn on a 120-unit square; its radius leaves room for the stroke. */
const RADIUS = 54;
const AROUND = 2 * Math.PI * RADIUS;

/**
 * A break (ADR-026): a few minutes away from the screen, with a clock that needs no
 * watching. Offered while a lesson is being written, which takes minutes whoever writes
 * it, and between lessons.
 *
 * Nothing here is counted or kept. A break is not a streak, has no score, and ending one
 * early is as fine as taking a longer one.
 */
export function BreakScreen() {
  const { back, navigate } = useRouter();
  const rest = useBreak();
  const writing = useWriting();
  // Which idea a break starts with moves on from one break to the next, not by chance.
  const [firstIdea] = useState(() => new Date().getMinutes());

  const leave = (): void => {
    // The break keeps running: the rail shows it, and it can be come back to.
    back();
  };
  const finish = (): void => {
    rest.end();
    back();
  };
  const open = (job: Job): void => {
    writing.acknowledge();
    rest.end();
    const lesson = readLessonOutcome(job);
    if (lesson && job.course_id) {
      navigate({ name: 'lesson', courseId: job.course_id, lessonId: lesson.lessonId });
    } else if (job.course_id) {
      navigate({
        name: 'course',
        courseId: job.course_id,
        tab: job.kind === KIND_PROPOSAL ? 'curriculum' : 'learn',
      });
    } else {
      navigate({ name: 'home' });
    }
  };

  const eyebrow = (
    <Button variant="tertiary" size="small" icon={<ArrowLeft />} onClick={leave}>
      Back
    </Button>
  );

  if (!rest.times) {
    return (
      <Page
        title="Take a break"
        width="reading"
        eyebrow={eyebrow}
        description="A few minutes away from the screen help what you have just learned to settle. Choose how long."
      >
        <Stack gap={5}>
          <div className={styles.lengths} role="group" aria-label="How long a break">
            {LENGTHS.map((minutes) => (
              <Button
                key={minutes}
                variant={minutes === USUAL_BREAK_MINUTES ? 'primary' : 'secondary'}
                size="large"
                icon={minutes === USUAL_BREAK_MINUTES ? <Coffee /> : undefined}
                onClick={() => rest.start(minutes)}
              >
                {minutes} minutes
              </Button>
            ))}
          </div>
          <Waiting writing={writing.jobs} finished={writing.finished} onOpen={open} />
        </Stack>
      </Page>
    );
  }

  const minutesIn = Math.floor(
    ((rest.times.endsAt - rest.times.startedAt) * rest.elapsed) / 60_000,
  );
  return (
    <Page
      title={rest.over ? 'Your break is over' : 'Taking a break'}
      width="reading"
      eyebrow={eyebrow}
      description={
        rest.over
          ? 'Ready when you are. There is no hurry.'
          : 'Nothing here needs watching. Adle will tell you when the time is up, and when what it is writing is ready.'
      }
    >
      <Stack gap={6}>
        <div className={styles.clock}>
          <div
            className={styles.dial}
            role="timer"
            aria-label={rest.over ? 'The break is over' : `Time left: ${spokenTime(rest.left)}`}
          >
            <svg className={styles.ring} viewBox="0 0 120 120" aria-hidden="true">
              <circle className={styles.track} cx="60" cy="60" r={RADIUS} />
              <circle
                className={styles.passed}
                cx="60"
                cy="60"
                r={RADIUS}
                strokeDasharray={AROUND}
                strokeDashoffset={AROUND * (1 - rest.elapsed)}
              />
            </svg>
            <span className={`${styles.time} ad-tabular`} aria-hidden="true">
              {clockText(rest.left)}
            </span>
          </div>
          <p className={styles.idea}>
            {rest.over ? 'Welcome back.' : restIdea(minutesIn, firstIdea)}
          </p>
        </div>

        <div className={styles.actions}>
          {rest.over ? (
            <>
              <Button variant="primary" size="large" icon={<ArrowRight />} onClick={finish}>
                Back to learning
              </Button>
              <Button size="large" onClick={() => rest.start(USUAL_BREAK_MINUTES)}>
                {USUAL_BREAK_MINUTES} more minutes
              </Button>
            </>
          ) : (
            <>
              <Button
                icon={<Minus />}
                disabled={rest.left <= SHORTEST_BREAK_MINUTES * 60}
                onClick={() => rest.adjust(-1)}
              >
                A minute less
              </Button>
              <Button
                icon={<Plus />}
                disabled={rest.left >= (LONGEST_BREAK_MINUTES - 1) * 60}
                onClick={() => rest.adjust(1)}
              >
                A minute more
              </Button>
              <Button variant="tertiary" onClick={finish}>
                End the break
              </Button>
            </>
          )}
        </div>

        <Waiting writing={writing.jobs} finished={writing.finished} onOpen={open} />
      </Stack>
    </Page>
  );
}

/** What Adle is writing meanwhile, and what has arrived. Nothing at all when neither. */
function Waiting({
  writing,
  finished,
  onOpen,
}: {
  writing: readonly Job[];
  finished: Job | null;
  onOpen: (job: Job) => void;
}) {
  if (writing.length === 0 && !finished) return null;
  return (
    <section className={styles.waiting} aria-label="What Adle is writing">
      <h2 className="ad-eyebrow">Meanwhile</h2>
      {finished ? <Arrived job={finished} onOpen={onOpen} /> : null}
      {writing.map((job) => {
        const progress = jobProgress(job, 'Waiting for its turn');
        return (
          <Card key={job.id} padding="compact">
            <Stack gap={2}>
              <p className={styles.what}>
                {job.kind === KIND_LESSON
                  ? 'A lesson is being written'
                  : 'Concepts are being suggested'}
              </p>
              <ProgressBar label={progress.message} showLabel value={progress.value} />
            </Stack>
          </Card>
        );
      })}
    </section>
  );
}

/** Something that finished while the learner was resting: there when they look up. */
function Arrived({ job, onOpen }: { job: Job; onOpen: (job: Job) => void }) {
  const failure = jobFailure(job);
  if (failure) {
    return (
      <Callout
        tone={failure.remedy === 'wait' ? 'warning' : 'danger'}
        title={
          job.kind === KIND_LESSON
            ? 'The lesson could not be written'
            : 'The suggestions could not be made'
        }
        actions={
          job.course_id ? (
            <Button size="small" onClick={() => onOpen(job)}>
              Go to the course
            </Button>
          ) : undefined
        }
      >
        {failure.message}
      </Callout>
    );
  }
  const lesson = readLessonOutcome(job);
  return (
    <Callout
      tone="success"
      title={lesson ? 'Your lesson is ready' : 'Suggested concepts are ready'}
      actions={
        <Button size="small" variant="primary" icon={<ArrowRight />} onClick={() => onOpen(job)}>
          {lesson ? 'Open the lesson' : 'Look at them'}
        </Button>
      }
    >
      {lesson?.title
        ? `"${lesson.title}" is there whenever you want it. Finish your break first if you like.`
        : 'They are there whenever you want them. Finish your break first if you like.'}
    </Callout>
  );
}
