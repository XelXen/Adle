import {
  ArrowLeft,
  ArrowRight,
  Captions,
  Check,
  ChevronDown,
  ChevronUp,
  Coffee,
  Hand,
  MessageCircleQuestion,
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
  LoadingState,
  Page,
  useToast,
} from '@adle/design-system';

import type { PlayerStatus } from '../../../../player/host/WanimPlayerAdapter';
import { useBreak } from '../../app/BreakContext';
import { useRouter } from '../../app/router';
import { MathText } from '../../components/MathText';
import { NextSteps } from '../../components/NextSteps';
import { ScenePlayer, type ScenePlayerHandle } from '../../components/ScenePlayer';
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
import { answeredAskId, asksAbout } from '../../lib/asks';
import { USUAL_BREAK_MINUTES } from '../../lib/breaks';
import { getBridge } from '../../lib/bridge';
import { callCore, CoreRequestError, describeError } from '../../lib/core-client';
import { type JobFailure, jobFailure, refusalOf } from '../../lib/generation';
import { isJobActive, useJob } from '../../lib/use-job';
import { useResource } from '../../lib/use-resource';
import { KNOWLEDGE_TONE } from '../course/ConceptDetail';
import { AskDialog, AskNote } from './AskDialog';
import { CheckpointPanel } from './CheckpointPanel';
import styles from './Lesson.module.css';
import { type ReportState, UnhelpfulDialog } from './UnhelpfulDialog';

const GROUNDING_NOTE: Record<LessonForPlayer['lesson']['grounding'], string> = {
  sample: 'A sample lesson written by Adle.',
  materials: 'Based on your own materials.',
  general_knowledge: 'From general knowledge, not from your materials.',
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
      Back to the course
    </Button>
  );

  if (
    lesson.resource.status === 'loading' ||
    preferences.resource.status === 'loading' ||
    voices.resource.status === 'loading'
  ) {
    return (
      <Page title="Lesson" eyebrow={back}>
        <LoadingState title="Opening the lesson…" />
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
                ? 'This lesson needs to be made again'
                : 'The lesson could not be opened'
          }
          description={describeError(error)}
          actions={
            code === null ? (
              <Button onClick={lesson.reload}>Try again</Button>
            ) : (
              <Button variant="primary" onClick={leave}>
                Back to the course
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
  const { lesson, scenes } = data;
  const [{ controller, cues, save, saved, silent, spoken }] = useState(() =>
    openSession(data, preferences, voices, (error) =>
      toast.show({
        tone: 'danger',
        title: 'Your place in this lesson could not be saved',
        description: describeError(error),
      }),
    ),
  );
  const state = useSyncExternalStore(controller.subscribe, controller.getState);
  const [aloud, setAloud] = useState(preferences.narration && spoken !== null);
  const [wordsShown, setWordsShown] = useState(preferences.captions);
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
  const [askStarting, setAskStarting] = useState(false);
  const [askRefusal, setAskRefusal] = useState<JobFailure | null>(null);
  /** The parts whose kept questions are unfolded. */
  const [notesOpen, setNotesOpen] = useState<ReadonlySet<string>>(new Set());
  const askJob = useJob(askStarted, (finished) => {
    asks.reload();
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
        title: 'Your question has an answer',
        description: index >= 0 ? `It is beside part ${index + 1} of this lesson.` : undefined,
      });
    }
  });
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
    // A new question starts from an empty page: the last answer is beside its part already.
    if (!answering) {
      setAskStarted(null);
      setAskRefusal(null);
    }
    setAskingAbout(state.segmentIndex);
  };
  const ask = async (question: string): Promise<void> => {
    const about = lesson.segments[askingAbout ?? state.segmentIndex];
    if (!about) return;
    setAskStarting(true);
    setAskRefusal(null);
    setAskStarted(null);
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
    callCore('jobs.cancel', { path: { job_id: askJob.id } }).catch((error: unknown) => {
      toast.show({
        tone: 'danger',
        title: 'It could not be stopped',
        description: describeError(error),
      });
    });
  };
  const removeAsk = (removed: Ask): void => {
    callCore('lessons.delete_ask', { path: { lesson_id: lessonId, ask_id: removed.id } }).then(
      () => {
        if (asks.resource.status !== 'ready') return;
        const data = asks.resource.data;
        asks.setData({ ...data, asks: data.asks.filter((item) => item.id !== removed.id) });
      },
      (error: unknown) => {
        toast.show({
          tone: 'danger',
          title: 'The question could not be removed',
          description: describeError(error),
        });
      },
    );
  };
  const aboutThisPart = asksAbout(kept, segment.id);
  const notesShown = notesOpen.has(segment.id);
  const askedPart = askingAbout === null ? null : (lesson.segments[askingAbout] ?? null);

  return (
    <Page
      title={lesson.title}
      eyebrow={eyebrow}
      description={
        <>
          <span className={styles.finishedLine}>
            <Badge tone={lesson.grounding === 'sample' ? 'accent' : 'neutral'}>
              {GROUNDING_NOTE[lesson.grounding]}
            </Badge>
            <span>About {lesson.estimated_minutes} minutes</span>
          </span>
          {/* Where in the learner's own materials the lesson draws from: named, never invented. */}
          {lesson.source_refs.length > 0 ? (
            <span className={styles.sources}>
              Draws on:{' '}
              {lesson.source_refs
                .map((source) => source.source_name + ', ' + source.locator)
                .join('; ')}
            </span>
          ) : null}
        </>
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
        <div className={styles.player}>
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

          <div className={styles.where}>
            <h2 className={styles.segmentTitle}>{segment.title}</h2>
            <span className={styles.position} role="status">
              Part {state.segmentIndex + 1} of {total}
            </span>
          </div>

          <div className={cx(styles.body, beats.length > 0 && transcriptShown && styles.withSide)}>
            <SegmentStage
              key={segment.id}
              lessonId={lesson.lesson_id}
              segment={segment}
              scene={sceneFor(segment, scenes)}
              state={state}
              controller={controller}
              cues={cues}
            />
            {beats.length > 0 && transcriptShown ? (
              <aside className={styles.side} aria-label="Transcript">
                <h3 className={styles.sideTitle}>Transcript</h3>
                <ol className={styles.transcript}>
                  {beats.map((beat, index) => {
                    const current = index === state.beatIndex && !settled;
                    const spoken = settled || index < state.beatsStarted;
                    return (
                      <li
                        key={index}
                        className={cx(
                          styles.beat,
                          spoken && styles.beatSpoken,
                          current && styles.beatCurrent,
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
              </aside>
            ) : null}
          </div>

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
                        label="Remove this question and its answer"
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
                  Play again
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
                  No voice is installed on this computer, so the narration is shown as text.
                </span>
              ) : null}
            </div>
            <div className={styles.controlGroup}>
              {!allowed ? (
                <span className={styles.note}>Answer or skip the question to continue.</span>
              ) : null}
              <Button variant="tertiary" icon={<Hand />} loading={answering} onClick={openAsk}>
                {answering ? 'Answering' : 'Ask a question'}
              </Button>
              {explains ? (
                <Button variant="tertiary" icon={<MessageCircleQuestion />} onClick={sayUnhelpful}>
                  This did not help
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
          answer={freshAnswer}
          onAsk={(question) => void ask(question)}
          onStop={stopAsk}
          onAnother={() => {
            setAskStarted(null);
            setAskRefusal(null);
          }}
          onClose={() => {
            setAskingAbout(null);
            // An answer that has been read, or a failure that has been seen, is put away.
            if (!answering) {
              setAskStarted(null);
              setAskRefusal(null);
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

function sceneFor(segment: LessonSegment, scenes: SceneArtifact[]): SceneArtifact | null {
  const reference = 'scene' in segment ? segment.scene : null;
  if (!reference) return null;
  return scenes.find((scene) => scene.id === reference.scene_id) ?? null;
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
  state,
  controller,
  cues,
}: {
  lessonId: string;
  segment: LessonSegment;
  scene: SceneArtifact | null;
  state: PlaybackState;
  controller: LessonController;
  cues: SceneCues;
}) {
  const player = useRef<ScenePlayerHandle>(null);
  const [sceneStatus, setSceneStatus] = useState<PlayerStatus | null>(null);
  const [describing, setDescribing] = useState(false);

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
  const wantPlaying =
    segment.type === 'interaction' ||
    (state.status === 'ready' ? !waitingToStart : state.status !== 'paused');
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

  if (segment.type === 'checkpoint') {
    return (
      <div className={styles.stage}>
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
      {segment.type === 'interaction' ? (
        <Callout tone="info" title="Try it">
          <MathText text={segment.prompt} />
        </Callout>
      ) : null}

      {scene && reference ? (
        <>
          <ScenePlayer
            ref={player}
            source={scene.source}
            sceneName={scene.scene_class}
            title={segment.title}
            autoplay={segment.type === 'interaction'}
            fallback={
              <p>
                <MathText text={reference.fallback_text} />
              </p>
            }
            onStatusChange={(status) => {
              setSceneStatus(status);
              cues.setHolding(segment.id, status === 'interactive');
            }}
            onSceneEvent={(event) => {
              if (event.name === 'explored' || event.name === 'passed') controller.markExplored();
            }}
          />
          {/* A scene that failed is already showing its description in its place. */}
          {sceneStatus !== 'failed' ? (
            <div className={styles.alternative}>
              <div>
                <Button
                  size="small"
                  variant="tertiary"
                  aria-expanded={describing}
                  onClick={() => setDescribing((open) => !open)}
                >
                  {describing ? 'Hide the description' : 'Describe this picture in words'}
                </Button>
              </div>
              {describing ? (
                <p className={styles.alternativeText}>
                  <MathText text={reference.fallback_text} />
                </p>
              ) : null}
            </div>
          ) : null}
          {waitingToStart && segment.type !== 'interaction' ? (
            <p className={styles.note}>Press Start to play the animation with its narration.</p>
          ) : null}
          {state.explored ? (
            <p className={styles.note} role="status">
              You tried it. Carry on exploring, or continue when you are ready.
            </p>
          ) : null}
        </>
      ) : reference ? (
        // The core withheld this scene (it is not something Adle will run): say it in words.
        <div className={styles.board}>
          <p>
            <MathText text={reference.fallback_text} />
          </p>
          <p className={styles.boardEmpty}>
            The picture for this part is not available, so here is the same idea in words.
          </p>
        </div>
      ) : null}

      {segment.type === 'reflection' ? (
        <div className={styles.board}>
          <p className={styles.prompt}>
            <MathText text={segment.prompt} />
          </p>
          <p className={styles.boardEmpty}>
            There is nothing to submit here. Take the time you want, then continue.
          </p>
        </div>
      ) : null}

      {segment.type === 'worked_example' || (!reference && segment.type !== 'reflection') ? (
        <div className={styles.board}>
          {segment.type === 'worked_example' ? (
            <p className={styles.problemStatement}>
              <MathText text={segment.problem} />
            </p>
          ) : null}
          {shown.length > 0 ? (
            <Points ordered={segment.type === 'worked_example'} items={shown} />
          ) : (
            <p className={styles.boardEmpty}>
              {state.status === 'ready'
                ? 'Press Start when you are ready.'
                : 'Listen, or read along in the transcript.'}
            </p>
          )}
        </div>
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
          Reading what your answers showed…
        </p>
      ) : evidence.resource.status === 'error' ? (
        <p className={styles.note}>
          What your answers showed could not be read just now. It is saved, and the course page will
          show it.
        </p>
      ) : knowledge ? (
        <div>
          <p className={styles.finishedLine}>
            <span>Where this concept stands:</span>
            <Badge tone={KNOWLEDGE_TONE[knowledge.state]}>{knowledge.label}</Badge>
          </p>
          {knowledge.missing.length > 0 ? (
            <p className={styles.note}>Still needed: {knowledge.missing.join('; ')}.</p>
          ) : (
            <p className={styles.note}>
              Adle will check again after a while to see that it has stuck.
            </p>
          )}
        </div>
      ) : null}
      {overview.resource.status === 'loading' ? (
        <p className={styles.note} role="status">
          Working out what to do next…
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
          Back to the course
        </Button>
        <Button variant="tertiary" icon={<RotateCcw />} onClick={onReview}>
          Go through it again
        </Button>
        {/* The end of a lesson is a natural place to stop for a few minutes. Offered, never urged. */}
        <Button
          variant="tertiary"
          icon={<Coffee />}
          onClick={() => {
            if (!rest.times) rest.start(USUAL_BREAK_MINUTES);
            navigate({ name: 'break' });
          }}
        >
          {rest.times ? 'Back to your break' : 'Take a ' + USUAL_BREAK_MINUTES + '-minute break'}
        </Button>
      </div>
    </section>
  );
}
