import { Download, Info, Trash2 } from 'lucide-react';
import { type ReactNode, useEffect, useId, useState } from 'react';

import type { Job, LearnerPreferences, VoiceStatus, VoiceTier } from '@adle/contracts';
import {
  Badge,
  Button,
  Callout,
  Card,
  Dialog,
  ErrorState,
  InfoPopover,
  LoadingState,
  ProgressBar,
  Select,
  Stack,
  useToast,
} from '@adle/design-system';

import { callCore, describeError } from '../../lib/core-client';
import { useResource } from '../../lib/use-resource';
import styles from './Settings.module.css';
import {
  aboutSize,
  computerVoiceInUse,
  downloadNote,
  isRecommended,
  setupBytes,
  setupProgress,
  tierState,
} from './voice-model';
import { ComputerVoiceSettings } from './VoiceSettings';

/** How often a setup under way is looked at. */
export const LOOK_EVERY_MS = 1_500;

interface Failure {
  tier: string;
  message: string;
}

/**
 * The voices that can read a lesson, from the lightest to the richest (ADR-042): the
 * computer's own, then the natural voices this computer can run, each set up at the
 * learner's word. A setup goes on in the background; this follows it while it is shown.
 */
export function VoiceChoices({
  preferences,
  onChange,
}: {
  preferences: LearnerPreferences;
  onChange: (patch: Partial<LearnerPreferences>) => void;
}) {
  const toast = useToast();
  const voice = useResource('voice-status', () => callCore('voice.status'));
  const [sending, setSending] = useState<string | null>(null);
  const [removing, setRemoving] = useState<VoiceTier | null>(null);
  const [failure, setFailure] = useState<Failure | null>(null);
  const { setData } = voice;
  const following =
    voice.resource.status === 'ready' ? (voice.resource.data.setting_up?.id ?? null) : null;

  // While a voice is set up it is looked at now and then; when that ends, how it ended is said.
  useEffect(() => {
    if (following === null) return;
    let stopped = false;
    let timer = 0;
    const look = async (): Promise<void> => {
      const next = await callCore('voice.status');
      if (stopped) return;
      if (next.setting_up?.id !== following) {
        const job = await callCore('jobs.get', { path: { job_id: following } });
        if (stopped) return;
        const name = next.tiers.find((tier) => tier.id === job.subject_id)?.name;
        if (job.status === 'failed') {
          setFailure({
            tier: job.subject_id ?? '',
            message: job.error_message ?? 'Something went wrong. Try again.',
          });
        } else if (job.status === 'succeeded' && name) {
          toast.show({ tone: 'success', title: `The ${name} voice is ready` });
        }
      }
      setData(next);
    };
    const later = (): void => {
      timer = window.setTimeout(() => {
        look()
          .catch(() => undefined)
          .finally(() => {
            if (!stopped) later();
          });
      }, LOOK_EVERY_MS);
    };
    later();
    return () => {
      stopped = true;
      window.clearTimeout(timer);
    };
  }, [following, setData, toast]);

  if (voice.resource.status === 'loading') {
    return <LoadingState title="Loading voices…" />;
  }
  if (voice.resource.status === 'error') {
    return (
      <ErrorState
        title="Couldn’t load the voices"
        description={describeError(voice.resource.error)}
        actions={<Button onClick={voice.reload}>Try again</Button>}
      />
    );
  }
  const status = voice.resource.data;

  /** Send one change; show what it comes back with, or say why it could not be made. */
  const send = async (
    what: string,
    work: () => Promise<VoiceStatus | null>,
    failed: string,
  ): Promise<void> => {
    setSending(what);
    try {
      const next = await work();
      if (next) setData(next);
    } catch (error) {
      toast.show({ tone: 'danger', title: failed, description: describeError(error) });
    } finally {
      setSending(null);
    }
  };

  const use = (tier: VoiceTier | null): Promise<void> =>
    send(
      `use:${tier?.id ?? 'computer'}`,
      () =>
        callCore('voice.choose', {
          body: tier ? { tier: tier.id, enabled: true } : { enabled: false },
        }),
      'Couldn’t change the voice',
    );

  const setUp = (tier: VoiceTier): Promise<void> =>
    send(
      `setup:${tier.id}`,
      async () => {
        setFailure(null);
        const job: Job = await callCore('voice.install', { body: { tier: tier.id } });
        return { ...status, setting_up: job };
      },
      'Couldn’t start setting the voice up',
    );

  const stop = (job: Job): Promise<void> =>
    send(
      'stop',
      async () => {
        await callCore('jobs.cancel', { path: { job_id: job.id } });
        return null;
      },
      'Couldn’t stop it',
    );

  const remove = (tier: VoiceTier): Promise<void> =>
    send(
      `remove:${tier.id}`,
      async () => {
        const next = await callCore('voice.remove', { path: { tier: tier.id } });
        setRemoving(null);
        toast.show({ tone: 'success', title: `The ${tier.name} voice was removed` });
        return next;
      },
      'Couldn’t remove the voice',
    );

  const chooseSpeaker = (tier: VoiceTier, speaker: string): Promise<void> =>
    send(
      `speaker:${tier.id}`,
      () => callCore('voice.choose', { body: { tier: tier.id, speaker } }),
      'Couldn’t change the voice',
    );

  const computer = computerVoiceInUse(status);
  return (
    <>
      <ul className={styles.choices} aria-label="Voices">
        <ComputerVoiceCard
          inUse={computer}
          sending={sending === 'use:computer'}
          onUse={() => void use(null)}
        >
          <ComputerVoiceSettings preferences={preferences} onChange={onChange} />
        </ComputerVoiceCard>
        {status.tiers.map((tier) => (
          <TierCard
            key={tier.id}
            tier={tier}
            status={status}
            sending={sending}
            failure={failure?.tier === tier.id ? failure.message : null}
            onUse={() => void use(tier)}
            onSetUp={() => void setUp(tier)}
            onStop={(job) => void stop(job)}
            onRemove={() => setRemoving(tier)}
            onSpeaker={(speaker) => void chooseSpeaker(tier, speaker)}
          />
        ))}
      </ul>
      {removing ? (
        <Dialog
          open
          onClose={() => setRemoving(null)}
          title={`Remove the ${removing.name} voice?`}
          description={`Frees ${aboutSize(setupBytes(removing))} at most. You can set it up again later.`}
          size="small"
          actions={
            <>
              <Button variant="secondary" onClick={() => setRemoving(null)}>
                Cancel
              </Button>
              <Button
                variant="destructive"
                icon={<Trash2 />}
                loading={sending === `remove:${removing.id}`}
                onClick={() => void remove(removing)}
              >
                Remove
              </Button>
            </>
          }
        />
      ) : null}
    </>
  );
}

function VoiceHeading({
  id,
  name,
  inUse,
  best,
}: {
  id: string;
  name: string;
  inUse: boolean;
  best?: boolean;
}) {
  return (
    <Stack direction="row" gap={3} align="center" wrap>
      <h3 id={id} className={styles.providerName}>
        {name}
      </h3>
      {inUse ? <Badge tone="accent">In use</Badge> : null}
      {best ? <Badge tone="info">Best for this computer</Badge> : null}
    </Stack>
  );
}

function ComputerVoiceCard({
  inUse,
  sending,
  onUse,
  children,
}: {
  inUse: boolean;
  sending: boolean;
  onUse: () => void;
  children: ReactNode;
}) {
  const heading = useId();
  return (
    <Card as="li" aria-labelledby={heading}>
      <Stack gap={4}>
        <div className={styles.dataRow}>
          <div className={styles.dataText}>
            <VoiceHeading id={heading} name="Computer’s voice" inUse={inUse} />
            <p className={styles.muted}>The voices that came with this computer.</p>
          </div>
          {inUse ? null : (
            <div className={styles.dataActions}>
              <Button loading={sending} onClick={onUse} aria-label="Use the computer’s voice">
                Use
              </Button>
            </div>
          )}
        </div>
        {children}
      </Stack>
    </Card>
  );
}

function TierCard({
  tier,
  status,
  sending,
  failure,
  onUse,
  onSetUp,
  onStop,
  onRemove,
  onSpeaker,
}: {
  tier: VoiceTier;
  status: VoiceStatus;
  sending: string | null;
  failure: string | null;
  onUse: () => void;
  onSetUp: () => void;
  onStop: (job: Job) => void;
  onRemove: () => void;
  onSpeaker: (speaker: string) => void;
}) {
  const heading = useId();
  const state = tierState(status, tier);
  const best = isRecommended(status, tier) && state.kind !== 'unavailable';
  // A voice a developer set up by hand is used as it is: nothing here sets it up or removes it.
  const ownable = !status.borrowed;
  const progress = state.kind === 'setting-up' ? setupProgress(state.job) : null;
  return (
    <Card as="li" aria-labelledby={heading}>
      <Stack gap={4}>
        <div className={styles.dataRow}>
          <div className={styles.dataText}>
            <VoiceHeading
              id={heading}
              name={tier.name}
              inUse={state.kind === 'in-use'}
              best={best}
            />
            <p className={styles.muted}>{tier.description}</p>
            {state.kind === 'unavailable' ? <p className={styles.muted}>{state.why}</p> : null}
          </div>
          <div className={styles.dataActions}>
            {(state.kind === 'available' || state.kind === 'waiting') && ownable ? (
              <>
                <span className={styles.muted}>{aboutSize(setupBytes(tier))}</span>
                <InfoPopover label="What is downloaded" icon={<Info />} title="What is downloaded">
                  <p>{downloadNote(tier)}</p>
                </InfoPopover>
                <Button
                  variant={best ? 'primary' : 'secondary'}
                  icon={<Download />}
                  disabled={state.kind === 'waiting'}
                  loading={sending === `setup:${tier.id}`}
                  onClick={onSetUp}
                  aria-label={`Set up the ${tier.name} voice`}
                >
                  Set up
                </Button>
              </>
            ) : null}
            {state.kind === 'ready' ? (
              <Button
                loading={sending === `use:${tier.id}`}
                onClick={onUse}
                aria-label={`Use the ${tier.name} voice`}
              >
                Use
              </Button>
            ) : null}
            {(state.kind === 'ready' || state.kind === 'in-use') && ownable ? (
              <Button
                variant="tertiary"
                icon={<Trash2 />}
                onClick={onRemove}
                aria-label={`Remove the ${tier.name} voice`}
              >
                Remove
              </Button>
            ) : null}
            {state.kind === 'setting-up' ? (
              <Button
                variant="secondary"
                loading={sending === 'stop'}
                onClick={() => onStop(state.job)}
                aria-label={`Stop setting up the ${tier.name} voice`}
              >
                Stop
              </Button>
            ) : null}
          </div>
        </div>
        {progress ? (
          <ProgressBar
            label={progress.label}
            showLabel
            value={progress.value}
            valueText={progress.valueText}
          />
        ) : null}
        {state.kind === 'waiting' ? (
          <p className={styles.muted}>Another voice is being set up.</p>
        ) : null}
        {state.kind === 'in-use' && tier.speakers.length > 0 ? (
          <div className={styles.voiceField}>
            <Select
              label="Speaker"
              value={status.speakers[tier.id] ?? tier.speakers[0]!.id}
              options={tier.speakers.map((speaker) => ({
                value: speaker.id,
                label: `${speaker.name} · ${speaker.description}`,
              }))}
              disabled={sending === `speaker:${tier.id}`}
              onValueChange={onSpeaker}
            />
          </div>
        ) : null}
        {failure ? (
          <Callout tone="danger" title="Couldn’t set the voice up">
            {failure}
          </Callout>
        ) : null}
      </Stack>
    </Card>
  );
}
