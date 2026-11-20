import type { Course } from '@adle/contracts';

import type { Route } from '../app/router';

/**
 * Where opening a course leads. One with something to learn opens on what to do next. One
 * that is still being set up opens where the setting up happens: its materials if it is
 * waiting for them, else its curriculum.
 */
export function courseRoute(course: Course): Route {
  return {
    name: 'course',
    courseId: course.id,
    tab:
      course.concept_count > 0
        ? 'learn'
        : course.origin === 'materials' && course.source_count === 0
          ? 'sources'
          : 'curriculum',
  };
}

/** How many courses the rail lists. The library has them all. */
export const RAIL_COURSES = 6;
