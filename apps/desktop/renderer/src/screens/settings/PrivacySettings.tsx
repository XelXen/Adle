import { Download, FolderOpen, History, Library, Trash2 } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

import { Button, Callout, Card, Section, Stack } from '@adle/design-system';

import { useApp } from '../../app/AppContext';
import { useRouter } from '../../app/router';
import { type CoreResult, getBridge } from '../../lib/bridge';
import {
  type DataAction,
  type DataOutcome,
  describeOutcome,
  readOutcome,
} from '../../lib/data-actions';
import styles from './Settings.module.css';

/**
 * Save a copy of everything, restore from a copy, delete everything.
 *
 * The page only asks. Where to save, which file to restore, and whether to delete are
 * asked by the main process in a window of the operating system, so this component
 * never holds a path and cannot answer for the learner.
 */
function YourData() {
  const { coreStatus } = useApp();
  const { navigate } = useRouter();
  const [working, setWorking] = useState<DataAction | null>(null);
  const [outcome, setOutcome] = useState<DataOutcome | null>(null);
  const [folderProblem, setFolderProblem] = useState<string | null>(null);
  const outcomeRef = useRef<HTMLDivElement>(null);

  // The buttons are further down the page than the place that says how it went.
  useEffect(() => {
    if (outcome) outcomeRef.current?.scrollIntoView({ block: 'nearest' });
  }, [outcome]);

  const run = async (action: DataAction): Promise<void> => {
    if (working) return;
    setWorking(action);
    setOutcome(null);
    setFolderProblem(null);
    const data = getBridge().data;
    try {
      let result: CoreResult<unknown>;
      if (action === 'save') result = await data.saveCopy();
      else if (action === 'restore') result = await data.restoreCopy();
      else result = await data.eraseAll();
      setOutcome(readOutcome(action, result));
    } catch {
      setOutcome({
        kind: 'failed',
        action,
        message: 'Something went wrong before this finished. Open the library to check your data.',
      });
    } finally {
      setWorking(null);
    }
  };

  const showSafetyCopies = async (): Promise<void> => {
    setFolderProblem(null);
    try {
      const result = await getBridge().data.showSafetyCopies();
      if (!result.ok) setFolderProblem(result.error.message);
    } catch {
      setFolderProblem('Couldn’t open the folder.');
    }
  };

  const said = outcome ? describeOutcome(outcome) : null;
  const serviceDown = coreStatus.state === 'failed' || coreStatus.state === 'stopped';
  const busyWith = (action: DataAction): boolean => working !== null && working !== action;

  return (
    <Section
      title="Your data"
      description="Back up, restore, or delete everything Adle stores on this computer."
    >
      <Stack gap={4}>
        {serviceDown && working === null ? (
          <Callout tone="warning" title="Adle isn’t fully running">
            You can’t save a copy right now. Restoring and deleting still work, and a restore may
            fix it.
          </Callout>
        ) : null}

        {said ? (
          <div ref={outcomeRef}>
            <Callout
              tone={said.tone}
              title={said.title}
              urgent={said.tone === 'danger'}
              actions={
                said.offersLibrary || said.offersSafetyCopies ? (
                  <>
                    {said.offersLibrary ? (
                      <Button icon={<Library />} onClick={() => navigate({ name: 'home' })}>
                        Open library
                      </Button>
                    ) : null}
                    {said.offersSafetyCopies ? (
                      <Button
                        variant="tertiary"
                        icon={<FolderOpen />}
                        onClick={() => void showSafetyCopies()}
                      >
                        Show safety copies
                      </Button>
                    ) : null}
                  </>
                ) : undefined
              }
            >
              {said.body}
            </Callout>
          </div>
        ) : null}

        <Card>
          <div className={styles.dataRow}>
            <div className={styles.dataText}>
              <h3 className={styles.rowTitle}>Save a copy</h3>
              <p className={styles.muted}>
                One file with your courses, lessons, answers, and progress, to keep or move to
                another computer. It isn’t password-protected, and doesn’t include your provider
                keys or the original files you imported.
              </p>
            </div>
            <div className={styles.dataActions}>
              <Button
                icon={<Download />}
                loading={working === 'save'}
                disabled={busyWith('save') || coreStatus.state !== 'ready'}
                onClick={() => void run('save')}
              >
                Save a copy
              </Button>
            </div>
          </div>
        </Card>

        <Card>
          <div className={styles.dataRow}>
            <div className={styles.dataText}>
              <h3 className={styles.rowTitle}>Restore from a copy</h3>
              <p className={styles.muted}>
                Replaces everything here with a copy you saved. What’s here now is kept as a safety
                copy first, so you can go back.
              </p>
              {folderProblem ? (
                <p className={styles.muted} role="alert">
                  {folderProblem}
                </p>
              ) : null}
            </div>
            <div className={styles.dataActions}>
              <Button
                icon={<History />}
                loading={working === 'restore'}
                disabled={busyWith('restore')}
                onClick={() => void run('restore')}
              >
                Restore from a copy
              </Button>
              <Button
                variant="tertiary"
                icon={<FolderOpen />}
                disabled={working !== null}
                onClick={() => void showSafetyCopies()}
              >
                Show safety copies
              </Button>
            </div>
          </div>
        </Card>

        <Card>
          <div className={styles.dataRow}>
            <div className={styles.dataText}>
              <h3 className={styles.rowTitle}>Delete everything</h3>
              <p className={styles.muted}>
                Permanently removes every course, material, lesson, answer, and safety copy from
                this computer. Copies saved elsewhere and your provider keys are kept. You’ll be
                asked to confirm.
              </p>
            </div>
            <div className={styles.dataActions}>
              <Button
                variant="destructive"
                icon={<Trash2 />}
                loading={working === 'erase'}
                disabled={busyWith('erase')}
                onClick={() => void run('erase')}
              >
                Delete everything
              </Button>
            </div>
          </div>
        </Card>
      </Stack>
    </Section>
  );
}

/** Where data lives, what leaves the device, and the controls over all of it. */
export function PrivacySettings() {
  return (
    <Stack gap={6}>
      <Section title="On this computer">
        <Card>
          <ul className={styles.list}>
            <li>Your courses, imported materials, lessons, answers, and progress.</li>
            <li>Questions you ask during lessons, and their answers.</li>
            <li>Your provider keys, encrypted by your operating system.</li>
            <li>Safety copies made before your data is updated or replaced.</li>
            <li>Narration is spoken by a voice already on this computer, and never recorded.</li>
          </ul>
        </Card>
      </Section>

      <Section
        title="Sent to your AI provider"
        description="Only when you ask Adle to create something, and only what that request needs."
      >
        <Card>
          <Stack gap={3}>
            <ul className={styles.list}>
              <li>
                <strong>Suggested concepts:</strong> the course name, topic, and description, your
                goal, existing concept names, and headings with short excerpts from your materials.
              </li>
              <li>
                <strong>A lesson:</strong> the course name, the concept and its objectives, your
                level on that concept in a few words, your preferences and goal, and a few related
                passages from your materials.
              </li>
              <li>
                <strong>A question during a lesson:</strong> your question, that part of the lesson,
                the lesson outline, the course name, the concept, and a few related passages. Never
                the answer to a question you haven’t answered.
              </li>
              <li>
                <strong>A key test:</strong> a fixed one-word prompt, with nothing of yours in it.
              </li>
            </ul>
            <p className={styles.muted}>
              Whole documents, your answers, your history, and your keys are never sent. Each key
              goes only to its own provider, and Adle contacts no other service. With one provider
              chosen, nothing ever goes to another. With Automatic, a request may go to the other
              provider you have a key for, and Adle says where before sending and who answered
              afterwards.
            </p>
          </Stack>
        </Card>
      </Section>

      <Section title="Never collected">
        <Card>
          <ul className={styles.list}>
            <li>No accounts, analytics, or telemetry.</li>
            <li>No crash reports.</li>
          </ul>
        </Card>
      </Section>

      <YourData />
    </Stack>
  );
}
