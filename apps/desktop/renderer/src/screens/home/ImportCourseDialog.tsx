import { useState } from 'react';

import {
  Button,
  Callout,
  Checkbox,
  Dialog,
  Disclosure,
  Stack,
  useToast,
} from '@adle/design-system';

import { type CourseFileFound, type CourseFileHolds, getBridge } from '../../lib/bridge';
import { describeError } from '../../lib/core-client';
import { heldBy, leftOutOfCourse, whatItHolds } from '../../lib/course-files';
import { pluralise } from '../../lib/format';

/**
 * Bring a course in from a file the learner chose (ADR-063). It says what the file holds
 * and makes a new course of it: everything, unless the learner leaves some of it out under
 * "Advanced". Nothing here is changed or replaced by a file.
 *
 * Mounted only while there is a file to ask about.
 */
export function ImportCourseDialog({
  found,
  onClose,
  onImported,
}: {
  found: CourseFileFound;
  onClose: () => void;
  onImported: (courseId: string) => void;
}) {
  const toast = useToast();
  const has = heldBy(found.counts);
  const [holds, setHolds] = useState<CourseFileHolds>(has);
  const [importing, setImporting] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  const bringIn = async (): Promise<void> => {
    setImporting(true);
    setProblem(null);
    try {
      const result = await getBridge().courses.bringIn(found.token, holds);
      if (!result.ok) {
        setProblem(result.error.message);
        return;
      }
      toast.show({
        tone: 'success',
        title: 'Course imported',
        description: leftOutOfCourse(result.data.lessonsLeftOut) ?? result.data.title,
      });
      onImported(result.data.courseId);
    } catch (error) {
      setProblem(describeError(error));
    } finally {
      setImporting(false);
    }
  };

  const hold = (part: keyof CourseFileHolds) => (checked: boolean) =>
    setHolds((current) => ({ ...current, [part]: checked }));
  const anything = has.lessons || has.materials || has.progress || has.notes;

  return (
    <Dialog
      open
      onClose={onClose}
      title={`Import “${found.title}”?`}
      description={`${found.fileName} holds ${whatItHolds(found.counts)} It becomes a new course.`}
      dismissible={!importing}
      actions={
        <>
          <Button onClick={onClose} disabled={importing}>
            Cancel
          </Button>
          <Button variant="primary" loading={importing} onClick={() => void bringIn()}>
            Import
          </Button>
        </>
      }
    >
      <Stack gap={4}>
        {anything ? (
          <Disclosure label="Advanced">
            {has.lessons ? (
              <Checkbox
                label={`Lessons (${found.counts.lessons.toLocaleString()})`}
                checked={holds.lessons}
                disabled={importing}
                onCheckedChange={hold('lessons')}
              />
            ) : null}
            {has.materials ? (
              <Checkbox
                label={`Materials (${pluralise(found.counts.materials, 'source')})`}
                description="The files the course was made from, and their text."
                checked={holds.materials}
                disabled={importing}
                onCheckedChange={hold('materials')}
              />
            ) : null}
            {has.progress ? (
              <Checkbox
                label="Progress"
                description="The answers given, and what they showed."
                checked={holds.progress}
                disabled={importing}
                onCheckedChange={hold('progress')}
              />
            ) : null}
            {has.notes ? (
              <Checkbox
                label={`Notes (${found.counts.notes.toLocaleString()})`}
                description="What was asked during lessons, and the answers."
                checked={holds.notes}
                disabled={importing}
                onCheckedChange={hold('notes')}
              />
            ) : null}
          </Disclosure>
        ) : null}
        {problem ? (
          <Callout tone="danger" title="Couldn’t import the course">
            {problem}
          </Callout>
        ) : null}
      </Stack>
    </Dialog>
  );
}
