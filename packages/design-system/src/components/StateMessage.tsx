import { CircleAlert } from 'lucide-react';
import type { ReactNode } from 'react';

import { cx } from '../cx';
import { Spinner } from './Spinner';
import styles from './StateMessage.module.css';

interface StateMessageProps {
  title: string;
  description?: ReactNode;
  /** Buttons that move the learner forward. */
  actions?: ReactNode;
  className?: string;
}

export interface EmptyStateProps extends StateMessageProps {
  /** Decorative illustration or icon. */
  visual?: ReactNode;
}

/**
 * Shown where content will appear once the learner acts. Always says what the
 * area is for and offers the next step; never a bare "Nothing here".
 */
export function EmptyState({ title, description, actions, visual, className }: EmptyStateProps) {
  return (
    <div className={cx(styles.state, className)}>
      {visual ? (
        <div className={styles.visual} aria-hidden="true">
          {visual}
        </div>
      ) : null}
      <h2 className={styles.title}>{title}</h2>
      {description ? <p className={styles.description}>{description}</p> : null}
      {actions ? <div className={styles.actions}>{actions}</div> : null}
    </div>
  );
}

/** Shown while content loads. Always names what is loading. */
export function LoadingState({
  title,
  description,
  className,
}: Omit<StateMessageProps, 'actions'>) {
  return (
    <div className={cx(styles.state, className)} role="status">
      <div className={styles.visual}>
        <Spinner size="large" />
      </div>
      <p className={styles.title}>{title}</p>
      {description ? <p className={styles.description}>{description}</p> : null}
    </div>
  );
}

/** Shown when something failed. States what happened and how to recover. */
export function ErrorState({ title, description, actions, className }: StateMessageProps) {
  return (
    <div className={cx(styles.state, className)} role="alert">
      <div className={cx(styles.visual, styles.errorVisual)} aria-hidden="true">
        <CircleAlert />
      </div>
      <h2 className={styles.title}>{title}</h2>
      {description ? <p className={styles.description}>{description}</p> : null}
      {actions ? <div className={styles.actions}>{actions}</div> : null}
    </div>
  );
}
