import { Download } from 'lucide-react';
import { useState } from 'react';

import type { Course } from '@adle/contracts';
import {
  Button,
  Callout,
  Checkbox,
  Dialog,
  Disclosure,
  RadioGroup,
  Stack,
  useToast,
} from '@adle/design-system';

import { type CourseFileHolds, type CourseFileKind, getBridge } from '../../lib/bridge';
import { describeError } from '../../lib/core-client';
import { holdsFor, KIND_CHOICES, leftOutOfFile } from '../../lib/course-files';
import styles from './CourseScreen.module.css';

/**
 * Save a course as a file (ADR-063): as a template, the plan and its lessons for someone
 * else to start from, or with everything, to move it to another computer. What either
 * holds can be changed under "Advanced". Where the file goes is asked by the system's own
 * window, after this: the page never names a place.
 *
 * Mounted only while it is open, so that it begins as a template every time.
 */
export function SaveCourseDialog({ course, onClose }: { course: Course; onClose: () => void }) {
  const toast = useToast();
  const [kind, setKind] = useState<CourseFileKind>('template');
  const [holds, setHolds] = useState<CourseFileHolds>(holdsFor('template'));
  const [saving, setSaving] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  const save = async (): Promise<void> => {
    setSaving(true);
    setProblem(null);
    try {
      const result = await getBridge().courses.saveFile(course.id, { kind, holds });
      if (!result.ok) {
        setProblem(result.error.message);
        return;
      }
      // Backed out of the window that asks where: the choices here are still theirs.
      if (result.data === null) return;
      const leftOut = leftOutOfFile(result.data.lessonsLeftOut);
      toast.show({
        tone: 'success',
        title: 'Course saved',
        description: leftOut ? `${result.data.fileName}. ${leftOut}` : result.data.fileName,
      });
      onClose();
    } catch (error) {
      setProblem(describeError(error));
    } finally {
      setSaving(false);
    }
  };

  const hold = (part: keyof CourseFileHolds) => (checked: boolean) =>
    setHolds((current) => ({ ...current, [part]: checked }));

  return (
    <Dialog
      open
      onClose={onClose}
      title={`Save “${course.title}” as a file`}
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
            onClick={() => void save()}
          >
            Save…
          </Button>
        </>
      }
    >
      <Stack gap={4}>
        <RadioGroup
          label="What to save"
          value={kind}
          options={KIND_CHOICES}
          disabled={saving}
          onValueChange={(next) => {
            setKind(next);
            setHolds(holdsFor(next));
          }}
        />
        <Disclosure label="Advanced">
          <p className={styles.fileNote}>The course’s plan is always saved.</p>
          <Checkbox
            label="Lessons"
            checked={holds.lessons}
            disabled={saving}
            onCheckedChange={hold('lessons')}
          />
          <Checkbox
            label="Materials"
            description="The files you imported, and their text."
            checked={holds.materials}
            disabled={saving}
            onCheckedChange={hold('materials')}
          />
          <Checkbox
            label="Progress"
            description="Your answers, and what you have shown you know."
            checked={holds.progress}
            disabled={saving}
            onCheckedChange={hold('progress')}
          />
          <Checkbox
            label="Notes"
            description="What you asked during lessons, and the answers."
            checked={holds.notes}
            disabled={saving}
            onCheckedChange={hold('notes')}
          />
        </Disclosure>
        {problem ? (
          <Callout tone="danger" title="Couldn’t save the course">
            {problem}
          </Callout>
        ) : null}
      </Stack>
    </Dialog>
  );
}
