import { FileText, FolderOpen, Lightbulb } from 'lucide-react';
import { type FormEvent, useState } from 'react';

import type { Course } from '@adle/contracts';
import {
  Button,
  Checkbox,
  Dialog,
  SegmentedControl,
  Stack,
  TextArea,
  TextField,
} from '@adle/design-system';

import { WhatIsSent } from '../../components/WhatIsSent';
import { getBridge } from '../../lib/bridge';
import { callCore, describeError } from '../../lib/core-client';
import { lessonDisclosure } from '../../lib/generation';
import { destination, usualWait } from '../../lib/provider';
import { useResource } from '../../lib/use-resource';
import styles from './HomeScreen.module.css';

type Origin = 'materials' | 'topic';

const ORIGINS = [
  { value: 'materials', label: 'From my files', icon: <FileText /> },
  { value: 'topic', label: 'From a topic', icon: <Lightbulb /> },
] as const;

export interface NewCourseDialogProps {
  open: boolean;
  onClose: () => void;
  /** The course was made; `settingUp` when Adle is setting it up (ADR-053). */
  onCreated: (course: Course, settingUp: boolean) => void;
}

/**
 * Create a course from the learner's own files or from a topic (ADR-053). The files are
 * chosen here, in the system's own dialog, and the name may be left to Adle, who names the
 * course from them and from the concepts it suggests. With "Set it up for me", Adle adds
 * the concepts it suggests and writes the first lesson.
 */
export function NewCourseDialog({ open, onClose, onCreated }: NewCourseDialogProps) {
  const [origin, setOrigin] = useState<Origin>('materials');
  const [title, setTitle] = useState('');
  const [topic, setTopic] = useState('');
  const [setUp, setSetUp] = useState(true);
  const [errors, setErrors] = useState<{ topic?: string; form?: string }>({});
  const [creating, setCreating] = useState(false);
  const provider = useResource('provider-status', () => callCore('provider.status'));
  const status = provider.resource.status === 'ready' ? provider.resource.data : undefined;
  // Setting a course up asks the AI: without a key there is nobody to ask.
  const canSetUp = status?.key_configured === true;
  const settingUp = canSetUp && setUp;

  const reset = (): void => {
    setOrigin('materials');
    setTitle('');
    setTopic('');
    setSetUp(true);
    setErrors({});
  };

  const close = (): void => {
    if (creating) return;
    reset();
    onClose();
  };

  const submit = async (event: FormEvent): Promise<void> => {
    event.preventDefault();
    if (origin === 'topic' && !topic.trim()) {
      setErrors({ topic: 'Describe what you want to learn, in a sentence or two.' });
      return;
    }
    setErrors({});
    setCreating(true);
    try {
      const named = title.trim();
      const course = await callCore('courses.create', {
        body: {
          ...(named ? { title: named } : {}),
          origin,
          topic: origin === 'topic' ? topic.trim() : null,
        },
      });
      if (origin === 'materials') {
        const picked = await getBridge().sources.importWithPicker(course.id);
        if (!picked.ok || picked.data === null) {
          // No files chosen: nothing is left behind, and the learner can choose again.
          await callCore('courses.delete', { path: { course_id: course.id } }).catch(
            () => undefined,
          );
          if (!picked.ok) setErrors({ form: picked.error.message });
          return;
        }
      }
      let started = false;
      if (settingUp) {
        try {
          await callCore('generation.propose_curriculum', {
            path: { course_id: course.id },
            body: { setup: true },
          });
          started = true;
        } catch {
          // The course is made; its curriculum can still be asked for there.
        }
      }
      reset();
      onCreated(course, started);
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
      description="A course holds your materials, curriculum, and progress."
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
            {origin === 'materials'
              ? 'PDFs, Word documents, Markdown, or text files. They stay on this computer.'
              : 'You can add files later.'}
          </p>
        </Stack>

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

        <TextField
          label="Course name"
          value={title}
          maxLength={200}
          onChange={(event) => setTitle(event.target.value)}
          description={
            origin === 'materials'
              ? 'Optional. Left empty, Adle names it from your files.'
              : 'Optional. Left empty, Adle names it from your topic.'
          }
        />

        <Checkbox
          label="Set it up for me"
          description={
            canSetUp
              ? 'Adle suggests the concepts and adds them, then writes the first lesson. You can change anything afterwards.'
              : 'Needs an AI key, in Settings.'
          }
          checked={settingUp}
          disabled={!canSetUp}
          onCheckedChange={setSetUp}
        />

        {errors.form ? (
          <p className={styles.formError} role="alert">
            {errors.form}
          </p>
        ) : null}

        <div className={styles.formActions}>
          {settingUp ? (
            <WhatIsSent
              what={`${
                origin === 'materials'
                  ? 'headings and short excerpts from your files'
                  : 'your topic'
              } and your goal, to suggest the concepts; then ${lessonDisclosure(
                origin === 'materials' ? 'some' : 'none',
              )}, to write the first lesson`}
              to={destination(status, 'curriculum')}
              wait={usualWait(status, 'lesson')}
            />
          ) : null}
          <Button onClick={close} disabled={creating}>
            Cancel
          </Button>
          <Button
            type="submit"
            variant="primary"
            icon={origin === 'materials' ? <FolderOpen /> : undefined}
            loading={creating}
          >
            {origin === 'materials' ? 'Choose files…' : 'Create course'}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
