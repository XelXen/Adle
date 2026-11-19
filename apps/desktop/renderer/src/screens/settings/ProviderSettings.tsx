import { ExternalLink, Eye, EyeOff, KeyRound } from 'lucide-react';
import { type FormEvent, useState } from 'react';

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
import { getBridge } from '../../lib/bridge';
import { callCore, describeError, unwrap } from '../../lib/core-client';
import { formatClockTime } from '../../lib/format';
import { useResource } from '../../lib/use-resource';
import styles from './Settings.module.css';

/** Add, replace, or remove the model provider key, and see what the provider is. */
export function ProviderSettings() {
  const { info, coreStatus } = useApp();
  const toast = useToast();
  const keyState = useResource('provider-key', () => getBridge().provider.keyState());
  const provider = useResource(`provider-status:${coreStatus.state}`, () =>
    callCore('provider.status'),
  );
  const usage = useResource(`provider-usage:${coreStatus.state}`, () => callCore('provider.usage'));

  const [draft, setDraft] = useState('');
  const [revealed, setRevealed] = useState(false);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [confirmingRemoval, setConfirmingRemoval] = useState(false);
  const [removing, setRemoving] = useState(false);

  const stored = keyState.resource.status === 'ready' && keyState.resource.data.stored;
  const hint = keyState.resource.status === 'ready' ? keyState.resource.data.hint : null;

  const save = async (event: FormEvent): Promise<void> => {
    event.preventDefault();
    if (!draft.trim()) {
      setFormError('Enter your API key first.');
      return;
    }
    setSaving(true);
    setFormError(null);
    try {
      keyState.setData(unwrap(await getBridge().provider.setApiKey(draft)));
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
      keyState.setData(unwrap(await getBridge().provider.clearApiKey()));
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
    <Stack gap={6}>
      <Callout tone="info" title="What is sent, and when">
        <p>
          When you ask Adle to build a course or a lesson, it sends the text needed for that request
          (for example a few passages from your notes and the concept being taught) to the provider
          below. Your files, answers, and progress are never uploaded in bulk, and nothing is sent
          until you start a generation.
        </p>
      </Callout>

      <Section
        title="API key"
        description="Adle works without a key: you can explore sample content and your saved courses."
      >
        <Card>
          <Stack gap={4}>
            <Stack direction="row" gap={3} align="center" wrap>
              <KeyRound className={styles.leadIcon} aria-hidden="true" />
              <span className={styles.rowTitle}>AIHubMix key</span>
              {keyState.resource.status === 'loading' ? (
                <Badge>Checking…</Badge>
              ) : stored ? (
                <Badge tone="success">Saved · ends in {hint}</Badge>
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
                  description="Stored encrypted by your operating system. It is never shown again and never leaves this computer except to call the provider."
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
                  <Button
                    variant="tertiary"
                    icon={<ExternalLink />}
                    onClick={() => void getBridge().app.openExternal('aihubmixKeys')}
                  >
                    Get a key from AIHubMix
                  </Button>
                </Stack>
              </form>
            )}
          </Stack>
        </Card>
      </Section>

      <Section title="Provider">
        {provider.resource.status === 'loading' ? (
          <LoadingState title="Reading provider settings…" />
        ) : provider.resource.status === 'error' ? (
          <ErrorState
            title="Provider settings are unavailable"
            description={describeError(provider.resource.error)}
            actions={<Button onClick={provider.reload}>Try again</Button>}
          />
        ) : (
          <Card>
            <dl className={styles.facts}>
              <div>
                <dt>Service</dt>
                <dd>{provider.resource.data.display_name}</dd>
              </div>
              <div>
                <dt>Address</dt>
                <dd className={styles.mono}>{provider.resource.data.base_url}</dd>
              </div>
              <div>
                <dt>Model</dt>
                <dd className={styles.mono}>{provider.resource.data.model}</dd>
              </div>
            </dl>
          </Card>
        )}
      </Section>

      <Section
        title="Use today"
        description="Adle's own count of what it has sent today. Your provider keeps the real total, and anything else that uses the same key counts against it too."
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
          <Card>
            <Stack gap={4}>
              <ProgressBar
                label="Requests"
                showLabel
                value={usage.resource.data.requests_today / usage.resource.data.requests_per_day}
                valueText={`${usage.resource.data.requests_today.toLocaleString()} of ${usage.resource.data.requests_per_day.toLocaleString()}`}
              />
              <ProgressBar
                label="Tokens (words and parts of words)"
                showLabel
                value={usage.resource.data.tokens_today / usage.resource.data.tokens_per_day}
                valueText={`about ${usage.resource.data.tokens_today.toLocaleString()} of ${usage.resource.data.tokens_per_day.toLocaleString()}`}
              />
              <p className={styles.usageNote}>
                Adle stops a little short of the provider's daily limit, sends one request at a
                time, and never more than {usage.resource.data.requests_per_minute} a minute: it
                waits instead. The count starts again at{' '}
                {formatClockTime(usage.resource.data.resets_at)}.
              </p>
            </Stack>
          </Card>
        )}
      </Section>

      <Dialog
        open={confirmingRemoval}
        onClose={() => setConfirmingRemoval(false)}
        title="Remove the saved key?"
        description="Adle will stop being able to generate new courses and lessons until you add a key again. Your existing courses and progress are not affected."
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
    </Stack>
  );
}
