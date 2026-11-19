import { ArrowDown, ArrowUp, List, ListTree, Network, Plus } from 'lucide-react';
import { useId, useState } from 'react';

import type { Concept, Course, Curriculum } from '@adle/contracts';
import {
  Badge,
  Button,
  Callout,
  cx,
  Dialog,
  EmptyState,
  ErrorState,
  IconButton,
  LoadingState,
  SegmentedControl,
  Stack,
  useToast,
} from '@adle/design-system';

import { callCore, describeError } from '../../lib/core-client';
import { pluralise } from '../../lib/format';
import { useResource } from '../../lib/use-resource';
import { ConceptDetail, KNOWLEDGE_TONE } from './ConceptDetail';
import {
  ConceptDialog,
  type ConceptDraft,
  OutlineDialog,
  PrerequisitesDialog,
} from './ConceptDialogs';
import { ConceptMap } from './ConceptMap';
import styles from './Curriculum.module.css';
import {
  checkMove,
  learningPath,
  type MoveDirection,
  movedOrder,
  summariseIssues,
} from './curriculum-model';

type View = 'list' | 'map';

const VIEWS = [
  { value: 'list', label: 'List', icon: <List /> },
  { value: 'map', label: 'Map', icon: <Network /> },
] as const;

type OpenDialog =
  | { kind: 'create' }
  | { kind: 'edit'; concept: Concept }
  | { kind: 'prerequisites'; concept: Concept }
  | { kind: 'remove'; concept: Concept }
  | { kind: 'outline' }
  | null;

/** Inspect and edit what a course teaches, and in what order. */
export function CurriculumPanel({ course }: { course: Course }) {
  const toast = useToast();
  const headingId = useId();
  const courseId = course.id;
  const curriculum = useResource(`curriculum:${courseId}`, () =>
    callCore('curriculum.get', { path: { course_id: courseId } }),
  );
  const outline = useResource(`outline:${courseId}`, () =>
    callCore('curriculum.outline_candidates', { path: { course_id: courseId } }),
  );
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [view, setView] = useState<View>('list');
  const [dialog, setDialog] = useState<OpenDialog>(null);
  const [removing, setRemoving] = useState(false);

  const candidates = outline.resource.status === 'ready' ? outline.resource.data.candidates : [];

  const accept = (next: Curriculum): void => {
    curriculum.setData(next);
    outline.reload();
  };

  if (curriculum.resource.status === 'loading') {
    return <LoadingState title="Reading the curriculum…" />;
  }
  if (curriculum.resource.status === 'error') {
    return (
      <ErrorState
        title="The curriculum could not be read"
        description={describeError(curriculum.resource.error)}
        actions={<Button onClick={curriculum.reload}>Try again</Button>}
      />
    );
  }

  const data = curriculum.resource.data;
  const path = learningPath(data);
  const selected = path.find((concept) => concept.id === selectedId) ?? path[0] ?? null;
  const hasMaterials = course.source_count > 0;

  const saveConcept = async (existing: Concept | null, draft: ConceptDraft): Promise<void> => {
    if (existing === null) {
      const next = await callCore('curriculum.create_concept', {
        path: { course_id: courseId },
        body: {
          title: draft.title,
          summary: draft.summary,
          objectives: draft.objectives.map((objective) => objective.statement),
        },
      });
      accept(next);
      setSelectedId(next.concepts.at(-1)?.id ?? null);
    } else {
      await callCore('curriculum.update_concept', {
        path: { concept_id: existing.id },
        body: { title: draft.title, summary: draft.summary },
      });
      accept(
        await callCore('curriculum.set_objectives', {
          path: { concept_id: existing.id },
          body: { objectives: draft.objectives },
        }),
      );
    }
    setDialog(null);
  };

  const savePrerequisites = async (
    concept: Concept,
    prerequisites: { concept_id: string; reason: string }[],
  ): Promise<void> => {
    accept(
      await callCore('curriculum.set_prerequisites', {
        path: { concept_id: concept.id },
        body: { prerequisites },
      }),
    );
    setDialog(null);
  };

  const addFromOutline = async (sectionIds: string[]): Promise<void> => {
    if (sectionIds.length === 0) return;
    const before = new Set(data.concepts.map((concept) => concept.id));
    const next = await callCore('curriculum.add_from_outline', {
      path: { course_id: courseId },
      body: { section_ids: sectionIds },
    });
    accept(next);
    const added = next.concepts.filter((concept) => !before.has(concept.id));
    setSelectedId(added[0]?.id ?? null);
    setDialog(null);
    toast.show({
      tone: 'success',
      title: `${pluralise(added.length, 'concept')} added from your materials`,
      description: 'Add objectives and say what depends on what when you are ready.',
    });
  };

  const removeConcept = async (concept: Concept): Promise<void> => {
    setRemoving(true);
    try {
      accept(await callCore('curriculum.delete_concept', { path: { concept_id: concept.id } }));
      setSelectedId(null);
      toast.show({ tone: 'success', title: 'Concept removed', description: concept.title });
    } catch (error) {
      toast.show({
        tone: 'danger',
        title: 'The concept could not be removed',
        description: describeError(error),
      });
    } finally {
      setRemoving(false);
      setDialog(null);
    }
  };

  const move = async (concept: Concept, direction: MoveDirection): Promise<void> => {
    const check = checkMove(path, concept.id, direction);
    if (!check.allowed) {
      if (check.reason) {
        toast.show({
          tone: 'info',
          title: `“${concept.title}” stays where it is`,
          description: check.reason,
        });
      }
      return;
    }
    try {
      accept(
        await callCore('curriculum.reorder', {
          path: { course_id: courseId },
          body: { concept_ids: movedOrder(path, concept.id, direction) },
        }),
      );
    } catch (error) {
      toast.show({
        tone: 'danger',
        title: 'The order could not be changed',
        description: describeError(error),
      });
    }
  };

  const actions = (
    <Stack direction="row" gap={2} wrap>
      {candidates.length > 0 ? (
        <Button icon={<ListTree />} onClick={() => setDialog({ kind: 'outline' })}>
          Start from your materials
        </Button>
      ) : null}
      <Button
        variant={path.length === 0 && candidates.length > 0 ? 'secondary' : 'primary'}
        icon={<Plus />}
        onClick={() => setDialog({ kind: 'create' })}
      >
        Add a concept
      </Button>
    </Stack>
  );

  const errors = data.issues.filter((issue) => issue.severity === 'error');
  const warnings = data.issues.filter((issue) => issue.severity === 'warning');

  return (
    <>
      <section className={styles.panel} aria-labelledby={headingId}>
        <div className={styles.toolbar}>
          <div className={styles.toolbarTitle}>
            <h2 id={headingId} className={styles.heading}>
              Curriculum
            </h2>
            {path.length > 0 ? (
              <span className={styles.count}>{pluralise(path.length, 'concept')}</span>
            ) : null}
          </div>
          {path.length > 0 ? (
            <div className={styles.toolbarActions}>
              <SegmentedControl<View>
                label="Show the curriculum as"
                value={view}
                options={VIEWS}
                onValueChange={setView}
              />
              {actions}
            </div>
          ) : null}
        </div>

        {path.length === 0 ? (
          <EmptyState
            visual={<ListTree />}
            title="No concepts yet"
            description={
              candidates.length > 0
                ? 'Start from the headings of your materials, or add concepts one at a time.'
                : hasMaterials
                  ? 'Your materials have no headings Adle can turn into concepts. Add them one at a time; you can still link each to a passage in your notes.'
                  : 'Add the ideas you want to learn, one at a time. Import course materials first if you would like Adle to suggest a starting list from their headings.'
            }
            actions={actions}
          />
        ) : (
          <>
            {errors.length > 0 ? (
              <Callout tone="danger" title="This course cannot be started yet">
                <IssueList messages={summariseIssues(errors, data.concepts)} />
              </Callout>
            ) : null}
            {warnings.length > 0 ? (
              <Callout tone="warning" title="Worth a look before you start">
                <IssueList messages={summariseIssues(warnings, data.concepts)} />
              </Callout>
            ) : null}

            <div className={cx(styles.layout, view === 'map' && styles.layoutStacked)}>
              <div className={styles.overview}>
                {view === 'list' ? (
                  <>
                    <ol className={styles.path} aria-label="Learning path">
                      {path.map((concept, index) => {
                        const isSelected = concept.id === selected?.id;
                        return (
                          <li
                            key={concept.id}
                            className={cx(styles.row, isSelected && styles.rowSelected)}
                          >
                            <button
                              type="button"
                              className={styles.rowMain}
                              aria-current={isSelected ? 'true' : undefined}
                              onClick={() => setSelectedId(concept.id)}
                            >
                              <span className={styles.rowNumber} aria-hidden="true">
                                {index + 1}
                              </span>
                              <span className={styles.rowText}>
                                <span className={styles.rowTitle}>{concept.title}</span>
                                <span className={styles.rowMeta}>
                                  {concept.prerequisites.length > 0
                                    ? `Needs ${concept.prerequisites.map((item) => item.title).join(', ')}`
                                    : 'Needs nothing first'}
                                </span>
                                <span className={styles.rowBadge}>
                                  <Badge tone={KNOWLEDGE_TONE[concept.knowledge.state]}>
                                    {concept.knowledge.label}
                                  </Badge>
                                </span>
                              </span>
                            </button>
                            <IconButton
                              label={`Move ${concept.title} earlier`}
                              icon={<ArrowUp />}
                              variant="tertiary"
                              size="small"
                              disabled={index === 0}
                              onClick={() => void move(concept, 'earlier')}
                            />
                            <IconButton
                              label={`Move ${concept.title} later`}
                              icon={<ArrowDown />}
                              variant="tertiary"
                              size="small"
                              disabled={index === path.length - 1}
                              onClick={() => void move(concept, 'later')}
                            />
                          </li>
                        );
                      })}
                    </ol>
                    <p className={styles.mapCaption}>
                      Taught from top to bottom. Each concept comes after everything it needs.
                    </p>
                  </>
                ) : (
                  <ConceptMap
                    curriculum={data}
                    selectedId={selected?.id ?? null}
                    onSelect={setSelectedId}
                  />
                )}
              </div>

              {selected ? (
                <ConceptDetail
                  key={selected.id}
                  concept={selected}
                  path={path}
                  hasMaterials={hasMaterials}
                  onEdit={() => setDialog({ kind: 'edit', concept: selected })}
                  onRemove={() => setDialog({ kind: 'remove', concept: selected })}
                  onEditPrerequisites={() =>
                    setDialog({ kind: 'prerequisites', concept: selected })
                  }
                  onSelect={setSelectedId}
                  onChanged={accept}
                  onReload={curriculum.reload}
                />
              ) : null}
            </div>
          </>
        )}
      </section>

      {dialog?.kind === 'create' ? (
        <ConceptDialog
          concept={null}
          onClose={() => setDialog(null)}
          onSave={(draft) => saveConcept(null, draft)}
        />
      ) : null}
      {dialog?.kind === 'edit' ? (
        <ConceptDialog
          concept={dialog.concept}
          onClose={() => setDialog(null)}
          onSave={(draft) => saveConcept(dialog.concept, draft)}
        />
      ) : null}
      {dialog?.kind === 'prerequisites' ? (
        <PrerequisitesDialog
          concept={dialog.concept}
          path={path}
          onClose={() => setDialog(null)}
          onSave={(prerequisites) => savePrerequisites(dialog.concept, prerequisites)}
        />
      ) : null}
      {dialog?.kind === 'outline' ? (
        <OutlineDialog
          candidates={candidates}
          onClose={() => setDialog(null)}
          onAdd={addFromOutline}
        />
      ) : null}
      <Dialog
        open={dialog?.kind === 'remove'}
        onClose={() => setDialog(null)}
        title={dialog?.kind === 'remove' ? `Remove “${dialog.concept.title}”?` : 'Remove concept?'}
        description="The concept, its objectives, and what has been recorded about it are removed from this course. Anything that needed it will simply no longer need it. Your materials are not touched."
        dismissible={!removing}
        actions={
          <>
            <Button onClick={() => setDialog(null)} disabled={removing}>
              Keep it
            </Button>
            <Button
              variant="destructive"
              loading={removing}
              onClick={() => {
                if (dialog?.kind === 'remove') void removeConcept(dialog.concept);
              }}
            >
              Remove concept
            </Button>
          </>
        }
      />
    </>
  );
}

function IssueList({ messages }: { messages: string[] }) {
  return (
    <ul className={styles.issueList}>
      {messages.map((message) => (
        <li key={message}>{message}</li>
      ))}
    </ul>
  );
}
