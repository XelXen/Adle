import { ArrowRight, Settings, Sparkles } from 'lucide-react';
import { type ReactNode, useState } from 'react';

import type { PlayerLesson } from '@adle/contracts';
import { Button, Callout, Dialog, Select, useToast } from '@adle/design-system';

import { useRouter } from '../../app/router';
import { callCore } from '../../lib/core-client';
import { type JobFailure, refusalOf } from '../../lib/generation';
import { useResource } from '../../lib/use-resource';
import { STRATEGY_CHOICES, type TeachingStrategy } from '../course/ConceptDetail';
import styles from './Lesson.module.css';

/** Whether the learner's "this did not help" has reached the core. */
export type ReportState = 'saving' | 'saved' | 'failed';

/**
 * What a learner can do after saying an explanation did not help. Nothing here
 * sends them back through the same content, and nothing treats it as their fault.
 * Mounted only while open.
 */
export function UnhelpfulDialog({
  lesson,
  report,
  canSkipToQuestion,
  onSkipToQuestion,
  onClose,
}: {
  lesson: PlayerLesson;
  report: ReportState;
  canSkipToQuestion: boolean;
  onSkipToQuestion: () => void;
  onClose: () => void;
}) {
  const { navigate } = useRouter();
  const toast = useToast();
  const provider = useResource('provider-status', () => callCore('provider.status'));
  // Another explanation should be another kind of explanation.
  const choices = STRATEGY_CHOICES.filter(
    (choice): choice is { value: TeachingStrategy; label: string } =>
      choice.value !== '' && choice.value !== lesson.strategy,
  );
  const [strategy, setStrategy] = useState<TeachingStrategy>(choices[0]?.value ?? 'worked_example');
  const [creating, setCreating] = useState(false);
  const [refusal, setRefusal] = useState<JobFailure | null>(null);
  const conceptId = lesson.concept_ids[0] ?? '';
  const courseId = lesson.course_id;
  const status = provider.resource.status === 'ready' ? provider.resource.data : null;

  const create = async (): Promise<void> => {
    setCreating(true);
    setRefusal(null);
    try {
      await callCore('generation.generate_lesson', {
        path: { concept_id: conceptId },
        body: { strategy },
      });
      toast.show({
        tone: 'info',
        title: 'Another lesson is being written',
        description: 'You can follow it here, and it will be suggested when it is ready.',
      });
      navigate({ name: 'course', courseId, tab: 'learn' });
    } catch (error) {
      setRefusal(refusalOf(error));
      setCreating(false);
    }
  };

  return (
    <Dialog
      open
      onClose={onClose}
      dismissible={!creating}
      title="Thanks for saying so"
      description={
        report === 'failed'
          ? 'That says something about the explanation, not about you. It could not be noted just now, but everything below still works.'
          : 'That says something about the explanation, not about you. It has been noted, and what Adle suggests next takes it into account.'
      }
      actions={
        <Button onClick={onClose} disabled={creating}>
          Keep going with this lesson
        </Button>
      }
    >
      <ul className={styles.ways}>
        {canSkipToQuestion ? (
          <Way
            title="Go straight to the next question"
            text="Leave the rest of this part and see whether the idea is there already. What you skip stays open."
          >
            <Button icon={<ArrowRight />} disabled={creating} onClick={onSkipToQuestion}>
              Skip to the question
            </Button>
          </Way>
        ) : null}

        <Way
          title="Have it explained another way"
          text={
            status?.key_configured
              ? 'A new lesson on the same concept, taught differently.'
              : 'A new lesson on the same concept, taught differently. That needs the AI provider, and no key is set up yet.'
          }
        >
          {status?.key_configured ? (
            <>
              <div className={styles.wayField}>
                <Select
                  label="How should it explain?"
                  value={strategy}
                  options={choices}
                  disabled={creating}
                  onValueChange={setStrategy}
                />
              </div>
              <div>
                <Button
                  variant="primary"
                  icon={<Sparkles />}
                  loading={creating}
                  onClick={() => void create()}
                >
                  Create that lesson
                </Button>
              </div>
              <p className={styles.note}>
                Sends this concept and its objectives to {status.display_name}. It usually takes
                three of today&rsquo;s requests.
              </p>
            </>
          ) : provider.resource.status === 'loading' ? (
            <p className={styles.note} role="status">
              Checking whether the AI provider is set up…
            </p>
          ) : (
            <div>
              <Button icon={<Settings />} onClick={() => navigate({ name: 'settings', tab: 'ai' })}>
                Set up the AI provider
              </Button>
            </div>
          )}
          {refusal ? (
            <Callout
              tone={refusal.remedy === 'wait' ? 'warning' : 'danger'}
              title="The lesson could not be started"
              urgent
              actions={
                refusal.remedy === 'settings' ? (
                  <Button size="small" onClick={() => navigate({ name: 'settings', tab: 'ai' })}>
                    Open AI settings
                  </Button>
                ) : undefined
              }
            >
              {refusal.message}
            </Callout>
          ) : null}
        </Way>

        <Way
          title="Do something else for now"
          text="See what else is worth doing in this course. Stopping for today is fine too: your place here is saved."
        >
          <Button
            disabled={creating}
            onClick={() => navigate({ name: 'course', courseId, tab: 'learn' })}
          >
            Go to the course
          </Button>
        </Way>
      </ul>
    </Dialog>
  );
}

function Way({ title, text, children }: { title: string; text: string; children: ReactNode }) {
  return (
    <li className={styles.way}>
      <p className={styles.wayTitle}>{title}</p>
      <p className={styles.note}>{text}</p>
      {children}
    </li>
  );
}
