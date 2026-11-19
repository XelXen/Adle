import { ArrowRight, BookOpen, KeyRound, Library, Plus } from 'lucide-react';
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
} from '@adle/design-system';

import { useApp } from '../../app/AppContext';
import { useRouter } from '../../app/router';
import { getBridge } from '../../lib/bridge';
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
  const [creating, setCreating] = useState(false);
  // Reload when the local service becomes ready (it may still be starting at first paint).
  const courses = useResource(`courses:${coreStatus.state}`, () => callCore('courses.list'));
  const keyState = useResource('provider-key', () => getBridge().provider.keyState());
  const aiReady = keyState.resource.status === 'ready' && keyState.resource.data.stored;

  const open = (course: Course): void =>
    navigate({ name: 'course', courseId: course.id, tab: 'sources' });

  const starting = coreStatus.state === 'starting';
  const list = courses.resource;

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
            description="Create a course from a topic you want to learn, or from your own notes and readings."
            actions={
              <Button variant="primary" icon={<Plus />} onClick={() => setCreating(true)}>
                Create your first course
              </Button>
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

      {keyState.resource.status === 'ready' && !aiReady ? (
        <Section title="Set up">
          <ActionCard
            media={<KeyRound />}
            title="AI provider"
            description="Add an AIHubMix key to generate curricula and lessons. Your library and materials work without one."
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
