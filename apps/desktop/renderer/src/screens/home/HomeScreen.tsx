import { ArrowRight, BookOpen, GraduationCap, KeyRound, Library, Plus } from 'lucide-react';
import { useState } from 'react';

import type { Course } from '@adle/contracts';
import {
  ActionCard,
  Badge,
  Button,
  EmptyState,
  ErrorState,
  LoadingState,
  Page,
  Section,
  useToast,
} from '@adle/design-system';

import { useApp } from '../../app/AppContext';
import { useRouter } from '../../app/router';
import { NextSteps } from '../../components/NextSteps';
import { callCore, describeError } from '../../lib/core-client';
import { courseRoute } from '../../lib/courses';
import { formatRelativeDay, pluralise } from '../../lib/format';
import { useResource } from '../../lib/use-resource';
import styles from './HomeScreen.module.css';
import { NewCourseDialog } from './NewCourseDialog';

const ORIGIN_LABEL: Record<Course['origin'], string> = {
  sample: 'Sample course',
  topic: 'From a topic',
  materials: 'From your materials',
};

function courseSummary(course: Course): string {
  const sources =
    course.source_count === 0 ? 'No materials' : pluralise(course.source_count, 'source');
  const used = course.last_opened_at
    ? `Opened ${formatRelativeDay(course.last_opened_at).toLowerCase()}`
    : `Created ${formatRelativeDay(course.created_at).toLowerCase()}`;
  return `${sources} · ${used}`;
}

/** The library: where a learner returns to continue or begin a course. */
export function HomeScreen() {
  const { navigate } = useRouter();
  const { coreStatus } = useApp();
  const toast = useToast();
  const [creating, setCreating] = useState(false);
  const [addingSample, setAddingSample] = useState(false);
  // Reload when the local service becomes ready (it may still be starting at first paint).
  const courses = useResource(`courses:${coreStatus.state}`, () => callCore('courses.list'));
  // The provider in use, and whether it has a key. Asked again once the service is ready.
  const provider = useResource(`provider-status:${coreStatus.state}`, () =>
    callCore('provider.status'),
  );
  const aiMissing = provider.resource.status === 'ready' && !provider.resource.data.key_configured;

  const open = (course: Course): void => navigate(courseRoute(course));

  // The course the learner was last in, and what Adle would suggest doing there next: the
  // same suggestion its own page shows, one press away from the moment the app opens.
  const recent =
    courses.resource.status === 'ready'
      ? courses.resource.data.courses.find((course) => course.last_opened_at)
      : undefined;
  const recentId = recent?.id ?? null;
  const next = useResource(`home-next:${recentId ?? 'none'}`, async () =>
    recentId ? callCore('learning.overview', { path: { course_id: recentId } }) : null,
  );

  // The sample course is written by Adle and ships with the app: adding it needs no provider.
  const addSample = async (): Promise<void> => {
    setAddingSample(true);
    try {
      const course = await callCore('courses.install_sample');
      navigate({ name: 'course', courseId: course.id, tab: 'learn' });
    } catch (error) {
      toast.show({
        tone: 'danger',
        title: 'Couldn’t add the sample course',
        description: describeError(error),
      });
      setAddingSample(false);
    }
  };

  const starting = coreStatus.state === 'starting';
  const list = courses.resource;
  const hasSample =
    list.status === 'ready' && list.data.courses.some((course) => course.origin === 'sample');

  return (
    <Page
      title="Library"
      description="Your courses, and where you left off."
      actions={
        <Button variant="primary" icon={<Plus />} onClick={() => setCreating(true)}>
          New course
        </Button>
      }
    >
      {/* Shown once it is known; the list of courses below never waits for it. */}
      {recent && next.resource.status === 'ready' && next.resource.data ? (
        <Section title="Continue learning">
          <NextSteps
            plan={next.resource.data.plan}
            courseId={recent.id}
            eyebrow={recent.title}
            withoutAlternatives
          />
        </Section>
      ) : null}

      <Section title="Your courses">
        {list.status === 'loading' || (list.status === 'error' && starting) ? (
          <LoadingState title="Loading library…" />
        ) : list.status === 'error' ? (
          <ErrorState
            title="Couldn’t load your library"
            description={describeError(list.error)}
            actions={<Button onClick={courses.reload}>Try again</Button>}
          />
        ) : list.data.courses.length === 0 ? (
          <EmptyState
            visual={<Library />}
            title="No courses yet"
            description="Create a course from a topic or your own notes, or try the sample."
            actions={
              <>
                <Button variant="primary" icon={<Plus />} onClick={() => setCreating(true)}>
                  Create your first course
                </Button>
                <Button
                  icon={<GraduationCap />}
                  loading={addingSample}
                  onClick={() => void addSample()}
                >
                  Try the sample course
                </Button>
              </>
            }
          />
        ) : (
          <ul className={styles.courses}>
            {list.data.courses.map((course) => (
              <li key={course.id}>
                <ActionCard
                  media={<BookOpen />}
                  title={course.title}
                  description={courseSummary(course)}
                  meta={
                    <>
                      <Badge tone={course.origin === 'sample' ? 'accent' : 'neutral'}>
                        {ORIGIN_LABEL[course.origin]}
                      </Badge>
                      <ArrowRight aria-hidden="true" />
                    </>
                  }
                  onClick={() => open(course)}
                />
              </li>
            ))}
          </ul>
        )}
      </Section>

      {list.status === 'ready' && list.data.courses.length > 0 && !hasSample ? (
        <Section title="See how it works">
          <ActionCard
            media={<GraduationCap />}
            title="Introduction to neural networks"
            description="A short course to see how lessons work."
            meta={
              <>
                <Badge tone="accent">Sample course</Badge>
                <ArrowRight aria-hidden="true" />
              </>
            }
            disabled={addingSample}
            onClick={() => void addSample()}
          />
        </Section>
      ) : null}

      {aiMissing ? (
        <Section title="Set up">
          <ActionCard
            media={<KeyRound />}
            title="AI provider"
            description="Add a key to create courses and lessons with AI."
            meta={
              <>
                <Badge>Not set up</Badge>
                <ArrowRight aria-hidden="true" />
              </>
            }
            onClick={() => navigate({ name: 'settings', tab: 'ai' })}
          />
        </Section>
      ) : null}

      <NewCourseDialog
        open={creating}
        onClose={() => setCreating(false)}
        onCreated={(course, settingUp) => {
          setCreating(false);
          // Being set up, the course is seen taking shape on its curriculum (ADR-053).
          navigate(
            settingUp
              ? { name: 'course', courseId: course.id, tab: 'curriculum' }
              : courseRoute(course),
          );
        }}
      />
    </Page>
  );
}
