import { ArrowRight, Settings, Sparkles } from 'lucide-react';
import { type ReactNode, useState } from 'react';

import type { PlayerLesson } from '@adle/contracts';
import { Button, Callout, Dialog, Select, useToast } from '@adle/design-system';

import { useRouter } from '../../app/router';
import { callCore } from '../../lib/core-client';
import { WhatIsSent } from '../../components/WhatIsSent';
import { type JobFailure, lessonDisclosure, refusalOf } from '../../lib/generation';
import { destination, usualWait } from '../../lib/provider';
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
        title: 'Writing another lesson',
        description: 'It’ll be suggested as your next step when it’s ready.',
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
      title="Thanks for the feedback"
      description={
        report === 'failed'
          ? 'That’s about the explanation, not you. It couldn’t be saved just now, but the options below still work.'
          : 'That’s about the explanation, not you. Adle will take it into account.'
      }
      actions={
        <Button onClick={onClose} disabled={creating}>
          Continue this lesson
        </Button>
      }
    >
      <ul className={styles.ways}>
        {canSkipToQuestion ? (
          <Way
            title="Go straight to the next question"
            text="Skip the rest of this part and check what you already know."
          >
            <Button icon={<ArrowRight />} disabled={creating} onClick={onSkipToQuestion}>
              Skip to the question
            </Button>
          </Way>
        ) : null}

        <Way
          title="Try a different explanation"
          text={
            status?.key_configured
              ? 'A new lesson on the same concept, taught differently.'
              : 'A new lesson on the same concept, taught differently. Needs an AI provider key.'
          }
        >
          {status?.key_configured ? (
            <>
              <div className={styles.wayField}>
                <Select
                  label="Teaching style"
                  value={strategy}
                  options={choices}
                  disabled={creating}
                  onValueChange={setStrategy}
                />
              </div>
              <div className={styles.sending}>
                <Button
                  variant="primary"
                  icon={<Sparkles />}
                  loading={creating}
                  onClick={() => void create()}
                >
                  Create lesson
                </Button>
                <WhatIsSent
                  what={lessonDisclosure('unknown')}
                  to={destination(status, 'lesson')}
                  wait={usualWait(status, 'lesson')}
                  after="Its pictures follow while you start."
                />
              </div>
            </>
          ) : provider.resource.status === 'loading' ? (
            <p className={styles.note} role="status">
              Checking AI provider…
            </p>
          ) : (
            <div>
              <Button icon={<Settings />} onClick={() => navigate({ name: 'settings', tab: 'ai' })}>
                Set up AI provider
              </Button>
            </div>
          )}
          {refusal ? (
            <Callout
              tone={refusal.remedy === 'wait' ? 'warning' : 'danger'}
              title="Couldn’t start the lesson"
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
          text="See what else there is in this course. Your place here is saved."
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
