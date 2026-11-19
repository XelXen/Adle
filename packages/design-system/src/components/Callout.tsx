import { CircleAlert, CircleCheck, Info, TriangleAlert } from 'lucide-react';
import type { ReactNode } from 'react';

import { cx } from '../cx';
import type { Tone } from './Badge';
import styles from './Callout.module.css';

export type CalloutTone = Extract<Tone, 'info' | 'success' | 'warning' | 'danger'>;

export interface CalloutProps {
  tone?: CalloutTone;
  title?: ReactNode;
  children: ReactNode;
  /** Buttons or links related to the message. */
  actions?: ReactNode;
  /** Announce immediately (errors) rather than politely. */
  urgent?: boolean;
  className?: string;
}

const ICONS: Record<CalloutTone, typeof Info> = {
  info: Info,
  success: CircleCheck,
  warning: TriangleAlert,
  danger: CircleAlert,
};

/** An inline message that explains a state, a consequence, or a recovery path. */
export function Callout({
  tone = 'info',
  title,
  children,
  actions,
  urgent = false,
  className,
}: CalloutProps) {
  const Icon = ICONS[tone];
  return (
    <div className={cx(styles.callout, styles[tone], className)} role={urgent ? 'alert' : 'status'}>
      <Icon className={styles.icon} aria-hidden="true" />
      <div className={styles.body}>
        {title ? <p className={styles.title}>{title}</p> : null}
        <div className={styles.message}>{children}</div>
        {actions ? <div className={styles.actions}>{actions}</div> : null}
      </div>
    </div>
  );
}
