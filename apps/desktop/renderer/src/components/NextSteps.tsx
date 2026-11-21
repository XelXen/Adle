import {
  ArrowRight,
  CalendarClock,
  CircleHelp,
  ListTree,
  PencilLine,
  Play,
  RotateCcw,
  Settings,
  Sparkles,
  Undo2,
} from 'lucide-react';
import { type ReactNode, useId } from 'react';

import type { LearningPlan, NextStep } from '@adle/contracts';
import { Button } from '@adle/design-system';

import { useRouter } from '../app/router';
import { type StepAction, stepAction } from '../lib/learning';
import styles from './NextSteps.module.css';

const ICONS: Record<NextStep['kind'], ReactNode> = {
  add_concepts: <ListTree />,
  resume_lesson: <Play />,
  start_lesson: <Play />,
  repeat_lesson: <RotateCcw />,
  revisit_prerequisite: <Undo2 />,
  check: <CircleHelp />,
  review: <CalendarClock />,
  practise: <PencilLine />,
  another_explanation: <Sparkles />,
  create_lesson: <Sparkles />,
  nothing_due: null,
};

export interface NextStepsProps {
  plan: LearningPlan;
  courseId: string;
  /**
   * Shown in place of the button of a step that asks the AI provider for a lesson:
   * the control that starts it with what it sends, or where that work stands. Without
   * it, such a step leads to the course page, where it can be started and followed.
   */
  renderGeneration?: (step: NextStep, conceptId: string, primary: boolean) => ReactNode;
  /**
   * What stands above the suggestion. On the library it names the course it is about.
   * `null` where a heading just above already says it.
   */
  eyebrow?: string | null;
  /** Leave out "Or instead": where the suggestion is a way in, not the place to choose. */
  withoutAlternatives?: boolean;
}

/**
 * What Adle suggests doing next, with the reason for it, and what could be done
 * instead. A suggestion and never an instruction: every alternative is one press away.
 */
export function NextSteps({
  plan,
  courseId,
  renderGeneration,
  eyebrow = 'Up next',
  withoutAlternatives = false,
}: NextStepsProps) {
  const titleId = useId();
  const othersId = useId();
  const step = plan.recommended;

  return (
    <div className={styles.steps}>
      <section className={styles.recommended} aria-labelledby={titleId}>
        {eyebrow ? <p className={styles.eyebrow}>{eyebrow}</p> : null}
        <h3 id={titleId} className={styles.title}>
          {step.title}
        </h3>
        <p className={styles.reason}>
          <span className={styles.why}>Why: </span>
          {step.reason}
        </p>
        {plan.note ? <p className={styles.note}>{plan.note}</p> : null}
        <StepControl
          step={step}
          courseId={courseId}
          describedBy={titleId}
          primary
          renderGeneration={renderGeneration}
        />
      </section>

      {plan.alternatives.length > 0 && !withoutAlternatives ? (
        <section className={styles.others} aria-labelledby={othersId}>
          <h3 id={othersId} className={styles.othersTitle}>
            Other options
          </h3>
          <ul className={styles.list}>
            {plan.alternatives.map((other) => (
              <Alternative
                key={`${other.kind}:${other.concept_id ?? ''}:${other.lesson_id ?? ''}`}
                step={other}
                courseId={courseId}
                renderGeneration={renderGeneration}
              />
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}

function Alternative({
  step,
  courseId,
  renderGeneration,
}: {
  step: NextStep;
  courseId: string;
  renderGeneration: NextStepsProps['renderGeneration'];
}) {
  const titleId = useId();
  return (
    <li className={styles.item}>
      <div className={styles.itemText}>
        <span id={titleId} className={styles.itemTitle}>
          {step.title}
        </span>
        <span className={styles.itemReason}>{step.reason}</span>
      </div>
      <StepControl
        step={step}
        courseId={courseId}
        describedBy={titleId}
        renderGeneration={renderGeneration}
      />
    </li>
  );
}

function StepControl({
  step,
  courseId,
  describedBy,
  primary = false,
  renderGeneration,
}: {
  step: NextStep;
  courseId: string;
  describedBy: string;
  primary?: boolean;
  renderGeneration: NextStepsProps['renderGeneration'];
}) {
  const { navigate } = useRouter();
  const action: StepAction = stepAction(step, courseId);
  if (action.type === 'none') return null;

  if (action.type === 'generate') {
    if (renderGeneration) {
      return (
        <div className={styles.generation}>{renderGeneration(step, action.conceptId, primary)}</div>
      );
    }
    return (
      <div className={styles.control}>
        <Button
          variant={primary ? 'primary' : 'secondary'}
          size={primary ? 'medium' : 'small'}
          icon={<ArrowRight />}
          aria-describedby={describedBy}
          onClick={() => navigate({ name: 'course', courseId, tab: 'learn' })}
        >
          Go to the course
        </Button>
      </div>
    );
  }

  const needsSetup = action.route.name === 'settings';
  return (
    <div className={styles.control}>
      <Button
        variant={primary ? 'primary' : 'secondary'}
        size={primary ? 'medium' : 'small'}
        icon={needsSetup ? <Settings /> : ICONS[step.kind]}
        aria-describedby={describedBy}
        onClick={() => navigate(action.route)}
      >
        {action.label}
      </Button>
      {needsSetup ? (
        <span className={styles.hint}>Add an AI provider key to create this lesson.</span>
      ) : null}
    </div>
  );
}
