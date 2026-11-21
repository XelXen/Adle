import { ArrowDown, ArrowUp, Lightbulb } from 'lucide-react';
import { type FormEvent, useEffect, useId, useRef, useState } from 'react';

import type { AnswerResult, PlayerQuestion } from '@adle/contracts';
import {
  Button,
  Callout,
  type CalloutTone,
  Checkbox,
  IconButton,
  RadioGroup,
  TextArea,
  TextField,
} from '@adle/design-system';

import { MathText } from '../../components/MathText';
import { callCore, describeError } from '../../lib/core-client';
import { type AnswerDraft, buildAnswer, emptyDraft, moved } from '../../lesson/answers';
import styles from './Lesson.module.css';

const OUTCOME: Record<AnswerResult['outcome'], { title: string; tone: CalloutTone }> = {
  correct: { title: 'Correct', tone: 'success' },
  partial: { title: 'Partly right', tone: 'info' },
  incorrect: { title: 'Not quite', tone: 'info' },
  skipped: { title: 'Skipped', tone: 'info' },
};

/**
 * One question of a lesson: answer it, ask for a hint, or skip it. The answer
 * is scored by the core, which is the only place the answer key exists.
 */
export function CheckpointPanel({
  lessonId,
  question,
  onAnswered,
}: {
  lessonId: string;
  question: PlayerQuestion;
  /** Called once the question has been answered or skipped. */
  onAnswered: (result: AnswerResult) => void;
}) {
  const stemId = useId();
  const [draft, setDraft] = useState<AnswerDraft>(() => emptyDraft(question));
  const [written, setWritten] = useState('');
  const [comparing, setComparing] = useState(false);
  const [hintShown, setHintShown] = useState(false);
  const [unsure, setUnsure] = useState(false);
  const [problem, setProblem] = useState<string>();
  const [busy, setBusy] = useState<'answer' | 'skip' | null>(null);
  const [result, setResult] = useState<AnswerResult | null>(null);
  const said = useRef<HTMLDivElement>(null);

  // What is said about an answer appears below the question, where the lesson's controls
  // may lie over it. It is brought into view, as far as the scroll padding of the page.
  const answered = result !== null;
  useEffect(() => {
    if (answered) said.current?.scrollIntoView({ block: 'nearest' });
  }, [answered]);

  const locked = result !== null || busy !== null;
  const options = question.options ?? [];
  const optionText = new Map(options.map((option) => [option.id, option.text]));
  const isExplanation = question.form === 'explanation';

  /** Once checked, each option says what it turned out to be: in words, not by colour. */
  const reviewNote = (optionId: string): string | undefined => {
    if (result === null || result.outcome === 'skipped') return undefined;
    const chosen = optionId === draft.choice;
    if (optionId === result.correct_option) {
      return chosen ? 'Your answer · correct' : 'Correct answer';
    }
    return chosen ? 'Your answer' : undefined;
  };

  const send = async (kind: 'answer' | 'skip'): Promise<void> => {
    let body;
    if (kind === 'skip') body = { skipped: true };
    else {
      const built = buildAnswer(question, draft);
      if (!built.ok) {
        setProblem(built.message);
        return;
      }
      body = { ...built.body, hinted: hintShown, unsure };
    }
    setProblem(undefined);
    setBusy(kind);
    try {
      const answered = await callCore('lessons.answer', {
        path: { lesson_id: lessonId, question_id: question.id },
        body,
      });
      setResult(answered);
      onAnswered(answered);
    } catch (error) {
      setProblem(describeError(error));
    } finally {
      setBusy(null);
    }
  };

  const submit = (event: FormEvent): void => {
    event.preventDefault();
    if (isExplanation && !comparing) {
      if (written.trim() === '') setProblem('Write your explanation first.');
      else {
        setProblem(undefined);
        setComparing(true);
      }
      return;
    }
    void send('answer');
  };

  return (
    <form className={styles.question} onSubmit={submit} noValidate aria-labelledby={stemId}>
      <p id={stemId} className={styles.stem}>
        <MathText text={question.stem} />
      </p>

      {question.form === 'multiple_choice' || question.form === 'prediction' ? (
        <RadioGroup
          label="Choose one"
          hideLabel
          value={draft.choice}
          disabled={busy !== null}
          readOnly={result !== null}
          options={options.map((option) => ({
            value: option.id,
            label: <MathText text={option.text} />,
            description: reviewNote(option.id),
          }))}
          onValueChange={(choice) => setDraft({ ...draft, choice })}
        />
      ) : null}

      {question.form === 'true_false' ? (
        <RadioGroup
          label="True or false?"
          hideLabel
          value={draft.choice}
          disabled={busy !== null}
          readOnly={result !== null}
          options={[
            { value: 'true', label: 'True', description: reviewNote('true') },
            { value: 'false', label: 'False', description: reviewNote('false') },
          ]}
          onValueChange={(choice) => setDraft({ ...draft, choice })}
        />
      ) : null}

      {question.form === 'numeric' || question.form === 'short_answer' ? (
        <div className={styles.answerField}>
          <TextField
            label="Your answer"
            value={draft.text}
            disabled={locked}
            maxLength={question.form === 'numeric' ? 40 : 400}
            inputMode={question.form === 'numeric' ? 'decimal' : 'text'}
            autoComplete="off"
            description={question.unit ? `In ${question.unit}.` : undefined}
            onChange={(event) => setDraft({ ...draft, text: event.target.value })}
          />
        </div>
      ) : null}

      {question.form === 'ordering' ? (
        <ol className={styles.ordering} aria-label="Your order, first to last">
          {draft.order.map((id, index) => (
            <li key={id} className={styles.orderingItem}>
              <span className={styles.orderingText}>
                <MathText text={optionText.get(id) ?? ''} />
              </span>
              <IconButton
                label={`Move “${optionText.get(id) ?? ''}” earlier`}
                icon={<ArrowUp />}
                variant="tertiary"
                size="small"
                disabled={locked || index === 0}
                onClick={() => setDraft({ ...draft, order: moved(draft.order, index, -1) })}
              />
              <IconButton
                label={`Move “${optionText.get(id) ?? ''}” later`}
                icon={<ArrowDown />}
                variant="tertiary"
                size="small"
                disabled={locked || index === draft.order.length - 1}
                onClick={() => setDraft({ ...draft, order: moved(draft.order, index, 1) })}
              />
            </li>
          ))}
        </ol>
      ) : null}

      {isExplanation ? (
        <>
          <TextArea
            label="Your explanation"
            value={written}
            rows={4}
            maxLength={2000}
            disabled={locked || comparing}
            description="Explain it as you would to a friend. It stays on this computer."
            onChange={(event) => setWritten(event.target.value)}
          />
          {comparing ? (
            <div className={styles.compare}>
              <div>
                <p className={styles.compareTitle}>A good answer</p>
                <p>
                  <MathText text={question.sample_answer ?? ''} />
                </p>
              </div>
              <fieldset className={styles.rubric} disabled={locked}>
                <legend className={styles.compareTitle}>
                  Which of these did your explanation include?
                </legend>
                {(question.rubric ?? []).map((point) => (
                  <Checkbox
                    key={point.id}
                    label={<MathText text={point.text} />}
                    checked={draft.covered.includes(point.id)}
                    disabled={locked}
                    onCheckedChange={(checked) =>
                      setDraft({
                        ...draft,
                        covered: checked
                          ? [...draft.covered, point.id]
                          : draft.covered.filter((id) => id !== point.id),
                      })
                    }
                  />
                ))}
              </fieldset>
            </div>
          ) : null}
        </>
      ) : null}

      {hintShown && question.hint ? (
        <Callout tone="info" title="Hint">
          <div className={styles.result}>
            <p>
              <MathText text={question.hint} />
            </p>
            <p className={styles.change}>A correct answer after a hint counts a little less.</p>
          </div>
        </Callout>
      ) : null}

      {problem ? (
        <p className={styles.problem} role="alert">
          {problem}
        </p>
      ) : null}

      {result === null ? (
        <>
          {!isExplanation ? (
            <Checkbox
              label="I’m not sure about this answer"
              description="Adle will check this idea again later."
              checked={unsure}
              disabled={locked}
              onCheckedChange={setUnsure}
            />
          ) : null}
          <div className={styles.questionActions}>
            <Button
              type="submit"
              variant="primary"
              loading={busy === 'answer'}
              disabled={busy === 'skip'}
            >
              {isExplanation
                ? comparing
                  ? 'Record this'
                  : 'Compare with a good answer'
                : 'Check answer'}
            </Button>
            {question.hint && !hintShown ? (
              <Button
                variant="tertiary"
                icon={<Lightbulb />}
                disabled={locked}
                onClick={() => setHintShown(true)}
              >
                Show a hint
              </Button>
            ) : null}
            <Button
              variant="tertiary"
              loading={busy === 'skip'}
              disabled={busy === 'answer'}
              onClick={() => void send('skip')}
            >
              Skip question
            </Button>
          </div>
        </>
      ) : null}

      {/* Present from the start, so that what arrives in it is announced. */}
      <div role="status" ref={said}>
        {result !== null ? (
          <Callout tone={OUTCOME[result.outcome].tone} title={OUTCOME[result.outcome].title}>
            <div className={styles.result}>
              {result.feedback ? (
                <p>
                  <MathText text={result.feedback} />
                </p>
              ) : null}
              {/* A question with options marks the right one among them instead. */}
              {result.correct_answer &&
              result.correct_option === null &&
              result.outcome !== 'correct' &&
              !isExplanation ? (
                <p>
                  <strong>The answer:</strong> <MathText text={result.correct_answer} />
                </p>
              ) : null}
              <p>
                <MathText text={result.explanation} />
              </p>
              <p className={styles.change}>{result.change}</p>
            </div>
          </Callout>
        ) : null}
      </div>
    </form>
  );
}
