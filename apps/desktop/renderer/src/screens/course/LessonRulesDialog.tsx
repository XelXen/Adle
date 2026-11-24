import { useState } from 'react';

import type { Course } from '@adle/contracts';
import {
  Button,
  Dialog,
  ErrorState,
  LoadingState,
  Select,
  Stack,
  useToast,
} from '@adle/design-system';

import { callCore, describeError } from '../../lib/core-client';
import {
  choiceOf,
  type SubjectChoice,
  subjectChoices,
  subjectOf,
  useLessonRules,
} from '../../lib/lesson-rules';
import styles from './CourseScreen.module.css';

/**
 * How this course's lessons are formed (ADR-061): the rules every lesson follows, what
 * this course's subject needs besides, and the subject itself, which the learner may
 * choose. What it says is the core's own list, the one a lesson's writer is given.
 */
export function LessonRulesDialog({
  course,
  open,
  onClose,
  onCourseChanged,
}: {
  course: Course;
  open: boolean;
  onClose: () => void;
  onCourseChanged: (course: Course) => void;
}) {
  const toast = useToast();
  const rules = useLessonRules();
  const [saving, setSaving] = useState(false);

  const choose = async (subject: SubjectChoice): Promise<void> => {
    setSaving(true);
    try {
      onCourseChanged(
        await callCore('courses.update', { path: { course_id: course.id }, body: { subject } }),
      );
    } catch (error) {
      toast.show({
        tone: 'danger',
        title: 'Couldn’t change the subject',
        description: describeError(error),
      });
    } finally {
      setSaving(false);
    }
  };

  const loaded = rules.resource.status === 'ready' ? rules.resource.data : null;
  const subject = subjectOf(loaded, course.subject ?? 'general');

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="How lessons are formed"
      size="medium"
      actions={<Button onClick={onClose}>Done</Button>}
    >
      {rules.resource.status === 'loading' ? (
        <LoadingState title="Reading the rules…" />
      ) : rules.resource.status === 'error' ? (
        <ErrorState
          title="Couldn’t read the rules"
          description={describeError(rules.resource.error)}
          actions={<Button onClick={rules.reload}>Try again</Button>}
        />
      ) : (
        <Stack gap={5}>
          <section aria-labelledby="every-lesson">
            <h3 id="every-lesson" className={styles.rulesHeading}>
              Every lesson
            </h3>
            <ul className={styles.rules}>
              {rules.resource.data.rules.map((rule) => (
                <li key={rule}>{rule}</li>
              ))}
            </ul>
          </section>
          <section aria-labelledby="this-course">
            <h3 id="this-course" className={styles.rulesHeading}>
              This course
            </h3>
            <Stack gap={3}>
              <Select<SubjectChoice>
                label="Taught as"
                description="Lessons already written stay as they are."
                value={choiceOf(course)}
                options={subjectChoices(course, rules.resource.data)}
                disabled={saving}
                onValueChange={(value) => void choose(value)}
              />
              {subject ? (
                <ol className={styles.rules} aria-label={`How a lesson of ${subject.name} goes`}>
                  {subject.steps.map((step) => (
                    <li key={step}>{step}</li>
                  ))}
                </ol>
              ) : null}
            </Stack>
          </section>
        </Stack>
      )}
    </Dialog>
  );
}
