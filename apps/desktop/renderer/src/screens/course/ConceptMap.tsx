import { useId, useMemo } from 'react';

import type { Curriculum } from '@adle/contracts';
import { cx } from '@adle/design-system';

import styles from './Curriculum.module.css';
import { layoutMap, MAP_NODE } from './curriculum-model';

/**
 * The curriculum as a picture: each concept below what it needs, joined by
 * arrows. The same information is in the list view; this is the overview.
 *
 * Concepts are real buttons laid over a decorative drawing of the links, so
 * they are reachable by keyboard and named for assistive technology.
 */
export function ConceptMap({
  curriculum,
  selectedId,
  onSelect,
}: {
  curriculum: Curriculum;
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const markerId = useId();
  const layout = useMemo(() => layoutMap(curriculum), [curriculum]);
  const byId = new Map(curriculum.concepts.map((concept) => [concept.id, concept]));

  return (
    <>
      <div className={styles.mapScroller}>
        <div
          className={styles.map}
          role="group"
          aria-label="Concept map"
          style={{ width: layout.width, height: layout.height }}
        >
          <svg
            className={styles.mapLinks}
            width={layout.width}
            height={layout.height}
            viewBox={`0 0 ${layout.width} ${layout.height}`}
            aria-hidden="true"
          >
            <defs>
              <marker
                id={`${markerId}-arrow`}
                viewBox="0 0 10 10"
                refX="9"
                refY="5"
                markerWidth="7"
                markerHeight="7"
                orient="auto-start-reverse"
              >
                <path className={styles.mapArrow} d="M 0 0 L 10 5 L 0 10 z" />
              </marker>
              <marker
                id={`${markerId}-arrow-active`}
                viewBox="0 0 10 10"
                refX="9"
                refY="5"
                markerWidth="6"
                markerHeight="6"
                orient="auto-start-reverse"
              >
                <path className={styles.mapArrowActive} d="M 0 0 L 10 5 L 0 10 z" />
              </marker>
            </defs>
            {layout.edges.map((edge) => {
              const active = edge.from === selectedId || edge.to === selectedId;
              return (
                <path
                  key={`${edge.from}-${edge.to}`}
                  className={cx(styles.mapLink, active && styles.mapLinkActive)}
                  d={edge.d}
                  markerEnd={`url(#${markerId}-arrow${active ? '-active' : ''})`}
                />
              );
            })}
          </svg>
          {layout.nodes.map((node) => {
            const concept = byId.get(node.id);
            const needs = concept?.prerequisites.map((item) => item.title) ?? [];
            const selected = node.id === selectedId;
            return (
              <button
                key={node.id}
                type="button"
                className={cx(styles.mapNode, selected && styles.mapNodeSelected)}
                style={{
                  left: node.x,
                  top: node.y,
                  width: MAP_NODE.width,
                  height: MAP_NODE.height,
                }}
                aria-pressed={selected}
                aria-label={
                  needs.length > 0
                    ? `${node.title}. Needs ${needs.join(', ')}.`
                    : `${node.title}. Needs nothing first.`
                }
                onClick={() => onSelect(node.id)}
              >
                <span className={styles.mapNodeTitle}>{node.title}</span>
              </button>
            );
          })}
        </div>
      </div>
      <p className={styles.mapCaption}>
        Each concept sits below what it needs. Arrows point from a prerequisite to what it unlocks.
      </p>
    </>
  );
}
