import { CalendarClock, PencilLine, Sparkles } from 'lucide-react';
import { type ReactNode, useId, useState } from 'react';

import type { ConceptProgress, Course, Hypothesis, Job, NextStep } from '@adle/contracts';
import { Badge, Button, ErrorState, LoadingState, useToast } from '@adle/design-system';

import { useRouter } from '../../app/router';
import { GenerationStatus } from '../../components/GenerationStatus';
import { NextSteps } from '../../components/NextSteps';
import { SessionSummary } from '../../components/SessionSummary';
import { callCore, describeError } from '../../lib/core-client';
import { pluralise } from '../../lib/format';
import { WhatIsSent } from '../../components/WhatIsSent';
import { destination, usualWait } from '../../lib/provider';
import { isDrawingPictures, KIND_LESSON, lessonDisclosure } from '../../lib/generation';
import {
  formatWait,
  hypothesisLabel,
  reviewNote,
  reviewSentence,
  sessionHeading,
  summarySentence,
} from '../../lib/learning';
import { useGeneration } from '../../lib/use-generation';
import { isJobActive } from '../../lib/use-job';
import { useLessonNotices } from '../../lib/use-lesson-notices';
import { useResource } from '../../lib/use-resource';
import { KNOWLEDGE_TONE } from './ConceptDetail';
import styles from './Learn.module.css';

/**
 * Where to go next in a course, and where the learner stands in it.
 *
 * Everything shown here was decided by the core: the suggestion, its reason,
 * the alternatives, and what each concept's answers add up to. This panel
 * only lays it out and carries the learner's choice back.
 */
export function LearnPanel({ course }: { course: Course }) {
  const toast = useToast();
  const { navigate } = useRouter();
  const nextId = useId();
  const progressId = useId();
  const sessionId = useId();
  const courseId = course.id;
  const overview = useResource(`learning:${courseId}`, () =>
    callCore('learning.overview', { path: { course_id: courseId } }),
  );
  const provider = useResource('provider-status', () => callCore('provider.status'));
  const [dismissing, setDismissing] = useState<string | null>(null);

  const sayLesson = useLessonNotices();
  // A lesson changes what is worth doing next: when it can be started, which is before its
  // pictures are drawn, and again when the work has ended.
  const lessonChanged = (job: Job): void => {
    if (job.kind !== KIND_LESSON) return;
    overview.reload();
    sayLesson(job);
  };
  const generation = useGeneration(courseId, lessonChanged, lessonChanged);

  if (overview.resource.status === 'loading') {
    return <LoadingState title="Planning your next step…" />;
  }
  if (overview.resource.status === 'error') {
    return (
      <ErrorState
        title="Couldn’t load your progress"
        description={describeError(overview.resource.error)}
        actions={<Button onClick={overview.reload}>Try again</Button>}
      />
    );
  }

  const data = overview.resource.data;
  const providerStatus = provider.resource.status === 'ready' ? provider.resource.data : undefined;
  const lessonWait = usualWait(providerStatus, 'lesson');
  const reviews = reviewSentence(data.summary);

  const createLesson = (conceptId: string): Promise<void> =>
    generation.begin(conceptId, () =>
      callCore('generation.generate_lesson', { path: { concept_id: conceptId }, body: null }),
    );

  /** The control that asks for a lesson, with what it sends; or where that work stands. */
  const lessonControl = (_step: NextStep, conceptId: string, primary: boolean): ReactNode => {
    const job = generation.jobs.find(KIND_LESSON, conceptId);
    if (isDrawingPictures(job)) {
      // Said once, above. Another lesson on this concept can be asked for when this one
      // has its pictures: one piece of long work at a time.
      return (
        <p className={styles.aiNote}>
          A new lesson on this concept is getting its pictures. You can create another when they’re
          done.
        </p>
      );
    }
    const starting = generation.starting.has(conceptId);
    const refusal = generation.refusals.get(conceptId) ?? null;
    const settled =
      !starting &&
      !isJobActive(job) &&
      refusal === null &&
      job?.status !== 'failed' &&
      job?.status !== 'cancelled';
    return (
      <>
        <GenerationStatus
          job={job?.status === 'succeeded' ? null : job}
          starting={starting}
          refusal={refusal}
          subject="the lesson"
          waitingText="Queued"
          usualSeconds={providerStatus?.routes.lesson.wait_seconds}
          onCancel={() => generation.cancel(job)}
          onRetry={() => void createLesson(conceptId)}
          onDismiss={() => generation.putAway(conceptId, job)}
        />
        {settled ? (
          <div className={styles.sending}>
            <Button
              variant={primary ? 'primary' : 'secondary'}
              size={primary ? 'medium' : 'small'}
              icon={<Sparkles />}
              onClick={() => void createLesson(conceptId)}
            >
              Create lesson
            </Button>
            <WhatIsSent
              what={lessonDisclosure(course.source_count > 0 ? 'some' : 'none')}
              to={destination(providerStatus, 'lesson')}
              wait={lessonWait}
              after="Its pictures follow while you start."
            />
          </div>
        ) : null}
      </>
    );
  };

  const dismiss = async (concept: ConceptProgress, hypothesis: Hypothesis): Promise<void> => {
    setDismissing(`${concept.concept_id}:${hypothesis.kind}`);
    try {
      overview.setData(
        await callCore('learning.dismiss_hypothesis', {
          path: { concept_id: concept.concept_id, kind: hypothesis.kind },
        }),
      );
      toast.show({
        tone: 'success',
        title: 'Set aside',
        description: 'It only comes back if later answers suggest it again.',
      });
      // The button that was pressed is gone with the update. Without this the keyboard
      // would be left nowhere; the line it belonged to now says what became of it.
      const line = hypothesisDomId(concept.concept_id, hypothesis.kind);
      requestAnimationFrame(() => document.getElementById(line)?.focus());
    } catch (error) {
      toast.show({
        tone: 'danger',
        title: 'Couldn’t set that aside',
        description: describeError(error),
      });
      overview.reload();
    } finally {
      setDismissing(null);
    }
  };

  return (
    <div className={styles.panel}>
      {/* A lesson that can be started while its pictures are still being drawn. */}
      {generation.jobs.jobs.filter(isDrawingPictures).map((job) => (
        <GenerationStatus
          key={job.id}
          job={job}
          starting={false}
          refusal={null}
          subject="the lesson"
          waitingText="Queued"
          lessonReady
          onCancel={() => generation.cancel(job)}
          onRetry={() => undefined}
          onDismiss={() => undefined}
        />
      ))}
      <section className={styles.section} aria-labelledby={nextId}>
        <h2 id={nextId} className={styles.heading}>
          Up next
        </h2>
        {/* The heading above already says "Up next". */}
        <NextSteps
          plan={data.plan}
          courseId={courseId}
          renderGeneration={lessonControl}
          eyebrow={null}
        />
      </section>

      {data.session ? (
        <section className={styles.section} aria-labelledby={sessionId}>
          <h2 id={sessionId} className={styles.heading}>
            {sessionHeading(data.session)}
          </h2>
          <SessionSummary session={data.session} />
        </section>
      ) : null}

      {data.concepts.length > 0 ? (
        <section className={styles.section} aria-labelledby={progressId}>
          <h2 id={progressId} className={styles.heading}>
            Your progress
          </h2>
          <p className={styles.summary}>
            {summarySentence(data.summary)}
            {reviews ? ` ${reviews}` : ''}
          </p>
          <ol className={styles.concepts} aria-label="Concepts, in learning order">
            {data.concepts.map((concept) => (
              <ConceptRow
                key={concept.concept_id}
                concept={concept}
                dismissing={dismissing}
                onDismiss={(hypothesis) => void dismiss(concept, hypothesis)}
                onPractise={() =>
                  navigate({ name: 'practice', courseId, conceptId: concept.concept_id })
                }
              />
            ))}
          </ol>
          <p className={styles.footnote}>
            Based on your answers so far. It changes as you learn, and it’s never a grade.
          </p>
        </section>
      ) : null}
    </div>
  );
}

/** The element that says where one hypothesis stands, so focus can be sent to it. */
function hypothesisDomId(conceptId: string, kind: string): string {
  return `hypothesis-${conceptId}-${kind}`;
}

function lessonsNote(concept: ConceptProgress): string {
  if (concept.lessons_total === 0) return 'No lesson yet.';
  if (concept.lessons_completed === 0) {
    return concept.lessons_total === 1 ? 'Lesson not finished.' : 'No lesson finished yet.';
  }
  return `${concept.lessons_completed} of ${pluralise(concept.lessons_total, 'lesson')} finished.`;
}

function ConceptRow({
  concept,
  dismissing,
  onDismiss,
  onPractise,
}: {
  concept: ConceptProgress;
  dismissing: string | null;
  onDismiss: (hypothesis: Hypothesis) => void;
  onPractise: () => void;
}) {
  const { knowledge } = concept;
  const review = reviewNote(concept);
  // Questions are worth asking once the learner has met the concept, or says they know it.
  const met =
    concept.lessons_completed > 0 ||
    knowledge.answered > 0 ||
    knowledge.self_report === 'confident';
  const practiceLabel = concept.review_due ? 'Start review' : 'Practise';

  return (
    <li className={styles.concept}>
      <div className={styles.conceptMain}>
        <div className={styles.conceptHead}>
          <span className={styles.conceptTitle}>{concept.title}</span>
          <Badge tone={KNOWLEDGE_TONE[knowledge.state]}>{knowledge.label}</Badge>
          {review ? (
            <Badge tone={concept.review_due ? 'warning' : 'neutral'} icon={<CalendarClock />}>
              {review}
            </Badge>
          ) : null}
        </div>
        <p className={styles.meta}>
          {lessonsNote(concept)}
          {knowledge.missing.length > 0 && knowledge.state !== 'not_assessed'
            ? ` Still needed: ${knowledge.missing.join('; ')}.`
            : ''}
        </p>
        {concept.hypotheses.length > 0 ? (
          <ul className={styles.hypotheses} aria-label={`Notes on ${concept.title}`}>
            {concept.hypotheses.map((hypothesis) => {
              const label = hypothesisLabel(hypothesis);
              return (
                <li
                  key={hypothesis.kind}
                  id={hypothesisDomId(concept.concept_id, hypothesis.kind)}
                  tabIndex={-1}
                  className={styles.hypothesis}
                >
                  <Badge tone={label.tone}>{label.status}</Badge>
                  <span className={styles.hypothesisText}>{hypothesis.description}</span>
                  {hypothesis.can_dismiss && !hypothesis.is_slip ? (
                    <Button
                      size="small"
                      variant="tertiary"
                      loading={dismissing === `${concept.concept_id}:${hypothesis.kind}`}
                      disabled={dismissing !== null}
                      onClick={() => onDismiss(hypothesis)}
                    >
                      That was a slip
                    </Button>
                  ) : null}
                </li>
              );
            })}
          </ul>
        ) : null}
      </div>
      {met ? (
        <div className={styles.conceptAction}>
          {concept.fresh_questions > 0 ? (
            <Button
              size="small"
              variant={concept.review_due ? 'primary' : 'secondary'}
              icon={concept.review_due ? <CalendarClock /> : <PencilLine />}
              aria-label={`${practiceLabel}: ${concept.title}`}
              onClick={onPractise}
            >
              {practiceLabel}
            </Button>
          ) : concept.next_fresh_at ? (
            <span className={styles.meta}>More questions {formatWait(concept.next_fresh_at)}</span>
          ) : null}
        </div>
      ) : null}
    </li>
  );
}
