import { useEffect, useRef, useState } from 'react';

import type { LearnerPreferences, TeacherCharacter } from '@adle/contracts';
import {
  Button,
  Card,
  ErrorState,
  LoadingState,
  Select,
  Stack,
  Switch,
  TextArea,
  useToast,
} from '@adle/design-system';

import { callCore, describeError } from '../../lib/core-client';
import { useResource } from '../../lib/use-resource';
import styles from './Settings.module.css';
import {
  chosenParts,
  presetOf,
  sameParts,
  type TeacherParts,
  teacherRequest,
  withPart,
} from './teacher-model';

/** As long as the core keeps a teacher in the learner's own words. */
const MAX_CHARACTER_LENGTH = 300;

/**
 * Who writes the lessons (ADR-071): the person the Expressive voice was made as, while that
 * voice reads them and the learner lets the teacher follow it; else a teacher the learner
 * puts together, a part at a time like that voice, or describes in their own words.
 */
export function TeacherSettings({
  preferences,
  onSaved,
}: {
  preferences: LearnerPreferences;
  onSaved: (next: LearnerPreferences) => void;
}) {
  const toast = useToast();
  const teacher = useResource('teacher-character', () => callCore('learner.character'));
  const { reload } = teacher;
  // Whether the voice reads the lessons changes who the teacher can be.
  useEffect(() => {
    reload();
  }, [reload, preferences.narration]);

  if (teacher.resource.status === 'loading') return <LoadingState title="Loading the teacher…" />;
  if (teacher.resource.status === 'error') {
    return (
      <ErrorState
        title="Couldn’t load the teacher"
        description={describeError(teacher.resource.error)}
        actions={<Button onClick={reload}>Try again</Button>}
      />
    );
  }
  const now = teacher.resource.data;

  const follow = async (follows: boolean): Promise<void> => {
    try {
      onSaved(
        await callCore('learner.update_preferences', {
          body: { character_follows_voice: follows },
        }),
      );
      reload();
    } catch (error) {
      toast.show({
        tone: 'danger',
        title: 'Couldn’t change the teacher',
        description: describeError(error),
      });
    }
  };

  return (
    <Card>
      <Stack gap={4}>
        {now.voice_in_use ? (
          <Switch
            label="Teach as the Expressive voice’s person"
            description="The person your voice was made as writes your lessons, too."
            checked={preferences.character_follows_voice}
            onCheckedChange={(follows) => void follow(follows)}
          />
        ) : null}
        {now.follows_voice ? (
          <p className={styles.teacherSaid}>{now.described}</p>
        ) : (
          <TeacherEditor
            // Begun again when the teacher saved, or the sentence the core has for it, changes.
            key={`${now.described}|${preferences.character}|${JSON.stringify(preferences.character_parts)}`}
            now={now}
            preferences={preferences}
            onSaved={(next) => {
              onSaved(next);
              reload();
            }}
          />
        )}
      </Stack>
    </Card>
  );
}

function TeacherEditor({
  now,
  preferences,
  onSaved,
}: {
  now: TeacherCharacter;
  preferences: LearnerPreferences;
  onSaved: (next: LearnerPreferences) => void;
}) {
  const toast = useToast();
  const [parts, setParts] = useState<TeacherParts>(preferences.character_parts);
  const [words, setWords] = useState(now.described);
  // The sentence the core made of the parts, and whether the words are the learner's own.
  const [composed, setComposed] = useState(preferences.character ? '' : now.described);
  const [own, setOwn] = useState(preferences.character !== '');
  const [saving, setSaving] = useState(false);
  // The latest thing asked of the core: an answer to an earlier one is not shown.
  const asked = useRef(0);
  const preset = presetOf(now.presets, parts, own);
  const changed = own
    ? words.trim() !== preferences.character
    : !sameParts(parts, preferences.character_parts) || preferences.character !== '';

  /** These parts, and the sentence the core writes from them. */
  const choose = async (next: TeacherParts): Promise<void> => {
    const turn = ++asked.current;
    setParts(next);
    setOwn(false);
    try {
      const described = await callCore('learner.describe_character', {
        body: { parts: chosenParts(next) },
      });
      if (asked.current !== turn) return;
      setComposed(described.text);
      setWords(described.text);
    } catch (error) {
      if (asked.current !== turn) return;
      toast.show({
        tone: 'danger',
        title: 'Couldn’t change the teacher',
        description: describeError(error),
      });
    }
  };

  const save = async (): Promise<void> => {
    setSaving(true);
    try {
      onSaved(
        await callCore('learner.update_preferences', {
          body: own ? { character: words.trim() } : teacherRequest(parts, words, composed),
        }),
      );
      toast.show({ tone: 'success', title: 'Teacher saved' });
    } catch (error) {
      toast.show({
        tone: 'danger',
        title: 'Couldn’t save the teacher',
        description: describeError(error),
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <Stack gap={4}>
      <Select
        className={styles.voiceField}
        label="Start from"
        value={preset}
        options={[
          ...(preset === ''
            ? [{ value: '', label: own ? 'Your own words' : 'Your own choice' }]
            : []),
          ...now.presets.map((item) => ({ value: item.name, label: item.name })),
        ]}
        onValueChange={(name) => {
          const chosen = now.presets.find((item) => item.name === name);
          if (chosen) void choose(chosen.parts);
        }}
      />
      <div className={styles.voiceParts} role="group" aria-label="What the teacher is like">
        {now.parts.map((part) => (
          <Select
            key={part.key}
            label={part.name}
            value={parts[part.key] ?? ''}
            options={[
              { value: '', label: 'Adle’s choice' },
              ...part.options.map((option) => ({ value: option.key, label: option.name })),
            ]}
            onValueChange={(choice) => void choose(withPart(parts, part.key, choice))}
          />
        ))}
      </div>
      <TextArea
        label="In your own words"
        description="How they speak, never what they teach."
        rows={3}
        maxLength={MAX_CHARACTER_LENGTH}
        value={words}
        onChange={(event) => {
          // Words of the learner's own: the parts are let go, and nothing overwrites them.
          asked.current += 1;
          setOwn(true);
          setParts({});
          setWords(event.target.value);
        }}
      />
      <div>
        <Button
          variant="primary"
          loading={saving}
          disabled={!changed || (own && words.trim() === '')}
          onClick={() => void save()}
        >
          Save teacher
        </Button>
      </div>
    </Stack>
  );
}
