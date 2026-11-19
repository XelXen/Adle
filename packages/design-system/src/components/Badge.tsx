import type { ReactNode } from 'react';

import { cx } from '../cx';
import styles from './Badge.module.css';

export type Tone = 'neutral' | 'success' | 'info' | 'warning' | 'danger' | 'accent';

export interface BadgeProps {
  tone?: Tone;
  /** Decorative leading icon. Never rely on colour alone to carry meaning. */
  icon?: ReactNode;
  children: ReactNode;
  className?: string;
}

/** A short status label. */
export function Badge({ tone = 'neutral', icon, children, className }: BadgeProps) {
  return (
    <span className={cx(styles.badge, styles[tone], className)}>
      {icon ? (
        <span className={styles.icon} aria-hidden="true">
          {icon}
        </span>
      ) : null}
      {children}
    </span>
  );
}
