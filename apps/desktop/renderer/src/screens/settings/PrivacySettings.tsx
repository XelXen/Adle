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
        message:
          'Something went wrong before Adle could finish. Open the library to see how things stand.',
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
      setFolderProblem('The folder could not be opened.');
    }
  };

  const said = outcome ? describeOutcome(outcome) : null;
  const serviceDown = coreStatus.state === 'failed' || coreStatus.state === 'stopped';
  const busyWith = (action: DataAction): boolean => working !== null && working !== action;

  return (
    <Section
      title="Your data"
      description="Everything Adle holds is on this computer. You can take a copy of it, put a copy back, or remove it all."
    >
      <Stack gap={4}>
        {serviceDown && working === null ? (
          <Callout tone="warning" title="The local service is not running">
            A copy cannot be saved until it is. Restoring from a copy and deleting everything still
            work, and restoring may be what gets it going again.
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
                        Go to the library
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
                One file with your courses, the text taken from your materials, your lessons,
                answers, and progress. Keep it wherever you like, or take it to another computer. It
                is an ordinary file, not protected by a password, so keep it as you would the notes
                themselves. Your AI provider key is not in it, and neither are the original files
                you imported: Adle does not need them again.
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
                Replaces what is here now with a copy you saved. What is here now is kept as a
                safety copy first, so you can go back. The local service restarts while this
                happens; it takes a few seconds.
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
                Permanently removes every course, imported material, lesson, answer, and safety copy
                from this computer. Copies you saved elsewhere and your AI provider key are not
                touched. You are asked once more before anything is deleted.
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
      <Section title="Stored on this computer">
        <Card>
          <ul className={styles.list}>
            <li>Course materials you import, and the text taken from them.</li>
            <li>Your curriculum, lessons, answers, and learning progress.</li>
            <li>
              Lessons written with AI, including the code that draws their pictures. Narration is
              spoken by a voice already on this computer and is never recorded.
            </li>
            <li>Safety copies Adle makes before it updates or replaces your data.</li>
            <li>
              The key of each AI provider you set up, encrypted by your operating system, and which
              provider you chose.
            </li>
          </ul>
        </Card>
      </Section>

      <Section title="Sent to the AI provider">
        <Card>
          <Stack gap={3}>
            <ul className={styles.list}>
              <li>
                When you ask for concepts: the course&rsquo;s name, topic, and description, your
                goal, the names of the concepts it already has, and the headings of your materials
                with a few short excerpts.
              </li>
              <li>
                When you ask for a lesson: the course&rsquo;s name, the concept and its objectives,
                where you stand on that concept in a few words, your preferences for pace and depth,
                your goal, and a few related passages from your materials.
              </li>
            </ul>
            <p className={styles.muted}>
              Nothing is sent until you start one of these, and each says what it sends before it
              does. Whole documents, your answers, the record of what you have learnt, and your key
              are never sent as content. Your answers are checked on this computer.
            </p>
            <p className={styles.muted}>
              These go to the one provider you chose under AI provider, with that provider&rsquo;s
              key and no other. Adle never changes provider on its own and contacts no other
              service. Where a provider offers several models, another of its models can stand in
              while the first is not available; you are told there which ones, and told again
              whenever it happens.
            </p>
          </Stack>
        </Card>
      </Section>

      <Section title="Never collected">
        <Card>
          <ul className={styles.list}>
            <li>No accounts, analytics, advertising identifiers, or usage telemetry.</li>
            <li>No crash reports are uploaded.</li>
          </ul>
        </Card>
      </Section>

      <YourData />
    </Stack>
  );
}
