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
    return <LoadingState title="Loading provider settings…" />;
  }
  if (provider.resource.status === 'error') {
    return (
      <ErrorState
        title="Couldn’t load provider settings"
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
          selection === AUTOMATIC ? 'Using Automatic' : `Using ${chosen?.label ?? 'that provider'}`,
        description:
          selection === AUTOMATIC || keys[selection]?.stored
            ? undefined
            : 'Add its key below to start using it.',
      });
    } catch (error) {
      toast.show({
        tone: 'danger',
        title: 'Couldn’t change the provider',
        description: describeError(error),
      });
    } finally {
      setChoosing(null);
    }
  };

  return (
    <Stack gap={6}>
      {providers.length > 1 ? (
        <Section
          title="Provider"
          description="Adle contacts a provider only when you ask it to create something. What is sent is listed under Privacy & data, and beside every button that sends."
        >
          <Stack gap={4}>
            {couldUseBoth(status) ? (
              <Callout
                tone="info"
                title="You have keys for both providers"
                actions={
                  <Button
                    size="small"
                    loading={choosing === AUTOMATIC}
                    disabled={choosing !== null && choosing !== AUTOMATIC}
                    onClick={() => void choose(AUTOMATIC)}
                  >
                    Switch to Automatic
                  </Button>
                }
              >
                Automatic uses the faster one for what you wait on, and the roomier one for long
                work.
              </Callout>
            ) : null}
            <ChoiceButtons
              label="Provider"
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
        title={providers.length > 1 ? 'Keys' : 'Key'}
        description="A key is encrypted on this computer and sent only to its own provider."
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
              Current routing
            </h3>
          </Stack>
          {status.key_configured ? (
            <dl className={styles.routes}>
              {routeLines(status).map((line) => (
                <div key={line.work}>
                  <dt>{line.label}</dt>
                  <dd>
                    {line.destination}
                    {line.model ? <span className={styles.routeModel}>{line.model}</span> : null}
                    {line.reason ? <span className={styles.routeReason}>{line.reason}</span> : null}
                  </dd>
                </div>
              ))}
            </dl>
          ) : (
            <p className={styles.muted}>
              {status.selection === AUTOMATIC
                ? 'No key yet. Add one below.'
                : 'No key for this provider yet. Add one below.'}
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
              <dt>{choice.models.length > 1 ? 'Models' : 'Model'}</dt>
              <dd>
                <ul className={styles.models}>
                  {choice.models.map((model) => (
                    <li key={model.id}>
                      {model.name} <span className={styles.modelId}>{model.id}</span>
                    </li>
                  ))}
                </ul>
              </dd>
            </div>
          </dl>
          {choice.models.length > 1 ? (
            <p className={styles.muted}>{modelOrder(choice.models)}</p>
          ) : null}

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
            <h4 className={styles.usageTitle}>Usage today</h4>
            {/* A day with no limit is counted, not measured against one (ADR-068). */}
            {usage.requests_per_day ? (
              <ProgressBar
                label="Requests"
                showLabel
                value={usage.requests_today / usage.requests_per_day}
                valueText={`${usage.requests_today.toLocaleString()} of ${usage.requests_per_day.toLocaleString()}`}
              />
            ) : (
              <p className={styles.usageCount}>
                <span className={styles.usageCountLabel}>Requests</span>
                <span className={styles.usageCountValue}>
                  {usage.requests_today.toLocaleString()} sent
                </span>
              </p>
            )}
            {usage.tokens_per_day ? (
              <ProgressBar
                label="Tokens"
                showLabel
                value={usage.tokens_today / usage.tokens_per_day}
                valueText={`about ${usage.tokens_today.toLocaleString()} of ${usage.tokens_per_day.toLocaleString()}`}
              />
            ) : (
              <p className={styles.usageCount}>
                <span className={styles.usageCountLabel}>Tokens</span>
                <span className={styles.usageCountValue}>
                  about {usage.tokens_today.toLocaleString()} used
                </span>
              </p>
            )}
            <p className={styles.usageNote}>
              {limitsNote(choice, usage, formatClockTime(usage.resets_at))}
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
      setFormError('Enter a key first.');
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
        description: 'Encrypted on this computer.',
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
      // The dialog goes first: what is said next would otherwise lie underneath it, where
      // it can neither be read nor dismissed.
      setConfirmingRemoval(false);
      toast.show({
        tone: 'danger',
        title: 'Couldn’t remove the key',
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
        This computer has no encrypted storage, so Adle can’t save a key. Everything except AI
        generation still works.
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
          description={`Encrypted by your operating system, never shown again, and sent only to ${name} at the address above.`}
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
              Test key
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
            Sends a one-word test request to {name}. Nothing of yours is sent.
          </p>
        ) : null}
      </form>

      {/* Announced when it arrives: the learner pressed a button and is waiting for this. */}
      <div role="status" aria-live="polite">
        {checking ? (
          <p className={styles.muted}>
            {check?.progress_message || 'Testing the key'}…{' '}
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
              The key works. {outcome.model || outcome.provider} answered {outcome.took}.
              {outcome.note ? ` ${outcome.note}` : ''}
            </span>
          </p>
        ) : null}
      </div>
      {!checking && failed ? (
        <Callout tone="danger" title={`The ${name} key test failed`} urgent>
          {failed}
        </Callout>
      ) : null}

      <Dialog
        open={confirmingRemoval}
        onClose={() => setConfirmingRemoval(false)}
        title={`Remove the ${name} key?`}
        description={`Adle won’t be able to use ${name} until you add a key again. Your courses and progress stay.`}
        dismissible={!removing}
        actions={
          <>
            <Button onClick={() => setConfirmingRemoval(false)} disabled={removing}>
              Cancel
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
