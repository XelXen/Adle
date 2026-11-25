import { describe, expect, it } from 'vitest';

import { ALL, coreTestsFor, journeysFor } from './affected.mjs';

describe('the journeys a change needs (ADR-059)', () => {
  it('needs none for words, decisions and unit tests', () => {
    expect(
      journeysFor([
        'CHANGELOG.md',
        'docs/decisions/ADR-058-an-axis-is-a-line-and-a-label-looks-again-when-moved.md',
        'services/core/tests/unit/test_ingestion.py',
        'apps/desktop/renderer/src/screens/lesson/LessonScreen.test.tsx',
        'scripts/affected.mjs',
      ]),
    ).toEqual([]);
  });

  it('runs the slides alone for a change to how a slide is written', () => {
    expect(
      journeysFor([
        'services/core/adle_core/generation/slides.py',
        'apps/desktop/e2e/fixtures/slides/tangent.py',
      ]),
    ).toEqual(['generation.spec.ts', 'slide-player.spec.ts']);
  });

  it('runs the slides and the figures for a change to how words are kept clear', () => {
    expect(journeysFor(['services/core/adle_core/generation/layout.py'])).toEqual([
      'scene-player.spec.ts',
      'slide-player.spec.ts',
    ]);
  });

  it('runs the journeys about lessons and courses for a change to how a lesson is formed', () => {
    expect(journeysFor(['services/core/adle_core/lessons/axioms.py'])).toEqual([
      'curriculum.spec.ts',
      'generation.spec.ts',
    ]);
    // The example each subject's writer is shown is a slide the player steps through.
    expect(journeysFor(['services/core/adle_core/generation/examples.py'])).toEqual([
      'generation.spec.ts',
      'slide-player.spec.ts',
    ]);
    expect(journeysFor(['apps/desktop/renderer/src/lib/lesson-rules.ts'])).toEqual([
      'curriculum.spec.ts',
      'generation.spec.ts',
      'learning.spec.ts',
      'lesson.spec.ts',
    ]);
  });

  it('runs the journeys about materials for a change to how a file is read', () => {
    expect(journeysFor(['services/core/adle_core/ingestion/parsers.py'])).toEqual([
      'course-materials.spec.ts',
      'curriculum.spec.ts',
    ]);
  });

  it('runs the film’s journey for a change to the film, its stand-ins, or its chapter', () => {
    expect(
      journeysFor([
        'services/core/adle_core/film/policy.py',
        'services/core/adle_core/application/films.py',
        'apps/desktop/renderer/src/screens/course/FilmPanel.tsx',
        'apps/desktop/electron/main/film-files.ts',
      ]),
    ).toEqual(['film.spec.ts', 'security.spec.ts']);
    expect(
      journeysFor([
        'services/core/tests/support/fake_film_engine.py',
        'fixtures/model-answers/film-chapter.py',
      ]),
    ).toEqual(['film.spec.ts']);
    // The voice's stand-in runs in its journey; the core's own fake provider does not.
    expect(journeysFor(['services/core/tests/support/fake_voice_engine.py'])).toEqual([
      'voice.spec.ts',
    ]);
    expect(journeysFor(['services/core/tests/support/model.py'])).toEqual([]);
  });

  it('runs a journey that was changed, and nothing else for it', () => {
    expect(journeysFor(['apps/desktop/e2e/voice.spec.ts'])).toEqual(['voice.spec.ts']);
  });

  it('runs every journey for what it does not know, or what everything stands on', () => {
    for (const file of [
      'apps/desktop/electron/main/index.ts',
      'packages/design-system/src/Button.tsx',
      'services/core/adle_core/api/app.py',
      'services/core/adle_core/infrastructure/database.py',
      'package-lock.json',
      'apps/desktop/e2e/support/app.ts',
      'a/file/nobody/expected.txt',
    ]) {
      expect(journeysFor(['CHANGELOG.md', file]), file).toBe(ALL);
    }
  });

  it('reads a Windows path as a path', () => {
    expect(journeysFor(['apps\\desktop\\e2e\\fixtures\\figures\\graph.py'])).toEqual([
      'scene-player.spec.ts',
    ]);
  });
});

describe("the core's tests a change needs", () => {
  it('needs none when the core is not touched', () => {
    expect(coreTestsFor(['apps/desktop/renderer/src/App.tsx', 'services/core/AGENTS.md'])).toBe(
      'none',
    );
  });

  it('follows the code each test ran when only code changed', () => {
    expect(
      coreTestsFor([
        'services/core/adle_core/ingestion/parsers.py',
        'services/core/tests/unit/test_ingestion.py',
      ]),
    ).toBe('code');
  });

  it('runs them all for what the code each test ran cannot show', () => {
    for (const file of [
      'services/core/adle_core/sample_course/course.json',
      'services/core/pyproject.toml',
      'services/core/uv.lock',
      'services/core/tests/support/fake_voice_engine.py',
      'services/core/tests/conftest.py',
    ]) {
      expect(coreTestsFor([file]), file).toBe('all');
    }
  });
});
