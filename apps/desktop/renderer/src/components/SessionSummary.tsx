import { useId } from 'react';

import type { SessionSummary as Session } from '@adle/contracts';

import {
  hasLighterEvidence,
  LIGHTER_EVIDENCE,
  reviewWhen,
  sessionCounts,
  shownSentence,
} from '../lib/learning';
import styles from './SessionSummary.module.css';

/** How many concepts a group names before it says "and N more". */
const MAX_LINES = 4;

interface Line {
  key: string;
  title: string;
  detail: string;
}

function Group({ title, lines }: { title: string; lines: Line[] }) {
  const headingId = useId();
  if (lines.length === 0) return null;
  const more = lines.length - MAX_LINES;
  return (
    <div className={styles.group}>
      <h3 id={headingId} className={styles.groupTitle}>
        {title}
      </h3>
      <ul className={styles.lines} aria-labelledby={headingId}>
        {lines.slice(0, MAX_LINES).map((line) => (
          <li key={line.key} className={styles.line}>
            <span className={styles.concept}>{line.title}</span>
            <span className={styles.detail}>{line.detail}</span>
          </li>
        ))}
        {more > 0 ? (
          <li className={styles.more}>and {more} more, listed under “Your progress”</li>
        ) : null}
      </ul>
    </div>
  );
}

/**
 * What the latest sitting on a course showed: what was demonstrated in answers, what still
 * needs evidence, and what is planned for review.
 *
 * Everything here comes from the core as counts and words. Nothing is worked out in the
 * interface, and nothing is shown as a score: a wrong answer simply is not among what was
 * shown, and a right answer that counted for less is still a right answer.
 */
export function SessionSummary({ session }: { session: Session }) {
  return (
    <div className={styles.session}>
      <p className={styles.counts}>{sessionCounts(session)}</p>
      <div className={styles.groups}>
        <Group
          title="What you got right"
          lines={session.shown.map((line) => ({
            key: line.concept_id,
            title: line.title,
            detail: shownSentence(line),
          }))}
        />
        <Group
          title="Still in progress"
          lines={session.still_needed.map((line) => ({
            key: line.concept_id,
            title: line.title,
            // The same words, in the same form, as the concept's own row further down.
            detail: `Still needed: ${line.missing.join('; ')}.`,
          }))}
        />
        <Group
          title="Upcoming reviews"
          lines={session.reviews.map((line) => ({
            key: line.concept_id,
            title: line.title,
            detail: reviewWhen(line.due_at),
          }))}
        />
      </div>
      {hasLighterEvidence(session.shown) ? (
        <p className={styles.footnote}>{LIGHTER_EVIDENCE}</p>
      ) : null}
    </div>
  );
}
