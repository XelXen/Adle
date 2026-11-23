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
  isDrawingPictures,
  isWritingTheRest,
  jobFailure,
  jobProgress,
  KIND_LESSON,
  KIND_PROPOSAL,
  readLessonOutcome,
} from '../../lib/generation';
import { barValue, readWritingProgress, writingHeadline } from '../../lib/writing-progress';
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

  /** Back where the break was taken from, or where it was said to lead. */
  const away = (): void => {
    if (rest.returnTo) navigate(rest.returnTo);
    else back();
  };
  const leave = (): void => {
    // The break keeps running: the rail shows it, and it can be come back to.
    away();
  };
  const finish = (): void => {
    rest.end();
    away();
  };
  // Only what arrived during this break: something that finished before it began has been
  // said already, and has nothing to do with this rest.
  const arrived =
    writing.finished !== null &&
    (rest.times === null || (writing.finishedAt ?? 0) >= rest.times.startedAt)
      ? writing.finished
      : null;
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
        description="A few minutes away helps new ideas settle. Choose how long."
      >
        <Stack gap={5}>
          <div className={styles.lengths} role="group" aria-label="Break length">
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
          <Waiting writing={writing.jobs} finished={arrived} onOpen={open} />
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
        rest.over ? 'Ready when you are.' : 'You can step away. You’ll be notified when time is up.'
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
                // Only while a whole minute can be taken off: the button says "a minute".
                disabled={rest.left < (SHORTEST_BREAK_MINUTES + 1) * 60}
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
                End break
              </Button>
            </>
          )}
        </div>

        <Waiting writing={writing.jobs} finished={arrived} onOpen={open} />
      </Stack>
      {/* The page's title changes when the time is up; this is what says so to someone who
          cannot see it change. */}
      <p className="ad-visually-hidden" role="status">
        {rest.over ? 'Your break is over.' : ''}
      </p>
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
  // A lesson that can be started while the rest of it is written (ADR-048) or its pictures
  // drawn (ADR-031) is said once, as something that has arrived, and not a second time as
  // something under way.
  const still = finished ? writing.find((job) => job.id === finished.id) : undefined;
  const coming = still ? (isWritingTheRest(still) ? 'parts' : 'pictures') : null;
  const others = writing.filter((job) => job.id !== finished?.id);
  return (
    <section className={styles.waiting} aria-label="In progress">
      <h2 className="ad-eyebrow">Meanwhile</h2>
      {finished ? <Arrived job={finished} coming={coming} onOpen={onOpen} /> : null}
      {others.map((job) => {
        const progress = jobProgress(job, 'Queued');
        const drawing = isDrawingPictures(job);
        const writing = drawing ? null : readWritingProgress(job);
        const kind = job.kind === KIND_LESSON ? 'lesson' : 'suggestions';
        const headline = drawing
          ? progress.message
          : writingHeadline(writing, kind, progress.message);
        const value = drawing ? progress.value : barValue(job, writing, progress.value);
        return (
          <Card key={job.id} padding="compact">
            <Stack gap={2}>
              <p className={styles.what}>
                {job.kind === KIND_LESSON
                  ? isDrawingPictures(job)
                    ? 'Drawing your lesson’s pictures'
                    : writing?.stage === 'voicing'
                      ? 'Recording your lesson’s voice'
                      : 'Writing your lesson'
                  : 'Suggesting concepts'}
              </p>
              <ProgressBar label={headline} showLabel value={value} />
            </Stack>
          </Card>
        );
      })}
    </section>
  );
}

/** Something that finished while the learner was resting: there when they look up. */
function Arrived({
  job,
  coming,
  onOpen,
}: {
  job: Job;
  /** It is a lesson, and the rest of its parts or its pictures are still to come. */
  coming: 'parts' | 'pictures' | null;
  onOpen: (job: Job) => void;
}) {
  const failure = jobFailure(job);
  if (failure) {
    return (
      <Callout
        tone={failure.remedy === 'wait' ? 'warning' : 'danger'}
        title={job.kind === KIND_LESSON ? 'Couldn’t write the lesson' : 'Couldn’t suggest concepts'}
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
          {lesson ? 'Open lesson' : 'Review them'}
        </Button>
      }
    >
      {lesson?.title
        ? `“${lesson.title}” is ready${
            coming === 'parts'
              ? ', and the rest of it is on its way'
              : coming === 'pictures'
                ? ', and its pictures are on their way'
                : ''
          }. Finish your break first if you like.`
        : 'Finish your break first if you like.'}
    </Callout>
  );
}
