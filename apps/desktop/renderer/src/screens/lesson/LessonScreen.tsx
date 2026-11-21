import {
  AlignLeft,
  ArrowLeft,
  ArrowRight,
  Captions,
  Check,
  ChevronDown,
  ChevronsDownUp,
  ChevronsUpDown,
  ChevronUp,
  Coffee,
  Hand,
  Info,
  Maximize,
  MessageCircleQuestion,
  Minimize,
  Pause,
  Play,
  RotateCcw,
  Trash2,
  Volume2,
  VolumeX,
} from 'lucide-react';
import { type ReactNode, useEffect, useRef, useState, useSyncExternalStore } from 'react';

import type { Ask, Job, LearnerPreferences, LessonForPlayer, SceneArtifact } from '@adle/contracts';
import {
  Badge,
  Button,
  Callout,
  cx,
  ErrorState,
  IconButton,
  InfoPopover,
  LoadingState,
  Page,
  Spinner,
  useToast,
} from '@adle/design-system';

import type { PlayerStatus } from '../../../../player/host/WanimPlayerAdapter';
import { useBreak } from '../../app/BreakContext';
import { useRouter } from '../../app/router';
import { MathText } from '../../components/MathText';
import { NextSteps } from '../../components/NextSteps';
import { ScenePlayer, type ScenePlayerHandle } from '../../components/ScenePlayer';
import { StageFrame } from '../../components/StageFrame';
import {
  canContinue,
  LessonController,
  type LessonSegment,
  type PlaybackState,
} from '../../lesson/controller';
import { type Narrator, TimedNarrator } from '../../lesson/narration';
import { SceneCues } from '../../lesson/scene-cues';
import {
  browserLine,
  browserSpeech,
  loadLocalVoices,
  pickVoice,
  SpeechNarrator,
  type Voice,
} from '../../lesson/speech';
import { answeredAskId, asksAbout, KIND_ASK } from '../../lib/asks';
import { USUAL_BREAK_MINUTES } from '../../lib/breaks';
import { getBridge } from '../../lib/bridge';
import { callCore, CoreRequestError, describeError } from '../../lib/core-client';
import { authorName, type JobFailure, jobFailure, refusalOf } from '../../lib/generation';
import { useFullscreen, useStillness } from '../../lib/use-fullscreen';
import { isJobActive, useJob } from '../../lib/use-job';
import { useLessonPictures } from '../../lib/use-lesson-pictures';
import { useResource } from '../../lib/use-resource';
import { KNOWLEDGE_TONE } from '../course/ConceptDetail';
import { AskDialog, AskNote } from './AskDialog';
import { CheckpointPanel } from './CheckpointPanel';
import styles from './Lesson.module.css';
import { type ReportState, UnhelpfulDialog } from './UnhelpfulDialog';

const GROUNDING_NOTE: Record<LessonForPlayer['lesson']['grounding'], string> = {
  sample: 'Sample lesson',
  materials: 'From your materials',
  general_knowledge: 'From general knowledge',
};

/** What a lesson is read with when the learner has not said otherwise. */
const DEFAULT_READING: LearnerPreferences = {
  pace: 'standard',
  explanation_density: 'balanced',
  narration: true,
  captions: true,
  goal: '',
  voice: '',
  volume: 100,
};

/** Everything that lives exactly as long as one opened lesson. */
interface Session {
  controller: LessonController;
  cues: SceneCues;
  save: (position: number, completed: boolean) => void;
  /** Resolves once the latest save has been answered, whether or not it worked. */
  saved: () => Promise<void>;
  /** Shows the narration as text, at reading pace. Always available. */
  silent: Narrator;
  /** Reads the narration aloud. Absent when this computer has no voice to read with. */
  spoken: Narrator | null;
}

function openSession(
  data: LessonForPlayer,
  preferences: LearnerPreferences,
  voices: readonly Voice[],
  onSaveFailed: (error: unknown) => void,
): Session {
  const { lesson, progress } = data;
  const cues = new SceneCues();
  const silent = new TimedNarrator(preferences.pace);
  const engine = browserSpeech();
  const voice = pickVoice(voices, preferences.voice);
  const spoken =
    engine && voice
      ? new SpeechNarrator(engine, browserLine, {
          voice,
          pace: preferences.pace,
          volume: preferences.volume / 100,
        })
      : null;
  let warned = false;
  let latest: Promise<unknown> = Promise.resolve();
  const save = (position: number, completed: boolean): void => {
    latest = callCore('lessons.save_progress', {
      path: { lesson_id: lesson.lesson_id },
      body: { position, completed },
    }).catch((error: unknown) => {
      // Said once: a lesson that cannot save its place would say so again at every part.
      if (warned) return;
      warned = true;
      onSaveFailed(error);
    });
  };
  const saved = (): Promise<void> => latest.then(() => undefined);
  const controller: LessonController = new LessonController(
    lesson,
    {
      narrator: preferences.narration && spoken ? spoken : silent,
      advanceScene: () => cues.advance(controller.segment.id),
      saveProgress: save,
    },
    // A finished lesson is reopened for review: from the beginning, with every part open.
    progress.completed
      ? { position: 0, furthest: lesson.segments.length - 1 }
      : { position: progress.position },
  );
  return { controller, cues, save, saved, silent, spoken };
}

/** One lesson, played from start to finish with the learner in control of the pace. */
export function LessonScreen({ courseId, lessonId }: { courseId: string; lessonId: string }) {
  const { navigate } = useRouter();
  const lesson = useResource(`lesson:${lessonId}`, () =>
    callCore('lessons.get', { path: { lesson_id: lessonId } }),
  );
  const preferences = useResource('learner-preferences', () => callCore('learner.get_preferences'));
  // Asked once per lesson: the list of voices is short and does not change while one plays.
  const voices = useResource('speech-voices', () => loadLocalVoices(browserSpeech()));
  const leave = (): void => navigate({ name: 'course', courseId, tab: 'learn' });
  const back = (
    <Button variant="tertiary" size="small" icon={<ArrowLeft />} onClick={leave}>
      Back to course
    </Button>
  );

  if (
    lesson.resource.status === 'loading' ||
    preferences.resource.status === 'loading' ||
    voices.resource.status === 'loading'
  ) {
    return (
      <Page title="Lesson" eyebrow={back}>
        <LoadingState title="Opening lesson…" />
      </Page>
    );
  }
  if (lesson.resource.status === 'error') {
    const error = lesson.resource.error;
    const code = error instanceof CoreRequestError ? error.code : null;
    return (
      <Page title="Lesson" eyebrow={back}>
        <ErrorState
          title={
            code === 'not_found'
              ? 'This lesson no longer exists'
              : code === 'lesson_outdated'
                ? 'This lesson needs to be recreated'
                : 'Couldn’t open the lesson'
          }
          description={describeError(error)}
          actions={
            code === null ? (
              <Button onClick={lesson.reload}>Try again</Button>
            ) : (
              <Button variant="primary" onClick={leave}>
                Back to course
              </Button>
            )
          }
        />
      </Page>
    );
  }

  // Preferences and voices are niceties here: without them a lesson still plays, at the
  // standard pace, with its narration shown as text.
  return (
    <LessonPlayer
      key={lessonId}
      data={lesson.resource.data}
      preferences={
        preferences.resource.status === 'ready' ? preferences.resource.data : DEFAULT_READING
      }
      voices={voices.resource.status === 'ready' ? voices.resource.data : []}
      eyebrow={back}
      onLeave={leave}
    />
  );
}

function LessonPlayer({
  data,
  preferences,
  voices,
  eyebrow,
  onLeave,
}: {
  data: LessonForPlayer;
  preferences: LearnerPreferences;
  voices: readonly Voice[];
  eyebrow: ReactNode;
  onLeave: () => void;
}) {
  const toast = useToast();
  const { lesson } = data;
  // A lesson can be opened before all its pictures are drawn (ADR-031): they are looked
  // for while any is still to come. The words stay as they were when it was opened.
  const pictures = useLessonPictures(lesson.lesson_id, data);
  const [{ controller, cues, save, saved, silent, spoken }] = useState(() =>
    openSession(data, preferences, voices, (error) =>
      toast.show({
        tone: 'danger',
        title: 'Couldn’t save your place',
        description: describeError(error),
      }),
    ),
  );
  const state = useSyncExternalStore(controller.subscribe, controller.getState);
  const [aloud, setAloud] = useState(preferences.narration && spoken !== null);
  const [wordsShown, setWordsShown] = useState(preferences.captions);
  // Listening, the words run along the foot of the screen one line at a time, as under
  // a film. Reading, with nothing spoken, they are what the lesson says, and every line
  // stays where it can be read again.
  const [everyLine, setEveryLine] = useState(!(preferences.narration && spoken !== null));
  // The whole player can fill the screen. While it does and the lesson is playing, the
  // bar of controls gets out of the picture's way once nothing is being done with it.
  const theatre = useRef<HTMLDivElement>(null);
  const screen = useFullscreen(theatre);
  useStillness(theatre, screen.active && state.status === 'playing');
  // With every line shown, the line being said is kept in view inside the list. Only the
  // list moves: the page stays where the learner put it.
  const lines = useRef<HTMLOListElement>(null);
  useEffect(() => {
    const list = lines.current;
    const line = list?.querySelector<HTMLElement>('[aria-current="true"]');
    if (!list || !line || list.scrollHeight <= list.clientHeight) return;
    const top = line.offsetTop - list.offsetTop;
    const hidden =
      top < list.scrollTop || top + line.offsetHeight > list.scrollTop + list.clientHeight;
    if (hidden) list.scrollTop = Math.max(0, top - list.clientHeight / 3);
  }, [state.beatIndex, state.segmentIndex, everyLine]);
  /** Set while the learner is choosing what to do after saying a part did not help. */
  const [unhelpful, setUnhelpful] = useState<ReportState | null>(null);

  // -- questions the learner asks Adle about a part (ADR-024) ------------------------
  const lessonId = lesson.lesson_id;
  const asks = useResource(`lesson-asks:${lessonId}`, () =>
    callCore('lessons.list_asks', { path: { lesson_id: lessonId } }),
  );
  /** The part the open dialog is about: it stays that part if the lesson moves on. */
  const [askingAbout, setAskingAbout] = useState<number | null>(null);
  const [askStarted, setAskStarted] = useState<Job | null>(null);
  /** The part the question being answered was asked about, where this screen saw it asked. */
  const [askedAbout, setAskedAbout] = useState<number | null>(null);
  const [askStarting, setAskStarting] = useState(false);
  const [askRefusal, setAskRefusal] = useState<JobFailure | null>(null);
  /** Why "Stop" did not work. Said in the dialog: a toast would lie underneath it. */
  const [stopProblem, setStopProblem] = useState<string | null>(null);
  /** The parts whose kept questions are unfolded. */
  const [notesOpen, setNotesOpen] = useState<ReadonlySet<string>>(new Set());
  const askJob = useJob(askStarted, (finished) => {
    asks.reload();
    if (finished.status === 'failed' && askingAbout === null) {
      // With the dialog open the failure is shown there. Back in the lesson nothing else
      // would say that no answer is coming.
      toast.show({
        tone: 'danger',
        title: 'Couldn’t get an answer',
        description: jobFailure(finished)?.message,
      });
    }
    if (finished.status !== 'succeeded') return;
    const about =
      typeof finished.result === 'object' && finished.result !== null
        ? (finished.result as { segment_id?: unknown }).segment_id
        : null;
    if (typeof about === 'string') setNotesOpen((open) => new Set(open).add(about));
    // Said only to a learner who went back to the lesson: in the dialog they see the answer.
    // And by the computer itself if they have gone to another window meanwhile.
    void getBridge().app.notify('answer_ready');
    if (askingAbout === null) {
      const index = lesson.segments.findIndex((item) => item.id === about);
      toast.show({
        tone: 'success',
        title: 'Your answer is ready',
        description: index >= 0 ? `See part ${index + 1} of this lesson.` : undefined,
      });
    }
  });
  // A question asked before the learner left this lesson may still be on its way: it is
  // picked up again, so that its answer arrives here and it can still be stopped.
  useEffect(() => {
    let cancelled = false;
    callCore('jobs.list_active', { path: { course_id: lesson.course_id } }).then(
      (list) => {
        if (cancelled) return;
        const waiting = list.jobs.find(
          (job) => job.kind === KIND_ASK && job.subject_id === lessonId,
        );
        if (waiting) setAskStarted((current) => current ?? waiting);
      },
      () => {
        // Nothing to pick up, or not now. Asking again says so if one is still out.
      },
    );
    return () => {
      cancelled = true;
    };
  }, [lesson.course_id, lessonId]);
  const kept: Ask[] = asks.resource.status === 'ready' ? asks.resource.data.asks : [];
  const answeredId = answeredAskId(askJob);
  const freshAnswer = kept.find((ask) => ask.id === answeredId) ?? null;

  /** Read aloud, or show the words at reading pace. The choice is kept for next time. */
  const readAloud = (next: boolean): void => {
    if (!spoken) return;
    setAloud(next);
    controller.setNarrator(next ? spoken : silent);
    callCore('learner.update_preferences', { body: { narration: next } }).catch(() => {
      // The lesson reads as asked either way; only remembering the choice failed.
    });
  };
  // With nothing spoken, the words are the narration: they are always shown.
  const transcriptShown = wordsShown || !aloud;

  useEffect(() => {
    // Opening a lesson is itself progress worth remembering.
    save(controller.getState().segmentIndex, false);
    return () => controller.dispose();
  }, [controller, save]);

  const segment = controller.segment;
  const total = lesson.segments.length;
  const last = state.segmentIndex === total - 1;
  const beats = segment.narration ?? [];
  const settled = state.status === 'done' || state.status === 'waiting';
  const allowed = canContinue(state, segment);
  const playing = state.status === 'playing';

  const replay = (): void => {
    cues.restart();
    controller.replay();
  };

  /** Record that this part did not help, and offer other ways forward. */
  const sayUnhelpful = (): void => {
    controller.pause();
    setUnhelpful('saving');
    const settle = (outcome: ReportState) => (): void =>
      // Only while the dialog is still open: the learner may already have moved on.
      setUnhelpful((current) => (current === null ? null : outcome));
    callCore('lessons.report_unhelpful', {
      path: { lesson_id: lesson.lesson_id },
      body: { segment_id: segment.id },
    }).then(settle('saved'), settle('failed'));
  };
  // A question or a pause for thought explains nothing, so there is nothing to report.
  const explains = segment.type !== 'checkpoint' && segment.type !== 'reflection';

  const answering = askStarting || isJobActive(askJob);
  const openAsk = (): void => {
    controller.pause();
    setStopProblem(null);
    const failed = askJob?.status === 'failed';
    if (answering || failed) {
      // Back to the question that is being answered, to watch it or to stop it; or to the
      // one that failed while the learner was back in the lesson, to see what happened.
      setAskingAbout(askedAbout ?? state.segmentIndex);
      return;
    }
    // A new question starts from an empty page: the last answer is beside its part already.
    setAskStarted(null);
    setAskRefusal(null);
    setAskingAbout(state.segmentIndex);
  };
  const ask = async (question: string): Promise<void> => {
    const about = lesson.segments[askingAbout ?? state.segmentIndex];
    if (!about) return;
    setAskStarting(true);
    setAskRefusal(null);
    setAskStarted(null);
    setAskedAbout(askingAbout ?? state.segmentIndex);
    try {
      setAskStarted(
        await callCore('lessons.ask', {
          path: { lesson_id: lessonId },
          body: { segment_id: about.id, question },
        }),
      );
    } catch (error) {
      setAskRefusal(refusalOf(error));
    } finally {
      setAskStarting(false);
    }
  };
  const stopAsk = (): void => {
    if (!askJob) return;
    setStopProblem(null);
    callCore('jobs.cancel', { path: { job_id: askJob.id } }).catch((error: unknown) => {
      setStopProblem(describeError(error));
    });
  };
  const removeAsk = (removed: Ask): void => {
    callCore('lessons.delete_ask', { path: { lesson_id: lessonId, ask_id: removed.id } }).then(
      // Read again, not worked out from the list as it was when the button was pressed:
      // two removed in quick succession would bring the first one back.
      () => asks.reload(),
      (error: unknown) => {
        toast.show({
          tone: 'danger',
          title: 'Couldn’t remove the question',
          description: describeError(error),
        });
      },
    );
  };
  const aboutThisPart = asksAbout(kept, segment.id);
  const notesShown = notesOpen.has(segment.id);
  const askedPart = askingAbout === null ? null : (lesson.segments[askingAbout] ?? null);

  // The line the foot of the screen shows: the one being said; the first before anything
  // has been, and the last once everything has, so that the band is never empty.
  const lineShown = settled ? beats.length - 1 : Math.max(0, state.beatIndex);
  const caption =
    beats.length > 0 && transcriptShown ? (
      <aside
        className={cx(styles.captions, everyLine && styles.captionsOpen)}
        aria-label="Transcript"
      >
        <h3 className="ad-visually-hidden">Transcript</h3>
        {/* With every line shown the list can be longer than its room and scrolls: a
            region that scrolls has to be reachable from the keyboard to be scrolled. */}
        <ol
          ref={lines}
          className={styles.transcript}
          // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex
          tabIndex={everyLine ? 0 : undefined}
          aria-label={everyLine ? 'Every line of this part' : undefined}
        >
          {beats.map((beat, index) => {
            const current = index === state.beatIndex && !settled;
            const said = settled || index < state.beatsStarted;
            return (
              <li
                key={index}
                className={cx(
                  styles.beat,
                  said && styles.beatSpoken,
                  current && styles.beatCurrent,
                  index === lineShown && styles.beatShown,
                )}
                aria-current={current ? 'true' : undefined}
              >
                {current && state.word ? (
                  <SpokenText text={beat.text} word={state.word} />
                ) : (
                  beat.text
                )}
              </li>
            );
          })}
        </ol>
        {beats.length > 1 ? (
          <IconButton
            variant="stage"
            size="small"
            label={everyLine ? 'Show one line at a time' : 'Show every line'}
            icon={everyLine ? <ChevronsDownUp /> : <ChevronsUpDown />}
            aria-expanded={everyLine}
            onClick={() => setEveryLine((open) => !open)}
          />
        ) : null}
      </aside>
    ) : null;

  return (
    <Page
      title={lesson.title}
      eyebrow={eyebrow}
      density="compact"
      actions={
        // What a lesson is made from and who wrote it is one press away, and out of the
        // way of the lesson itself (ADR-036).
        <InfoPopover label="About this lesson" icon={<Info />} title="About this lesson">
          <p>
            {GROUNDING_NOTE[lesson.grounding]}. About {lesson.estimated_minutes} minutes.
          </p>
          {/* Where in the learner's own materials the lesson draws from: named, never invented. */}
          {lesson.source_refs.length > 0 ? (
            <p>
              Sources:{' '}
              {lesson.source_refs
                .map((source) => source.source_name + ', ' + source.locator)
                .join('; ')}
            </p>
          ) : null}
          {/* Who wrote it, where a model did. */}
          {data.written_by ? (
            <p>
              Written by {authorName(data.written_by, 'AI')}. AI can make mistakes.
              {data.written_by.note ? ` ${data.written_by.note}` : ''}
            </p>
          ) : null}
        </InfoPopover>
      }
    >
      {state.finished ? (
        <FinishedPanel
          data={data}
          whenSaved={saved}
          onLeave={onLeave}
          onReview={() => controller.restart()}
        />
      ) : (
        <div ref={theatre} className={styles.player}>
          <ol className={styles.parts} aria-label="Parts of this lesson">
            {lesson.segments.map((item, index) => {
              const current = index === state.segmentIndex;
              const reached = index <= state.furthest;
              return (
                <li key={item.id}>
                  <button
                    type="button"
                    className={cx(
                      styles.part,
                      index < state.furthest && styles.partDone,
                      current && styles.partCurrent,
                    )}
                    aria-current={current ? 'step' : undefined}
                    aria-label={`Part ${index + 1}: ${item.title}${reached ? '' : ' (not reached yet)'}`}
                    disabled={!reached || current}
                    onClick={() => controller.goTo(index)}
                  >
                    {index + 1}
                  </button>
                </li>
              );
            })}
          </ol>

          <div className={styles.body}>
            <SegmentStage
              key={segment.id}
              lessonId={lesson.lesson_id}
              segment={segment}
              scene={sceneFor(segment, pictures.scenes)}
              pending={isPictureComing(segment, pictures.pending)}
              state={state}
              controller={controller}
              cues={cues}
              caption={caption}
              position={
                <span className={styles.position} role="status">
                  Part {state.segmentIndex + 1} of {total}
                </span>
              }
            />
          </div>

          {asks.resource.status === 'error' ? (
            <p className={styles.note} role="alert">
              Couldn’t load your questions about this lesson.{' '}
              <Button size="small" variant="tertiary" onClick={asks.reload}>
                Try again
              </Button>
            </p>
          ) : null}
          {aboutThisPart.length > 0 ? (
            <section className={styles.asked} aria-label="Your questions about this part">
              <div>
                <Button
                  size="small"
                  variant="tertiary"
                  icon={notesShown ? <ChevronUp /> : <ChevronDown />}
                  aria-expanded={notesShown}
                  onClick={() =>
                    setNotesOpen((open) => {
                      const next = new Set(open);
                      if (!next.delete(segment.id)) next.add(segment.id);
                      return next;
                    })
                  }
                >
                  Your questions about this part ({aboutThisPart.length})
                </Button>
              </div>
              {notesShown ? (
                <ul className={styles.askedList}>
                  {aboutThisPart.map((item) => (
                    <li key={item.id} className={styles.askedItem}>
                      <AskNote ask={item} />
                      <IconButton
                        label="Remove question"
                        icon={<Trash2 />}
                        size="small"
                        onClick={() => removeAsk(item)}
                      />
                    </li>
                  ))}
                </ul>
              ) : null}
            </section>
          ) : null}

          <div className={styles.controls}>
            <div className={styles.controlGroup}>
              <Button
                variant="tertiary"
                icon={<ArrowLeft />}
                disabled={state.segmentIndex === 0}
                onClick={() => controller.previous()}
              >
                Previous
              </Button>
              {beats.length === 0 ? null : settled ? (
                <Button icon={<RotateCcw />} onClick={replay}>
                  Replay
                </Button>
              ) : (
                <Button
                  variant="primary"
                  icon={playing ? <Pause /> : <Play />}
                  onClick={() => (playing ? controller.pause() : controller.play())}
                >
                  {playing ? 'Pause' : state.status === 'paused' ? 'Resume' : 'Start'}
                </Button>
              )}
              {spoken ? (
                <Button
                  aria-pressed={aloud}
                  icon={aloud ? <Volume2 /> : <VolumeX />}
                  onClick={() => readAloud(!aloud)}
                >
                  Read aloud
                </Button>
              ) : null}
              {aloud ? (
                <Button
                  aria-pressed={wordsShown}
                  icon={<Captions />}
                  onClick={() => setWordsShown((shown) => !shown)}
                >
                  Transcript
                </Button>
              ) : null}
              {!spoken && preferences.narration ? (
                <span className={styles.note}>
                  No voice is installed, so narration is shown as text.
                </span>
              ) : null}
            </div>
            <div className={styles.controlGroup}>
              {!allowed ? <span className={styles.note}>Answer or skip to continue.</span> : null}
              {/* Busy, and still a button: opening it again is the way to watch the answer
                  being written, or to stop it. */}
              <Button
                variant="tertiary"
                icon={answering ? <Spinner size="small" /> : <Hand />}
                aria-busy={answering || undefined}
                onClick={openAsk}
              >
                {answering ? 'Answering' : 'Ask a question'}
              </Button>
              {explains ? (
                <Button variant="tertiary" icon={<MessageCircleQuestion />} onClick={sayUnhelpful}>
                  This didn’t help
                </Button>
              ) : null}
              <Button
                variant={settled && allowed ? 'primary' : 'secondary'}
                icon={last ? <Check /> : <ArrowRight />}
                disabled={!allowed}
                onClick={() => controller.next()}
              >
                {last ? 'Finish lesson' : 'Continue'}
              </Button>
              <IconButton
                label="Full screen"
                icon={screen.active ? <Minimize /> : <Maximize />}
                aria-pressed={screen.active}
                onClick={screen.toggle}
              />
            </div>
          </div>
        </div>
      )}
      {askedPart !== null && askingAbout !== null ? (
        <AskDialog
          partLabel={`Part ${askingAbout + 1}: ${askedPart.title}`}
          kind={askedPart.type}
          unanswered={
            askedPart.type === 'checkpoint' &&
            askingAbout === state.segmentIndex &&
            !canContinue(state, askedPart)
          }
          job={askJob}
          starting={askStarting}
          failure={askRefusal ?? jobFailure(askJob)}
          refused={askRefusal !== null}
          stopProblem={stopProblem}
          answer={freshAnswer}
          onAsk={(question) => void ask(question)}
          onStop={stopAsk}
          onAnother={() => {
            setAskStarted(null);
            setAskRefusal(null);
          }}
          onClose={() => {
            setAskingAbout(null);
            setStopProblem(null);
            // An answer that has been read, or a failure that has been seen, is put away.
            if (!answering) {
              setAskStarted(null);
              setAskRefusal(null);
              setAskedAbout(null);
            }
          }}
        />
      ) : null}
      {unhelpful !== null ? (
        <UnhelpfulDialog
          lesson={lesson}
          report={unhelpful}
          canSkipToQuestion={controller.nextQuestionIndex() !== null}
          onSkipToQuestion={() => {
            setUnhelpful(null);
            controller.skipToNextQuestion();
          }}
          onClose={() => setUnhelpful(null)}
        />
      ) : null}
    </Page>
  );
}

function sceneFor(segment: LessonSegment, scenes: readonly SceneArtifact[]): SceneArtifact | null {
  const reference = 'scene' in segment ? segment.scene : null;
  if (!reference) return null;
  return scenes.find((scene) => scene.id === reference.scene_id) ?? null;
}

/** Whether this part's picture is still being drawn. */
function isPictureComing(segment: LessonSegment, coming: ReadonlySet<string>): boolean {
  const reference = 'scene' in segment ? segment.scene : null;
  return reference ? coming.has(reference.scene_id) : false;
}

/** The narration being spoken, with the word the narrator has reached marked. */
function SpokenText({ text, word }: { text: string; word: { start: number; length: number } }) {
  const end = word.start + word.length;
  return (
    <>
      {text.slice(0, word.start)}
      <mark className={styles.word}>{text.slice(word.start, end)}</mark>
      {text.slice(end)}
    </>
  );
}

/** What the current segment puts on screen: a scene, the board, a question, or a prompt. */
function SegmentStage({
  lessonId,
  segment,
  scene,
  pending,
  state,
  controller,
  cues,
  caption,
  position,
}: {
  lessonId: string;
  segment: LessonSegment;
  /** The part's picture, as the lesson has it now. */
  scene: SceneArtifact | null;
  /** The picture is still being drawn (ADR-031). */
  pending: boolean;
  state: PlaybackState;
  controller: LessonController;
  cues: SceneCues;
  /** The words being said, for the foot of whatever this part puts on the screen. */
  caption: ReactNode;
  /** Where in the lesson this part comes ("Part 2 of 10"). */
  position: ReactNode;
}) {
  const player = useRef<ScenePlayerHandle>(null);
  const [sceneStatus, setSceneStatus] = useState<PlayerStatus | null>(null);
  const [describing, setDescribing] = useState(false);
  // The picture this visit to the part shows. One that arrives once the part has begun is
  // not sprung on the learner in the middle of a sentence: it is offered, and shown when
  // they ask. Before the part has begun, it simply takes its place.
  const [picture, setPicture] = useState<SceneArtifact | null>(scene);
  if (scene !== null && picture === null && state.status === 'ready') setPicture(scene);
  const arrived = scene !== null && picture === null;

  // While this part is on screen, its scene is the one the narration cues.
  useEffect(
    () =>
      cues.attach(segment.id, {
        next: () => player.current?.next(),
        reset: () => player.current?.reset(),
      }),
    [cues, segment.id],
  );

  const beats = segment.narration ?? [];
  const revisiting = state.segmentIndex < state.furthest;
  const settled = state.status === 'done' || state.status === 'waiting';
  const waitingToStart = state.status === 'ready' && !revisiting && beats.length > 0;

  // An interaction is live from the start. Any other scene follows the narration:
  // it holds on its first frame until the lesson starts, and pauses when it pauses.
  // A part that is being looked at again simply shows its picture.
  //
  // A picture that was meant to be operated can come out as an animation. The lesson is
  // then stored as showing one; a lesson opened before the picture arrived still calls
  // the part an interaction, so the picture itself is asked what it is.
  const live = segment.type === 'interaction' && (picture?.interactive ?? true);
  const wantPlaying =
    live || (state.status === 'ready' ? !waitingToStart : state.status !== 'paused');
  useEffect(() => {
    if (sceneStatus === 'paused' && wantPlaying) player.current?.play();
    else if (!wantPlaying && (sceneStatus === 'playing' || sceneStatus === 'interactive')) {
      player.current?.pause();
    }
  }, [wantPlaying, sceneStatus]);

  const shown = (revisiting || settled ? beats : beats.slice(0, state.beatsStarted)).flatMap(
    (beat) => (beat.show ? [beat.show] : []),
  );
  const reference = 'scene' in segment ? (segment.scene ?? null) : null;
  const describable = picture !== null && reference !== null && sceneStatus !== 'failed';

  // What the part is and where in the lesson it comes, along the top of whatever it shows.
  const where = (
    <div className={styles.where}>
      <h2 className={styles.segmentTitle}>{segment.title}</h2>
      <span className={styles.whereTools}>
        {describable ? (
          <IconButton
            variant="stage"
            size="small"
            label={describing ? 'Hide description' : 'Describe this picture'}
            icon={<AlignLeft />}
            aria-expanded={describing}
            onClick={() => setDescribing((open) => !open)}
          />
        ) : null}
        {position}
      </span>
    </div>
  );
  // A part puts one thing on the screen, now and then two: a picture, or the words that
  // stand in for it, and under that a board. The line along the top and the words along
  // the foot go to the first.
  const framed = { header: where, caption };
  const below = reference ? { header: undefined, caption: undefined } : framed;

  if (segment.type === 'checkpoint') {
    return (
      <div className={cx(styles.stage, styles.stageQuestion)}>
        {where}
        <CheckpointPanel
          lessonId={lessonId}
          question={segment.question}
          onAnswered={() => controller.markAnswered()}
        />
      </div>
    );
  }

  return (
    <div className={styles.stage}>
      {/* What to try is said only while there is something to try it on: a picture that
          is not there, or did not run, is told in words below instead. */}
      {segment.type === 'interaction' && picture && live && sceneStatus !== 'failed' ? (
        <Callout tone="info" title="Try it">
          <MathText text={segment.prompt} />
        </Callout>
      ) : null}

      {picture && reference ? (
        <>
          <ScenePlayer
            ref={player}
            source={picture.source}
            sceneName={picture.scene_class}
            title={segment.title}
            autoplay={live}
            onStage
            {...framed}
            fallback={
              <p>
                <MathText text={reference.fallback_text} />
              </p>
            }
            onStart={waitingToStart ? () => controller.play() : undefined}
            onStatusChange={(status) => {
              setSceneStatus(status);
              cues.setHolding(segment.id, status === 'interactive');
            }}
            onSceneEvent={(event) => {
              if (event.name === 'explored' || event.name === 'passed') controller.markExplored();
            }}
          />
          {/* The picture in words, for whoever asks. A scene that failed is already
              showing them in its place. */}
          {describing && describable ? (
            <p className={styles.alternativeText}>
              <MathText text={reference.fallback_text} />
            </p>
          ) : null}
          {state.explored ? (
            <p className={styles.note} role="status">
              Keep exploring, or continue when you’re ready.
            </p>
          ) : null}
        </>
      ) : reference ? (
        // No picture to show here: it is still being drawn, it arrived after this part had
        // begun, or the core withheld it (it is not something Adle will run). Either way
        // the same idea is said in words.
        <StageFrame {...framed}>
          <div className={styles.board}>
            <p>
              <MathText text={reference.fallback_text} />
            </p>
            {arrived ? (
              <div className={styles.pictureReady} role="status">
                <span>The picture is ready.</span>
                <Button size="small" icon={<Play />} onClick={() => setPicture(scene)}>
                  Show picture
                </Button>
              </div>
            ) : (
              <p className={styles.boardEmpty} role={pending ? 'status' : undefined}>
                {pending
                  ? 'This picture is still being drawn. It’ll appear here when it’s ready.'
                  : 'The picture isn’t available. Here’s the same idea in words.'}
              </p>
            )}
          </div>
        </StageFrame>
      ) : null}

      {segment.type === 'reflection' ? (
        <StageFrame {...below}>
          <div className={styles.board}>
            <p className={styles.prompt}>
              <MathText text={segment.prompt} />
            </p>
            <p className={styles.boardEmpty}>Nothing to submit. Take your time, then continue.</p>
          </div>
        </StageFrame>
      ) : null}

      {segment.type === 'worked_example' || (!reference && segment.type !== 'reflection') ? (
        <StageFrame {...below}>
          <div className={styles.board}>
            {segment.type === 'worked_example' ? (
              <p className={styles.problemStatement}>
                <MathText text={segment.problem} />
              </p>
            ) : null}
            {shown.length > 0 ? (
              <Points ordered={segment.type === 'worked_example'} items={shown} />
            ) : (
              // Nothing has been put on the board yet: it says what this part is about,
              // as the first slide of a talk does.
              <div className={styles.titleCard}>
                <p className={styles.titleCardTitle} aria-hidden="true">
                  {segment.title}
                </p>
                {state.status === 'ready' ? (
                  <p className={styles.boardEmpty}>Press Start when you’re ready.</p>
                ) : null}
              </div>
            )}
          </div>
        </StageFrame>
      ) : shown.length > 0 ? (
        <Points ordered={false} items={shown} />
      ) : null}
    </div>
  );
}

function Points({ ordered, items }: { ordered: boolean; items: string[] }) {
  const List = ordered ? 'ol' : 'ul';
  return (
    <List className={styles.points} aria-live="polite">
      {items.map((item) => (
        <li key={item}>
          <MathText text={item} />
        </li>
      ))}
    </List>
  );
}

/** Shown when the last part is done: what the lesson was for, and what it changed. */
function FinishedPanel({
  data,
  whenSaved,
  onLeave,
  onReview,
}: {
  data: LessonForPlayer;
  /** Resolves once the lesson has been recorded as finished. */
  whenSaved: () => Promise<void>;
  onLeave: () => void;
  onReview: () => void;
}) {
  const { navigate } = useRouter();
  const rest = useBreak();
  const conceptId = data.lesson.concept_ids[0] ?? '';
  const evidence = useResource(`lesson-evidence:${data.lesson.lesson_id}`, () =>
    callCore('learner.concept_evidence', { path: { concept_id: conceptId } }),
  );
  const knowledge = evidence.resource.status === 'ready' ? evidence.resource.data.knowledge : null;
  // Asked for only once the lesson is recorded as finished: asked any sooner, the answer
  // could still say "continue this lesson".
  const overview = useResource(`lesson-next:${data.lesson.lesson_id}`, async () => {
    await whenSaved();
    return callCore('learning.overview', { path: { course_id: data.lesson.course_id } });
  });

  return (
    <section className={styles.finished} aria-labelledby="lesson-finished">
      <h2 id="lesson-finished" className={styles.finishedTitle}>
        Lesson complete
      </h2>
      <div>
        <p>You worked on:</p>
        <ul className={styles.objectives}>
          {data.lesson.objectives.map((objective) => (
            <li key={objective.statement}>
              <MathText text={objective.statement} />
            </li>
          ))}
        </ul>
      </div>
      {evidence.resource.status === 'loading' ? (
        <p className={styles.note} role="status">
          Updating your progress…
        </p>
      ) : evidence.resource.status === 'error' ? (
        <p className={styles.note}>
          Couldn’t load your progress just now. It’s saved, and the course page will show it.
        </p>
      ) : knowledge ? (
        <div>
          <p className={styles.finishedLine}>
            <span>Status:</span>
            <Badge tone={KNOWLEDGE_TONE[knowledge.state]}>{knowledge.label}</Badge>
          </p>
          {knowledge.missing.length > 0 ? (
            <p className={styles.note}>Still needed: {knowledge.missing.join('; ')}.</p>
          ) : (
            <p className={styles.note}>A review later will check that it stuck.</p>
          )}
        </div>
      ) : null}
      {overview.resource.status === 'loading' ? (
        <p className={styles.note} role="status">
          Planning your next step…
        </p>
      ) : overview.resource.status === 'ready' ? (
        <div className={styles.finishedNext}>
          <NextSteps plan={overview.resource.data.plan} courseId={data.lesson.course_id} />
        </div>
      ) : null}
      <div className={styles.controlGroup}>
        {/* With a suggestion on screen, going back is the quieter choice; without one it
            is the way forward. */}
        <Button
          variant={overview.resource.status === 'ready' ? 'secondary' : 'primary'}
          onClick={onLeave}
        >
          Back to course
        </Button>
        <Button variant="tertiary" icon={<RotateCcw />} onClick={onReview}>
          Replay lesson
        </Button>
        {/* The end of a lesson is a natural place to stop for a few minutes. Offered, never urged. */}
        <Button
          variant="tertiary"
          icon={<Coffee />}
          onClick={() => {
            if (!rest.times) rest.start(USUAL_BREAK_MINUTES);
            // Not back into this lesson, which would open again at its first part: on to
            // the course, where the next step is.
            rest.returnVia({ name: 'course', courseId: data.lesson.course_id, tab: 'learn' });
            navigate({ name: 'break' });
          }}
        >
          {rest.times ? 'Back to your break' : 'Take a ' + USUAL_BREAK_MINUTES + '-minute break'}
        </Button>
      </div>
    </section>
  );
}
