import { Plus, Trash2 } from 'lucide-react';
import { type FormEvent, useId, useState } from 'react';

import type { Concept, OutlineCandidate } from '@adle/contracts';
import {
  Button,
  Callout,
  Checkbox,
  Dialog,
  IconButton,
  TextArea,
  TextField,
} from '@adle/design-system';

import { describeError } from '../../lib/core-client';
import { pluralise } from '../../lib/format';
import styles from './Curriculum.module.css';
import { dependentsOf } from './curriculum-model';

const MAX_OBJECTIVES = 12;

export interface ConceptDraft {
  title: string;
  summary: string;
  /** `id` is null for an objective that does not exist yet. */
  objectives: { id: string | null; statement: string }[];
}

interface ObjectiveRow {
  key: number;
  id: string | null;
  statement: string;
}

/** Create a concept, or change its name, description, and learning objectives. */
export function ConceptDialog({
  concept,
  onClose,
  onSave,
}: {
  /** The concept being edited, or null to create one. */
  concept: Concept | null;
  onClose: () => void;
  onSave: (draft: ConceptDraft) => Promise<void>;
}) {
  const formId = useId();
  const [title, setTitle] = useState(concept?.title ?? '');
  const [summary, setSummary] = useState(concept?.summary ?? '');
  const [objectives, setObjectives] = useState<ObjectiveRow[]>(() => {
    const existing = (concept?.objectives ?? []).map((objective, index) => ({
      key: index,
      id: objective.id,
      statement: objective.statement,
    }));
    return existing.length > 0 ? existing : [{ key: 0, id: null, statement: '' }];
  });
  const [nextKey, setNextKey] = useState(objectives.length);
  const [titleError, setTitleError] = useState<string>();
  const [formError, setFormError] = useState<string>();
  const [saving, setSaving] = useState(false);

  const submit = async (event: FormEvent): Promise<void> => {
    event.preventDefault();
    if (!title.trim()) {
      setTitleError('Give the concept a name.');
      return;
    }
    setTitleError(undefined);
    setFormError(undefined);
    setSaving(true);
    try {
      await onSave({
        title: title.trim(),
        summary: summary.trim(),
        objectives: objectives
          .filter((row) => row.statement.trim())
          .map((row) => ({ id: row.id, statement: row.statement.trim() })),
      });
    } catch (error) {
      setFormError(describeError(error));
      setSaving(false);
    }
  };

  const setStatement = (key: number, statement: string): void =>
    setObjectives((rows) => rows.map((row) => (row.key === key ? { ...row, statement } : row)));

  return (
    <Dialog
      open
      onClose={() => {
        if (!saving) onClose();
      }}
      title={concept ? 'Edit concept' : 'Add a concept'}
      description="A concept is one idea or skill, small enough for a single lesson."
      size="medium"
      dismissible={!saving}
    >
      <form id={formId} className={styles.form} onSubmit={(event) => void submit(event)} noValidate>
        <TextField
          label="Name"
          data-autofocus
          value={title}
          maxLength={200}
          error={titleError}
          placeholder="For example: The chain rule"
          onChange={(event) => setTitle(event.target.value)}
        />
        <TextArea
          label="What it covers"
          value={summary}
          maxLength={4000}
          rows={3}
          description="Optional. A sentence or two in your own words."
          onChange={(event) => setSummary(event.target.value)}
        />
        <fieldset className={styles.fieldGroup}>
          <legend className={styles.fieldGroupLabel}>Learning objectives</legend>
          <p className={styles.muted}>
            What should you be able to do afterwards? Start with something that can be checked:
            “Compute…”, “Explain why…”, “Predict what happens when…”.
          </p>
          {objectives.map((row, index) => (
            <div key={row.key} className={styles.objectiveRow}>
              <div className={styles.objectiveField}>
                <TextField
                  label={`Objective ${index + 1}`}
                  hideLabel
                  value={row.statement}
                  maxLength={400}
                  placeholder="Compute the output of a neuron from its inputs and weights"
                  onChange={(event) => setStatement(row.key, event.target.value)}
                />
              </div>
              <IconButton
                label={`Remove objective ${index + 1}`}
                icon={<Trash2 />}
                variant="tertiary"
                disabled={objectives.length === 1 && !row.statement}
                onClick={() =>
                  setObjectives((rows) =>
                    rows.length === 1
                      ? [{ ...row, id: null, statement: '' }]
                      : rows.filter((other) => other.key !== row.key),
                  )
                }
              />
            </div>
          ))}
          {objectives.length < MAX_OBJECTIVES ? (
            <div>
              <Button
                size="small"
                variant="tertiary"
                icon={<Plus />}
                onClick={() => {
                  setObjectives((rows) => [...rows, { key: nextKey, id: null, statement: '' }]);
                  setNextKey((key) => key + 1);
                }}
              >
                Add another objective
              </Button>
            </div>
          ) : null}
        </fieldset>

        {formError ? (
          <p className={styles.formError} role="alert">
            {formError}
          </p>
        ) : null}

        <div className={styles.formActions}>
          <Button onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" loading={saving}>
            {concept ? 'Save changes' : 'Add concept'}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}

/** Choose what must be learned before a concept, and say why. */
export function PrerequisitesDialog({
  concept,
  path,
  onClose,
  onSave,
}: {
  concept: Concept;
  /** Every concept of the course, in learning order. */
  path: readonly Concept[];
  onClose: () => void;
  onSave: (prerequisites: { concept_id: string; reason: string }[]) => Promise<void>;
}) {
  const [chosen, setChosen] = useState<Map<string, string>>(
    () => new Map(concept.prerequisites.map((item) => [item.concept_id, item.reason])),
  );
  const [formError, setFormError] = useState<string>();
  const [saving, setSaving] = useState(false);
  // Anything that builds on this concept cannot also come before it.
  const dependents = dependentsOf(path, concept.id);
  const others = path.filter((other) => other.id !== concept.id);

  const submit = async (event: FormEvent): Promise<void> => {
    event.preventDefault();
    setFormError(undefined);
    setSaving(true);
    try {
      await onSave(
        others
          .filter((other) => chosen.has(other.id))
          .map((other) => ({ concept_id: other.id, reason: (chosen.get(other.id) ?? '').trim() })),
      );
    } catch (error) {
      setFormError(describeError(error));
      setSaving(false);
    }
  };

  const toggle = (id: string, checked: boolean): void =>
    setChosen((current) => {
      const next = new Map(current);
      if (checked) next.set(id, current.get(id) ?? '');
      else next.delete(id);
      return next;
    });

  return (
    <Dialog
      open
      onClose={() => {
        if (!saving) onClose();
      }}
      title={`What does “${concept.title}” need first?`}
      description="Tick what has to be understood before this makes sense. Adle teaches those first, and comes back to them if this one proves difficult."
      size="medium"
      dismissible={!saving}
    >
      <form className={styles.form} onSubmit={(event) => void submit(event)} noValidate>
        {others.length === 0 ? (
          <p className={styles.muted}>There are no other concepts in this course yet.</p>
        ) : (
          <ul className={styles.choices} aria-label="Other concepts in this course">
            {others.map((other) => {
              const blocked = dependents.has(other.id);
              const checked = chosen.has(other.id);
              return (
                <li key={other.id}>
                  <Checkbox
                    label={other.title}
                    description={
                      blocked ? `Builds on “${concept.title}”, so it cannot come first.` : undefined
                    }
                    checked={checked}
                    disabled={blocked && !checked}
                    onCheckedChange={(value) => toggle(other.id, value)}
                  />
                  {checked ? (
                    <div className={styles.choiceReason}>
                      <TextField
                        label={`Why “${other.title}” is needed`}
                        hideLabel
                        value={chosen.get(other.id) ?? ''}
                        maxLength={500}
                        placeholder="Why is it needed? (optional)"
                        onChange={(event) =>
                          setChosen((current) => new Map(current).set(other.id, event.target.value))
                        }
                      />
                    </div>
                  ) : null}
                </li>
              );
            })}
          </ul>
        )}

        {formError ? (
          <Callout tone="danger" urgent title="That could not be saved">
            {formError}
          </Callout>
        ) : null}

        <div className={styles.formActions}>
          <Button onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" loading={saving} disabled={others.length === 0}>
            Save prerequisites
          </Button>
        </div>
      </form>
    </Dialog>
  );
}

/** Pick which headings of the imported materials become concepts. */
export function OutlineDialog({
  candidates,
  onClose,
  onAdd,
}: {
  candidates: readonly OutlineCandidate[];
  onClose: () => void;
  onAdd: (sectionIds: string[]) => Promise<void>;
}) {
  const [chosen, setChosen] = useState<Set<string>>(
    () => new Set(candidates.map((candidate) => candidate.section_id)),
  );
  const [formError, setFormError] = useState<string>();
  const [saving, setSaving] = useState(false);

  const sources = [...new Set(candidates.map((candidate) => candidate.source_name))];
  const allChosen = chosen.size === candidates.length;

  const submit = async (event: FormEvent): Promise<void> => {
    event.preventDefault();
    setFormError(undefined);
    setSaving(true);
    try {
      await onAdd(
        candidates
          .filter((candidate) => chosen.has(candidate.section_id))
          .map((candidate) => candidate.section_id),
      );
    } catch (error) {
      setFormError(describeError(error));
      setSaving(false);
    }
  };

  return (
    <Dialog
      open
      onClose={() => {
        if (!saving) onClose();
      }}
      title="Start from your materials"
      description="These are the headings of what you imported. Keep the ones that are things to learn. Adle does not guess which depends on which; you can say so afterwards."
      size="medium"
      dismissible={!saving}
    >
      <form className={styles.form} onSubmit={(event) => void submit(event)} noValidate>
        <div>
          <Button
            size="small"
            variant="tertiary"
            onClick={() =>
              setChosen(
                allChosen
                  ? new Set()
                  : new Set(candidates.map((candidate) => candidate.section_id)),
              )
            }
          >
            {allChosen ? 'Clear all' : 'Select all'}
          </Button>
        </div>
        <div className={styles.choices}>
          {sources.map((source) => (
            <fieldset key={source} className={styles.fieldGroup}>
              <legend className={styles.sourceHeading}>From {source}</legend>
              {candidates
                .filter((candidate) => candidate.source_name === source)
                .map((candidate) => (
                  <Checkbox
                    key={candidate.section_id}
                    label={candidate.title}
                    checked={chosen.has(candidate.section_id)}
                    onCheckedChange={(checked) =>
                      setChosen((current) => {
                        const next = new Set(current);
                        if (checked) next.add(candidate.section_id);
                        else next.delete(candidate.section_id);
                        return next;
                      })
                    }
                  />
                ))}
            </fieldset>
          ))}
        </div>

        {formError ? (
          <p className={styles.formError} role="alert">
            {formError}
          </p>
        ) : null}

        <div className={styles.formActions}>
          <Button onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" loading={saving} disabled={chosen.size === 0}>
            {chosen.size === 0 ? 'Add concepts' : `Add ${pluralise(chosen.size, 'concept')}`}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
