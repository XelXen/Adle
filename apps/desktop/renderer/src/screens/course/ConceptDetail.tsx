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
  LessonSummary,
  Passage,
} from '@adle/contracts';
import {
  Badge,
  Button,
  Callout,
  Card,
  IconButton,
  Spinner,
  type Tone,
  useToast,
} from '@adle/design-system';

import { GenerationStatus } from '../../components/GenerationStatus';
import { callCore, describeError } from '../../lib/core-client';
import { formatRelativeDay } from '../../lib/format';
import type { JobFailure } from '../../lib/generation';
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
  outline: 'Taken from a heading in your materials.',
  model: 'Proposed by the AI. Check that it fits your course.',
  sample: 'Part of the sample course written by Adle.',
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

/** Where the making of a lesson for one concept stands. */
export interface LessonGeneration {
  /** The job writing a lesson for this concept, if this screen knows of one. */
  job: Job | null;
  /** The request to start one is on its way. */
  starting: boolean;
  /** Starting was refused before a job existed. */
  refusal: JobFailure | null;
  /** The provider the request goes to, as the learner knows it. */
  providerName: string;
  onCreate: () => void;
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
  onEdit,
  onRemove,
  onEditPrerequisites,
  onSelect,
  onChanged,
  onReload,
}: {
  concept: Concept;
  path: readonly Concept[];
  hasMaterials: boolean;
  lessons: ConceptLessons;
  generation: LessonGeneration;
  onOpenLesson: (lessonId: string) => void;
  onEdit: () => void;
  onRemove: () => void;
  onEditPrerequisites: () => void;
  onSelect: (id: string) => void;
  /** A change that returned the whole curriculum. */
  onChanged: (curriculum: Curriculum) => void;
  /** A change after which the curriculum must be read again. */
  onReload: () => void;
}) {
  const toast = useToast();
  const headingId = useId();
  const historyId = useId();
  const [rating, setRating] = useState<SelfReport | null>(null);
  const [passages, setPassages] = useState<PassageState>({ status: 'idle' });
  const [history, setHistory] = useState<HistoryState>({ status: 'closed' });
  const [linking, setLinking] = useState<string | null>(null);

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
      report('That could not be recorded')(error);
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
      report('The link could not be added')(error);
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
      report('The link could not be removed')(error);
    }
  };

  return (
    <Card as="section" aria-labelledby={headingId} className={styles.detail}>
      <div className={styles.detailHeader}>
        <h3 id={headingId} className={styles.detailTitle}>
          {concept.title}
        </h3>
        <div className={styles.knowledgeLine}>
          <Button size="small" icon={<Pencil />} onClick={onEdit}>
            Edit
          </Button>
          <Button size="small" variant="tertiary" icon={<Trash2 />} onClick={onRemove}>
            Remove
          </Button>
        </div>
      </div>

      {concept.summary ? <p className={styles.detailSummary}>{concept.summary}</p> : null}
      {ORIGIN_NOTE[concept.origin] ? (
        <p className={styles.muted}>{ORIGIN_NOTE[concept.origin]}</p>
      ) : null}

      <div className={styles.block}>
        <h4 className={styles.blockTitle}>Lessons</h4>
        {lessons.status === 'loading' ? (
          <Spinner size="small" label="Looking for lessons" />
        ) : lessons.status === 'error' ? (
          <div className={styles.itemRow}>
            <p className={styles.formError}>{lessons.message}</p>
            <Button size="small" onClick={lessons.retry}>
              Try again
            </Button>
          </div>
        ) : lessons.lessons.length === 0 ? (
          <p className={styles.muted}>No lesson has been made for this concept yet.</p>
        ) : (
          <ul className={styles.bareList} aria-label="Lessons for this concept">
            {lessons.lessons.map((lesson) => {
              const action = lessonAction(lesson.progress);
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
          waitingText="Waiting for its turn"
          onCancel={generation.onCancel}
          onRetry={generation.onCreate}
          onDismiss={generation.onDismiss}
        />
        {/* While work is under way, or its failure is on screen with its own way forward,
            a second button to start the same thing would only be noise. */}
        {generation.starting ||
        isJobActive(generation.job) ||
        generation.refusal !== null ||
        generation.job?.status === 'failed' ||
        generation.job?.status === 'cancelled' ? null : (
          <div className={styles.generation}>
            <div>
              <Button
                size="small"
                icon={<Sparkles />}
                disabled={concept.objectives.length === 0}
                onClick={generation.onCreate}
              >
                {lessons.status === 'ready' && lessons.lessons.length > 0
                  ? 'Create another lesson with AI'
                  : 'Create a lesson with AI'}
              </Button>
            </div>
            <p className={styles.aiNote}>
              {concept.objectives.length === 0
                ? 'Add a learning objective first, so the lesson has something to aim at.'
                : `Sends ${
                    hasMaterials
                      ? 'this concept, its objectives, and a few related passages from your materials'
                      : 'this concept and its objectives'
                  } to ${generation.providerName}. It usually takes three of today's requests.`}
            </p>
          </div>
        )}
      </div>

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
            None yet. Add at least one so there is something to check your understanding against.
          </p>
        )}
      </div>

      <div className={styles.block}>
        <div className={styles.blockHeader}>
          <h4 className={styles.blockTitle}>Needs first</h4>
          <Button size="small" variant="tertiary" onClick={onEditPrerequisites}>
            Change prerequisites
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
          <p className={styles.muted}>Nothing. This can be learned straight away.</p>
        )}
        {dependents.length > 0 ? (
          <p className={styles.muted}>
            Needed by: {dependents.map((dependent) => dependent.title).join(', ')}.
          </p>
        ) : null}
      </div>

      <div className={styles.block}>
        <h4 className={styles.blockTitle}>What you have shown</h4>
        <div className={styles.knowledge}>
          <div className={styles.knowledgeLine}>
            <Badge tone={KNOWLEDGE_TONE[concept.knowledge.state]}>{concept.knowledge.label}</Badge>
            {concept.knowledge.missing.length > 0 ? (
              <span className={styles.muted}>
                Still needed: {concept.knowledge.missing.join('; ')}.
              </span>
            ) : null}
          </div>
          <div className={styles.block}>
            <span className={styles.muted} id={`${historyId}-rate`}>
              How well do you know this already? Your answer sets where lessons start. It is never
              counted as proof.
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
              {shownHistory.status === 'closed' ? 'Show the record' : 'Hide the record'}
            </Button>
          </div>
          <div id={historyId} aria-live="polite">
            {shownHistory.status === 'loading' ? (
              <Spinner size="small" label="Reading the record" />
            ) : shownHistory.status === 'error' ? (
              <p className={styles.formError}>{shownHistory.message}</p>
            ) : shownHistory.status === 'ready' ? (
              shownHistory.evidence.history.length === 0 ? (
                <p className={styles.muted}>
                  Nothing has been recorded for this concept yet. Every answer and every change of
                  status will be listed here, with the reason.
                </p>
              ) : (
                <ol className={styles.history} aria-label="Record for this concept, newest first">
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
          <ul className={styles.bareList} aria-label="Places linked to this concept">
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
              ? 'Not linked to anything yet. Linking a concept to your notes keeps lessons tied to what your course actually says.'
              : 'This course has no imported materials. Lessons for this concept will come from general knowledge, and Adle will say so.'}
          </p>
        )}
        <div aria-live="polite">
          {shownPassages.status === 'error' ? (
            <Callout tone="danger" title="The search did not work">
              {shownPassages.message}
            </Callout>
          ) : shownPassages.status === 'ready' && shownPassages.passages.length === 0 ? (
            <p className={styles.muted}>
              Nothing in your materials mentions the words of this concept. Try adding a description
              or objectives that use the terms your notes use.
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
    </Card>
  );
}
