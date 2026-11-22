import { describe, expect, it } from 'vitest';

import type { Concept, Curriculum, LessonSummary } from '@adle/contracts';

import {
  checkMove,
  dependentsOf,
  describeLesson,
  describeLocation,
  directDependents,
  layoutMap,
  learningPath,
  lessonAction,
  lessonsByConcept,
  MAP_NODE,
  movedOrder,
  summariseIssues,
} from './curriculum-model';

function concept(id: string, layer: number | null, ...needs: string[]): Concept {
  return {
    id,
    course_id: 'crs_1',
    title: id.toUpperCase(),
    summary: '',
    position: 0,
    complexity: 2,
    tags: [],
    origin: 'learner',
    objectives: [],
    prerequisites: needs.map((needed) => ({
      concept_id: needed,
      title: needed.toUpperCase(),
      reason: '',
    })),
    source_refs: [],
    layer,
    knowledge: {
      state: 'not_assessed',
      label: 'Not started',
      missing: [],
      answered: 0,
      self_report: null,
      review_due_at: null,
    },
  };
}

function curriculum(concepts: Concept[], order: string[]): Curriculum {
  return { course_id: 'crs_1', concepts, learning_order: order, issues: [], startable: true };
}

// weights and activation feed perceptron, which feeds forward; chain stands alone.
const COURSE = curriculum(
  [
    concept('forward', 2, 'perceptron'),
    concept('weights', 0),
    concept('chain', 0),
    concept('perceptron', 1, 'weights', 'activation'),
    concept('activation', 0),
  ],
  ['weights', 'chain', 'activation', 'perceptron', 'forward'],
);
const PATH = learningPath(COURSE);

describe('learningPath', () => {
  it('shows concepts in the order they will be taught', () => {
    expect(PATH.map((item) => item.id)).toEqual([
      'weights',
      'chain',
      'activation',
      'perceptron',
      'forward',
    ]);
  });

  it('falls back to the stored order while no learning order exists', () => {
    const looped = curriculum([concept('a', null, 'b'), concept('b', null, 'a')], []);
    expect(learningPath(looped).map((item) => item.id)).toEqual(['a', 'b']);
  });
});

describe('moving a concept along the path', () => {
  it('allows a swap with an unrelated neighbour', () => {
    expect(checkMove(PATH, 'chain', 'earlier')).toEqual({ allowed: true });
    expect(checkMove(PATH, 'chain', 'later')).toEqual({ allowed: true });
    expect(movedOrder(PATH, 'chain', 'earlier')).toEqual([
      'chain',
      'weights',
      'activation',
      'perceptron',
      'forward',
    ]);
    expect(movedOrder(PATH, 'chain', 'later')).toEqual([
      'weights',
      'activation',
      'chain',
      'perceptron',
      'forward',
    ]);
  });

  it('refuses to move a concept before something it needs, and says why', () => {
    expect(checkMove(PATH, 'perceptron', 'earlier')).toEqual({
      allowed: false,
      reason: 'Needs “ACTIVATION” first.',
    });
    expect(checkMove(PATH, 'activation', 'later')).toEqual({
      allowed: false,
      reason: '“PERCEPTRON” depends on this.',
    });
  });

  it('has nowhere to go at either end of the path', () => {
    expect(checkMove(PATH, 'weights', 'earlier')).toEqual({ allowed: false });
    expect(checkMove(PATH, 'forward', 'later')).toEqual({ allowed: false });
    expect(checkMove(PATH, 'not-a-concept', 'later')).toEqual({ allowed: false });
    expect(movedOrder(PATH, 'weights', 'earlier')).toEqual(PATH.map((item) => item.id));
  });
});

describe('dependents', () => {
  it('finds everything that builds on a concept, however indirectly', () => {
    expect([...dependentsOf(COURSE.concepts, 'weights')].sort()).toEqual(['forward', 'perceptron']);
    expect([...dependentsOf(COURSE.concepts, 'forward')]).toEqual([]);
    expect(directDependents(PATH, 'weights').map((item) => item.id)).toEqual(['perceptron']);
  });

  it('terminates on a loop', () => {
    const looped = [concept('a', null, 'b'), concept('b', null, 'a')];
    expect([...dependentsOf(looped, 'a')]).toEqual(['b']);
  });
});

describe('layoutMap', () => {
  const layout = layoutMap(COURSE);
  const node = (id: string) => layout.nodes.find((item) => item.id === id)!;

  it('puts each concept in the row below everything it needs', () => {
    expect(node('weights').y).toBe(node('chain').y);
    expect(node('perceptron').y).toBeGreaterThan(node('weights').y);
    expect(node('forward').y).toBeGreaterThan(node('perceptron').y);
    // Three rows, three concepts in the widest.
    expect(layout.height).toBe(3 * MAP_NODE.height + 2 * MAP_NODE.gapY + 2 * MAP_NODE.padding);
    expect(layout.width).toBe(3 * MAP_NODE.width + 2 * MAP_NODE.gapX + 2 * MAP_NODE.padding);
  });

  it('keeps the path order among concepts that unlock something, and never overlaps two', () => {
    // "chain" unlocks nothing, so it steps aside; the other two keep their order.
    expect(node('chain').x).toBeLessThan(node('weights').x);
    expect(node('weights').x).toBeLessThan(node('activation').x);
    for (const a of layout.nodes) {
      for (const b of layout.nodes) {
        if (a.id === b.id || a.y !== b.y) continue;
        expect(Math.abs(a.x - b.x)).toBeGreaterThanOrEqual(MAP_NODE.width + MAP_NODE.gapX);
      }
    }
  });

  it('draws one link per prerequisite, from the prerequisite down to the concept', () => {
    expect(layout.edges.map((edge) => `${edge.from}>${edge.to}`).sort()).toEqual([
      'activation>perceptron',
      'perceptron>forward',
      'weights>perceptron',
    ]);
    const edge = layout.edges.find((item) => item.from === 'perceptron')!;
    const start = node('perceptron');
    expect(
      edge.d.startsWith(`M ${start.x + MAP_NODE.width / 2} ${start.y + MAP_NODE.height} `),
    ).toBe(true);
  });

  it('wraps a long row onto further lines instead of growing sideways', () => {
    const roots = Array.from({ length: 6 }, (_, index) => concept(`r${index}`, 0));
    const wide = layoutMap(
      curriculum([...roots, concept('after', 1, 'r0')], [...roots.map((item) => item.id), 'after']),
    );
    const at = (id: string) => wide.nodes.find((item) => item.id === id)!;
    // The short line comes first: two, then four, then the concept that needs one of them.
    expect(at('r2').y).toBe(at('r1').y);
    expect(at('r3').y).toBe(at('r1').y + MAP_NODE.height + MAP_NODE.lineGap);
    expect(new Set(['r3', 'r4', 'r5', 'r0'].map((id) => at(id).y)).size).toBe(1);
    // What unlocks something sits on the line right above it, so the link crosses nothing.
    expect(at('after').y).toBe(at('r0').y + MAP_NODE.height + MAP_NODE.gapY);
    expect(wide.width).toBe(
      MAP_NODE.maxColumns * MAP_NODE.width +
        (MAP_NODE.maxColumns - 1) * MAP_NODE.gapX +
        2 * MAP_NODE.padding,
    );
    expect(wide.height).toBe(at('after').y + MAP_NODE.height + MAP_NODE.padding);
    for (const a of wide.nodes) {
      for (const b of wide.nodes) {
        if (a.id === b.id) continue;
        const apart =
          Math.abs(a.x - b.x) >= MAP_NODE.width || Math.abs(a.y - b.y) >= MAP_NODE.height;
        expect(apart).toBe(true);
      }
    }
  });

  it('handles an empty course', () => {
    expect(layoutMap(curriculum([], []))).toMatchObject({ nodes: [], edges: [] });
  });
});

describe('describeLocation', () => {
  it('prefers the page, then the heading, then the whole file', () => {
    expect(describeLocation({ page_number: 3, section_title: 'Loss' })).toBe('page 3');
    expect(describeLocation({ page_number: null, section_title: 'Unit 4 › Loss' })).toBe(
      'Unit 4 › Loss',
    );
    expect(describeLocation({ page_number: null, section_title: null })).toBe('whole document');
  });
});

describe('summariseIssues', () => {
  const issue = (code: string, id: string, severity: 'error' | 'warning' = 'warning') => ({
    code,
    severity,
    concept_ids: [id],
    message: `${code} for ${id}`,
  });

  it('says a repeated piece of advice once, naming the concepts', () => {
    const messages = summariseIssues(
      [
        issue('no_objective', 'weights'),
        issue('no_objective', 'chain'),
        issue('no_objective', 'perceptron'),
        issue('no_objective', 'activation'),
        issue('no_objective', 'forward'),
        issue('no_source_reference', 'weights'),
        issue('no_source_reference', 'chain'),
      ],
      COURSE.concepts,
    );
    expect(messages).toEqual([
      '5 concepts have no learning objective yet: WEIGHTS, CHAIN, PERCEPTRON and 2 more. Add one to each.',
      '2 concepts aren’t linked to anything in your materials: WEIGHTS, CHAIN.',
    ]);
  });

  it('keeps a single issue, and anything it does not know how to group, word for word', () => {
    expect(
      summariseIssues(
        [
          issue('cycle', 'weights', 'error'),
          issue('cycle', 'chain', 'error'),
          issue('no_objective', 'forward'),
        ],
        COURSE.concepts,
      ),
    ).toEqual(['cycle for weights', 'cycle for chain', 'no_objective for forward']);
    expect(summariseIssues([], COURSE.concepts)).toEqual([]);
  });
});

describe('lessons of a concept', () => {
  const lesson = (
    id: string,
    conceptId: string,
    progress: Partial<LessonSummary['progress']> = {},
  ): LessonSummary => ({
    id,
    course_id: 'crs_1',
    concept_id: conceptId,
    title: `Lesson ${id}`,
    origin: 'sample',
    estimated_minutes: 8,
    segment_count: 10,
    progress: { started: false, position: 0, completed: false, ...progress },
  });

  it('groups lessons by the concept they teach, keeping their order', () => {
    const grouped = lessonsByConcept([
      lesson('a', 'weights'),
      lesson('b', 'chain'),
      lesson('c', 'weights'),
    ]);
    expect(grouped.get('weights')?.map((item) => item.id)).toEqual(['a', 'c']);
    expect(grouped.get('chain')?.map((item) => item.id)).toEqual(['b']);
    expect(grouped.get('forward')).toBeUndefined();
  });

  it('names the button after what opening the lesson will do', () => {
    expect(lessonAction(lesson('a', 'weights').progress)).toBe('Start lesson');
    expect(lessonAction(lesson('a', 'weights', { started: true, position: 3 }).progress)).toBe(
      'Continue',
    );
    expect(
      lessonAction(
        lesson('a', 'weights', { started: true, position: 9, completed: true }).progress,
      ),
    ).toBe('Replay lesson');
  });

  it('says how long a lesson takes and how far the learner has got', () => {
    expect(describeLesson(lesson('a', 'weights'))).toBe('About 8 minutes · Not started');
    expect(describeLesson(lesson('a', 'weights', { started: true, position: 3 }))).toBe(
      'About 8 minutes · Part 4 of 10',
    );
    // A position past the end (a lesson that was shortened) never reads "Part 12 of 10".
    expect(describeLesson(lesson('a', 'weights', { started: true, position: 11 }))).toBe(
      'About 8 minutes · Part 10 of 10',
    );
    expect(
      describeLesson({
        ...lesson('a', 'weights', { started: true, position: 9, completed: true }),
        estimated_minutes: 1,
      }),
    ).toBe('About 1 minute · Completed');
  });

  it('says so while a lesson’s pictures are still being drawn', () => {
    expect(describeLesson({ ...lesson('a', 'weights'), pictures_pending: 2 })).toBe(
      'About 8 minutes · Not started · Pictures on their way',
    );
    expect(describeLesson({ ...lesson('a', 'weights'), pictures_pending: 0 })).toBe(
      'About 8 minutes · Not started',
    );
  });

  it('says so while the rest of a lesson is still being written, and not how long it is', () => {
    expect(describeLesson({ ...lesson('a', 'weights'), writing: true })).toBe(
      'Still being written · Not started',
    );
    expect(
      describeLesson({
        ...lesson('a', 'weights', { started: true, position: 1 }),
        segment_count: 2,
        writing: true,
        pictures_pending: 1,
      }),
    ).toBe('Still being written · Part 2 of 2 so far · Pictures on their way');
  });
});
