import { ArrowLeft, Trash2 } from 'lucide-react';
import { useState } from 'react';

import {
  Badge,
  Button,
  Dialog,
  ErrorState,
  LoadingState,
  Page,
  Stack,
  useToast,
} from '@adle/design-system';

import { useRouter } from '../../app/router';
import { callCore, CoreRequestError, describeError } from '../../lib/core-client';
import { useResource } from '../../lib/use-resource';
import styles from './CourseScreen.module.css';
import { SourcesPanel } from './SourcesPanel';

const ORIGIN_LABEL = {
  sample: 'Sample course',
  topic: 'From a topic',
  materials: 'From your materials',
} as const;

/** One course: its materials today; curriculum, lessons, and progress as they are built. */
export function CourseScreen({ courseId }: { courseId: string }) {
  const { navigate } = useRouter();
  const toast = useToast();
  // Opening a course records the visit so the library can sort by recent use.
  const course = useResource(`course:${courseId}`, () =>
    callCore('courses.get', { path: { course_id: courseId }, query: { opened: true } }),
  );
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const backToLibrary = (
    <Button
      variant="tertiary"
      size="small"
      icon={<ArrowLeft />}
      onClick={() => navigate({ name: 'home' })}
    >
      Library
    </Button>
  );

  if (course.resource.status === 'loading') {
    return (
      <Page title="Course" eyebrow={backToLibrary}>
        <LoadingState title="Opening the course…" />
      </Page>
    );
  }

  if (course.resource.status === 'error') {
    const missing =
      course.resource.error instanceof CoreRequestError &&
      course.resource.error.code === 'not_found';
    return (
      <Page title="Course" eyebrow={backToLibrary}>
        <ErrorState
          title={missing ? 'This course no longer exists' : 'The course could not be opened'}
          description={missing ? 'It may have been deleted.' : describeError(course.resource.error)}
          actions={
            missing ? (
              <Button variant="primary" onClick={() => navigate({ name: 'home' })}>
                Back to the library
              </Button>
            ) : (
              <Button onClick={course.reload}>Try again</Button>
            )
          }
        />
      </Page>
    );
  }

  const data = course.resource.data;

  const deleteCourse = async (): Promise<void> => {
    setDeleting(true);
    try {
      await callCore('courses.delete', { path: { course_id: courseId } });
      toast.show({ tone: 'success', title: 'Course deleted', description: data.title });
      navigate({ name: 'home' });
    } catch (error) {
      toast.show({
        tone: 'danger',
        title: 'The course could not be deleted',
        description: describeError(error),
      });
      setDeleting(false);
      setConfirmingDelete(false);
    }
  };

  return (
    <Page
      title={data.title}
      eyebrow={backToLibrary}
      description={
        <Stack gap={2}>
          <span>
            <Badge tone={data.origin === 'sample' ? 'accent' : 'neutral'}>
              {ORIGIN_LABEL[data.origin]}
            </Badge>
          </span>
          {data.topic ? <span className={styles.topic}>{data.topic}</span> : null}
          {data.description ? <span>{data.description}</span> : null}
        </Stack>
      }
      actions={
        <Button variant="tertiary" icon={<Trash2 />} onClick={() => setConfirmingDelete(true)}>
          Delete course
        </Button>
      }
    >
      <SourcesPanel courseId={courseId} />

      <Dialog
        open={confirmingDelete}
        onClose={() => setConfirmingDelete(false)}
        title={`Delete “${data.title}”?`}
        description="This permanently removes the course, its imported materials, and your progress in it from this computer. The original files you imported from are not touched. This cannot be undone."
        dismissible={!deleting}
        actions={
          <>
            <Button onClick={() => setConfirmingDelete(false)} disabled={deleting}>
              Keep course
            </Button>
            <Button variant="destructive" loading={deleting} onClick={() => void deleteCourse()}>
              Delete course
            </Button>
          </>
        }
      />
    </Page>
  );
}
