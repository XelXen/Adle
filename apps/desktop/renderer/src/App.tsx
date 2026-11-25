import { BookOpen, Clapperboard, Coffee, Library, PenLine, Settings } from 'lucide-react';
import type { ReactNode } from 'react';

import {
  AppShell,
  Logo,
  NavItem,
  NavSection,
  ToastProvider,
  WindowStrip,
} from '@adle/design-system';

import { useApp } from './app/AppContext';
import { BreakProvider, useBreak } from './app/BreakContext';
import { FilmWatchProvider, useFilmWatch } from './app/FilmWatch';
import { type Route, useRouter } from './app/router';
import { SceneTrials } from './app/SceneTrials';
import { useWriting, WritingProvider } from './app/WritingContext';
import { CoreStatusIndicator } from './components/CoreStatusIndicator';
import { clockText } from './lib/breaks';
import { callCore } from './lib/core-client';
import { courseRoute, RAIL_COURSES } from './lib/courses';
import { useResource } from './lib/use-resource';
import { KIND_FILM } from './lib/films';
import { isDrawingPictures, KIND_LESSON } from './lib/generation';
import { BreakScreen } from './screens/break/BreakScreen';
import { CourseScreen } from './screens/course/CourseScreen';
import { HomeScreen } from './screens/home/HomeScreen';
import { LessonScreen } from './screens/lesson/LessonScreen';
import { PracticeScreen } from './screens/practice/PracticeScreen';
import { SettingsScreen } from './screens/settings/SettingsScreen';
import { WelcomeScreen } from './screens/welcome/WelcomeScreen';

function Screen({ route, visit }: { route: Route; visit: number }) {
  switch (route.name) {
    case 'home':
      return <HomeScreen />;
    case 'course':
      // The key resets the screen's state when moving between courses.
      return <CourseScreen key={route.courseId} courseId={route.courseId} tab={route.tab} />;
    case 'lesson':
      return (
        <LessonScreen key={route.lessonId} courseId={route.courseId} lessonId={route.lessonId} />
      );
    case 'practice':
      // Opening practice again, even on the same concept, asks for a fresh set of questions.
      return (
        <PracticeScreen
          key={visit}
          courseId={route.courseId}
          conceptId={route.conceptId}
          about={route.about}
        />
      );
    case 'break':
      return <BreakScreen />;
    case 'settings':
      return <SettingsScreen tab={route.tab} />;
  }
}

/**
 * What is going on besides the screen in front of the learner: something being written,
 * a break running. In the rail, so that it is one click away from anywhere, and so that
 * "you do not have to wait here" is true.
 */
function RailActivity() {
  const { route, navigate } = useRouter();
  const rest = useBreak();
  const { jobs } = useWriting();
  const films = useFilmWatch();
  const [first] = jobs;
  const [film] = films.jobs;
  if (!rest.times && !first && !film) return null;
  return (
    <NavSection label="Now" keepWhenNarrow>
      {first ? (
        <NavItem
          label={
            jobs.length > 1
              ? `Writing ${jobs.length} things`
              : first.kind === KIND_LESSON
                ? isDrawingPictures(first)
                  ? 'Drawing pictures'
                  : 'Writing a lesson'
                : 'Suggesting concepts'
          }
          icon={<PenLine />}
          disabled={!first.course_id}
          onClick={() => {
            if (!first.course_id) return;
            navigate({
              name: 'course',
              courseId: first.course_id,
              tab: first.kind === KIND_LESSON ? 'learn' : 'curriculum',
            });
          }}
        />
      ) : null}
      {film ? (
        <NavItem
          label={film.kind === KIND_FILM ? 'Making a film' : 'Setting up the film maker'}
          icon={<Clapperboard />}
          disabled={!film.course_id}
          onClick={() => {
            if (!film.course_id) return;
            navigate({ name: 'course', courseId: film.course_id, tab: 'film' });
          }}
        />
      ) : null}
      {rest.times ? (
        <NavItem
          label={rest.over ? 'Break over' : `On a break · ${clockText(rest.left)}`}
          icon={<Coffee />}
          current={route.name === 'break'}
          onClick={() => {
            // From the rail a break is a detour: leaving it leads back to where one was.
            if (route.name !== 'break') rest.returnVia(null);
            navigate({ name: 'break' });
          }}
        />
      ) : null}
    </NavSection>
  );
}

/**
 * The most recent courses, in the rail: one click from anywhere to any of them. Read again
 * on every navigation, which is when the list can have changed (a course was made, opened
 * or removed). While it cannot be read the rail simply has no such group; the library
 * says why.
 */
function RailCourses() {
  const { coreStatus } = useApp();
  const { route, visit, navigate } = useRouter();
  const courses = useResource(`rail-courses:${coreStatus.state}:${visit}`, () =>
    callCore('courses.list'),
  );
  if (courses.resource.status !== 'ready' || courses.resource.data.courses.length === 0) {
    return null;
  }
  return (
    <NavSection label="Courses">
      {courses.resource.data.courses.slice(0, RAIL_COURSES).map((course) => (
        <NavItem
          key={course.id}
          label={course.title}
          icon={<BookOpen />}
          current={route.name === 'course' && route.courseId === course.id}
          onClick={() => navigate(courseRoute(course))}
        />
      ))}
    </NavSection>
  );
}

/** What goes on across screens: what is being written, and a break being taken. */
function Activity({ children }: { children: ReactNode }) {
  return (
    <WritingProvider>
      <FilmWatchProvider>
        <BreakProvider>{children}</BreakProvider>
      </FilmWatchProvider>
      <SceneTrials />
    </WritingProvider>
  );
}

export function App() {
  const { ui } = useApp();
  const { route, visit, navigate } = useRouter();
  // A lesson, a round of questions, and a break are each one thing to attend to: they
  // get the window.
  const focus = route.name === 'lesson' || route.name === 'practice' || route.name === 'break';

  return (
    <ToastProvider>
      <WindowStrip />
      {ui.onboardingCompleted ? (
        <Activity>
          <AppShell
            brand={<Logo />}
            focus={focus}
            navigation={
              <>
                <NavItem
                  label="Library"
                  icon={<Library />}
                  current={route.name === 'home'}
                  onClick={() => navigate({ name: 'home' })}
                />
                <NavItem
                  label="Settings"
                  icon={<Settings />}
                  current={route.name === 'settings'}
                  onClick={() => navigate({ name: 'settings', tab: 'ai' })}
                />
                <RailCourses />
                <RailActivity />
              </>
            }
            footer={<CoreStatusIndicator />}
          >
            <Screen route={route} visit={visit} />
          </AppShell>
        </Activity>
      ) : (
        <WelcomeScreen />
      )}
    </ToastProvider>
  );
}
