import { CalendarClock, PencilLine, Sparkles } from 'lucide-react';
import { type ReactNode, useId, useState } from 'react';

import type { ConceptProgress, Course, Hypothesis, NextStep } from '@adle/contracts';
import { Badge, Button, ErrorState, LoadingState, useToast } from '@adle/design-system';

import { useRouter } from '../../app/router';
import { GenerationStatus } from '../../components/GenerationStatus';
import { NextSteps } from '../../components/NextSteps';
import { SessionSummary } from '../../components/SessionSummary';
import { callCore, describeError } from '../../lib/core-client';
import { pluralise } from '../../lib/format';
import { KIND_LESSON, lessonDisclosure, readLessonOutcome } from '../../lib/generation';
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

  const generation = useGeneration(courseId, (job) => {
    if (job.kind !== KIND_LESSON) return;
    // A new lesson changes what is worth doing next.
    overview.reload();
    const outcome = readLessonOutcome(job);
    if (outcome) {
      toast.show({
        tone: 'success',
        title: 'Lesson ready',
        description: [outcome.title, ...outcome.notes].join(' '),
      });
    }
  });

  if (overview.resource.status === 'loading') {
    return <LoadingState title="Working out what to do next…" />;
  }
  if (overview.resource.status === 'error') {
    return (
      <ErrorState
        title="Your progress could not be read"
        description={describeError(overview.resource.error)}
        actions={<Button onClick={overview.reload}>Try again</Button>}
      />
    );
  }

  const data = overview.resource.data;
  const providerName =
    provider.resource.status === 'ready' ? provider.resource.data.display_name : 'the AI provider';
  const reviews = reviewSentence(data.summary);

  const createLesson = (conceptId: string): Promise<void> =>
    generation.begin(conceptId, () =>
      callCore('generation.generate_lesson', { path: { concept_id: conceptId }, body: null }),
    );

  /** The control that asks for a lesson, with what it sends; or where that work stands. */
  const lessonControl = (_step: NextStep, conceptId: string, primary: boolean): ReactNode => {
    const job = generation.jobs.find(KIND_LESSON, conceptId);
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
          waitingText="Waiting for its turn"
          onCancel={() => generation.cancel(job)}
          onRetry={() => void createLesson(conceptId)}
          onDismiss={() => generation.putAway(conceptId, job)}
        />
        {settled ? (
          <>
            <div>
              <Button
                variant={primary ? 'primary' : 'secondary'}
                size={primary ? 'medium' : 'small'}
                icon={<Sparkles />}
                onClick={() => void createLesson(conceptId)}
              >
                Create the lesson
              </Button>
            </div>
            <p className={styles.aiNote}>
              Sends to {providerName}: {lessonDisclosure(course.source_count > 0 ? 'some' : 'none')}
              . It usually takes three of today&rsquo;s requests.
            </p>
          </>
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
        description: 'It only comes back if later answers point the same way.',
      });
    } catch (error) {
      toast.show({
        tone: 'danger',
        title: 'That could not be set aside',
        description: describeError(error),
      });
      overview.reload();
    } finally {
      setDismissing(null);
    }
  };

  return (
    <div className={styles.panel}>
      <section className={styles.section} aria-labelledby={nextId}>
        <h2 id={nextId} className={styles.heading}>
          What next
        </h2>
        <NextSteps plan={data.plan} courseId={courseId} renderGeneration={lessonControl} />
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
            Where you are
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
            These words describe what your answers have shown so far. They change as you answer
            more, and they are never a grade.
          </p>
        </section>
      ) : null}
    </div>
  );
}

function lessonsNote(concept: ConceptProgress): string {
  if (concept.lessons_total === 0) return 'No lesson yet.';
  if (concept.lessons_completed === 0) {
    return concept.lessons_total === 1 ? 'Its lesson is not finished.' : 'No lesson finished yet.';
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
          <ul
            className={styles.hypotheses}
            aria-label={`What Adle has noticed about ${concept.title}`}
          >
            {concept.hypotheses.map((hypothesis) => {
              const label = hypothesisLabel(hypothesis);
              return (
                <li key={hypothesis.kind} className={styles.hypothesis}>
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
