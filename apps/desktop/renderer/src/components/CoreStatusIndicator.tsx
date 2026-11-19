import { cx } from '@adle/design-system';

import { useApp } from '../app/AppContext';
import { useRouter } from '../app/router';
import styles from './CoreStatusIndicator.module.css';

const LABELS = {
  starting: 'Local service starting…',
  ready: 'Local service ready',
  failed: 'Local service needs attention',
  stopped: 'Local service stopped',
} as const;

/** Compact status of the local core, shown at the foot of the navigation rail. */
export function CoreStatusIndicator() {
  const { coreStatus } = useApp();
  const { navigate } = useRouter();
  const problem = coreStatus.state === 'failed' || coreStatus.state === 'stopped';

  return (
    <button
      type="button"
      className={cx(styles.indicator, styles[coreStatus.state])}
      onClick={() => navigate({ name: 'settings', tab: 'about' })}
      title={problem ? 'Open diagnostics' : undefined}
    >
      <span className={styles.dot} aria-hidden="true" />
      <span className={styles.text}>{LABELS[coreStatus.state]}</span>
    </button>
  );
}
