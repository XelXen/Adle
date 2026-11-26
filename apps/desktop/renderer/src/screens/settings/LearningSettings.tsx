import { useState } from 'react';

import type { LearnerPreferences } from '@adle/contracts';
import {
  Button,
  Card,
  ErrorState,
  LoadingState,
  Section,
  SegmentedControl,
  Stack,
  Switch,
  TextArea,
  useToast,
} from '@adle/design-system';

import { callCore, describeError } from '../../lib/core-client';
import { useResource } from '../../lib/use-resource';
import styles from './Settings.module.css';
import { TeacherSettings } from './TeacherSettings';
import { VoiceChoices } from './VoiceChoices';
import { VolumeSetting } from './VoiceSettings';

type Pace = LearnerPreferences['pace'];
type Density = LearnerPreferences['explanation_density'];

const PACES = [
  { value: 'relaxed', label: 'Relaxed' },
  { value: 'standard', label: 'Standard' },
  { value: 'brisk', label: 'Brisk' },
] as const;

const PACE_NOTE: Record<Pace, string> = {
  relaxed: 'Smaller steps, more pauses, and more practice before moving on.',
  standard: 'A steady pace with a check after each idea.',
  brisk: 'Larger steps and fewer pauses. Adle still slows down when an answer shows a gap.',
};

const DENSITIES = [
  { value: 'concise', label: 'Concise' },
  { value: 'balanced', label: 'Balanced' },
  { value: 'detailed', label: 'Detailed' },
] as const;

const DENSITY_NOTE: Record<Density, string> = {
  concise: 'The essential idea and one example.',
  balanced: 'The idea, why it works, and an example.',
  detailed: 'Fuller explanations with intermediate steps and more than one example.',
};

const MAX_GOAL_LENGTH = 300;

/** How the learner likes to be taught. Explicit choices only; nothing here is inferred. */
export function LearningSettings() {
  const toast = useToast();
  const preferences = useResource('learner-preferences', () => callCore('learner.get_preferences'));
  const [goalDraft, setGoalDraft] = useState<string | null>(null);
  const [savingGoal, setSavingGoal] = useState(false);

  if (preferences.resource.status === 'loading') {
    return <LoadingState title="Loading preferences…" />;
  }
  if (preferences.resource.status === 'error') {
    return (
      <ErrorState
        title="Couldn’t load your preferences"
        description={describeError(preferences.resource.error)}
        actions={<Button onClick={preferences.reload}>Try again</Button>}
      />
    );
  }

  const current = preferences.resource.data;
  const goal = goalDraft ?? current.goal;
  const goalChanged = goal.trim() !== current.goal;

  /** Show the change at once; put it back and say so if it could not be saved. */
  const change = async (patch: Partial<LearnerPreferences>): Promise<void> => {
    preferences.setData({ ...current, ...patch });
    try {
      preferences.setData(await callCore('learner.update_preferences', { body: patch }));
    } catch (error) {
      preferences.setData(current);
      toast.show({
        tone: 'danger',
        title: 'Couldn’t save that preference',
        description: describeError(error),
      });
    }
  };

  const saveGoal = async (): Promise<void> => {
    setSavingGoal(true);
    try {
      preferences.setData(
        await callCore('learner.update_preferences', { body: { goal: goal.trim() } }),
      );
      setGoalDraft(null);
      toast.show({ tone: 'success', title: 'Goal saved' });
    } catch (error) {
      toast.show({
        tone: 'danger',
        title: 'Couldn’t save your goal',
        description: describeError(error),
      });
    } finally {
      setSavingGoal(false);
    }
  };

  return (
    <Stack gap={6}>
      <Section title="Pace and depth" description="Used when preparing lessons.">
        <Card>
          <Stack gap={5}>
            <Stack gap={2}>
              <span className={styles.rowTitle} id="learning-pace">
                Pace
              </span>
              <div>
                <SegmentedControl<Pace>
                  label="Pace"
                  value={current.pace}
                  options={PACES}
                  onValueChange={(pace) => void change({ pace })}
                />
              </div>
              <p className={styles.muted}>{PACE_NOTE[current.pace]}</p>
            </Stack>
            <Stack gap={2}>
              <span className={styles.rowTitle} id="learning-density">
                Explanations
              </span>
              <div>
                <SegmentedControl<Density>
                  label="Explanations"
                  value={current.explanation_density}
                  options={DENSITIES}
                  onValueChange={(explanation_density) => void change({ explanation_density })}
                />
              </div>
              <p className={styles.muted}>{DENSITY_NOTE[current.explanation_density]}</p>
            </Stack>
          </Stack>
        </Card>
      </Section>

      <Section title="Listening and reading">
        <Card>
          <Stack gap={4}>
            <Switch
              label="Narration"
              description="Read lessons aloud, in a voice on this computer."
              checked={current.narration}
              onCheckedChange={(narration) => void change({ narration })}
            />
            <Switch
              label="Captions"
              description="Show the words as they’re spoken."
              checked={current.captions}
              onCheckedChange={(captions) => void change({ captions })}
            />
            {current.narration ? (
              <VolumeSetting preferences={current} onChange={(patch) => void change(patch)} />
            ) : null}
          </Stack>
        </Card>
      </Section>

      {current.narration ? (
        <Section title="Voice" description="From the lightest to the richest.">
          <VoiceChoices preferences={current} onChange={(patch) => void change(patch)} />
        </Section>
      ) : null}

      <Section title="Teacher" description="Who writes your lessons and answers your questions.">
        <TeacherSettings preferences={current} onSaved={preferences.setData} />
      </Section>

      <Section title="Your goal" description="Optional. What do you want to be able to do?">
        <Card>
          <Stack gap={3}>
            <TextArea
              label="What are you working toward?"
              value={goal}
              rows={3}
              maxLength={MAX_GOAL_LENGTH}
              placeholder="For example: understand backpropagation well enough to implement it myself."
              onChange={(event) => setGoalDraft(event.target.value)}
            />
            <div>
              <Button
                variant="primary"
                loading={savingGoal}
                disabled={!goalChanged}
                onClick={() => void saveGoal()}
              >
                Save goal
              </Button>
            </div>
          </Stack>
        </Card>
      </Section>
    </Stack>
  );
}
