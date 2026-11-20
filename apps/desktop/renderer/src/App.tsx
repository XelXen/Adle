import { Library, Settings } from 'lucide-react';

import { AppShell, Logo, NavItem, ToastProvider } from '@adle/design-system';

import { useApp } from './app/AppContext';
import { type Route, useRouter } from './app/router';
import { CoreStatusIndicator } from './components/CoreStatusIndicator';
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

export function App() {
  const { ui } = useApp();
  const { route, visit, navigate } = useRouter();

  return (
    <ToastProvider>
      {ui.onboardingCompleted ? (
        <AppShell
          brand={<Logo />}
          navigation={
            <>
              <NavItem
                label="Library"
                icon={<Library />}
                current={route.name !== 'settings'}
                onClick={() => navigate({ name: 'home' })}
              />
              <NavItem
                label="Settings"
                icon={<Settings />}
                current={route.name === 'settings'}
                onClick={() => navigate({ name: 'settings', tab: 'ai' })}
              />
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
