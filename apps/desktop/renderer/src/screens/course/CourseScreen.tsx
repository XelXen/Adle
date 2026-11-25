import {
  ArrowLeft,
  Clapperboard,
  Download,
  FileText,
  GraduationCap,
  ListTree,
  Trash2,
} from 'lucide-react';
import { useState } from 'react';

import {
  Badge,
  Button,
  Dialog,
  ErrorState,
  LoadingState,
  Page,
  Stack,
  type TabItem,
  Tabs,
  useToast,
} from '@adle/design-system';

import { type CourseTab, useRouter } from '../../app/router';
import { callCore, CoreRequestError, describeError } from '../../lib/core-client';
import { originLabel } from '../../lib/course-files';
import { taughtAs, useLessonRules } from '../../lib/lesson-rules';
import { useResource } from '../../lib/use-resource';
import styles from './CourseScreen.module.css';
import { CurriculumPanel } from './CurriculumPanel';
import { FilmPanel } from './FilmPanel';
import { LearnPanel } from './LearnPanel';
import { LessonRulesDialog } from './LessonRulesDialog';
import { SaveCourseDialog } from './SaveCourseDialog';
import { SourcesPanel } from './SourcesPanel';

const TABS: readonly TabItem<CourseTab>[] = [
  { value: 'learn', label: 'Learn', icon: <GraduationCap /> },
  { value: 'curriculum', label: 'Curriculum', icon: <ListTree /> },
  { value: 'sources', label: 'Materials', icon: <FileText /> },
  { value: 'film', label: 'Film', icon: <Clapperboard /> },
];

/** One course: what to do next in it, what it teaches, and the materials it draws on. */
export function CourseScreen({ courseId, tab }: { courseId: string; tab: CourseTab }) {
  const { navigate } = useRouter();
  const toast = useToast();
  // Opening a course records the visit so the library can sort by recent use.
  const course = useResource(`course:${courseId}`, () =>
    callCore('courses.get', { path: { course_id: courseId }, query: { opened: true } }),
  );
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  // How this course's lessons are formed, and as what subject (ADR-061): one press away.
  const rules = useLessonRules();
  const [showingRules, setShowingRules] = useState(false);
  // The course as a file, for someone else or for another computer (ADR-063).
  const [savingFile, setSavingFile] = useState(false);

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
        <LoadingState title="Opening course…" />
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
          title={missing ? 'This course no longer exists' : 'Couldn’t open the course'}
          description={missing ? 'It may have been deleted.' : describeError(course.resource.error)}
          actions={
            missing ? (
              <Button variant="primary" onClick={() => navigate({ name: 'home' })}>
                Back to library
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
        title: 'Couldn’t delete the course',
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
          <span className={styles.facts}>
            <Badge tone={data.origin === 'sample' ? 'accent' : 'neutral'}>
              {originLabel(data)}
            </Badge>
            <Button variant="tertiary" size="small" onClick={() => setShowingRules(true)}>
              {taughtAs(data, rules.resource.status === 'ready' ? rules.resource.data : null)}
            </Button>
          </span>
          {data.topic ? <span className={styles.topic}>{data.topic}</span> : null}
          {data.description ? <span>{data.description}</span> : null}
        </Stack>
      }
      actions={
        <>
          <Button variant="tertiary" icon={<Download />} onClick={() => setSavingFile(true)}>
            Save as a file
          </Button>
          <Button variant="tertiary" icon={<Trash2 />} onClick={() => setConfirmingDelete(true)}>
            Delete course
          </Button>
        </>
      }
    >
      <Tabs
        label="Parts of this course"
        tabs={TABS}
        value={tab}
        onValueChange={(next) => {
          // Importing or removing materials changes what the other tab can offer.
          course.reload();
          navigate({ name: 'course', courseId, tab: next });
        }}
      >
        {(current) =>
          current === 'learn' ? (
            <LearnPanel course={data} />
          ) : current === 'curriculum' ? (
            <CurriculumPanel course={data} onCourseChanged={course.reload} />
          ) : current === 'film' ? (
            <FilmPanel course={data} />
          ) : (
            <SourcesPanel courseId={courseId} onCourseChanged={course.reload} />
          )
        }
      </Tabs>

      <LessonRulesDialog
        course={data}
        open={showingRules}
        onClose={() => setShowingRules(false)}
        onCourseChanged={course.setData}
      />

      {savingFile ? <SaveCourseDialog course={data} onClose={() => setSavingFile(false)} /> : null}

      <Dialog
        open={confirmingDelete}
        onClose={() => setConfirmingDelete(false)}
        title={`Delete “${data.title}”?`}
        description="This permanently removes the course, its materials, and your progress. Your original files aren’t touched."
        dismissible={!deleting}
        actions={
          <>
            <Button onClick={() => setConfirmingDelete(false)} disabled={deleting}>
              Cancel
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
