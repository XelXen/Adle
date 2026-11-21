import { cx } from '@adle/design-system';

import { useApp } from '../app/AppContext';
import { useRouter } from '../app/router';
import styles from './CoreStatusIndicator.module.css';

const LABELS = {
  starting: 'Starting…',
  failed: 'Something needs attention',
  stopped: 'Adle has stopped',
} as const;

/**
 * Says so, at the foot of the rail, while the part of Adle that keeps the courses is
 * starting or has stopped. While all is well it shows nothing: a learner has no use for
 * being told that the app they are using is running.
 */
export function CoreStatusIndicator() {
  const { coreStatus } = useApp();
  const { navigate } = useRouter();
  if (coreStatus.state === 'ready') return null;
  const problem = coreStatus.state === 'failed' || coreStatus.state === 'stopped';

  return (
    <button
      type="button"
      className={cx(styles.indicator, styles[coreStatus.state])}
      onClick={() => navigate({ name: 'settings', tab: 'about' })}
      title={problem ? 'Show details' : undefined}
    >
      <span className={styles.dot} aria-hidden="true" />
      <span className={styles.text}>{LABELS[coreStatus.state]}</span>
    </button>
  );
}
