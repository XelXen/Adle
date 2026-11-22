import type { Concept, Curriculum, CurriculumIssue, LessonSummary } from '@adle/contracts';

import { pluralise } from '../../lib/format';

/**
 * Pure helpers behind the curriculum screen: what order to show, what may be
 * moved where, and where each concept sits on the map. No React, no I/O.
 */

/** The concepts in the order they will be taught. */
export function learningPath(curriculum: Curriculum): Concept[] {
  const byId = new Map(curriculum.concepts.map((concept) => [concept.id, concept]));
  const ordered = curriculum.learning_order.flatMap((id) => byId.get(id) ?? []);
  // No learning order exists while the graph has a loop; fall back to the stored order.
  return ordered.length === curriculum.concepts.length ? ordered : curriculum.concepts;
}

export type MoveDirection = 'earlier' | 'later';

export interface MoveCheck {
  allowed: boolean;
  /** Why not, in words for the learner. Present only when the move is refused. */
  reason?: string;
}

/**
 * Whether a concept can swap places with its neighbour in the path.
 *
 * Neighbours in a valid path can only be tied by a direct prerequisite link (an
 * indirect one would put a third concept between them), so one lookup decides.
 */
export function checkMove(
  path: readonly Concept[],
  id: string,
  direction: MoveDirection,
): MoveCheck {
  const index = path.findIndex((concept) => concept.id === id);
  const concept = path[index];
  if (!concept) return { allowed: false };
  const neighbour = path[direction === 'earlier' ? index - 1 : index + 1];
  if (!neighbour) return { allowed: false };

  if (direction === 'earlier' && needs(concept, neighbour)) {
    return { allowed: false, reason: `Needs “${neighbour.title}” first.` };
  }
  if (direction === 'later' && needs(neighbour, concept)) {
    return { allowed: false, reason: `“${neighbour.title}” depends on this.` };
  }
  return { allowed: true };
}

function needs(concept: Concept, other: Concept): boolean {
  return concept.prerequisites.some((prerequisite) => prerequisite.concept_id === other.id);
}

/** The whole path, as ids, after swapping a concept with its neighbour. */
export function movedOrder(
  path: readonly Concept[],
  id: string,
  direction: MoveDirection,
): string[] {
  const ids = path.map((concept) => concept.id);
  const index = ids.indexOf(id);
  const target = direction === 'earlier' ? index - 1 : index + 1;
  const moved = ids[index];
  const displaced = ids[target];
  if (moved === undefined || displaced === undefined) return ids;
  ids[index] = displaced;
  ids[target] = moved;
  return ids;
}

/** Every concept that needs `id`, directly or through others. */
export function dependentsOf(concepts: readonly Concept[], id: string): Set<string> {
  const direct = new Map<string, string[]>();
  for (const concept of concepts) {
    for (const prerequisite of concept.prerequisites) {
      direct.set(prerequisite.concept_id, [
        ...(direct.get(prerequisite.concept_id) ?? []),
        concept.id,
      ]);
    }
  }
  const found = new Set<string>();
  const queue = [...(direct.get(id) ?? [])];
  while (queue.length > 0) {
    const current = queue.shift();
    if (current === undefined || current === id || found.has(current)) continue;
    found.add(current);
    queue.push(...(direct.get(current) ?? []));
  }
  return found;
}

/** Concepts that list `id` as a direct prerequisite, in path order. */
export function directDependents(path: readonly Concept[], id: string): Concept[] {
  return path.filter((concept) =>
    concept.prerequisites.some((prerequisite) => prerequisite.concept_id === id),
  );
}

export interface MapNode {
  id: string;
  title: string;
  x: number;
  y: number;
}

export interface MapEdge {
  /** The prerequisite. */
  from: string;
  /** The concept that needs it. */
  to: string;
  /** SVG path data from the bottom of `from` to the top of `to`. */
  d: string;
}

export interface MapLayout {
  nodes: MapNode[];
  edges: MapEdge[];
  width: number;
  height: number;
}

export const MAP_NODE = {
  width: 160,
  height: 56,
  gapX: 20,
  /** Between a concept and what it unlocks. */
  gapY: 48,
  /** Between lines of concepts at the same depth. */
  lineGap: 16,
  padding: 16,
  /** A longer row wraps, so the map never grows wider than the page. */
  maxColumns: 4,
} as const;

/**
 * Place concepts in rows: a concept sits below its deepest prerequisite.
 * Concepts at the same depth keep their order in the path and wrap onto
 * further lines when there are many. Lines are centred.
 */
export function layoutMap(curriculum: Curriculum): MapLayout {
  const path = learningPath(curriculum);
  const byDepth = new Map<number, Concept[]>();
  for (const concept of path) {
    const depth = concept.layer ?? 0;
    byDepth.set(depth, [...(byDepth.get(depth) ?? []), concept]);
  }
  const depths = [...byDepth.keys()].sort((a, b) => a - b);
  const { width: w, height: h, gapX, gapY, lineGap, padding, maxColumns } = MAP_NODE;
  const widest = Math.min(
    maxColumns,
    Math.max(1, ...[...byDepth.values()].map((row) => row.length)),
  );
  const innerWidth = widest * w + (widest - 1) * gapX;

  // Concepts that unlock something go on the line nearest to what they unlock, and a
  // short line goes first, so links rarely have to pass behind an unrelated concept.
  const unlocksSomething = new Set(
    path.flatMap((concept) => concept.prerequisites.map((item) => item.concept_id)),
  );

  const nodes: MapNode[] = [];
  const position = new Map<string, MapNode>();
  let y = padding;
  depths.forEach((depth, depthIndex) => {
    const atDepth = byDepth.get(depth) ?? [];
    const concepts = [
      ...atDepth.filter((concept) => !unlocksSomething.has(concept.id)),
      ...atDepth.filter((concept) => unlocksSomething.has(concept.id)),
    ];
    if (depthIndex > 0) y += gapY;
    const firstLineLength = concepts.length % maxColumns || maxColumns;
    for (
      let first = 0;
      first < concepts.length;
      first += first === 0 ? firstLineLength : maxColumns
    ) {
      const line = concepts.slice(first, first + (first === 0 ? firstLineLength : maxColumns));
      if (first > 0) y += lineGap;
      const lineWidth = line.length * w + (line.length - 1) * gapX;
      const startX = padding + (innerWidth - lineWidth) / 2;
      const lineY = y;
      line.forEach((concept, column) => {
        const node: MapNode = {
          id: concept.id,
          title: concept.title,
          x: startX + column * (w + gapX),
          y: lineY,
        };
        nodes.push(node);
        position.set(concept.id, node);
      });
      y += h;
    }
  });

  const edges: MapEdge[] = [];
  for (const concept of path) {
    const to = position.get(concept.id);
    if (!to) continue;
    for (const prerequisite of concept.prerequisites) {
      const from = position.get(prerequisite.concept_id);
      if (!from) continue;
      const startX = from.x + w / 2;
      const startY = from.y + h;
      const endX = to.x + w / 2;
      const endY = to.y;
      const bend = Math.max(gapY / 2, (endY - startY) / 2);
      edges.push({
        from: from.id,
        to: to.id,
        d: `M ${startX} ${startY} C ${startX} ${startY + bend}, ${endX} ${endY - bend}, ${endX} ${endY}`,
      });
    }
  }

  return { nodes, edges, width: innerWidth + padding * 2, height: y + padding };
}

/** "page 3", a heading path, or the file as a whole. */
export function describeLocation(place: {
  page_number: number | null;
  section_title: string | null;
}): string {
  if (place.page_number !== null) return `page ${place.page_number}`;
  return place.section_title ?? 'whole document';
}

const NAMES_SHOWN = 3;

/** "A, B, C and 2 more". */
function listNames(names: readonly string[]): string {
  const shown = names.slice(0, NAMES_SHOWN).join(', ');
  const hidden = names.length - NAMES_SHOWN;
  return hidden > 0 ? `${shown} and ${hidden} more` : shown;
}

/** Advice that tends to apply to many concepts at once is said once, with the names. */
const GROUPED: Record<string, (count: number, names: string) => string> = {
  no_objective: (count, names) =>
    `${count} concepts have no learning objective yet: ${names}. Add one to each.`,
  no_source_reference: (count, names) =>
    `${count} concepts aren’t linked to anything in your materials: ${names}.`,
};

/** The messages to show for a set of issues: one line per problem, repeats folded together. */
export function summariseIssues(
  issues: readonly CurriculumIssue[],
  concepts: readonly Concept[],
): string[] {
  const titles = new Map(concepts.map((concept) => [concept.id, concept.title]));
  const messages: string[] = [];
  const groups = new Map<string, CurriculumIssue[]>();
  for (const issue of issues) {
    if (issue.code in GROUPED) groups.set(issue.code, [...(groups.get(issue.code) ?? []), issue]);
    else messages.push(issue.message);
  }
  for (const [code, group] of groups) {
    const describe = GROUPED[code];
    const only = group[0];
    if (group.length === 1 && only) messages.push(only.message);
    else if (describe) {
      const names = group.flatMap((issue) =>
        issue.concept_ids.flatMap((id) => titles.get(id) ?? []),
      );
      messages.push(describe(group.length, listNames(names)));
    }
  }
  return messages;
}

/** The lessons of a course, grouped by the concept each one teaches. */
export function lessonsByConcept(lessons: readonly LessonSummary[]): Map<string, LessonSummary[]> {
  const grouped = new Map<string, LessonSummary[]>();
  for (const lesson of lessons) {
    grouped.set(lesson.concept_id, [...(grouped.get(lesson.concept_id) ?? []), lesson]);
  }
  return grouped;
}

/** What opening a lesson will do, in the words on its button. */
export function lessonAction(progress: LessonSummary['progress']): string {
  if (progress.completed) return 'Replay lesson';
  return progress.started ? 'Continue' : 'Start lesson';
}

/** One line about a lesson: how long it takes and how far the learner has got. */
export function describeLesson(lesson: LessonSummary): string {
  const { progress, segment_count: parts } = lesson;
  // A lesson can be started while the rest of it is still being written (ADR-048): how
  // long it is, and how many parts it has, are not known yet.
  const writing = lesson.writing ?? false;
  const place = progress.completed
    ? 'Completed'
    : progress.started
      ? `Part ${Math.min(progress.position + 1, parts)} of ${parts}${writing ? ' so far' : ''}`
      : 'Not started';
  // A lesson can be started while its pictures are still being drawn (ADR-031).
  const pictures = (lesson.pictures_pending ?? 0) > 0 ? ' · Pictures on their way' : '';
  const length = writing
    ? 'Still being written'
    : `About ${pluralise(lesson.estimated_minutes, 'minute')}`;
  return `${length} · ${place}${pictures}`;
}
