import { type ReactNode, useId } from 'react';

import { cx } from '../cx';
import { IconButton } from './Button';
import styles from './Popover.module.css';

export interface InfoPopoverProps {
  /** What the button shows when pressed, as its accessible name and tooltip. */
  label: string;
  icon: ReactNode;
  /** A heading for what is shown. Optional: most notes are a sentence or two. */
  title?: string;
  children: ReactNode;
  className?: string;
}

/**
 * Something worth knowing that nobody needs to read every time: one press away, and out
 * of the way otherwise. What a request sends and where, who wrote a lesson, what a
 * setting does behind the scenes.
 *
 * The browser's own popover: it opens above everything else, beside its button, and
 * closes on Escape or on a press anywhere else. The button says whether it is open.
 */
export function InfoPopover({ label, icon, title, children, className }: InfoPopoverProps) {
  const id = useId();
  return (
    <span className={cx(styles.anchor, className)}>
      <IconButton label={label} icon={icon} size="small" popoverTarget={id} />
      <div id={id} popover="auto" className={styles.popover}>
        {title ? <p className={styles.title}>{title}</p> : null}
        <div className={styles.body}>{children}</div>
      </div>
    </span>
  );
}
