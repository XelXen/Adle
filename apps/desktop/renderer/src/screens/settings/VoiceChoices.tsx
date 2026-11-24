import { Download, Info, Play, Trash2 } from 'lucide-react';
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
  TextArea,
  useToast,
} from '@adle/design-system';

import { callCore, describeError } from '../../lib/core-client';
import { useResource } from '../../lib/use-resource';
import { type SampleRequest, useVoiceSample } from '../../lib/use-voice-sample';
import styles from './Settings.module.css';
import {
  aboutSize,
  computerVoiceInUse,
  downloadNote,
  recordingNote,
  speedNote,
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
  const sample = useVoiceSample();
  const following =
    voice.resource.status === 'ready' ? (voice.resource.data.setting_up?.id ?? null) : null;
  const recording =
    voice.resource.status === 'ready' ? voice.resource.data.recording.length > 0 : false;

  // While lessons are recorded in a voice just chosen, how far they have come is looked at.
  useEffect(() => {
    if (!recording) return;
    let stopped = false;
    const timer = window.setInterval(() => {
      callCore('voice.status').then(
        (next) => {
          if (!stopped) setData(next);
        },
        () => undefined,
      );
    }, LOOK_EVERY_MS);
    return () => {
      stopped = true;
      window.clearInterval(timer);
    };
  }, [recording, setData]);

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

  const describe = (design: string): Promise<void> =>
    send(
      'design',
      async () => {
        const next = await callCore('voice.choose', { body: { design } });
        toast.show({ tone: 'success', title: 'Voice saved' });
        return next;
      },
      'Couldn’t save the voice',
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
            onDesign={(design) => void describe(design)}
            sampling={sample.making}
            onListen={(key, request) => void sample.listen(key, request)}
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
  onDesign,
  sampling,
  onListen,
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
  onDesign: (design: string) => void;
  sampling: string | null;
  onListen: (key: string, request: SampleRequest) => void;
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
            {speedNote(tier) ? <p className={styles.muted}>{speedNote(tier)}</p> : null}
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
        {state.kind === 'in-use' && recordingNote(status.recording) ? (
          <p className={styles.muted} role="status">
            {recordingNote(status.recording)}
          </p>
        ) : null}
        {(state.kind === 'in-use' || state.kind === 'ready') && tier.speakers.length > 0 ? (
          <Speakers
            tier={tier}
            chosen={state.kind === 'in-use' ? (status.speakers[tier.id] ?? null) : null}
            sending={sending === `speaker:${tier.id}`}
            sampling={sampling}
            onSpeaker={onSpeaker}
            onListen={onListen}
          />
        ) : null}
        {(state.kind === 'in-use' || state.kind === 'ready') && tier.id === 'expressive' ? (
          <Design
            status={status}
            saving={sending === 'design'}
            sampling={sampling}
            onSave={onDesign}
            onListen={onListen}
          />
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

/**
 * The speakers of a voice, each to listen to before it is chosen (ADR-057): choosing one
 * records the lessons opened last in it, so a sample is the way to compare them.
 */
function Speakers({
  tier,
  chosen,
  sending,
  sampling,
  onSpeaker,
  onListen,
}: {
  tier: VoiceTier;
  chosen: string | null;
  sending: boolean;
  sampling: string | null;
  onSpeaker: (speaker: string) => void;
  onListen: (key: string, request: SampleRequest) => void;
}) {
  return (
    <ul className={styles.speakers} aria-label={`Speakers of the ${tier.name} voice`}>
      {tier.speakers.map((speaker) => {
        const key = `${tier.id}:${speaker.id}`;
        return (
          <li key={speaker.id} className={styles.dataRow}>
            <div className={styles.dataText}>
              <p>
                <strong>{speaker.name}</strong>{' '}
                {chosen === speaker.id ? <Badge tone="accent">In use</Badge> : null}{' '}
                <span className={styles.muted}>{speaker.description}</span>
              </p>
            </div>
            <div className={styles.dataActions}>
              <Button
                variant="tertiary"
                icon={<Play />}
                loading={sampling === key}
                disabled={sampling !== null && sampling !== key}
                onClick={() => onListen(key, { tier: tier.id, speaker: speaker.id })}
                aria-label={`Listen to ${speaker.name}`}
              >
                Listen
              </Button>
              {chosen === null ? null : (
                <Button
                  aria-pressed={chosen === speaker.id}
                  disabled={sending}
                  onClick={() => {
                    if (chosen !== speaker.id) onSpeaker(speaker.id);
                  }}
                  aria-label={`Use ${speaker.name}`}
                >
                  Use
                </Button>
              )}
            </div>
          </li>
        );
      })}
    </ul>
  );
}

/**
 * Who reads the lessons in the Expressive voice, in the learner's words, with descriptions to
 * start from (ADR-057). Each lesson adds how it is delivered; this is the voice itself.
 */
function Design({
  status,
  saving,
  sampling,
  onSave,
  onListen,
}: {
  status: VoiceStatus;
  saving: boolean;
  sampling: string | null;
  onSave: (design: string) => void;
  onListen: (key: string, request: SampleRequest) => void;
}) {
  const [draft, setDraft] = useState(status.design);
  const presets = status.design_presets;
  const preset = presets.find((item) => item.text === draft)?.name ?? '';
  const changed = draft.trim() !== status.design;
  const key = 'expressive:design';
  return (
    <div className={styles.voiceField}>
      <Stack gap={3}>
        <Select
          label="Start from"
          value={preset}
          options={[
            ...(preset === '' ? [{ value: '', label: 'Your own words' }] : []),
            ...presets.map((item) => ({ value: item.name, label: item.name })),
          ]}
          onValueChange={(name) => {
            const chosen = presets.find((item) => item.name === name);
            if (chosen) setDraft(chosen.text);
          }}
        />
        <TextArea
          label="The voice"
          description="Who reads your lessons. Each lesson adds how it is delivered."
          rows={3}
          maxLength={200}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
        />
        <Stack direction="row" gap={3} align="center" wrap>
          <Button
            variant="tertiary"
            icon={<Play />}
            loading={sampling === key}
            disabled={draft.trim() === '' || (sampling !== null && sampling !== key)}
            onClick={() => onListen(key, { tier: 'expressive', design: draft.trim() })}
            aria-label="Listen to this voice"
          >
            Listen
          </Button>
          <Button
            disabled={!changed || draft.trim() === ''}
            loading={saving}
            onClick={() => onSave(draft.trim())}
          >
            Save
          </Button>
        </Stack>
      </Stack>
    </div>
  );
}
