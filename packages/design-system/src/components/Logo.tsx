import { cx } from '../cx';
import styles from './Logo.module.css';

export interface LogoProps {
  /** Show the wordmark next to the mark. */
  wordmark?: boolean;
  size?: 'medium' | 'large';
  className?: string;
}

/**
 * The Adle mark: the letters "a" and "d" as two interlocking rings, the "d" passing in
 * front of the "a".
 *
 * Geometry is taken from the original artwork (`apps/desktop/assets/brand`) at one tenth
 * of its scale: rings of outer radius 24 and stroke 9 whose centres are one radius apart,
 * and a stem that rises from the right edge of the "d" to a round cap. The "a" is its ring
 * minus the whole disc of the "d", which is what makes the two read as linked.
 *
 * The "d" takes the brand colour. The "a" takes `brand-ink`, which is the artwork's navy
 * on light surfaces and a near-white on dark ones, so the mark never disappears.
 */
export function Logo({ wordmark = true, size = 'medium', className }: LogoProps) {
  return (
    <span className={cx(styles.logo, styles[size], className)}>
      <svg className={styles.mark} viewBox="0 0 72 63" role="img" aria-label="Adle">
        <path
          className={styles.a}
          d="M36 18.215A24 24 0 1 0 36 59.785A24 24 0 0 1 28.688 53.249A15 15 0 1 1 28.688 24.751A24 24 0 0 1 36 18.215Z"
        />
        <circle className={styles.d} cx="48" cy="39" r="19.5" />
        <path className={styles.d} d="M67.5 4.5V39" />
      </svg>
      {wordmark ? (
        <span className={styles.wordmark} aria-hidden="true">
          Adle
        </span>
      ) : null}
    </span>
  );
}
