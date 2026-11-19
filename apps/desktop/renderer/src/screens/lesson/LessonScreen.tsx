import {
  ArrowLeft,
  ArrowRight,
  Captions,
  Check,
  Pause,
  Play,
  RotateCcw,
  Volume2,
  VolumeX,
} from 'lucide-react';
import { type ReactNode, useEffect, useRef, useState, useSyncExternalStore } from 'react';

import type { LearnerPreferences, LessonForPlayer, SceneArtifact } from '@adle/contracts';
import {
  Badge,
  Button,
  Callout,
  cx,
  ErrorState,
  LoadingState,
  Page,
  useToast,
} from '@adle/design-system';

import type { PlayerStatus } from '../../../../player/host/WanimPlayerAdapter';
import { useRouter } from '../../app/router';
import { MathText } from '../../components/MathText';
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
import { callCore, CoreRequestError, describeError } from '../../lib/core-client';
import { useResource } from '../../lib/use-resource';
import { KNOWLEDGE_TONE } from '../course/ConceptDetail';
import { CheckpointPanel } from './CheckpointPanel';
import styles from './Lesson.module.css';

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
  const save = (position: number, completed: boolean): void => {
    callCore('lessons.save_progress', {
      path: { lesson_id: lesson.lesson_id },
      body: { position, completed },
    }).catch((error: unknown) => {
      // Said once: a lesson that cannot save its place would say so again at every part.
      if (warned) return;
      warned = true;
      onSaveFailed(error);
    });
  };
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
  return { controller, cues, save, silent, spoken };
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
  const leave = (): void => navigate({ name: 'course', courseId, tab: 'curriculum' });
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
  const [{ controller, cues, save, silent, spoken }] = useState(() =>
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

  return (
    <Page
      title={lesson.title}
      eyebrow={eyebrow}
      description={
        <span className={styles.finishedLine}>
          <Badge tone={lesson.grounding === 'sample' ? 'accent' : 'neutral'}>
            {GROUNDING_NOTE[lesson.grounding]}
          </Badge>
          <span>About {lesson.estimated_minutes} minutes</span>
        </span>
      }
    >
      {state.finished ? (
        <FinishedPanel data={data} onLeave={onLeave} onReview={() => controller.restart()} />
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
  onLeave,
  onReview,
}: {
  data: LessonForPlayer;
  onLeave: () => void;
  onReview: () => void;
}) {
  const conceptId = data.lesson.concept_ids[0] ?? '';
  const evidence = useResource(`lesson-evidence:${data.lesson.lesson_id}`, () =>
    callCore('learner.concept_evidence', { path: { concept_id: conceptId } }),
  );
  const knowledge = evidence.resource.status === 'ready' ? evidence.resource.data.knowledge : null;

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
      <div className={styles.controlGroup}>
        <Button variant="primary" onClick={onLeave}>
          Back to the course
        </Button>
        <Button icon={<RotateCcw />} onClick={onReview}>
          Go through it again
        </Button>
      </div>
    </section>
  );
}
