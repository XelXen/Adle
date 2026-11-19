import { cx } from '../cx';
import styles from './Logo.module.css';

export interface LogoProps {
  /** Show the wordmark next to the mark. */
  wordmark?: boolean;
  size?: 'medium' | 'large';
  className?: string;
}

/**
 * The Adle mark: a sprout made of two leaves on a stem. Original geometry,
 * deliberately simple so it reads at 20 px and never becomes a mascot.
 */
export function Logo({ wordmark = true, size = 'medium', className }: LogoProps) {
  return (
    <span className={cx(styles.logo, styles[size], className)}>
      <svg className={styles.mark} viewBox="0 0 32 32" role="img" aria-label="Adle">
        <rect className={styles.tile} width="32" height="32" rx="9" />
        <path
          className={styles.stem}
          d="M16 25V14"
          fill="none"
          strokeWidth="2.4"
          strokeLinecap="round"
        />
        <path className={styles.leaf} d="M16 15c0-4.4 3.1-7.5 7.5-7.5 0 4.4-3.1 7.5-7.5 7.5Z" />
        <path
          className={styles.leafSmall}
          d="M16 19c0-3.3-2.4-5.6-5.7-5.6 0 3.3 2.4 5.6 5.7 5.6Z"
        />
      </svg>
      {wordmark ? (
        <span className={styles.wordmark} aria-hidden="true">
          Adle
        </span>
      ) : null}
    </span>
  );
}
