import { FileText, Lightbulb } from 'lucide-react';
import { type FormEvent, useState } from 'react';

import type { Course } from '@adle/contracts';
import { Button, Dialog, SegmentedControl, Stack, TextArea, TextField } from '@adle/design-system';

import { callCore, describeError } from '../../lib/core-client';
import styles from './HomeScreen.module.css';

type Origin = 'topic' | 'materials';

const ORIGINS = [
  { value: 'topic', label: 'Start with a topic', icon: <Lightbulb /> },
  { value: 'materials', label: 'Import my materials', icon: <FileText /> },
] as const;

export interface NewCourseDialogProps {
  open: boolean;
  onClose: () => void;
  onCreated: (course: Course) => void;
}

/** Create a course from a topic or from the learner's own materials. */
export function NewCourseDialog({ open, onClose, onCreated }: NewCourseDialogProps) {
  const [origin, setOrigin] = useState<Origin>('topic');
  const [title, setTitle] = useState('');
  const [topic, setTopic] = useState('');
  const [errors, setErrors] = useState<{ title?: string; topic?: string; form?: string }>({});
  const [creating, setCreating] = useState(false);

  const reset = (): void => {
    setOrigin('topic');
    setTitle('');
    setTopic('');
    setErrors({});
  };

  const close = (): void => {
    if (creating) return;
    reset();
    onClose();
  };

  const submit = async (event: FormEvent): Promise<void> => {
    event.preventDefault();
    const problems: typeof errors = {};
    if (!title.trim()) problems.title = 'Give the course a name.';
    if (origin === 'topic' && !topic.trim()) {
      problems.topic = 'Describe what you want to learn, in a sentence or two.';
    }
    setErrors(problems);
    if (Object.keys(problems).length > 0) return;

    setCreating(true);
    try {
      const course = await callCore('courses.create', {
        body: {
          title: title.trim(),
          origin,
          topic: origin === 'topic' ? topic.trim() : null,
        },
      });
      reset();
      onCreated(course);
    } catch (error) {
      setErrors({ form: describeError(error) });
    } finally {
      setCreating(false);
    }
  };

  return (
    <Dialog
      open={open}
      onClose={close}
      title="New course"
      description="A course keeps your materials, the curriculum built from them, and your progress together."
      size="medium"
      dismissible={!creating}
    >
      <form className={styles.form} onSubmit={(event) => void submit(event)} noValidate>
        <Stack gap={2}>
          <span className={styles.groupLabel} id="new-course-origin">
            How do you want to start?
          </span>
          <SegmentedControl<Origin>
            label="How do you want to start?"
            value={origin}
            options={ORIGINS}
            onValueChange={setOrigin}
          />
          <p className={styles.hint}>
            {origin === 'topic'
              ? 'Adle will propose a curriculum for the topic. You can add your own materials at any time.'
              : 'Add PDFs, Word documents, Markdown, or text files next. They stay on this computer.'}
          </p>
        </Stack>

        <TextField
          label="Course name"
          value={title}
          maxLength={200}
          error={errors.title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder={
            origin === 'topic' ? 'Introduction to neural networks' : 'Machine learning, autumn term'
          }
        />

        {origin === 'topic' ? (
          <TextArea
            label="What do you want to learn?"
            value={topic}
            maxLength={4000}
            rows={4}
            error={errors.topic}
            onChange={(event) => setTopic(event.target.value)}
            description="Mention your goal and what you already know. For example: “How neural networks learn, for someone comfortable with basic algebra.”"
          />
        ) : null}

        {errors.form ? (
          <p className={styles.formError} role="alert">
            {errors.form}
          </p>
        ) : null}

        <div className={styles.formActions}>
          <Button onClick={close} disabled={creating}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" loading={creating}>
            Create course
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
