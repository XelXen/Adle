import { BookOpen, Library, Settings } from 'lucide-react';

import { AppShell, Logo, NavItem, NavSection, ToastProvider } from '@adle/design-system';

import { useApp } from './app/AppContext';
import { type Route, useRouter } from './app/router';
import { CoreStatusIndicator } from './components/CoreStatusIndicator';
import { callCore } from './lib/core-client';
import { courseRoute, RAIL_COURSES } from './lib/courses';
import { useResource } from './lib/use-resource';
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
    case 'settings':
      return <SettingsScreen tab={route.tab} />;
  }
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

export function App() {
  const { ui } = useApp();
  const { route, visit, navigate } = useRouter();
  // A lesson, and a round of questions, are one thing to attend to: they get the window.
  const focus = route.name === 'lesson' || route.name === 'practice';

  return (
    <ToastProvider>
      {ui.onboardingCompleted ? (
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
            </>
          }
          footer={<CoreStatusIndicator />}
        >
          <Screen route={route} visit={visit} />
        </AppShell>
      ) : (
        <WelcomeScreen />
      )}
    </ToastProvider>
  );
}
