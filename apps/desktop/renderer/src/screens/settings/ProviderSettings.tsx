import { CircleCheck, ExternalLink, Eye, EyeOff, Route } from 'lucide-react';
import { type FormEvent, useId, useState } from 'react';

import type { Job, ProviderChoice, ProviderStatus } from '@adle/contracts';
import {
  Badge,
  Button,
  Callout,
  Card,
  ChoiceButtons,
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
import { jobFailure } from '../../lib/generation';
import { AUTOMATIC, readCheck } from '../../lib/provider';
import { isJobActive, useJob } from '../../lib/use-job';
import { useResource } from '../../lib/use-resource';
import {
  couldUseBoth,
  keyBadge,
  keyPage,
  limitsNote,
  modelOrder,
  providerCharacter,
  routeLines,
  selectionOptions,
} from './provider-model';
import styles from './Settings.module.css';

/**
 * Which providers Adle may use, their keys, and what has been used today.
 *
 * The learner chooses: one provider, or "automatic" (every provider they have a key for,
 * each for what it is good at). Nothing else changes that choice (ADR-023).
 */
export function ProviderSettings() {
  const { coreStatus } = useApp();
  const toast = useToast();
  const keyState = useResource(`provider-key:${coreStatus.state}`, () =>
    getBridge().provider.keyState(),
  );
  const provider = useResource(`provider-status:${coreStatus.state}`, () =>
    callCore('provider.status'),
  );
  const [choosing, setChoosing] = useState<string | null>(null);

  const keys: ProviderKeyStates =
    keyState.resource.status === 'ready' ? keyState.resource.data : {};
  const keysKnown = keyState.resource.status === 'ready';

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

  const status = provider.resource.data;
  const { providers } = status;
  const options = selectionOptions(providers);

  const choose = async (selection: string): Promise<void> => {
    const chosen = options.find((option) => option.value === selection);
    setChoosing(selection);
    try {
      unwrap(await getBridge().provider.select(selection));
      provider.reload();
      toast.show({
        tone: 'success',
        title:
          selection === AUTOMATIC
            ? 'Adle now uses every provider with a key'
            : `Now using ${chosen?.label ?? 'that provider'}`,
        description:
          selection === AUTOMATIC || keys[selection]?.stored
            ? undefined
            : 'Add its key below to create courses and lessons with it.',
      });
    } catch (error) {
      toast.show({
        tone: 'danger',
        title: 'The choice was not changed',
        description: describeError(error),
      });
    } finally {
      setChoosing(null);
    }
  };

  return (
    <Stack gap={6}>
      <Callout tone="info" title="What is sent, and when">
        <p>
          When you ask Adle to build a course, write a lesson, or answer a question, it sends the
          text needed for that request (for example the concept being taught and a few passages from
          your notes) to a provider you have given a key to below, and to no other. Before each
          request Adle says where it will go, and afterwards who wrote the answer. Your files,
          answers, and progress are never uploaded in bulk, and nothing is sent until you ask.
        </p>
      </Callout>

      {providers.length > 1 ? (
        <Section
          title="Which provider to use"
          description="This is your choice, and nothing else changes it."
        >
          <Stack gap={4}>
            {couldUseBoth(status) ? (
              <Callout
                tone="info"
                title="You have keys for more than one provider"
                actions={
                  <Button
                    size="small"
                    loading={choosing === AUTOMATIC}
                    disabled={choosing !== null && choosing !== AUTOMATIC}
                    onClick={() => void choose(AUTOMATIC)}
                  >
                    Use both, automatically
                  </Button>
                }
              >
                Adle can use each for what it is best at: the quicker one for what you are waiting
                for, the one with more room for long work.
              </Callout>
            ) : null}
            <ChoiceButtons
              label="Which provider to use"
              value={status.selection}
              pending={choosing}
              options={options.map((option) => ({
                value: option.value,
                label: option.label,
                description: option.description,
                badge: option.recommended ? <Badge tone="accent">Recommended</Badge> : undefined,
              }))}
              onValueChange={(selection) => void choose(selection)}
            />
            <RoutesCard status={status} />
          </Stack>
        </Section>
      ) : null}

      <Section
        title={providers.length > 1 ? 'Providers and keys' : 'Provider and key'}
        description="Adle works without a key: you can explore sample content and your saved courses."
      >
        <ul className={styles.choices} aria-label="AI providers">
          {providers.map((choice) => (
            <li key={choice.provider_id}>
              <ProviderCard
                choice={choice}
                alone={providers.length === 1}
                keyState={keys[choice.provider_id]}
                keysKnown={keysKnown}
                onKeysChange={(next) => {
                  keyState.setData(next);
                  // Whether a provider "has a key", and where requests go, is the core's to say.
                  provider.reload();
                }}
                onChecked={provider.reload}
              />
            </li>
          ))}
        </ul>
      </Section>
    </Stack>
  );
}

/** Where each kind of request would go at this moment, as the core says. */
function RoutesCard({ status }: { status: ProviderStatus }) {
  const heading = useId();
  return (
    <Card padding="compact" tone="subtle">
      <section aria-labelledby={heading}>
        <Stack gap={3}>
          <Stack direction="row" gap={2} align="center">
            <Route className={styles.leadIcon} aria-hidden="true" />
            <h3 id={heading} className={styles.rowTitle}>
              Where requests go now
            </h3>
          </Stack>
          {status.key_configured ? (
            <dl className={styles.routes}>
              {routeLines(status).map((line) => (
                <div key={line.work}>
                  <dt>{line.label}</dt>
                  <dd>
                    {line.destination}
                    {line.reason ? <span className={styles.routeReason}>{line.reason}</span> : null}
                  </dd>
                </div>
              ))}
            </dl>
          ) : (
            <p className={styles.muted}>
              Nowhere yet: there is no key for
              {status.selection === AUTOMATIC ? ' any provider' : ' the provider you chose'}. Add
              one below.
            </p>
          )}
        </Stack>
      </section>
    </Card>
  );
}

/** One provider: what it is, its key, a way to check the key, and what was sent today. */
function ProviderCard({
  choice,
  alone,
  keyState,
  keysKnown,
  onKeysChange,
  onChecked,
}: {
  choice: ProviderChoice;
  /** It is the only provider there is. */
  alone: boolean;
  keyState: ProviderKeyState | undefined;
  keysKnown: boolean;
  onKeysChange: (next: ProviderKeyStates) => void;
  /** A check of the key has finished: today's count has changed. */
  onChecked: () => void;
}) {
  const heading = useId();
  const badge = keyBadge(keyState);
  const { usage } = choice;
  return (
    <Card>
      <section aria-labelledby={heading}>
        <Stack gap={5}>
          <Stack gap={2}>
            <Stack direction="row" gap={3} align="center" wrap>
              <h3 id={heading} className={styles.providerName}>
                {choice.display_name}
              </h3>
              {keysKnown ? <Badge tone={badge.tone}>{badge.text}</Badge> : <Badge>Checking…</Badge>}
              {!alone && choice.in_use ? <Badge tone="accent">In use</Badge> : null}
            </Stack>
            <p className={styles.muted}>{providerCharacter(choice)}</p>
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

          <KeyControls
            // A key typed for one provider must never be saved for another.
            key={choice.provider_id}
            provider={choice}
            state={keyState}
            known={keysKnown}
            onChange={onKeysChange}
            onChecked={onChecked}
          />

          <div className={styles.usage}>
            <h4 className={styles.usageTitle}>Sent to {choice.display_name} today</h4>
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
              {limitsNote(choice, usage, formatClockTime(usage.resets_at))} The provider keeps the
              real total, and anything else that uses the same key counts against it too.
            </p>
          </div>
        </Stack>
      </section>
    </Card>
  );
}

/** Add, check, replace, or remove one provider's key. */
function KeyControls({
  provider,
  state,
  known,
  onChange,
  onChecked,
}: {
  provider: ProviderChoice;
  state: ProviderKeyState | undefined;
  /** Whether what is stored has been read yet. */
  known: boolean;
  onChange: (next: ProviderKeyStates) => void;
  onChecked: () => void;
}) {
  const { info } = useApp();
  const toast = useToast();
  const [draft, setDraft] = useState('');
  const [revealed, setRevealed] = useState(false);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [confirmingRemoval, setConfirmingRemoval] = useState(false);
  const [removing, setRemoving] = useState(false);
  const [checkStarted, setCheckStarted] = useState<Job | null>(null);
  const [checkRefusal, setCheckRefusal] = useState<string | null>(null);
  const [startingCheck, setStartingCheck] = useState(false);
  const check = useJob(checkStarted, onChecked);

  const stored = state?.stored === true;
  const page = keyPage(provider.provider_id);
  const name = provider.display_name;

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
      // What an earlier check said was about the key before this one.
      setCheckStarted(null);
      setCheckRefusal(null);
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
      setCheckStarted(null);
      setCheckRefusal(null);
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

  const startCheck = async (): Promise<void> => {
    setStartingCheck(true);
    setCheckRefusal(null);
    try {
      setCheckStarted(
        await callCore('provider.check', { body: { provider_id: provider.provider_id } }),
      );
    } catch (error) {
      setCheckStarted(null);
      setCheckRefusal(describeError(error));
    } finally {
      setStartingCheck(false);
    }
  };

  if (!info.secureStorageAvailable) {
    return (
      <Callout tone="warning" title="Secure storage is unavailable">
        This computer does not offer encrypted credential storage, so Adle will not save a key.
        Everything that does not need AI still works.
      </Callout>
    );
  }

  const checking = startingCheck || isJobActive(check);
  const outcome = readCheck(check);
  const failed = checkRefusal ?? jobFailure(check)?.message ?? null;

  return (
    <>
      <form className={styles.keyForm} onSubmit={(event) => void save(event)} noValidate>
        <TextField
          label={stored ? `Replace the ${name} key` : `${name} API key`}
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
          description={`Stored encrypted by your operating system. It is never shown again, and it is only ever sent to ${name}, at the address above.`}
          trailing={
            <IconButton
              label={revealed ? `Hide the ${name} key` : `Show the ${name} key`}
              icon={revealed ? <EyeOff /> : <Eye />}
              size="small"
              onClick={() => setRevealed((value) => !value)}
            />
          }
        />
        <Stack direction="row" gap={3} wrap>
          <Button type="submit" variant={stored ? 'secondary' : 'primary'} loading={saving}>
            {stored ? 'Replace key' : 'Save key'}
          </Button>
          {stored && known ? (
            <Button
              loading={checking}
              onClick={() => void startCheck()}
              aria-describedby={`${provider.provider_id}-check-note`}
            >
              Check that it works
            </Button>
          ) : null}
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
        {stored && known ? (
          <p id={`${provider.provider_id}-check-note`} className={styles.muted}>
            A check asks {name} for one word. It counts as one of today&apos;s requests, and nothing
            of yours is sent.
          </p>
        ) : null}
      </form>

      {/* Announced when it arrives: the learner pressed a button and is waiting for this. */}
      <div role="status" aria-live="polite">
        {checking ? (
          <p className={styles.muted}>
            {check?.progress_message || 'Asking for one word'}…{' '}
            {check ? (
              <Button
                size="small"
                variant="tertiary"
                onClick={() =>
                  void callCore('jobs.cancel', { path: { job_id: check.id } }).catch(() => {
                    // The check ends by itself in a moment either way.
                  })
                }
              >
                Stop
              </Button>
            ) : null}
          </p>
        ) : outcome ? (
          <p className={styles.checkOk}>
            <CircleCheck aria-hidden="true" />
            <span>
              {outcome.provider} answered {outcome.took}
              {outcome.model ? ` (${outcome.model})` : ''}. The key works.
              {outcome.note ? ` ${outcome.note}` : ''}
            </span>
          </p>
        ) : null}
      </div>
      {!checking && failed ? (
        <Callout tone="danger" title={`${name} did not answer the check`} urgent>
          {failed}
        </Callout>
      ) : null}

      <Dialog
        open={confirmingRemoval}
        onClose={() => setConfirmingRemoval(false)}
        title={`Remove the saved ${name} key?`}
        description={`Adle will stop being able to send anything to ${name} until you add a key again. Your existing courses and progress are not affected.`}
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
