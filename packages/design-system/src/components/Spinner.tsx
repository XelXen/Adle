import { cx } from '../cx';
import styles from './Spinner.module.css';

export interface SpinnerProps {
  /** Announced to assistive technology. Omit when a parent already announces the busy state. */
  label?: string;
  size?: 'small' | 'medium' | 'large';
  className?: string;
}

/** Indeterminate activity indicator. Respects reduced motion (it slows, it does not vanish). */
export function Spinner({ label, size = 'medium', className }: SpinnerProps) {
  return (
    <span
      className={cx(styles.spinner, styles[size], className)}
      role={label ? 'status' : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
    >
      <svg viewBox="0 0 24 24" fill="none" focusable="false">
        <circle className={styles.track} cx="12" cy="12" r="9" strokeWidth="3" />
        <path
          className={styles.arc}
          d="M21 12a9 9 0 0 0-9-9"
          strokeWidth="3"
          strokeLinecap="round"
        />
      </svg>
    </span>
  );
}
