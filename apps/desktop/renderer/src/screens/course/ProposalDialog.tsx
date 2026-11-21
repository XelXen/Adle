import { type FormEvent, useState } from 'react';

import { Button, Checkbox, Dialog } from '@adle/design-system';

import { describeError } from '../../lib/core-client';
import { pluralise } from '../../lib/format';
import { authorName, keptNeeds, type Proposal } from '../../lib/generation';
import styles from './Curriculum.module.css';

/**
 * What the AI suggested for a course, for the learner to pick from. Nothing is
 * in the course until they add it, and anything added can be edited afterwards
 * like a concept they wrote themselves.
 */
export function ProposalDialog({
  proposal,
  providerName,
  onAdd,
  onDiscard,
  onClose,
}: {
  proposal: Proposal;
  providerName: string;
  /** Add the concepts at these positions of the proposal. */
  onAdd: (selected: number[]) => Promise<void>;
  /** Set the proposal aside for good. */
  onDiscard: () => Promise<void>;
  /** Close without deciding; the proposal stays available. */
  onClose: () => void;
}) {
  const [chosen, setChosen] = useState<Set<number>>(
    () => new Set(proposal.concepts.map((_, index) => index)),
  );
  const [busy, setBusy] = useState<'add' | 'discard' | null>(null);
  const [formError, setFormError] = useState<string>();
  // Who suggested it is what the job recorded, not whichever provider is in use by now.
  const author = authorName(proposal.writtenBy, providerName);
  const standIn = proposal.writtenBy?.note ? ` ${proposal.writtenBy.note}` : '';
  const allChosen = chosen.size === proposal.concepts.length;

  const run = async (kind: 'add' | 'discard', work: () => Promise<void>): Promise<void> => {
    setFormError(undefined);
    setBusy(kind);
    try {
      await work();
    } catch (error) {
      setFormError(describeError(error));
      setBusy(null);
    }
  };

  const submit = (event: FormEvent): void => {
    event.preventDefault();
    if (chosen.size === 0) {
      setFormError('Choose at least one concept, or discard the suggestions.');
      return;
    }
    void run('add', () => onAdd([...chosen].sort((a, b) => a - b)));
  };

  return (
    <Dialog
      open
      onClose={() => {
        if (busy === null) onClose();
      }}
      title="Suggested concepts"
      description={
        proposal.groundedInMaterials
          ? `Suggested by ${author} from your course details and material headings.${standIn} Keep what fits. You can edit everything later.`
          : `Suggested by ${author} from your course details only.${standIn} Keep what fits. You can edit everything later.`
      }
      size="medium"
      dismissible={busy === null}
    >
      <form className={styles.form} onSubmit={submit} noValidate>
        <div>
          <Button
            size="small"
            variant="tertiary"
            disabled={busy !== null}
            onClick={() =>
              setChosen(allChosen ? new Set() : new Set(proposal.concepts.map((_, index) => index)))
            }
          >
            {allChosen ? 'Clear all' : 'Select all'}
          </Button>
        </div>
        <ol className={styles.proposal} aria-label="Suggested concepts, in teaching order">
          {proposal.concepts.map((concept, index) => {
            const needs = keptNeeds(proposal, chosen, index);
            const dropped = concept.needs.length - needs.length;
            return (
              <li key={`${index}-${concept.title}`} className={styles.proposalItem}>
                <Checkbox
                  label={concept.title}
                  description={concept.summary || undefined}
                  checked={chosen.has(index)}
                  disabled={busy !== null}
                  onCheckedChange={(checked) =>
                    setChosen((current) => {
                      const next = new Set(current);
                      if (checked) next.add(index);
                      else next.delete(index);
                      return next;
                    })
                  }
                />
                <div className={styles.proposalDetail}>
                  {concept.objectives.length > 0 ? (
                    <ul className={styles.plainList}>
                      {concept.objectives.map((objective) => (
                        <li key={objective}>{objective}</li>
                      ))}
                    </ul>
                  ) : null}
                  {needs.length > 0 ? (
                    <p className={styles.muted}>
                      Prerequisites:{' '}
                      {needs
                        .map((need) => {
                          const title = proposal.concepts[need.index]?.title ?? '';
                          return need.reason ? `${title} (${need.reason})` : title;
                        })
                        .join('; ')}
                    </p>
                  ) : null}
                  {chosen.has(index) && dropped > 0 ? (
                    <p className={styles.muted}>
                      {dropped === 1
                        ? 'Builds on a suggestion you didn’t keep, so that link won’t be added.'
                        : 'Builds on suggestions you didn’t keep, so those links won’t be added.'}
                    </p>
                  ) : null}
                </div>
              </li>
            );
          })}
        </ol>

        {formError ? (
          <p className={styles.formError} role="alert">
            {formError}
          </p>
        ) : null}

        <div className={styles.formActions}>
          <Button
            variant="tertiary"
            loading={busy === 'discard'}
            disabled={busy === 'add'}
            onClick={() => void run('discard', onDiscard)}
          >
            Discard
          </Button>
          <Button onClick={onClose} disabled={busy !== null}>
            Decide later
          </Button>
          <Button
            type="submit"
            variant="primary"
            loading={busy === 'add'}
            disabled={busy === 'discard'}
            data-autofocus
          >
            {chosen.size === 0 ? 'Add concepts' : `Add ${pluralise(chosen.size, 'concept')}`}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
