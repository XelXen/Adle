import type { ReactNode } from 'react';

import { cx } from '../cx';
import styles from './Disclosure.module.css';

export interface DisclosureProps {
  /** What is behind it, in a word or two: "Advanced". */
  label: string;
  /** Open to begin with. It is the learner's to open and close after that. */
  defaultOpen?: boolean;
  children: ReactNode;
  className?: string;
}

/**
 * Choices most people never need, one press away and out of the way otherwise: what a
 * saved course holds, what is brought in from a file. What is behind it has sensible
 * defaults, so leaving it closed is always a fine choice.
 *
 * The browser's own `<details>`: it opens and closes by a press or by the keyboard, says
 * so to assistive technology, and what is inside is found by a search of the page.
 */
export function Disclosure({ label, defaultOpen = false, children, className }: DisclosureProps) {
  return (
    <details className={cx(styles.root, className)} open={defaultOpen || undefined}>
      <summary className={styles.summary}>{label}</summary>
      <div className={styles.content}>{children}</div>
    </details>
  );
}
