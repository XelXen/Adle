#!/usr/bin/env node
/**
 * What a change needs checked (ADR-059): the files it touches, read against the parts of
 * the app each end-to-end journey goes through.
 *
 *   node scripts/affected.mjs            # the journeys for what is not yet on origin/main
 *
 * `scripts/check.mjs` runs, by default, only what a change can affect: the unit tests
 * related to the files changed (vitest), the core's tests whose code changed since they
 * last ran (pytest-testmon), and, with --e2e, the journeys this file picks. With --all,
 * and on GitHub for every push, everything runs.
 *
 * A file the table does not know runs every journey: a rule left out costs time, never a
 * check.
 */
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const ALL = 'all';

const SCENE = 'scene-player.spec.ts';
const SLIDE = 'slide-player.spec.ts';
/** What the AI writes, and who is asked: a lesson, a plan, a question, a key. */
const AI = [
  'generation.spec.ts',
  'providers.spec.ts',
  'provider-key.spec.ts',
  'ask.spec.ts',
  'break.spec.ts',
  'curriculum.spec.ts',
];
/** The scene frame and what talks to it. */
const PLAYER = [SCENE, SLIDE, 'lesson.spec.ts', 'security.spec.ts', 'generation.spec.ts'];
const CURRICULUM = ['curriculum.spec.ts', 'learning.spec.ts', 'generation.spec.ts'];
const LEARNING = ['learning.spec.ts', 'lesson.spec.ts', 'ask.spec.ts'];
const LESSONS = ['lesson.spec.ts', 'ask.spec.ts', 'generation.spec.ts', 'learning.spec.ts'];
const MATERIALS = ['course-materials.spec.ts', 'curriculum.spec.ts'];
const CORE = 'services/core/adle_core/';

/** Nothing a journey covers: words, decisions, tooling, and the unit tests themselves. */
const NO_JOURNEY = [
  /\.md$/,
  /^docs\//,
  /^LICENSE$/,
  /^\.github\//,
  /^\.gitignore$/,
  /^scripts\//,
  /^services\/core\/tests\//,
  /\.test\.(ts|tsx|mjs)$/,
];

/** A path pattern and the journeys that cover what lies there; the first that matches. */
const RULES = [
  [/^apps\/desktop\/e2e\/([a-z0-9-]+\.spec\.ts)$/, (match) => [match[1]]],
  [/^apps\/desktop\/e2e\/fixtures\/slides\//, [SLIDE]],
  [/^apps\/desktop\/e2e\/fixtures\/figures\//, [SCENE]],
  [/^skills\/wanim-scene-authoring\/examples\//, [SCENE]],
  [new RegExp(`^${CORE}generation/layout\\.py$`), [SLIDE, SCENE]],
  [new RegExp(`^${CORE}generation/slides\\.py$`), [SLIDE, 'generation.spec.ts']],
  [new RegExp(`^${CORE}generation/figures\\.py$`), [SCENE, 'generation.spec.ts']],
  [new RegExp(`^${CORE}generation/examples\\.py$`), [SLIDE, 'generation.spec.ts']],
  [new RegExp(`^${CORE}generation/(scene_policy\\.py|data/)`), PLAYER],
  [new RegExp(`^${CORE}generation/`), AI],
  [new RegExp(`^${CORE}application/(generation|model_gateway|asks|scene_trials)\\.py$`), AI],
  [new RegExp(`^${CORE}(voice/|application/narration\\.py$)`), ['voice.spec.ts']],
  [new RegExp(`^${CORE}(ingestion/|application/sources\\.py$)`), MATERIALS],
  [new RegExp(`^${CORE}(curriculum/|application/curriculum\\.py$)`), CURRICULUM],
  [
    new RegExp(
      `^${CORE}(learner_model/|evaluation/|application/(learning|learner|assessment|evidence|retrieval)\\.py$)`,
    ),
    LEARNING,
  ],
  // How a lesson is formed, and a course's subject (ADR-061).
  [new RegExp(`^${CORE}lessons/axioms\\.py$`), ['generation.spec.ts', 'curriculum.spec.ts']],
  [new RegExp(`^${CORE}application/courses\\.py$`), [...MATERIALS, ...CURRICULUM]],
  [new RegExp(`^${CORE}(lessons/|application/lessons\\.py$)`), LESSONS],
  [new RegExp(`^${CORE}sample_course/`), [...LESSONS, SCENE]],
  [/^apps\/desktop\/player\//, PLAYER],
  [/^packages\/event-protocol\//, PLAYER],
  [
    /^apps\/desktop\/renderer\/src\/(screens\/lesson|lesson)\//,
    [
      'lesson.spec.ts',
      'ask.spec.ts',
      'narration.spec.ts',
      'voice.spec.ts',
      'generation.spec.ts',
      'break.spec.ts',
    ],
  ],
  [/^apps\/desktop\/renderer\/src\/screens\/course\//, [...MATERIALS, ...CURRICULUM]],
  [/^apps\/desktop\/renderer\/src\/lib\/lesson-rules\.ts$/, [...CURRICULUM, 'lesson.spec.ts']],
  [/^apps\/desktop\/renderer\/src\/screens\/practice\//, ['learning.spec.ts']],
  [
    /^apps\/desktop\/renderer\/src\/screens\/settings\//,
    [
      'provider-key.spec.ts',
      'providers.spec.ts',
      'learning-preferences.spec.ts',
      'voice.spec.ts',
      'first-run.spec.ts',
      'appearance-a11y.spec.ts',
      'data.spec.ts',
    ],
  ],
  [
    /^apps\/desktop\/renderer\/src\/screens\/(home|welcome)\//,
    ['first-run.spec.ts', 'course-materials.spec.ts', 'appearance-a11y.spec.ts'],
  ],
  [/^apps\/desktop\/renderer\/src\/screens\/break\//, ['break.spec.ts']],
];

/**
 * The journeys a set of changed files needs: `ALL`, or the names of spec files (sorted,
 * none twice), or none at all.
 */
export function journeysFor(files) {
  const picked = new Set();
  for (const file of files) {
    const posix = file.replaceAll('\\', '/');
    if (NO_JOURNEY.some((pattern) => pattern.test(posix))) continue;
    const rule = RULES.find(([pattern]) => pattern.test(posix));
    if (!rule) return ALL;
    const [pattern, journeys] = rule;
    const named = typeof journeys === 'function' ? journeys(posix.match(pattern)) : journeys;
    for (const journey of named) picked.add(journey);
  }
  return [...picked].sort();
}

/**
 * Whether the core's tests are touched, and how: `none`; `code`, which pytest-testmon can
 * follow from the code each test ran; or `all`, for what it cannot follow (the data the
 * core carries, its dependencies, the helpers of its tests, run as separate programs).
 */
export function coreTestsFor(files) {
  let touched = 'none';
  for (const file of files) {
    const posix = file.replaceAll('\\', '/');
    if (!posix.startsWith('services/core/')) continue;
    if (/\.md$/.test(posix)) continue;
    const followed =
      posix.endsWith('.py') &&
      !posix.startsWith('services/core/tests/support/') &&
      !posix.endsWith('/conftest.py');
    if (!followed) return 'all';
    touched = 'code';
  }
  return touched;
}

function git(args, cwd) {
  const result = spawnSync('git', args, { cwd, encoding: 'utf8' });
  return result.status === 0 ? result.stdout.trim() : null;
}

/**
 * The files that differ from where this branch left origin/main: committed and not pushed,
 * staged, changed, and new. `null` when that cannot be told, which means: check everything.
 */
export function changedFiles(repoRoot) {
  const base = git(['merge-base', 'HEAD', 'origin/main'], repoRoot);
  if (!base) return null;
  const changed = git(['diff', '--name-only', base], repoRoot);
  const untracked = git(['ls-files', '--others', '--exclude-standard'], repoRoot);
  if (changed === null || untracked === null) return null;
  const files = [...changed.split('\n'), ...untracked.split('\n')].filter(Boolean);
  return { base, files: [...new Set(files)].sort() };
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
  const change = changedFiles(repoRoot);
  if (!change) {
    console.log('Cannot tell what changed: every journey.');
  } else {
    const journeys = journeysFor(change.files);
    console.log(
      journeys === ALL
        ? 'Every journey.'
        : journeys.length === 0
          ? 'No journey.'
          : journeys.join('\n'),
    );
  }
}
