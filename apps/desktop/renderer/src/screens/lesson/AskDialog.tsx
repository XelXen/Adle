import { ArrowRight, Hand, Settings, Square } from 'lucide-react';
import { type FormEvent, useState } from 'react';

import type { Ask, Job } from '@adle/contracts';
import { Button, Callout, Dialog, ProgressBar, TextArea } from '@adle/design-system';

import { useRouter } from '../../app/router';
import { MathText } from '../../components/MathText';
import {
  answeredBy,
  askDisclosure,
  MAX_QUESTION_CHARACTERS,
  questionProblem,
  suggestedQuestions,
} from '../../lib/asks';
import { callCore } from '../../lib/core-client';
import { type JobFailure, jobProgress } from '../../lib/generation';
import { destination, usualWait } from '../../lib/provider';
import { isJobActive } from '../../lib/use-job';
import { useResource } from '../../lib/use-resource';
import styles from './Lesson.module.css';

export interface AskDialogProps {
  /** Which part the question is about, as the learner sees it: "Part 3: The bias". */
  partLabel: string;
  /** What kind of part it is, as the lesson names it. */
  kind: string;
  /** The part is a question the lesson is asking, and it has not been answered yet. */
  unanswered: boolean;
  /** The question being answered at the moment, or the one that was just answered. */
  job: Job | null;
  /** The request to start is on its way. */
  starting: boolean;
  /** Why it could not be started, or why it failed. */
  failure: JobFailure | null;
  /** The answer that has just arrived, once it has. */
  answer: Ask | null;
  onAsk: (question: string) => void;
  onStop: () => void;
  /** Put the last answer or failure away, to ask something else. */
  onAnother: () => void;
  onClose: () => void;
}

/**
 * Asking Adle about the part of the lesson on screen (ADR-024).
 *
 * One question, one answer, kept beside the part: a note in the margin, not a
 * conversation. The lesson is paused while this is open, and nothing is sent until the
 * learner presses Ask. They do not have to wait here: the dialog can be closed while the
 * answer is written, and the answer appears beside the part when it arrives.
 * Mounted only while open.
 */
export function AskDialog({
  partLabel,
  kind,
  unanswered,
  job,
  starting,
  failure,
  answer,
  onAsk,
  onStop,
  onAnother,
  onClose,
}: AskDialogProps) {
  const { navigate } = useRouter();
  const provider = useResource('provider-status', () => callCore('provider.status'));
  const [draft, setDraft] = useState('');
  const [problem, setProblem] = useState<string | null>(null);

  const status = provider.resource.status === 'ready' ? provider.resource.data : undefined;
  const waiting = starting || isJobActive(job);

  const submit = (event: FormEvent): void => {
    event.preventDefault();
    const found = questionProblem(draft);
    setProblem(found);
    if (!found) onAsk(draft.trim());
  };

  if (waiting) {
    const progress = job
      ? jobProgress(job, 'Waiting for its turn')
      : { value: undefined, message: 'Sending your question' };
    return (
      <Dialog
        open
        onClose={onClose}
        title="Your question is being answered"
        description={partLabel}
        actions={
          <>
            <Button icon={<Square />} disabled={!job} onClick={onStop}>
              Stop
            </Button>
            <Button variant="primary" icon={<ArrowRight />} onClick={onClose}>
              Carry on with the lesson
            </Button>
          </>
        }
      >
        <div className={styles.askBody}>
          <ProgressBar label={progress.message} showLabel value={progress.value} />
          <p className={styles.note}>
            You do not have to wait here. The answer will appear beside this part of the lesson when
            it arrives.
          </p>
        </div>
      </Dialog>
    );
  }

  if (answer) {
    return (
      <Dialog
        open
        onClose={onClose}
        title="An answer to your question"
        description={partLabel}
        actions={
          <>
            <Button onClick={onAnother}>Ask something else</Button>
            <Button variant="primary" icon={<ArrowRight />} onClick={onClose}>
              Back to the lesson
            </Button>
          </>
        }
      >
        <AskNote ask={answer} />
      </Dialog>
    );
  }

  if (provider.resource.status === 'ready' && !provider.resource.data.key_configured) {
    return (
      <Dialog
        open
        onClose={onClose}
        title="Ask about this part"
        description={partLabel}
        actions={
          <>
            <Button onClick={onClose}>Back to the lesson</Button>
            <Button
              variant="primary"
              icon={<Settings />}
              onClick={() => navigate({ name: 'settings', tab: 'ai' })}
            >
              Set up the AI provider
            </Button>
          </>
        }
      >
        <p className={styles.askLead}>
          An answer to a question is written by an AI model, and no key for an AI provider is set up
          yet. The lesson itself, its pictures, and its questions work without one.
        </p>
      </Dialog>
    );
  }

  const suggestions = suggestedQuestions(kind, unanswered);
  const wait = usualWait(status, 'ask');
  return (
    <Dialog
      open
      onClose={onClose}
      title="Ask about this part"
      description={partLabel}
      actions={
        <>
          <Button onClick={onClose}>Not now</Button>
          <Button type="submit" form="ask-form" variant="primary" icon={<Hand />}>
            Ask
          </Button>
        </>
      }
    >
      <form id="ask-form" className={styles.askBody} onSubmit={submit} noValidate>
        {failure ? (
          <Callout
            tone={failure.remedy === 'wait' ? 'warning' : 'danger'}
            title="No answer came"
            urgent
          >
            {failure.message}
          </Callout>
        ) : null}
        {unanswered ? (
          <Callout tone="info" title="This part is a question for you">
            Adle will help you think about it, and will not give the answer away. Asking here counts
            like using the hint: a right answer afterwards counts for a little less.
          </Callout>
        ) : null}
        <TextArea
          label="Your question"
          data-autofocus
          rows={3}
          maxLength={MAX_QUESTION_CHARACTERS}
          value={draft}
          onChange={(event) => {
            setDraft(event.target.value);
            setProblem(null);
          }}
          error={problem}
          placeholder="What would you like explained?"
        />
        <div>
          <p className={styles.askHint} id="ask-suggestions">
            Or ask one of these
          </p>
          <ul className={styles.askSuggestions} aria-labelledby="ask-suggestions">
            {suggestions.map((suggestion) => (
              <li key={suggestion}>
                <Button
                  size="small"
                  onClick={() => {
                    setProblem(null);
                    onAsk(suggestion);
                  }}
                >
                  {suggestion}
                </Button>
              </li>
            ))}
          </ul>
        </div>
        <p className={styles.note}>
          Sends to {destination(status, 'ask')}: {askDisclosure()}. It uses one of today&rsquo;s
          requests{wait ? `, and usually takes ${wait}` : ''}. The answer is written by an AI model,
          and can be wrong.
        </p>
      </form>
    </Dialog>
  );
}

/** One question and its answer, as a note: the learner's words, then the answer to read. */
export function AskNote({ ask }: { ask: Ask }) {
  return (
    <div className={styles.askNote}>
      {/* The learner's own words are shown exactly as typed: never as mathematics or markup. */}
      <p className={styles.askQuestion}>{ask.question}</p>
      <div className={styles.askAnswer}>
        {ask.paragraphs.map((paragraph, index) => (
          <p key={index}>
            <MathText text={paragraph} />
          </p>
        ))}
      </div>
      {ask.citations.length > 0 ? (
        <p className={styles.askMeta}>
          From your materials:{' '}
          {ask.citations
            .map((citation) => `${citation.source_name}, ${citation.locator}`)
            .join('; ')}
        </p>
      ) : null}
      <p className={styles.askMeta}>
        Written by {answeredBy(ask)}. A model wrote this, and it can be wrong.
        {ask.written_by.note ? ` ${ask.written_by.note}` : ''}
      </p>
    </div>
  );
}
