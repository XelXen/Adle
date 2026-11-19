import { CircleCheck, RotateCw } from 'lucide-react';
import { useState } from 'react';

import { Badge, Button, Card, Section, Stack } from '@adle/design-system';

import type { PlayerStatus, SceneFailure } from '../../../../player/host/WanimPlayerAdapter';
import { useApp } from '../../app/AppContext';
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
        title="Local service"
        description="The part of Adle that stores and prepares your courses."
      >
        <Card>
          <div className={styles.statusRow}>
            <div className={styles.statusText}>
              <Stack direction="row" gap={3} align="center" wrap>
                <span className={styles.rowTitle}>Core service</span>
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
              Restart service
            </Button>
          </div>
        </Card>
      </Section>

      <Section
        title="Visual runtime check"
        description="Runs a small interactive scene to confirm that animations work on this computer."
      >
        {checking ? (
          <Stack gap={4} className={styles.checkStage}>
            <ScenePlayer
              source={checkScene}
              title="Runtime check: a circle that resizes with a slider"
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
                    The scene could not run ({failure.stage}). Lessons will use text explanations
                    instead.
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
              <p className={styles.muted}>Nothing is sent anywhere; the scene runs locally.</p>
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
    </Stack>
  );
}
