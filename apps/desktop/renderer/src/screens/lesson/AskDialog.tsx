import { ArrowRight, Hand, Image, RotateCcw, Settings, Square } from 'lucide-react';
import { type FormEvent, type ReactNode, useEffect, useRef, useState } from 'react';

import type { Ask, Job } from '@adle/contracts';
import {
  Button,
  Callout,
  Dialog,
  ProgressBar,
  SegmentedControl,
  TextArea,
} from '@adle/design-system';

import { useRouter } from '../../app/router';
import { MathText } from '../../components/MathText';
import { WhatIsSent } from '../../components/WhatIsSent';
import {
  answeredBy,
  askDisclosure,
  MAX_QUESTION_CHARACTERS,
  questionProblem,
  suggestedQuestions,
  suggestedRedraws,
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
  /** The question was turned away before anything was sent, rather than left unanswered. */
  refused: boolean;
  /** Why "Stop" did not work, if it did not. */
  stopProblem: string | null;
  /** The answer that has just arrived, once it has. */
  answer: Ask | null;
  /** The part's picture can be drawn again as the learner asks (ADR-067). */
  canRedraw: boolean;
  /** A picture is being put into the lesson, or taken out. */
  changingPicture: boolean;
  onAsk: (question: string, redraw: boolean) => void;
  /** Put the picture an answer drew into its part of the lesson. */
  onUsePicture: (ask: Ask) => void;
  onStop: () => void;
  /** Put the last answer or failure away, to ask something else. */
  onAnother: () => void;
  onClose: () => void;
}

type View = 'waiting' | 'answer' | 'no-key' | 'form';

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
  refused,
  stopProblem,
  answer,
  canRedraw,
  changingPicture,
  onAsk,
  onUsePicture,
  onStop,
  onAnother,
  onClose,
}: AskDialogProps) {
  const { navigate } = useRouter();
  const provider = useResource('provider-status', () => callCore('provider.status'));
  const [draft, setDraft] = useState('');
  const [problem, setProblem] = useState<string | null>(null);
  /** What the learner wants: words, or this part's picture drawn again. */
  const [wanted, setWanted] = useState<'words' | 'picture'>('words');
  const redraw = canRedraw && wanted === 'picture';
  const field = useRef<HTMLTextAreaElement>(null);

  const status = provider.resource.status === 'ready' ? provider.resource.data : undefined;
  const waiting = starting || isJobActive(job);
  const noKey = provider.resource.status === 'ready' && !provider.resource.data.key_configured;
  const view: View = waiting ? 'waiting' : answer ? 'answer' : noKey ? 'no-key' : 'form';

  // Coming back to the form from an answer ("Ask another"), typing starts in the field
  // again. The dialog itself only places the focus when it opens.
  const shown = useRef(view);
  useEffect(() => {
    if (view === 'form' && shown.current !== 'form') field.current?.focus();
    shown.current = view;
  }, [view]);

  const submit = (event: FormEvent): void => {
    event.preventDefault();
    const found = questionProblem(draft);
    setProblem(found);
    if (!found) onAsk(draft.trim(), redraw);
  };

  let title: string;
  let actions: ReactNode;
  let body: ReactNode;

  if (view === 'waiting') {
    const progress = job ? jobProgress(job, 'Queued') : { value: undefined, message: 'Sending' };
    title =
      redraw || progress.message.startsWith('Drawing the picture')
        ? 'Drawing the picture again'
        : 'Answering your question';
    actions = (
      <>
        <Button icon={<Square />} disabled={!job} onClick={onStop}>
          Stop
        </Button>
        <Button variant="primary" icon={<ArrowRight />} onClick={onClose}>
          Continue lesson
        </Button>
      </>
    );
    body = (
      <>
        <ProgressBar label={progress.message} showLabel value={progress.value} />
        <p className={styles.note}>
          No need to wait here. The answer will appear next to this part of the lesson.
        </p>
        {stopProblem ? (
          <p className={styles.note} role="alert">
            Couldn’t stop it. {stopProblem}
          </p>
        ) : null}
      </>
    );
  } else if (view === 'answer' && answer) {
    title = 'Answer';
    const offered = answer.picture?.state === 'offered';
    actions = (
      <>
        <Button
          onClick={() => {
            // A new question starts from an empty field.
            setDraft('');
            setProblem(null);
            onAnother();
          }}
        >
          Ask another
        </Button>
        {offered ? (
          <Button
            variant="primary"
            icon={<Image />}
            loading={changingPicture}
            onClick={() => onUsePicture(answer)}
          >
            Use this picture
          </Button>
        ) : (
          <Button variant="primary" icon={<ArrowRight />} onClick={onClose}>
            Back to lesson
          </Button>
        )}
      </>
    );
    body = <AskNote ask={answer} />;
  } else if (view === 'no-key') {
    title = 'Ask about this part';
    actions = (
      <>
        <Button onClick={onClose}>Back to lesson</Button>
        <Button
          variant="primary"
          icon={<Settings />}
          onClick={() => navigate({ name: 'settings', tab: 'ai' })}
        >
          Set up AI provider
        </Button>
      </>
    );
    body = (
      <p className={styles.askLead}>
        Answers are written by AI, and no provider key is set up yet. The rest of the lesson works
        without one.
      </p>
    );
  } else {
    const suggestions = redraw ? suggestedRedraws() : suggestedQuestions(kind, unanswered);
    // A picture is drawn by the model that writes lessons' pictures (ADR-067).
    const work = redraw ? 'lesson' : 'ask';
    const wait = usualWait(status, work);
    title = 'Ask about this part';
    actions = (
      <>
        <WhatIsSent what={askDisclosure(redraw)} to={destination(status, work)} wait={wait} />
        <Button onClick={onClose}>Cancel</Button>
        <Button type="submit" form="ask-form" variant="primary" icon={<Hand />}>
          Ask
        </Button>
      </>
    );
    body = (
      <form id="ask-form" className={styles.askBody} onSubmit={submit} noValidate>
        {failure ? (
          <Callout
            tone={failure.remedy === 'wait' ? 'warning' : 'danger'}
            title={refused ? 'Couldn’t ask that' : 'Couldn’t get an answer'}
            urgent
          >
            {failure.message}
          </Callout>
        ) : null}
        {canRedraw ? (
          <SegmentedControl
            label="What you want"
            value={wanted}
            options={[
              { value: 'words', label: 'Ask a question' },
              { value: 'picture', label: 'Change the picture' },
            ]}
            onValueChange={(value) => {
              setWanted(value);
              setProblem(null);
            }}
          />
        ) : null}
        {unanswered ? (
          <Callout tone="info" title="You haven’t answered this question yet">
            You’ll get help thinking it through, not the answer. Like a hint, asking makes a correct
            answer count a little less.
          </Callout>
        ) : null}
        <TextArea
          ref={field}
          label={redraw ? 'What should the picture show?' : 'Your question'}
          data-autofocus
          rows={3}
          maxLength={MAX_QUESTION_CHARACTERS}
          value={draft}
          onChange={(event) => {
            setDraft(event.target.value);
            setProblem(null);
          }}
          error={problem}
          placeholder={
            redraw
              ? 'For example: draw the bonds between the molecules.'
              : 'What would you like explained?'
          }
        />
        <div>
          <p className={styles.askHint} id="ask-suggestions">
            Or pick one
          </p>
          <ul className={styles.askSuggestions} aria-labelledby="ask-suggestions">
            {suggestions.map((suggestion) => (
              <li key={suggestion}>
                <Button
                  size="small"
                  onClick={() => {
                    setProblem(null);
                    onAsk(suggestion, redraw);
                  }}
                >
                  {suggestion}
                </Button>
              </li>
            ))}
          </ul>
        </div>
      </form>
    );
  }

  return (
    <Dialog open onClose={onClose} title={title} description={partLabel} actions={actions}>
      <div className={styles.askBody}>
        {/* Always here, so that what it comes to say is heard: the dialog changes from
            waiting to the answer in place, with nothing else to announce it. */}
        <p className="ad-visually-hidden" role="status">
          {view === 'waiting'
            ? 'Answering your question.'
            : view === 'answer'
              ? 'The answer has arrived.'
              : ''}
        </p>
        {body}
      </div>
    </Dialog>
  );
}

export interface AskNoteProps {
  ask: Ask;
  /** Put the picture the answer drew into the lesson; with no way to, nothing is offered. */
  onUsePicture?: () => void;
  /** Give the part its own picture back. */
  onPutBack?: () => void;
  /** A picture is being put in or taken out. */
  changing?: boolean;
}

/**
 * One question and its answer, as a note: the learner's words, then the answer to read,
 * and the part's picture drawn again when that is what they asked for (ADR-067).
 */
export function AskNote({ ask, onUsePicture, onPutBack, changing = false }: AskNoteProps) {
  const picture = ask.picture ?? null;
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
      {picture ? (
        <div className={styles.askPicture}>
          <p className={styles.askMeta}>
            {picture.state === 'in_use'
              ? 'This part shows the picture drawn for this answer.'
              : 'This answer drew a new picture for this part.'}
          </p>
          {picture.state === 'in_use' && onPutBack ? (
            <Button size="small" icon={<RotateCcw />} loading={changing} onClick={onPutBack}>
              Put the original back
            </Button>
          ) : null}
          {picture.state === 'offered' && onUsePicture ? (
            <Button size="small" icon={<Image />} loading={changing} onClick={onUsePicture}>
              Use this picture
            </Button>
          ) : null}
        </div>
      ) : null}
      <p className={styles.askMeta}>
        Answered by {answeredBy(ask)}. AI can make mistakes.
        {ask.written_by.note ? ` ${ask.written_by.note}` : ''}
      </p>
    </div>
  );
}
