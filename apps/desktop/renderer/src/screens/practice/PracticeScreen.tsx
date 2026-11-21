import { ArrowLeft, ArrowRight, Check } from 'lucide-react';
import { useId, useState } from 'react';

import type { AnswerResult, PracticeSet } from '@adle/contracts';
import { Badge, Button, EmptyState, ErrorState, LoadingState, Page } from '@adle/design-system';

import { type MistakeKind, useRouter } from '../../app/router';
import { MathText } from '../../components/MathText';
import { NextSteps } from '../../components/NextSteps';
import { callCore, CoreRequestError, describeError } from '../../lib/core-client';
import { formatWait, outcomeWords, practiceSummary, practiceTitle } from '../../lib/learning';
import { useResource } from '../../lib/use-resource';
import { KNOWLEDGE_TONE } from '../course/ConceptDetail';
import { CheckpointPanel } from '../lesson/CheckpointPanel';
import styles from './Practice.module.css';

/**
 * A few questions on one concept: practice, a review that is due, or a check on
 * something a wrong answer suggested. The core chooses the questions and says
 * why; each answer is scored and recorded exactly as it is in a lesson.
 */
export function PracticeScreen({
  courseId,
  conceptId,
  about,
}: {
  courseId: string;
  conceptId: string;
  about?: MistakeKind;
}) {
  const { navigate } = useRouter();
  const practice = useResource(`practice:${conceptId}:${about ?? ''}`, () =>
    callCore('learning.start_practice', {
      path: { concept_id: conceptId },
      body: about ? { about } : {},
    }),
  );
  const leave = (): void => navigate({ name: 'course', courseId, tab: 'learn' });
  const back = (
    <Button variant="tertiary" size="small" icon={<ArrowLeft />} onClick={leave}>
      Back to course
    </Button>
  );

  if (practice.resource.status === 'loading') {
    return (
      <Page title="Practice" eyebrow={back} width="reading">
        <LoadingState title="Choosing questions…" />
      </Page>
    );
  }
  if (practice.resource.status === 'error') {
    const error = practice.resource.error;
    const missing = error instanceof CoreRequestError && error.code === 'not_found';
    return (
      <Page title="Practice" eyebrow={back} width="reading">
        <ErrorState
          title={missing ? 'This concept no longer exists' : 'Couldn’t load questions'}
          description={describeError(error)}
          actions={
            missing ? (
              <Button variant="primary" onClick={leave}>
                Back to course
              </Button>
            ) : (
              <Button onClick={practice.reload}>Try again</Button>
            )
          }
        />
      </Page>
    );
  }

  const data = practice.resource.data;
  if (data.questions.length === 0) {
    return (
      <Page title={practiceTitle(data)} eyebrow={back} width="reading">
        <EmptyState
          title="Nothing to ask right now"
          description={
            data.next_fresh_at
              ? `${data.reason} Check back ${formatWait(data.next_fresh_at)}.`
              : data.reason
          }
          actions={
            <Button variant="primary" onClick={leave}>
              Back to course
            </Button>
          }
        />
      </Page>
    );
  }

  return (
    <Page
      title={practiceTitle(data)}
      eyebrow={back}
      width="reading"
      description={
        <span>
          <span className={styles.why}>Why these questions: </span>
          {data.reason}
        </span>
      }
    >
      {/* A fresh set of questions starts a fresh run through them. */}
      <PracticeRun key={data.questions.map((item) => item.question.id).join(',')} data={data} />
    </Page>
  );
}

function PracticeRun({ data }: { data: PracticeSet }) {
  const [index, setIndex] = useState(0);
  const [results, setResults] = useState<readonly AnswerResult[]>([]);
  const [finished, setFinished] = useState(false);
  const total = data.questions.length;
  const current = data.questions[index];
  const answered = results.length > index;
  const last = index === total - 1;

  if (finished || !current) {
    return <PracticeFinished data={data} results={results} />;
  }

  return (
    <div className={styles.run}>
      <p className={styles.position} role="status">
        Question {index + 1} of {total}
      </p>
      <div className={styles.card}>
        <CheckpointPanel
          key={`${current.lesson_id}:${current.question.id}`}
          lessonId={current.lesson_id}
          question={current.question}
          onAnswered={(result) => setResults((earlier) => [...earlier, result])}
        />
      </div>
      <div className={styles.controls}>
        {!answered ? <span className={styles.note}>Answer or skip to continue.</span> : null}
        <Button
          variant="primary"
          icon={last ? <Check /> : <ArrowRight />}
          disabled={!answered}
          onClick={() => (last ? setFinished(true) : setIndex(index + 1))}
        >
          {last ? 'See results' : 'Next question'}
        </Button>
      </div>
    </div>
  );
}

/** After the last question: what was answered, where the concept stands, and what next. */
function PracticeFinished({
  data,
  results,
}: {
  data: PracticeSet;
  results: readonly AnswerResult[];
}) {
  const headingId = useId();
  const overview = useResource(`practice-next:${data.concept_id}`, () =>
    callCore('learning.overview', { path: { course_id: data.course_id } }),
  );
  // The last answer carries the concept's state as it stands after the whole set.
  const knowledge = results.at(-1)?.knowledge ?? null;

  return (
    <div className={styles.run}>
      <section className={styles.card} aria-labelledby={headingId}>
        <h2 id={headingId} className={styles.title}>
          Done
        </h2>
        <p>{practiceSummary(results.map((result) => result.outcome))}</p>
        <ol className={styles.outcomes} aria-label="Your answers">
          {data.questions.map((item, position) => {
            const result = results[position];
            return (
              <li key={`${item.lesson_id}:${item.question.id}`} className={styles.outcome}>
                <span className={styles.outcomeStem}>
                  <MathText text={item.question.stem} />
                </span>
                <span className={styles.outcomeWords}>
                  {result ? outcomeWords(result.outcome) : 'Not answered'}
                </span>
              </li>
            );
          })}
        </ol>
        {knowledge ? (
          <div className={styles.standing}>
            <p className={styles.standingLine}>
              <span>Status of “{data.concept_title}”:</span>
              <Badge tone={KNOWLEDGE_TONE[knowledge.state]}>{knowledge.label}</Badge>
            </p>
            {knowledge.missing.length > 0 ? (
              <p className={styles.note}>Still needed: {knowledge.missing.join('; ')}.</p>
            ) : (
              <p className={styles.note}>A review later will check that it stuck.</p>
            )}
          </div>
        ) : null}
      </section>

      {overview.resource.status === 'loading' ? (
        <p className={styles.note} role="status">
          Planning your next step…
        </p>
      ) : overview.resource.status === 'error' ? (
        <p className={styles.note}>
          Couldn’t plan your next step just now. Your answers are saved, and the course page will
          show it.
        </p>
      ) : (
        <NextSteps plan={overview.resource.data.plan} courseId={data.course_id} />
      )}
    </div>
  );
}
