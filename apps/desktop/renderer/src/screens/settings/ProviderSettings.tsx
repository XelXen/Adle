import { ExternalLink, Eye, EyeOff, KeyRound } from 'lucide-react';
import { type FormEvent, useState } from 'react';

import type { ProviderChoice, ProviderUsage } from '@adle/contracts';
import {
  Badge,
  Button,
  Callout,
  Card,
  Dialog,
  ErrorState,
  IconButton,
  LoadingState,
  ProgressBar,
  Section,
  Stack,
  TextField,
  useToast,
} from '@adle/design-system';

import { useApp } from '../../app/AppContext';
import { getBridge, type ProviderKeyState, type ProviderKeyStates } from '../../lib/bridge';
import { callCore, describeError, unwrap } from '../../lib/core-client';
import { formatClockTime } from '../../lib/format';
import { useResource } from '../../lib/use-resource';
import { keyBadge, keyPage, limitsNote, modelOrder } from './provider-model';
import styles from './Settings.module.css';

/** Choose the model provider, look after its key, and see what has been used today. */
export function ProviderSettings() {
  const { coreStatus } = useApp();
  const toast = useToast();
  const keyState = useResource(`provider-key:${coreStatus.state}`, () =>
    getBridge().provider.keyState(),
  );
  const provider = useResource(`provider-status:${coreStatus.state}`, () =>
    callCore('provider.status'),
  );
  const usage = useResource(`provider-usage:${coreStatus.state}`, () => callCore('provider.usage'));
  const [switching, setSwitching] = useState<string | null>(null);

  const keys: ProviderKeyStates =
    keyState.resource.status === 'ready' ? keyState.resource.data : {};
  const keysKnown = keyState.resource.status === 'ready';

  const choose = async (choice: ProviderChoice): Promise<void> => {
    setSwitching(choice.provider_id);
    try {
      unwrap(await getBridge().provider.select(choice.provider_id));
      provider.reload();
      usage.reload();
      toast.show({
        tone: 'success',
        title: `Now using ${choice.display_name}`,
        description: keys[choice.provider_id]?.stored
          ? 'Its key is already saved.'
          : 'Add its key below to create courses and lessons with it.',
      });
    } catch (error) {
      toast.show({
        tone: 'danger',
        title: 'The provider was not changed',
        description: describeError(error),
      });
    } finally {
      setSwitching(null);
    }
  };

  if (provider.resource.status === 'loading') {
    return <LoadingState title="Reading provider settings…" />;
  }
  if (provider.resource.status === 'error') {
    return (
      <ErrorState
        title="Provider settings are unavailable"
        description={describeError(provider.resource.error)}
        actions={<Button onClick={provider.reload}>Try again</Button>}
      />
    );
  }

  const { providers } = provider.resource.data;
  const inUse = providers.find((choice) => choice.selected);

  return (
    <Stack gap={6}>
      <Callout tone="info" title="What is sent, and when">
        <p>
          When you ask Adle to build a course or a lesson, it sends the text needed for that request
          (for example a few passages from your notes and the concept being taught) to the provider
          in use below, and to no other. Your files, answers, and progress are never uploaded in
          bulk, and nothing is sent until you start a generation.
        </p>
      </Callout>

      <Section
        title="Provider"
        description={
          providers.length > 1
            ? 'Adle sends requests to one provider: the one you choose here. It never changes provider by itself.'
            : undefined
        }
      >
        <ul className={styles.choices} aria-label="AI providers">
          {providers.map((choice) => (
            <li key={choice.provider_id}>
              <ProviderCard
                choice={choice}
                alone={providers.length === 1}
                keyState={keys[choice.provider_id]}
                keysKnown={keysKnown}
                switching={switching}
                onChoose={() => void choose(choice)}
              />
            </li>
          ))}
        </ul>
      </Section>

      {inUse ? (
        <Section
          title="API key"
          description="Adle works without a key: you can explore sample content and your saved courses."
        >
          <KeyCard
            // A key typed for one provider must never be saved for another: start afresh.
            key={inUse.provider_id}
            provider={inUse}
            state={keys[inUse.provider_id]}
            known={keysKnown}
            onChange={(next) => {
              keyState.setData(next);
              // Whether the provider "has a key" is the core's to say, too.
              provider.reload();
            }}
          />
        </Section>
      ) : null}

      <Section
        title="Use today"
        description={`Adle's own count of what it has sent ${
          inUse ? `to ${inUse.display_name} ` : ''
        }today. The provider keeps the real total, and anything else that uses the same key counts against it too.`}
      >
        {usage.resource.status === 'loading' ? (
          <LoadingState title="Counting today's requests…" />
        ) : usage.resource.status === 'error' ? (
          <ErrorState
            title="Today's use could not be read"
            description={describeError(usage.resource.error)}
            actions={<Button onClick={usage.reload}>Try again</Button>}
          />
        ) : (
          <UsageCard usage={usage.resource.data} provider={inUse} />
        )}
      </Section>
    </Stack>
  );
}

/** One provider: where it is, which models it asks, and the control that chooses it. */
function ProviderCard({
  choice,
  alone,
  keyState,
  keysKnown,
  switching,
  onChoose,
}: {
  choice: ProviderChoice;
  /** It is the only provider there is, so there is nothing to choose. */
  alone: boolean;
  keyState: ProviderKeyState | undefined;
  keysKnown: boolean;
  /** The provider being switched to at the moment, if any. */
  switching: string | null;
  onChoose: () => void;
}) {
  const badge = keyBadge(keyState);
  return (
    <Card>
      <Stack gap={4}>
        <Stack direction="row" gap={3} align="center" wrap>
          <h3 className={styles.rowTitle}>{choice.display_name}</h3>
          {alone ? null : (
            <>
              {choice.selected ? <Badge tone="accent">In use</Badge> : null}
              {keysKnown ? <Badge tone={badge.tone}>{badge.text}</Badge> : null}
            </>
          )}
        </Stack>
        <dl className={styles.facts}>
          <div>
            <dt>Address</dt>
            <dd className={styles.mono}>{choice.base_url}</dd>
          </div>
          <div>
            <dt>{choice.models.length > 1 ? 'Models, in order' : 'Model'}</dt>
            <dd>
              <ol className={styles.models}>
                {choice.models.map((model) => (
                  <li key={model.id}>
                    {model.name} <span className={styles.modelId}>{model.id}</span>
                  </li>
                ))}
              </ol>
            </dd>
          </div>
        </dl>
        <p className={styles.muted}>{modelOrder(choice.models)}</p>
        {alone ? null : (
          <div>
            <Button
              size="small"
              aria-pressed={choice.selected}
              loading={switching === choice.provider_id}
              disabled={switching !== null && switching !== choice.provider_id}
              onClick={() => {
                if (!choice.selected) onChoose();
              }}
            >
              {choice.selected ? `Using ${choice.display_name}` : `Use ${choice.display_name}`}
            </Button>
          </div>
        )}
      </Stack>
    </Card>
  );
}

/** Add, replace, or remove the key of the provider in use. */
function KeyCard({
  provider,
  state,
  known,
  onChange,
}: {
  provider: ProviderChoice;
  state: ProviderKeyState | undefined;
  /** Whether what is stored has been read yet. */
  known: boolean;
  onChange: (next: ProviderKeyStates) => void;
}) {
  const { info } = useApp();
  const toast = useToast();
  const [draft, setDraft] = useState('');
  const [revealed, setRevealed] = useState(false);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [confirmingRemoval, setConfirmingRemoval] = useState(false);
  const [removing, setRemoving] = useState(false);

  const stored = state?.stored === true;
  const page = keyPage(provider.provider_id);

  const save = async (event: FormEvent): Promise<void> => {
    event.preventDefault();
    if (!draft.trim()) {
      setFormError('Enter your API key first.');
      return;
    }
    setSaving(true);
    setFormError(null);
    try {
      onChange(unwrap(await getBridge().provider.setApiKey(provider.provider_id, draft)));
      // Drop the plaintext from renderer state as soon as it has been handed over.
      setDraft('');
      setRevealed(false);
      toast.show({
        tone: 'success',
        title: 'Key saved',
        description: 'It is encrypted on this computer.',
      });
    } catch (error) {
      setFormError(describeError(error));
    } finally {
      setSaving(false);
    }
  };

  const remove = async (): Promise<void> => {
    setRemoving(true);
    try {
      onChange(unwrap(await getBridge().provider.clearApiKey(provider.provider_id)));
      toast.show({ tone: 'success', title: 'Key removed' });
      setConfirmingRemoval(false);
    } catch (error) {
      toast.show({
        tone: 'danger',
        title: 'The key could not be removed',
        description: describeError(error),
      });
    } finally {
      setRemoving(false);
    }
  };

  return (
    <>
      <Card>
        <Stack gap={4}>
          <Stack direction="row" gap={3} align="center" wrap>
            <KeyRound className={styles.leadIcon} aria-hidden="true" />
            <span className={styles.rowTitle}>{provider.display_name} key</span>
            {!known ? (
              <Badge>Checking…</Badge>
            ) : stored ? (
              <Badge tone="success">Saved · ends in {state.hint}</Badge>
            ) : (
              <Badge>Not set</Badge>
            )}
          </Stack>

          {!info.secureStorageAvailable ? (
            <Callout tone="warning" title="Secure storage is unavailable">
              This computer does not offer encrypted credential storage, so Adle will not save a
              key. Everything that does not need AI still works.
            </Callout>
          ) : (
            <form className={styles.keyForm} onSubmit={(event) => void save(event)} noValidate>
              <TextField
                label={stored ? 'Replace key' : 'API key'}
                type={revealed ? 'text' : 'password'}
                value={draft}
                onChange={(event) => {
                  setDraft(event.target.value);
                  setFormError(null);
                }}
                autoComplete="off"
                spellCheck={false}
                placeholder="Paste your key"
                error={formError}
                description={`Stored encrypted by your operating system. It is never shown again, and it is only ever sent to ${provider.display_name}, at the address above.`}
                trailing={
                  <IconButton
                    label={revealed ? 'Hide key' : 'Show key'}
                    icon={revealed ? <EyeOff /> : <Eye />}
                    size="small"
                    onClick={() => setRevealed((value) => !value)}
                  />
                }
              />
              <Stack direction="row" gap={3} wrap>
                <Button type="submit" variant="primary" loading={saving}>
                  {stored ? 'Replace key' : 'Save key'}
                </Button>
                {stored ? (
                  <Button variant="tertiary" onClick={() => setConfirmingRemoval(true)}>
                    Remove key
                  </Button>
                ) : null}
                {page ? (
                  <Button
                    variant="tertiary"
                    icon={<ExternalLink />}
                    onClick={() => void getBridge().app.openExternal(page.link)}
                  >
                    {page.label}
                  </Button>
                ) : null}
              </Stack>
            </form>
          )}
        </Stack>
      </Card>

      <Dialog
        open={confirmingRemoval}
        onClose={() => setConfirmingRemoval(false)}
        title={`Remove the saved ${provider.display_name} key?`}
        description={`Adle will stop being able to create new courses and lessons with ${provider.display_name} until you add a key again. Your existing courses and progress are not affected.`}
        dismissible={!removing}
        actions={
          <>
            <Button onClick={() => setConfirmingRemoval(false)} disabled={removing}>
              Keep key
            </Button>
            <Button variant="destructive" loading={removing} onClick={() => void remove()}>
              Remove key
            </Button>
          </>
        }
      />
    </>
  );
}

/** Adle's own count of today's requests to the provider in use. */
function UsageCard({
  usage,
  provider,
}: {
  usage: ProviderUsage;
  provider: ProviderChoice | undefined;
}) {
  return (
    <Card>
      <Stack gap={4}>
        <ProgressBar
          label="Requests"
          showLabel
          value={usage.requests_today / usage.requests_per_day}
          valueText={`${usage.requests_today.toLocaleString()} of ${usage.requests_per_day.toLocaleString()}`}
        />
        <ProgressBar
          label="Tokens (words and parts of words)"
          showLabel
          value={usage.tokens_today / usage.tokens_per_day}
          valueText={`about ${usage.tokens_today.toLocaleString()} of ${usage.tokens_per_day.toLocaleString()}`}
        />
        <p className={styles.usageNote}>
          {limitsNote(
            { display_name: provider?.display_name ?? 'The provider' },
            usage,
            formatClockTime(usage.resets_at),
          )}
        </p>
      </Stack>
    </Card>
  );
}
