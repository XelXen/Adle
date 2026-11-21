import type { ReactNode } from 'react';

import { cx } from '@adle/design-system';

import styles from './StageFrame.module.css';

export interface StageFrameProps {
  /** What is on the screen: a picture, or a board with what has been said so far. */
  children: ReactNode;
  /** A line along the top of the screen: what this is, and what can be done with it. */
  header?: ReactNode;
  /**
   * The words being said, shown along the foot of the screen as they would be under a
   * film. Left out, the screen has no band for them.
   */
  caption?: ReactNode;
  className?: string;
}

/**
 * The screen a lesson is watched on: one dark surface in either theme, the picture on it
 * at 16 to 9, the words being said along its foot. A lesson's pictures are drawn for this
 * surface and no other, so that they look the same whatever the theme around them is.
 */
export function StageFrame({ children, header, caption, className }: StageFrameProps) {
  return (
    <div className={cx(styles.frame, className)} data-stage-frame="">
      {header ? <div className={styles.header}>{header}</div> : null}
      <div className={styles.screen} data-stage-screen="">
        {children}
      </div>
      {caption ? <div className={styles.caption}>{caption}</div> : null}
    </div>
  );
}
