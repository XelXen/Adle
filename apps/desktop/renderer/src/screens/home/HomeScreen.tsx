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
import { callCore, describeError } from '../../lib/core-client';
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
    course.source_count === 0 ? 'No sources yet' : pluralise(course.source_count, 'source');
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

  // A course with something to learn opens on what to do next. One that is still being set
  // up opens where the setting up happens: its materials if it is waiting for them, else its
  // curriculum.
  const open = (course: Course): void =>
    navigate({
      name: 'course',
      courseId: course.id,
      tab:
        course.concept_count > 0
          ? 'learn'
          : course.origin === 'materials' && course.source_count === 0
            ? 'sources'
            : 'curriculum',
    });

  // The sample course is written by Adle and ships with the app: adding it needs no provider.
  const addSample = async (): Promise<void> => {
    setAddingSample(true);
    try {
      const course = await callCore('courses.install_sample');
      navigate({ name: 'course', courseId: course.id, tab: 'learn' });
    } catch (error) {
      toast.show({
        tone: 'danger',
        title: 'The sample course could not be added',
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
      description="Your courses, and the place to pick up where you left off."
      actions={
        <Button variant="primary" icon={<Plus />} onClick={() => setCreating(true)}>
          New course
        </Button>
      }
    >
      <Section title="Your courses">
        {list.status === 'loading' || (list.status === 'error' && starting) ? (
          <LoadingState title="Opening your library…" />
        ) : list.status === 'error' ? (
          <ErrorState
            title="Your library could not be opened"
            description={describeError(list.error)}
            actions={<Button onClick={courses.reload}>Try again</Button>}
          />
        ) : list.data.courses.length === 0 ? (
          <EmptyState
            visual={<Library />}
            title="No courses yet"
            description="Create a course from a topic you want to learn, or from your own notes and readings. Or try the sample course first to see how a lesson works."
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
            description="A short sample course written by Adle. Add it to try a narrated lesson with a live picture and a few questions."
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
            description="Choose an AI provider and add its key to generate curricula and lessons. Your library and materials work without one."
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
        onCreated={(course) => {
          setCreating(false);
          open(course);
        }}
      />
    </Page>
  );
}
