import {
  Link as LinkIcon,
  Pencil,
  Play,
  RotateCcw,
  Search,
  Sparkles,
  Trash2,
  Unlink,
} from 'lucide-react';
import { useId, useState } from 'react';

import type {
  Concept,
  ConceptEvidence,
  Curriculum,
  Job,
  LessonRequest,
  LessonSummary,
  Passage,
} from '@adle/contracts';
import {
  Badge,
  Button,
  Callout,
  Card,
  cx,
  IconButton,
  Select,
  Spinner,
  type Tone,
  useToast,
} from '@adle/design-system';

import { GenerationStatus } from '../../components/GenerationStatus';
import { callCore, describeError } from '../../lib/core-client';
import { formatRelativeDay } from '../../lib/format';
import { WhatIsSent } from '../../components/WhatIsSent';
import { type JobFailure, lessonDisclosure } from '../../lib/generation';
import { useLessonRules, waysFor } from '../../lib/lesson-rules';
import { isJobActive } from '../../lib/use-job';
import styles from './Curriculum.module.css';
import {
  describeLesson,
  describeLocation,
  directDependents,
  lessonAction,
} from './curriculum-model';

type KnowledgeState = Concept['knowledge']['state'];
type SelfReport = NonNullable<Concept['knowledge']['self_report']>;

export const KNOWLEDGE_TONE: Record<KnowledgeState, Tone> = {
  not_assessed: 'neutral',
  building: 'info',
  needs_evidence: 'accent',
  demonstrated: 'success',
};

const SELF_REPORTS: readonly { value: SelfReport; label: string }[] = [
  { value: 'new', label: 'New to me' },
  { value: 'some', label: 'I know some of it' },
  { value: 'confident', label: 'I know this well' },
];

const ORIGIN_NOTE: Partial<Record<Concept['origin'], string>> = {
  outline: 'From a heading in your materials.',
  model: 'Suggested by AI.',
  sample: 'Part of the sample course.',
};

type PassageState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'ready'; conceptId: string; passages: Passage[] }
  | { status: 'error'; message: string };

type HistoryState =
  | { status: 'closed' }
  | { status: 'loading' }
  | { status: 'ready'; conceptId: string; evidence: ConceptEvidence }
  | { status: 'error'; message: string };

/** The lessons that teach one concept, or where the course is in finding them. */
export type ConceptLessons =
  | { status: 'loading' }
  | { status: 'error'; message: string; retry: () => void }
  | { status: 'ready'; lessons: readonly LessonSummary[] };

/** A way of teaching a lesson can be asked to use. */
export type TeachingStrategy = NonNullable<NonNullable<LessonRequest['strategy']>>;

export const STRATEGY_CHOICES: readonly { value: TeachingStrategy | ''; label: string }[] = [
  { value: '', label: 'Automatic' },
  { value: 'visual', label: 'Visual first' },
  { value: 'worked_example', label: 'Worked example' },
  { value: 'analogy', label: 'Everyday analogy' },
  { value: 'mathematical', label: 'Step-by-step math' },
  { value: 'computational', label: 'Calculation by hand' },
  { value: 'socratic', label: 'Guided questions' },
];

/** Where the making of a lesson for one concept stands. */
export interface LessonGeneration {
  /** The job writing a lesson for this concept, if this screen knows of one. */
  job: Job | null;
  /**
   * The lesson that job is writing can be started already, and is in the list: what is
   * still under way is its pictures (ADR-031).
   */
  lessonReady: boolean;
  /** The request to start one is on its way. */
  starting: boolean;
  /** Starting was refused before a job existed. */
  refusal: JobFailure | null;
  /** Where the request would go, as the core plans it: to put after "Sends to". */
  destination: string;
  /** How long a lesson usually takes there, in words, where that is known. */
  usualWait: string | null;
  /** The same in seconds, for sizing a break taken meanwhile. */
  usualSeconds: number | null;
  /** Ask for a lesson, in a chosen way of teaching or (with null) in whichever suits. */
  onCreate: (strategy: TeachingStrategy | null) => void;
  onCancel: () => void;
  onDismiss: () => void;
}

/** Everything about one concept: what it is, what it needs, where it comes from, what you have shown. */
export function ConceptDetail({
  concept,
  path,
  hasMaterials,
  lessons,
  generation,
  onOpenLesson,
  onRemoveLesson,
  onEdit,
  onRemove,
  onEditPrerequisites,
  onSelect,
  onChanged,
  onReload,
  subject,
}: {
  concept: Concept;
  path: readonly Concept[];
  hasMaterials: boolean;
  lessons: ConceptLessons;
  generation: LessonGeneration;
  onOpenLesson: (lessonId: string) => void;
  /** Ask to remove a lesson. The caller confirms first. */
  onRemoveLesson: (lesson: LessonSummary) => void;
  onEdit: () => void;
  onRemove: () => void;
  onEditPrerequisites: () => void;
  onSelect: (id: string) => void;
  /** A change that returned the whole curriculum. */
  onChanged: (curriculum: Curriculum) => void;
  /** A change after which the curriculum must be read again. */
  onReload: () => void;
  /** The kind of subject the course is: the teaching styles offered are those that suit it. */
  subject?: string | null;
}) {
  const toast = useToast();
  const headingId = useId();
  const historyId = useId();
  const [rating, setRating] = useState<SelfReport | null>(null);
  const [passages, setPassages] = useState<PassageState>({ status: 'idle' });
  const [history, setHistory] = useState<HistoryState>({ status: 'closed' });
  const [linking, setLinking] = useState<string | null>(null);
  const [strategy, setStrategy] = useState<TeachingStrategy | ''>('');
  // A lesson of history is not offered "Step-by-step math" (ADR-061).
  const rules = useLessonRules();
  const offered = waysFor(
    STRATEGY_CHOICES,
    rules.resource.status === 'ready' ? rules.resource.data : null,
    subject,
  );

  const dependents = directDependents(path, concept.id);
  const linkedSections = new Set(concept.source_refs.map((ref) => ref.section_id));
  // State loaded for another concept is not shown for this one.
  const shownPassages =
    passages.status === 'ready' && passages.conceptId !== concept.id
      ? ({ status: 'idle' } as const)
      : passages;
  const shownHistory =
    history.status === 'ready' && history.conceptId !== concept.id
      ? ({ status: 'closed' } as const)
      : history;

  const report = (text: string) => (error: unknown) =>
    toast.show({ tone: 'danger', title: text, description: describeError(error) });

  const rate = async (level: SelfReport): Promise<void> => {
    if (rating || concept.knowledge.self_report === level) return;
    setRating(level);
    try {
      const evidence = await callCore('learner.self_rate', {
        path: { concept_id: concept.id },
        body: { level },
      });
      if (shownHistory.status === 'ready') {
        setHistory({ status: 'ready', conceptId: concept.id, evidence });
      }
      onReload();
    } catch (error) {
      report('Couldn’t save that')(error);
    } finally {
      setRating(null);
    }
  };

  const toggleHistory = async (): Promise<void> => {
    if (shownHistory.status !== 'closed') {
      setHistory({ status: 'closed' });
      return;
    }
    setHistory({ status: 'loading' });
    try {
      const evidence = await callCore('learner.concept_evidence', {
        path: { concept_id: concept.id },
      });
      setHistory({ status: 'ready', conceptId: concept.id, evidence });
    } catch (error) {
      setHistory({ status: 'error', message: describeError(error) });
    }
  };

  const findPassages = async (): Promise<void> => {
    setPassages({ status: 'loading' });
    try {
      const found = await callCore('curriculum.related_passages', {
        path: { concept_id: concept.id },
        query: { limit: 5 },
      });
      setPassages({ status: 'ready', conceptId: concept.id, passages: found.passages });
    } catch (error) {
      setPassages({ status: 'error', message: describeError(error) });
    }
  };

  const link = async (sectionId: string): Promise<void> => {
    setLinking(sectionId);
    try {
      onChanged(
        await callCore('curriculum.add_source_ref', {
          path: { concept_id: concept.id },
          body: { section_id: sectionId },
        }),
      );
    } catch (error) {
      report('Couldn’t add the link')(error);
    } finally {
      setLinking(null);
    }
  };

  const unlink = async (refId: number): Promise<void> => {
    try {
      onChanged(
        await callCore('curriculum.remove_source_ref', {
          path: { concept_id: concept.id, ref_id: refId },
        }),
      );
    } catch (error) {
      report('Couldn’t remove the link')(error);
    }
  };

  return (
    <Card as="section" aria-labelledby={headingId} className={styles.detail}>
      <h3 id={headingId} className={styles.detailTitle}>
        {concept.title}
      </h3>

      {concept.summary ? <p className={styles.detailSummary}>{concept.summary}</p> : null}
      {ORIGIN_NOTE[concept.origin] ? (
        <p className={styles.muted}>{ORIGIN_NOTE[concept.origin]}</p>
      ) : null}

      {/* What the concept is: what it says, what you will be able to do, what it builds on. */}
      <div className={styles.group} role="group" aria-labelledby={`${headingId}-about`}>
        <p className={cx('ad-eyebrow', styles.groupLabel)} id={`${headingId}-about`}>
          About this concept
        </p>
        <div className={styles.block}>
          <h4 className={styles.blockTitle}>Learning objectives</h4>
          {concept.objectives.length > 0 ? (
            <ul className={styles.plainList}>
              {concept.objectives.map((objective) => (
                <li key={objective.id}>{objective.statement}</li>
              ))}
            </ul>
          ) : (
            <p className={styles.muted}>
              None yet. Add at least one to check your understanding against.
            </p>
          )}
        </div>

        <div className={styles.block}>
          <div className={styles.blockHeader}>
            <h4 className={styles.blockTitle}>Prerequisites</h4>
            <Button size="small" variant="tertiary" onClick={onEditPrerequisites}>
              Edit prerequisites
            </Button>
          </div>
          {concept.prerequisites.length > 0 ? (
            <ul className={styles.bareList}>
              {concept.prerequisites.map((prerequisite) => (
                <li key={prerequisite.concept_id} className={styles.itemText}>
                  <span>
                    <Button
                      size="small"
                      variant="tertiary"
                      onClick={() => onSelect(prerequisite.concept_id)}
                    >
                      {prerequisite.title}
                    </Button>
                  </span>
                  {prerequisite.reason ? (
                    <span className={styles.muted}>{prerequisite.reason}</span>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : (
            <p className={styles.muted}>None. You can start here.</p>
          )}
          {dependents.length > 0 ? (
            <p className={styles.muted}>
              Required for: {dependents.map((dependent) => dependent.title).join(', ')}.
            </p>
          ) : null}
        </div>
      </div>

      {/* Where you are with it, and the lessons that teach it. */}
      <div className={styles.group} role="group" aria-labelledby={`${headingId}-learning`}>
        <p className={cx('ad-eyebrow', styles.groupLabel)} id={`${headingId}-learning`}>
          Your learning
        </p>
        <div className={styles.block}>
          <h4 className={styles.blockTitle}>Your progress</h4>
          <div className={styles.knowledge}>
            <div className={styles.knowledgeLine}>
              <Badge tone={KNOWLEDGE_TONE[concept.knowledge.state]}>
                {concept.knowledge.label}
              </Badge>
              {concept.knowledge.missing.length > 0 ? (
                <span className={styles.muted}>
                  Still needed: {concept.knowledge.missing.join('; ')}.
                </span>
              ) : null}
            </div>
            <div className={styles.block}>
              <span className={styles.muted} id={`${historyId}-rate`}>
                How well do you know this already?
              </span>
              <div
                className={styles.knowledgeLine}
                role="group"
                aria-labelledby={`${historyId}-rate`}
              >
                {SELF_REPORTS.map((option) => (
                  <Button
                    key={option.value}
                    size="small"
                    aria-pressed={concept.knowledge.self_report === option.value}
                    loading={rating === option.value}
                    disabled={rating !== null && rating !== option.value}
                    onClick={() => void rate(option.value)}
                  >
                    {option.label}
                  </Button>
                ))}
              </div>
            </div>
            <div>
              <Button
                size="small"
                variant="tertiary"
                aria-expanded={shownHistory.status !== 'closed'}
                aria-controls={historyId}
                onClick={() => void toggleHistory()}
              >
                {shownHistory.status === 'closed' ? 'Show history' : 'Hide history'}
              </Button>
            </div>
            <div id={historyId} aria-live="polite">
              {shownHistory.status === 'loading' ? (
                <Spinner size="small" label="Loading history" />
              ) : shownHistory.status === 'error' ? (
                <p className={styles.formError}>{shownHistory.message}</p>
              ) : shownHistory.status === 'ready' ? (
                shownHistory.evidence.history.length === 0 ? (
                  <p className={styles.muted}>
                    Nothing yet. Your answers and status changes will appear here.
                  </p>
                ) : (
                  <ol className={styles.history} aria-label="History, newest first">
                    {shownHistory.evidence.history.map((entry) => (
                      <li key={entry.id} className={styles.itemText}>
                        <span className={styles.historyWhen}>
                          {formatRelativeDay(entry.occurred_at)}
                        </span>
                        <span>{entry.explanation}</span>
                      </li>
                    ))}
                  </ol>
                )
              ) : null}
            </div>
          </div>
        </div>

        <div className={styles.block}>
          <h4 className={styles.blockTitle}>Lessons</h4>
          {lessons.status === 'loading' ? (
            <Spinner size="small" label="Loading lessons" />
          ) : lessons.status === 'error' ? (
            <div className={styles.itemRow}>
              <p className={styles.formError}>{lessons.message}</p>
              <Button size="small" onClick={lessons.retry}>
                Try again
              </Button>
            </div>
          ) : lessons.lessons.length === 0 ? (
            <p className={styles.muted}>No lessons yet.</p>
          ) : (
            <ul className={styles.bareList} aria-label="Lessons for this concept">
              {lessons.lessons.map((lesson) => {
                const action = lessonAction(lesson.progress);
                const removable = lessons.lessons.some((other) => other.origin === 'generated');
                return (
                  <li key={lesson.id} className={styles.itemRow}>
                    <span className={styles.itemText}>
                      <span className={styles.itemTitle}>{lesson.title}</span>
                      <span className={styles.muted}>{describeLesson(lesson)}</span>
                    </span>
                    <Button
                      size="small"
                      variant={lesson.progress.completed ? 'secondary' : 'primary'}
                      icon={lesson.progress.completed ? <RotateCcw /> : <Play />}
                      aria-label={`${action}: ${lesson.title}`}
                      onClick={() => onOpenLesson(lesson.id)}
                    >
                      {action}
                    </Button>
                    {/* A lesson a model wrote can be removed, to make room for another way of
                        teaching the same thing. The sample course's own lessons stay. */}
                    {lesson.origin === 'generated' ? (
                      <IconButton
                        label={`Remove lesson: ${lesson.title}`}
                        icon={<Trash2 />}
                        size="small"
                        onClick={() => onRemoveLesson(lesson)}
                      />
                    ) : removable ? (
                      // Its place is kept, so that every row's button stands in one column.
                      <span className={styles.itemSpacer} aria-hidden="true" />
                    ) : null}
                  </li>
                );
              })}
            </ul>
          )}
          <GenerationStatus
            job={generation.job?.status === 'succeeded' ? null : generation.job}
            starting={generation.starting}
            refusal={generation.refusal}
            subject="the lesson"
            kind="lesson"
            waitingText="Queued"
            usualSeconds={generation.usualSeconds}
            lessonReady={generation.lessonReady}
            onCancel={generation.onCancel}
            onRetry={() => generation.onCreate(strategy || null)}
            onDismiss={generation.onDismiss}
          />
          {/* While work is under way, or its failure is on screen with its own way forward,
              a second button to start the same thing would only be noise. Nor is one offered
              before the lessons there already are known: it would say "a lesson" where it
              means "another". */}
          {lessons.status === 'loading' ||
          generation.starting ||
          isJobActive(generation.job) ||
          generation.refusal !== null ||
          generation.job?.status === 'failed' ||
          generation.job?.status === 'cancelled' ? null : (
            <div className={styles.generation}>
              {/* The learner can say what kind of explanation they want, for a first lesson
                  as for another; left on Automatic, the writer chooses. */}
              {lessons.status === 'ready' ? (
                <div className={styles.strategy}>
                  <Select
                    label="Teaching style"
                    value={strategy}
                    options={offered}
                    onValueChange={setStrategy}
                  />
                </div>
              ) : null}
              <div className={styles.sending}>
                <Button
                  size="small"
                  icon={<Sparkles />}
                  disabled={concept.objectives.length === 0}
                  onClick={() => generation.onCreate(strategy || null)}
                >
                  {lessons.status === 'ready' && lessons.lessons.length > 0
                    ? 'Create another lesson with AI'
                    : 'Create a lesson with AI'}
                </Button>
                {concept.objectives.length === 0 ? null : (
                  <WhatIsSent
                    what={lessonDisclosure(hasMaterials ? 'some' : 'none')}
                    to={generation.destination}
                    wait={generation.usualWait}
                    after="Its pictures follow while you start."
                  />
                )}
              </div>
              {/* The one thing here the learner has to do something about. */}
              {concept.objectives.length === 0 ? (
                <p className={styles.aiNote}>Add a learning objective first.</p>
              ) : null}
            </div>
          )}
        </div>
      </div>

      {/* Where it is in the learner's own files: often long, so after the rest. */}
      <div className={styles.group}>
        <div className={styles.block}>
          <div className={styles.blockHeader}>
            <h4 className={styles.blockTitle}>In your materials</h4>
            {hasMaterials ? (
              <Button
                size="small"
                variant="tertiary"
                icon={<Search />}
                loading={shownPassages.status === 'loading'}
                onClick={() => void findPassages()}
              >
                Find related passages
              </Button>
            ) : null}
          </div>
          {concept.source_refs.length > 0 ? (
            <ul className={styles.bareList} aria-label="Linked passages">
              {concept.source_refs.map((ref) => (
                <li key={ref.id} className={styles.itemRow}>
                  <span className={styles.itemText}>
                    <span className={styles.itemTitle}>{ref.source_name}</span>
                    <span className={styles.muted}>{describeLocation(ref)}</span>
                  </span>
                  <IconButton
                    label={`Unlink ${ref.source_name}, ${describeLocation(ref)}`}
                    icon={<Unlink />}
                    variant="tertiary"
                    size="small"
                    onClick={() => void unlink(ref.id)}
                  />
                </li>
              ))}
            </ul>
          ) : (
            <p className={styles.muted}>
              {hasMaterials
                ? 'Nothing linked yet. Linking passages keeps lessons close to your course.'
                : 'No materials imported. Lessons will draw on general knowledge.'}
            </p>
          )}
          <div aria-live="polite">
            {shownPassages.status === 'error' ? (
              <Callout tone="danger" title="Search failed">
                {shownPassages.message}
              </Callout>
            ) : shownPassages.status === 'ready' && shownPassages.passages.length === 0 ? (
              <p className={styles.muted}>
                No matches. Try a description or objectives that use the terms in your notes.
              </p>
            ) : shownPassages.status === 'ready' ? (
              <ul className={styles.bareList} aria-label="Related passages">
                {shownPassages.passages.map((passage) => {
                  const linked = linkedSections.has(passage.section_id);
                  return (
                    <li key={passage.chunk_id} className={styles.passage}>
                      <div className={styles.itemRow}>
                        <span className={styles.itemText}>
                          <span className={styles.itemTitle}>{passage.source_name}</span>
                          <span className={styles.muted}>{describeLocation(passage)}</span>
                        </span>
                        {linked ? (
                          <Badge tone="success">Linked</Badge>
                        ) : (
                          <Button
                            size="small"
                            icon={<LinkIcon />}
                            loading={linking === passage.section_id}
                            aria-label={`Link ${passage.source_name}, ${describeLocation(passage)} to this concept`}
                            onClick={() => void link(passage.section_id)}
                          >
                            Link
                          </Button>
                        )}
                      </div>
                      <p className={styles.passageText}>{passage.text}</p>
                    </li>
                  );
                })}
              </ul>
            ) : null}
          </div>
        </div>
      </div>

      <div className={styles.detailActions}>
        <Button size="small" icon={<Pencil />} onClick={onEdit}>
          Edit concept
        </Button>
        <Button size="small" variant="tertiary" icon={<Trash2 />} onClick={onRemove}>
          Remove concept
        </Button>
      </div>
    </Card>
  );
}
