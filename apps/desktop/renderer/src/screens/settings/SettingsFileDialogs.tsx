import { Download } from 'lucide-react';
import { useState } from 'react';

import {
  Button,
  Callout,
  Checkbox,
  Dialog,
  Disclosure,
  Stack,
  TextField,
  useToast,
} from '@adle/design-system';

import {
  getBridge,
  type SettingsBroughtIn,
  type SettingsFileFound,
  type SettingsFileParts,
} from '../../lib/bridge';
import { describeError } from '../../lib/core-client';
import {
  chosenOf,
  EVERY_PART,
  MIN_PASSWORD_LENGTH,
  nothingChosen,
  PARTS,
  partsListed,
  passwordProblem,
  setUpNote,
  type SettingsPart,
} from '../../lib/settings-file';
import styles from './Settings.module.css';

/** The parts other than the keys: rarely left out, so they sit under "Advanced". */
const OTHER_PARTS = PARTS.filter((part) => part.key !== 'keys');

/**
 * Save settings to a file (ADR-064): the look of the app, how the learner likes to learn,
 * the voice, the choice of AI provider, and the providers' keys, locked with a password
 * typed here. The keys themselves never come to the page: it only says whether to put them
 * in. Where the file goes is asked by the system's own window.
 *
 * Mounted only while it is open, so that it begins with everything chosen every time.
 */
export function SaveSettingsDialog({ onClose }: { onClose: () => void }) {
  const toast = useToast();
  const [parts, setParts] = useState<SettingsFileParts>(EVERY_PART);
  const [password, setPassword] = useState('');
  const [again, setAgain] = useState('');
  const [tried, setTried] = useState(false);
  const [saving, setSaving] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const wrong = parts.keys ? (passwordProblem(password, again) ?? undefined) : undefined;
  // Said under the field it is about, once the learner has tried to save.
  const tooShort = tried && wrong !== undefined && password.length < MIN_PASSWORD_LENGTH;

  const save = async (): Promise<void> => {
    setTried(true);
    if (wrong || nothingChosen(parts)) return;
    setSaving(true);
    setProblem(null);
    try {
      const result = await getBridge().settings.saveFile(parts, parts.keys ? password : null);
      if (!result.ok) {
        setProblem(result.error.message);
        return;
      }
      // Backed out of the window that asks where: the choices here are still theirs.
      if (result.data === null) return;
      const noKeys = parts.keys && result.data.keys === 0;
      toast.show({
        tone: 'success',
        title: 'Settings saved',
        description: noKeys
          ? `${result.data.fileName}. There are no keys on this computer, so it has none.`
          : result.data.fileName,
      });
      onClose();
    } catch (error) {
      setProblem(describeError(error));
    } finally {
      setSaving(false);
    }
  };

  const hold = (part: SettingsPart) => (checked: boolean) =>
    setParts((current) => ({ ...current, [part]: checked }));

  return (
    <Dialog
      open
      onClose={onClose}
      title="Save your settings to a file"
      description="To use them on another computer, or to keep them."
      dismissible={!saving}
      actions={
        <>
          <Button onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button
            variant="primary"
            icon={<Download />}
            loading={saving}
            disabled={nothingChosen(parts)}
            onClick={() => void save()}
          >
            Save…
          </Button>
        </>
      }
    >
      <Stack gap={4}>
        <Checkbox
          label="Include my API keys"
          description="Locked with a password. Without it, nobody can read them from the file."
          checked={parts.keys}
          disabled={saving}
          onCheckedChange={hold('keys')}
        />
        {parts.keys ? (
          <Stack gap={3} className={styles.voiceField}>
            <TextField
              label="Password for the keys"
              description={`${MIN_PASSWORD_LENGTH} characters or more. You type it again when you import the file.`}
              type="password"
              autoComplete="new-password"
              data-autofocus
              value={password}
              disabled={saving}
              error={tooShort ? wrong : undefined}
              onChange={(event) => setPassword(event.target.value)}
            />
            <TextField
              label="The password again"
              type="password"
              autoComplete="new-password"
              value={again}
              disabled={saving}
              error={tried && wrong && !tooShort ? wrong : undefined}
              onChange={(event) => setAgain(event.target.value)}
            />
          </Stack>
        ) : null}
        <Disclosure label="Advanced">
          {OTHER_PARTS.map((part) => (
            <Checkbox
              key={part.key}
              label={part.label}
              description={part.description}
              checked={parts[part.key]}
              disabled={saving}
              onCheckedChange={hold(part.key)}
            />
          ))}
        </Disclosure>
        {problem ? (
          <Callout tone="danger" title="Couldn’t save your settings">
            {problem}
          </Callout>
        ) : null}
      </Stack>
    </Dialog>
  );
}

/**
 * Bring settings in from a file the learner chose (ADR-064). It says what the file holds,
 * asks for the password if the file has keys, and says before anything is changed what a
 * voice that is not on this computer would be here, and what setting it up downloads.
 * Afterwards it says what could not be had as the file has it.
 *
 * Mounted only while there is a file to ask about.
 */
export function ImportSettingsDialog({
  found,
  nameOf,
  onClose,
  onDone,
}: {
  found: SettingsFileFound;
  /** A provider's name as the core gives it, from its identifier. */
  nameOf: (providerId: string) => string;
  onClose: () => void;
  /** The settings were brought in and the learner has read what happened. */
  onDone: () => void;
}) {
  const hasKeys = found.parts.keys && found.keysFor.length > 0;
  const has: SettingsFileParts = { ...found.parts, keys: hasKeys };
  const [parts, setParts] = useState<SettingsFileParts>(has);
  const [password, setPassword] = useState('');
  const [setUpVoice, setSetUpVoice] = useState(true);
  const [importing, setImporting] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [wrongPassword, setWrongPassword] = useState<string | null>(null);
  const [brought, setBrought] = useState<SettingsBroughtIn | null>(null);
  const chosen = chosenOf(parts, has);
  const voice = chosen.voice ? found.voice : null;

  const bringIn = async (): Promise<void> => {
    if (chosen.keys && password.length < MIN_PASSWORD_LENGTH) {
      setWrongPassword('Type the password the keys were locked with.');
      return;
    }
    setImporting(true);
    setProblem(null);
    setWrongPassword(null);
    try {
      const result = await getBridge().settings.bringIn(found.token, chosen, {
        password: chosen.keys ? password : null,
        setUpVoice: Boolean(voice?.setUp) && setUpVoice,
      });
      if (result.ok) {
        setBrought(result.data);
      } else if (result.error.code === 'wrong_password') {
        setWrongPassword(result.error.message);
      } else {
        setProblem(result.error.message);
      }
    } catch (error) {
      setProblem(describeError(error));
    } finally {
      setImporting(false);
    }
  };

  const hold = (part: SettingsPart) => (checked: boolean) =>
    setParts((current) => ({ ...current, [part]: checked }));

  if (brought) {
    const said = partsListed(brought.parts);
    return (
      <Dialog
        open
        onClose={onDone}
        title="Settings imported"
        description={said ? `Brought in: ${said}.` : 'Nothing in the file could be used here.'}
        actions={
          <Button variant="primary" onClick={onDone}>
            Done
          </Button>
        }
      >
        {brought.notes.length > 0 ? (
          <ul className={styles.list} aria-label="What is different here">
            {brought.notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        ) : null}
      </Dialog>
    );
  }

  const keysNote = hasKeys ? ` Keys for ${found.keysFor.map(nameOf).join(' and ')}.` : '';
  return (
    <Dialog
      open
      onClose={onClose}
      title="Import these settings?"
      description={
        nothingChosen(found.parts)
          ? `${found.fileName} has no settings in it.`
          : `${found.fileName} holds ${partsListed(found.parts)}.${keysNote} They replace yours.`
      }
      dismissible={!importing}
      actions={
        <>
          <Button onClick={onClose} disabled={importing}>
            Cancel
          </Button>
          <Button
            variant="primary"
            loading={importing}
            disabled={nothingChosen(chosen)}
            onClick={() => void bringIn()}
          >
            Import
          </Button>
        </>
      }
    >
      <Stack gap={4}>
        {chosen.keys ? (
          <TextField
            className={styles.voiceField}
            label="Password for the keys"
            type="password"
            autoComplete="off"
            data-autofocus
            value={password}
            disabled={importing}
            error={wrongPassword ?? undefined}
            onChange={(event) => setPassword(event.target.value)}
          />
        ) : null}
        {voice?.note ? <p className={styles.muted}>{voice.note}</p> : null}
        {voice?.setUp && voice.name ? (
          <Checkbox
            label={`Set up the ${voice.name} voice`}
            description={setUpNote(voice)}
            checked={setUpVoice}
            disabled={importing}
            onCheckedChange={setSetUpVoice}
          />
        ) : null}
        {nothingChosen(has) ? null : (
          <Disclosure label="Advanced">
            {PARTS.filter((part) => has[part.key]).map((part) => (
              <Checkbox
                key={part.key}
                label={part.label}
                description={part.key === 'keys' ? undefined : part.description}
                checked={parts[part.key]}
                disabled={importing}
                onCheckedChange={hold(part.key)}
              />
            ))}
          </Disclosure>
        )}
        {problem ? (
          <Callout tone="danger" title="Couldn’t import the settings">
            {problem}
          </Callout>
        ) : null}
      </Stack>
    </Dialog>
  );
}
