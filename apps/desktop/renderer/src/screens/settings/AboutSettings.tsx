import { CircleCheck, FolderOpen, RotateCw } from 'lucide-react';
import { useState } from 'react';

import { Badge, Button, Card, Section, Stack } from '@adle/design-system';

import type { PlayerStatus, SceneFailure } from '../../../../player/host/WanimPlayerAdapter';
import { useApp } from '../../app/AppContext';
import { getBridge } from '../../lib/bridge';
import { ScenePlayer } from '../../components/ScenePlayer';
import checkScene from './runtime-check.py?raw';
import styles from './Settings.module.css';

const CORE_STATE_LABEL = {
  starting: 'Starting…',
  ready: 'Running',
  failed: 'Needs attention',
  stopped: 'Stopped',
} as const;

/** Versions, the state of the local service, and a self-check of the visual runtime. */
export function AboutSettings() {
  const { info, coreStatus, restartCore } = useApp();
  const [restarting, setRestarting] = useState(false);
  const [checking, setChecking] = useState(false);
  const [sceneStatus, setSceneStatus] = useState<PlayerStatus>('idle');
  const [failure, setFailure] = useState<SceneFailure | null>(null);
  const [interacted, setInteracted] = useState(false);
  const [logsProblem, setLogsProblem] = useState<string | null>(null);

  const showLogs = async (): Promise<void> => {
    setLogsProblem(null);
    try {
      const result = await getBridge().app.showLogs();
      if (!result.ok) setLogsProblem(result.error.message);
    } catch {
      setLogsProblem('Couldn’t open the folder.');
    }
  };

  const restart = async (): Promise<void> => {
    setRestarting(true);
    try {
      await restartCore();
    } finally {
      setRestarting(false);
    }
  };

  const sceneWorks =
    sceneStatus === 'interactive' || sceneStatus === 'playing' || sceneStatus === 'finished';

  return (
    <Stack gap={6}>
      <Section
        title="Status"
        description="Adle’s background service stores your courses and prepares lessons. Restart it if something seems stuck."
      >
        <Card>
          <div className={styles.statusRow}>
            <div className={styles.statusText}>
              <Stack direction="row" gap={3} align="center" wrap>
                <span className={styles.rowTitle}>Background service</span>
                <Badge
                  tone={
                    coreStatus.state === 'ready'
                      ? 'success'
                      : coreStatus.state === 'starting'
                        ? 'warning'
                        : 'danger'
                  }
                >
                  {CORE_STATE_LABEL[coreStatus.state]}
                </Badge>
              </Stack>
              {coreStatus.state === 'failed' ? (
                <p className={styles.muted}>{coreStatus.message}</p>
              ) : coreStatus.state === 'ready' ? (
                <p className={styles.muted}>Version {coreStatus.version}</p>
              ) : null}
            </div>
            <Button icon={<RotateCw />} loading={restarting} onClick={() => void restart()}>
              Restart
            </Button>
          </div>
        </Card>
      </Section>

      <Section
        title="Animation check"
        description="Runs a small interactive scene to confirm that animations work on this computer."
      >
        {checking ? (
          <Stack gap={4} className={styles.checkStage}>
            <ScenePlayer
              source={checkScene}
              title="Animation check: a circle that resizes with a slider"
              controlLabels={{ size: 'Circle radius' }}
              fallback={
                <p>
                  The check scene shows a circle whose radius follows a slider, next to the formula
                  for its area.
                </p>
              }
              onStatusChange={(status) => {
                setSceneStatus(status);
                if (status !== 'failed') setFailure(null);
              }}
              onFailure={setFailure}
              onSceneEvent={(event) => {
                if (event.name === 'explored') setInteracted(true);
              }}
            />
            <div className={styles.checkResult} role="status">
              {failure ? (
                <>
                  <Badge tone="danger">Not working</Badge>
                  <span className={styles.muted}>
                    Couldn’t run the scene ({failure.stage}). Lessons will use text instead.
                  </span>
                </>
              ) : sceneWorks ? (
                <>
                  <Badge tone="success" icon={<CircleCheck />}>
                    Rendering works
                  </Badge>
                  <Badge
                    tone={interacted ? 'success' : 'neutral'}
                    icon={interacted ? <CircleCheck /> : undefined}
                  >
                    {interacted ? 'Interaction works' : 'Move the slider to test interaction'}
                  </Badge>
                </>
              ) : (
                <Badge>Running…</Badge>
              )}
            </div>
          </Stack>
        ) : (
          <Card>
            <div className={styles.statusRow}>
              <p className={styles.muted}>Runs on this computer. Nothing is sent.</p>
              <Button onClick={() => setChecking(true)}>Run check</Button>
            </div>
          </Card>
        )}
      </Section>

      <Section title="About">
        <Card>
          <dl className={styles.facts}>
            <div>
              <dt>Adle</dt>
              <dd>{info.version}</dd>
            </div>
            <div>
              <dt>Electron</dt>
              <dd>{info.versions.electron}</dd>
            </div>
            <div>
              <dt>Chromium</dt>
              <dd>{info.versions.chrome}</dd>
            </div>
            <div>
              <dt>Platform</dt>
              <dd>{info.platform}</dd>
            </div>
          </dl>
        </Card>
      </Section>

      <Section
        title="Logs"
        description="A short log of app errors, kept on this computer and never sent anywhere."
      >
        <Card>
          <div className={styles.statusRow}>
            <div className={styles.statusText}>
              <p className={styles.muted}>
                It records what went wrong in the app, never what you typed, opened, or answered.
                Share these files if you ask someone for help.
              </p>
              {logsProblem ? (
                <p className={styles.muted} role="alert">
                  {logsProblem}
                </p>
              ) : null}
            </div>
            <Button icon={<FolderOpen />} onClick={() => void showLogs()}>
              Open log folder
            </Button>
          </div>
        </Card>
      </Section>
    </Stack>
  );
}
