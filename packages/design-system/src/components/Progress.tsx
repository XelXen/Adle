import type { CSSProperties } from 'react';

import { cx } from '../cx';
import styles from './Progress.module.css';

export interface ProgressBarProps {
  /** Accessible name, e.g. "Importing notes.pdf". */
  label: string;
  /** 0–1. Omit for work whose length is unknown. */
  value?: number;
  /** Show the label above the bar. Off by default when the context already names it. */
  showLabel?: boolean;
  /** Text shown beside the label instead of a percentage, e.g. "3 of 8 concepts". */
  valueText?: string;
  tone?: 'primary' | 'info';
  className?: string;
}

/**
 * Progress of a task or through content.
 *
 * Not for mastery: learning state is shown with qualitative labels, because a
 * percentage would claim precision the evidence does not support.
 */
export function ProgressBar({
  label,
  value,
  showLabel = false,
  valueText,
  tone = 'primary',
  className,
}: ProgressBarProps) {
  const determinate = typeof value === 'number';
  const clamped = determinate ? Math.min(1, Math.max(0, value)) : 0;
  const percent = Math.round(clamped * 100);
  return (
    <div className={cx(styles.progress, className)}>
      {showLabel ? (
        <div className={styles.header}>
          <span className={styles.label}>{label}</span>
          {determinate || valueText ? (
            <span className={cx(styles.value, 'ad-tabular')}>{valueText ?? `${percent}%`}</span>
          ) : null}
        </div>
      ) : null}
      <div
        className={cx(styles.track, styles[tone])}
        role="progressbar"
        aria-label={label}
        aria-valuemin={determinate ? 0 : undefined}
        aria-valuemax={determinate ? 100 : undefined}
        aria-valuenow={determinate ? percent : undefined}
        aria-valuetext={valueText}
      >
        <div
          className={cx(styles.fill, !determinate && styles.indeterminate)}
          style={determinate ? ({ '--ad-progress': `${percent}%` } as CSSProperties) : undefined}
        />
      </div>
    </div>
  );
}
