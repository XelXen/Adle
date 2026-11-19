import { X } from 'lucide-react';
import { type ReactNode, type SyntheticEvent, useEffect, useId, useRef } from 'react';

import { cx } from '../cx';
import { IconButton } from './Button';
import styles from './Dialog.module.css';

export interface DialogProps {
  open: boolean;
  /** Called when the learner dismisses the dialog (Escape, close button, backdrop). */
  onClose: () => void;
  title: string;
  description?: ReactNode;
  children?: ReactNode;
  /** Footer buttons. Put the primary action last. */
  actions?: ReactNode;
  /** Prevent dismissal while an irreversible operation is running. */
  dismissible?: boolean;
  size?: 'small' | 'medium';
}

/**
 * A modal dialog built on the native `<dialog>` element, which provides the
 * focus trap, Escape handling, and inert background for free.
 *
 * Focus starts on the close button, the safe choice for a confirmation. In a
 * form, put `data-autofocus` on the field the learner should start typing in.
 */
export function Dialog({
  open,
  onClose,
  title,
  description,
  children,
  actions,
  dismissible = true,
  size = 'small',
}: DialogProps) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const descriptionId = useId();

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) {
      dialog.showModal();
      // The browser focuses the first focusable element, which is the close button.
      // A form dialog marks the field to start in with `data-autofocus` instead.
      dialog.querySelector<HTMLElement>('[data-autofocus]')?.focus();
    } else if (!open && dialog.open) dialog.close();
  }, [open]);

  const handleCancel = (event: SyntheticEvent<HTMLDialogElement>): void => {
    // Keep React in charge of the open state.
    event.preventDefault();
    if (dismissible) onClose();
  };

  return (
    // The dialog element handles Escape natively (the `cancel` event); the click
    // handler only implements backdrop dismissal, which has a keyboard equivalent.
    // eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-noninteractive-element-interactions
    <dialog
      ref={ref}
      className={cx(styles.dialog, styles[size])}
      aria-labelledby={titleId}
      aria-describedby={description ? descriptionId : undefined}
      onCancel={handleCancel}
      onClose={() => {
        if (open) onClose();
      }}
      onClick={(event) => {
        if (dismissible && event.target === ref.current) onClose();
      }}
    >
      <div className={styles.content}>
        <header className={styles.header}>
          <h2 id={titleId} className={styles.title}>
            {title}
          </h2>
          {dismissible ? (
            <IconButton label="Close" icon={<X />} size="small" onClick={onClose} />
          ) : null}
        </header>
        {description ? (
          <p id={descriptionId} className={styles.description}>
            {description}
          </p>
        ) : null}
        {children ? <div className={styles.body}>{children}</div> : null}
        {actions ? <footer className={styles.actions}>{actions}</footer> : null}
      </div>
    </dialog>
  );
}
